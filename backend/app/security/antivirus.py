import socket
import struct
import io
import re
import uuid
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List
from backend.app.core.config import settings

# EICAR Standard Anti-Virus Test File string (safe standard test signature)
# Standard form: exactly 68 characters ASCII
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

@dataclass
class ScanResult:
    status: str            # 'CLEAN', 'INFECTED', 'SCAN_ERROR'
    is_clean: bool         # True ONLY if status == 'CLEAN'
    threat_name: Optional[str] = None
    details: Optional[str] = None
    engine: str = "ClamAV 1.3 / DocuSpace Security Shield"


class QuarantineManager:
    """
    Manages isolated quarantine storage for infected files.
    Ensures infected files are segregated from tenant document directories,
    never accessible for download or execution.
    """
    def __init__(self):
        # In-memory incident registry
        self._quarantined_records: Dict[str, Dict[str, Any]] = {}

    def quarantine_file(
        self,
        storage_client,
        tenant_id: uuid.UUID,
        storage_key: str,
        original_name: str,
        threat_name: str,
        content: bytes
    ) -> Dict[str, Any]:
        """
        Moves or stores an infected payload into an isolated quarantine storage location.
        Deletes any pre-existing object at storage_key.
        """
        quarantine_id = str(uuid.uuid4())
        clean_threat = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', threat_name)
        timestamp = datetime.now(timezone.utc).isoformat()
        quarantine_key = f"quarantine/{tenant_id}/{quarantine_id}_{clean_threat}.quarantine"

        # 1. Store in isolated quarantine path
        try:
            if storage_client:
                storage_client.put_object(quarantine_key, content, "application/octet-stream")
        except Exception:
            pass

        # 2. Delete original active storage key if present
        if storage_key and storage_client:
            try:
                storage_client.delete_object(storage_key)
            except Exception:
                pass

        record = {
            "quarantine_id": quarantine_id,
            "tenant_id": str(tenant_id),
            "original_name": original_name,
            "threat_name": threat_name,
            "quarantine_key": quarantine_key,
            "size_bytes": len(content),
            "isolated_at": timestamp,
            "status": "QUARANTINED"
        }
        self._quarantined_records[quarantine_id] = record
        return record

    def list_quarantined_files(self, tenant_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """Lists quarantined records, optionally filtered by tenant."""
        if tenant_id:
            return [r for r in self._quarantined_records.values() if r.get("tenant_id") == str(tenant_id)]
        return list(self._quarantined_records.values())

    def clear(self):
        self._quarantined_records.clear()


class ClamAVScanner:
    """
    ClamAV Antivirus Scanner with strict Fail-Closed security policy.
    
    In Fail-Closed mode:
      - ClamAV available & scan negative: status = 'CLEAN'
      - Threat found: status = 'INFECTED'
      - ClamAV unavailable / connection refused: status = 'SCAN_ERROR'
      - Timeout: status = 'SCAN_ERROR'
      - Invalid / corrupted response: status = 'SCAN_ERROR'
      - Communication / socket error: status = 'SCAN_ERROR'
      - Local heuristics (EICAR & dangerous executable headers) detect threats immediately as 'INFECTED'
      - Under NO circumstances is an unanalyzed file marked 'CLEAN'
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        fail_closed: bool = True,
        timeout_seconds: float = 3.0,
        socket_factory=None
    ):
        self.host = host if host is not None else settings.CLAMAV_HOST
        self.port = port if port is not None else settings.CLAMAV_PORT
        self.fail_closed = fail_closed
        self.timeout = timeout_seconds
        self.socket_factory = socket_factory or socket.socket

    def scan_bytes(self, data: bytes) -> ScanResult:
        """
        Scans a byte sequence for virus and malware signatures.
        Executes heuristic local pattern analysis first, then communicates with ClamAV daemon via INSTREAM.
        Strict Fail-Closed: any socket / connectivity / response error yields SCAN_ERROR (never CLEAN).
        """
        # 1. Immediate heuristic signature check (EICAR & malicious executable headers)
        if EICAR_SIGNATURE in data:
            return ScanResult(
                status="INFECTED",
                is_clean=False,
                threat_name="EICAR.Test.File-FOUND",
                details="Signature de test antivirus standard détectée (EICAR)",
                engine="DocuSpace ClamAV Heuristics"
            )

        # Check for dangerous executable headers disguised as other files
        if data.startswith(b"MZ") and len(data) > 64:  # DOS/PE executable header
            return ScanResult(
                status="INFECTED",
                is_clean=False,
                threat_name="Heuristic.Executable.PE-Header-Found",
                details="Format binaire exécutable Windows non autorisé détecté",
                engine="DocuSpace Binary Guard"
            )

        if data.startswith(b"\x7fELF"):  # Linux ELF executable binary
            return ScanResult(
                status="INFECTED",
                is_clean=False,
                threat_name="Heuristic.Executable.ELF-Binary-Found",
                details="Format binaire exécutable Linux ELF non autorisé détecté",
                engine="DocuSpace Binary Guard"
            )

        # 2. ClamAV Daemon TCP socket scan via INSTREAM protocol
        if not self.host or not self.port:
            return ScanResult(
                status="SCAN_ERROR",
                is_clean=False,
                threat_name=None,
                details="Hôte ou port ClamAV non configuré (SCAN_ERROR).",
                engine="DocuSpace Security Shield"
            )

        try:
            with self.socket_factory(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                
                # Send INSTREAM command
                sock.sendall(b"zINSTREAM\0")
                
                # Send chunks in ClamAV chunk protocol: 4-byte big-endian length + chunk data
                chunk_size = 2048
                stream = io.BytesIO(data)
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    length_header = struct.pack("!I", len(chunk))
                    sock.sendall(length_header + chunk)
                
                # Zero-length chunk signals end of stream
                sock.sendall(struct.pack("!I", 0))
                
                # Read response from daemon
                response = b""
                while True:
                    part = sock.recv(1024)
                    if not part:
                        break
                    response += part

                response_str = response.decode("utf-8", errors="ignore").strip("\x00 \t\r\n")
                
                if "OK" in response_str:
                    return ScanResult(
                        status="CLEAN",
                        is_clean=True,
                        details="Document analysé avec succès par ClamAV daemon. Aucune menace détectée.",
                        engine="ClamAV Daemon TCP"
                    )
                elif "FOUND" in response_str:
                    threat = response_str.replace("stream:", "").replace("FOUND", "").strip("\x00 \t\r\n")
                    return ScanResult(
                        status="INFECTED",
                        is_clean=False,
                        threat_name=threat or "Threat.Detected",
                        details=f"Menace détectée par ClamAV : {threat}",
                        engine="ClamAV Daemon TCP"
                    )
                else:
                    return ScanResult(
                        status="SCAN_ERROR",
                        is_clean=False,
                        threat_name=None,
                        details=f"Réponse ClamAV invalide ou corrompue : {response_str[:120]}",
                        engine="ClamAV Daemon TCP"
                    )

        except (socket.timeout, TimeoutError) as e:
            # Timeout during ClamAV scan -> FAIL-CLOSED
            return ScanResult(
                status="SCAN_ERROR",
                is_clean=False,
                threat_name=None,
                details=f"Délai d'attente d'analyse ClamAV dépassé (Timeout : {self.timeout}s).",
                engine="ClamAV Daemon TCP"
            )
        except (socket.error, ConnectionRefusedError, ConnectionResetError, OSError) as e:
            # ClamAV daemon is unreachable or socket dropped -> FAIL-CLOSED (NEVER CLEAN)
            return ScanResult(
                status="SCAN_ERROR",
                is_clean=False,
                threat_name=None,
                details=f"Daemon ClamAV indisponible ou erreur de communication socket : {str(e)}",
                engine="ClamAV Daemon TCP"
            )
        except Exception as e:
            # Any unexpected critical exception -> FAIL-CLOSED
            return ScanResult(
                status="SCAN_ERROR",
                is_clean=False,
                threat_name=None,
                details=f"Erreur critique lors de l'analyse antivirus (Fail-Closed) : {str(e)}",
                engine="DocuSpace Security Shield"
            )


# Global instances
quarantine_manager = QuarantineManager()
clamav_scanner = ClamAVScanner()
