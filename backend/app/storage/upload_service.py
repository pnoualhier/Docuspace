import os
import uuid
import secrets
import hashlib
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.app.models.document import UploadSession, Folder, Document, DocumentVersion
from backend.app.models.tenant import StorageUsage
from backend.app.storage.storage_interface import is_prohibited_extension, is_prohibited_mime_type
from backend.app.services.quota_service import quota_service, FileSizeLimitExceededError, QuotaExceededError

CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunks

# Binary signatures of dangerous executable payloads
DANGEROUS_MAGIC_SIGNATURES = [
    (b"MZ", "Executable Windows PE / DOS"),
    (b"\x7fELF", "Binaire exécutable Linux ELF"),
    (b"#!", "Script Shell exécutable"),
    (b"\xca\xfe\xba\xbe", "Binaire Java bytecode class"),
    (b"%!PS-Adobe", "Script exécutable PostScript"),
    (b"<?php", "Script exécutable PHP"),
    (b"<script", "Script exécutable HTML/JS"),
]

KNOWN_MIME_SIGNATURES = [
    (b"%PDF", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"PK\x03\x04", "application/zip"),  # Also ZIP-based Office docs
    (b"\x1f\x8b", "application/gzip"),
    (b"BM", "image/bmp"),
]

def detect_real_mime_type(sample: bytes, filename: str, fallback_mime: str) -> Tuple[str, bool]:
    """
    Inspects real magic bytes from the initial chunk.
    Returns (detected_mime, is_dangerous_executable).
    Prevents file extension and MIME type spoofing (polyglot files).
    """
    # 1. Check for dangerous executable signatures
    for sig, desc in DANGEROUS_MAGIC_SIGNATURES:
        if sample.startswith(sig):
            return "application/x-executable", True

    # 2. Check for known valid document / image signatures
    for sig, mime in KNOWN_MIME_SIGNATURES:
        if sample.startswith(sig):
            # Special check for ZIP-based formats (docx, xlsx, pptx)
            if mime == "application/zip":
                _, ext = os.path.splitext(filename.lower())
                if ext == ".docx":
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", False
                elif ext == ".xlsx":
                    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False
                elif ext == ".pptx":
                    return "application/vnd.openxmlformats-officedocument.presentationml.presentation", False
            return mime, False

    # 3. Check for WebP image
    if len(sample) >= 12 and sample[0:4] == b"RIFF" and sample[8:12] == b"WEBP":
        return "image/webp", False

    # 4. Check for MP4 video
    if len(sample) >= 8 and sample[4:8] == b"ftyp":
        return "video/mp4", False

    # 5. Check for plain text formats
    try:
        sample.decode("utf-8")
        if b"\x00" not in sample:
            _, ext = os.path.splitext(filename.lower())
            if ext in (".json", ".geojson"):
                return "application/json", False
            elif ext == ".csv":
                return "text/csv", False
            elif ext in (".md", ".markdown"):
                return "text/markdown", False
            return "text/plain", False
    except UnicodeDecodeError:
        pass

    return fallback_mime or "application/octet-stream", False

def generate_secure_storage_key(tenant_id: uuid.UUID, filename: str) -> Tuple[str, str]:
    """
    Generates a secure, cryptographically random storage key.
    Prevents predictable object paths and information leakage.
    """
    _, ext = os.path.splitext(filename)
    clean_ext = ext.lstrip(".").lower()
    random_token = secrets.token_hex(16)
    storage_key = f"tenants/{tenant_id}/{random_token}.{clean_ext}"
    return storage_key, clean_ext

async def validate_folder_ownership(db: AsyncSession, folder_id: Optional[uuid.UUID], tenant_id: uuid.UUID) -> Optional[Folder]:
    """Validates that folder exists, is not trashed, and belongs to the requesting tenant."""
    if not folder_id:
        return None
    folder_res = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.tenant_id == tenant_id,
            Folder.is_trashed == False
        )
    )
    folder = folder_res.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Le dossier cible spécifié n'existe pas ou n'appartient pas à votre espace documentaire."
        )
    return folder

async def stream_and_verify_upload(
    file: UploadFile,
    max_allowed_bytes: int
) -> Tuple[bytes, str, int, str]:
    """
    Streams the upload in 64 KB chunks:
    - Calculates SHA-256 on the fly without loading all in unconstrained memory
    - Enforces real-time strict size ceiling
    - Inspects initial chunk for magic bytes real MIME type
    - Rejects executable and dangerous signatures immediately
    """
    filename = file.filename or "sans-nom"
    if is_prohibited_extension(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extension de fichier strictement interdite pour des raisons de sécurité."
        )

    hasher = hashlib.sha256()
    total_size = 0
    chunks = []
    first_chunk = b""

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        if not first_chunk:
            first_chunk = chunk
            # Immediate MIME inspection on first chunk
            real_mime, is_dangerous = detect_real_mime_type(first_chunk, filename, file.content_type or "")
            if is_dangerous or is_prohibited_mime_type(real_mime):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Contenu exécutable binaire non autorisé détecté par analyse des signatures (magic bytes)."
                )

        total_size += len(chunk)
        if total_size > max_allowed_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Taille réelle du fichier ({total_size // (1024*1024)} Mo) dépasse la limite autorisée ({max_allowed_bytes // (1024*1024)} Mo)."
            )

        hasher.update(chunk)
        chunks.append(chunk)

    if total_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le fichier téléversé est vide (0 octet).")

    full_content = b"".join(chunks)
    real_mime, is_dangerous = detect_real_mime_type(first_chunk, filename, file.content_type or "")
    if is_dangerous:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Format exécutable interdit détecté.")

    return full_content, hasher.hexdigest(), total_size, real_mime

async def create_persisted_upload_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    folder_id: Optional[uuid.UUID],
    original_name: str,
    extension: str,
    mime_type: str,
    size_bytes: int,
    storage_key: str,
    upload_token: str,
    expires_minutes: int = 30
) -> UploadSession:
    """Persists a new upload session in PostgreSQL with strict TTL expiration."""
    now = datetime.now(timezone.utc)
    session = UploadSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        folder_id=folder_id,
        original_name=original_name,
        extension=extension,
        mime_type=mime_type,
        size_bytes=size_bytes,
        storage_key=storage_key,
        upload_token=upload_token,
        status="INITIATED",
        antivirus_status="PENDING",
        expires_at=now + timedelta(minutes=expires_minutes),
        created_at=now
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

async def get_valid_persisted_upload_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID
) -> UploadSession:
    """
    Fetches and row-locks an upload session from PostgreSQL.
    Verifies tenant ownership, active INITIATED status, and unexpired TTL.
    """
    res = await db.execute(
        select(UploadSession)
        .where(
            UploadSession.id == session_id,
            UploadSession.tenant_id == tenant_id
        )
        .with_for_update()
    )
    session = res.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session d'importation introuvable ou n'appartenant pas à cet espace documentaire."
        )

    now = datetime.now(timezone.utc)
    if session.expires_at < now or session.status == "EXPIRED":
        session.status = "EXPIRED"
        await quota_service.release_reservation_db(db, tenant_id, session.size_bytes)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Cette session d'importation a expiré. Veuillez réinitier l'import."
        )

    if session.status != "INITIATED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session d'importation déjà finalisée ou invalide (statut: {session.status})."
        )

    return session

async def cleanup_expired_sessions(
    db: AsyncSession,
    storage_client
) -> Dict[str, Any]:
    """
    Cleans up expired upload sessions:
    - Releases uncommitted reserved quota in PostgreSQL
    - Deletes any dangling partially uploaded objects in MinIO
    - Sets session status to EXPIRED
    """
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(UploadSession)
        .where(
            UploadSession.status == "INITIATED",
            UploadSession.expires_at < now
        )
        .with_for_update()
    )
    expired_sessions = res.scalars().all()

    cleaned_count = len(expired_sessions)
    total_freed_bytes = 0

    for sess in expired_sessions:
        total_freed_bytes += sess.size_bytes
        sess.status = "EXPIRED"
        # Release quota reservation
        await quota_service.release_reservation_db(db, sess.tenant_id, sess.size_bytes)
        # Delete S3 object if present
        try:
            storage_client.delete_object(sess.storage_key)
        except Exception:
            pass

    await db.commit()

    return {
        "cleaned_sessions_count": cleaned_count,
        "freed_reserved_bytes": total_freed_bytes,
        "timestamp": now.isoformat()
    }
