"""
DocuSpace Phase 9 — MinIO S3 & ClamAV Real Protocol / Service Integration Tests
- When TEST_MINIO_ENDPOINT is set (e.g. GitHub Actions CI service), uses real MinIO S3 SDK.
- Otherwise validates real HTTP presigned HMAC flow via local asyncio HTTP S3 server + S3Storage contract.
- When TEST_CLAMAV_HOST is set, scans EICAR & benign payloads against real clamd container.
- Otherwise spins up a real TCP zINSTREAM socket daemon to verify chunked protocol, timeout, and malformed frame Fail-Closed behavior.
"""
import asyncio
import hashlib
import io
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid

import httpx
import pytest

from backend.app.security.antivirus import ClamAVScanner, EICAR_SIGNATURE, ScanResult
from backend.app.storage.s3_storage import S3Storage
from backend.tests.pg_harness import find_free_port


class _LocalS3HttpHandler(BaseHTTPRequestHandler):
    store: dict[str, bytes] = {}
    storage_ref: S3Storage | None = None

    def log_message(self, format, *args):
        return

    def do_PUT(self):
        path = self.path.split("?")[0].lstrip("/")
        # path = <bucket>/<storage_key>
        _, _, key = path.partition("/")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.store[key] = body
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        path, _, query = self.path.partition("?")
        _, _, key = path.lstrip("/").partition("/")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        if self.storage_ref and not self.storage_ref.verify_presigned_token(
            key, int(params.get("Expires", "0")), params.get("Signature", ""), action="GET"
        ):
            self.send_response(403)
            self.end_headers()
            return
        data = self.store.get(key)
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)


def test_phase9_minio_s3_presigned_http_and_ci_sdk():
    minio_ep = os.getenv("TEST_MINIO_ENDPOINT", "").strip()
    if minio_ep:
        from minio import Minio

        client = Minio(
            minio_ep,
            access_key=os.environ["MINIO_ACCESS_KEY"],
            secret_key=os.environ["MINIO_SECRET_KEY"],
            secure=False,
        )
        bucket = f"docuspace-ci-{uuid.uuid4().hex[:8]}"
        client.make_bucket(bucket)
        key = f"tenants/{uuid.uuid4()}/{uuid.uuid4().hex}.pdf"
        payload = b"%PDF-1.4\nCI MinIO Real Object Test\n"
        client.put_object(bucket, key, io.BytesIO(payload), len(payload), content_type="application/pdf")
        resp = client.get_object(bucket, key)
        assert resp.read() == payload
        resp.close()
        resp.release_conn()
        client.remove_object(bucket, key)
        client.remove_bucket(bucket)
        return

    port = find_free_port()
    storage = S3Storage(
        endpoint=f"127.0.0.1:{port}",
        access_key="ci_test_access",
        secret_key="ci_test_super_secret_key_32_bytes",
        bucket_name="docuspace-test-bucket",
        secure=False,
    )
    _LocalS3HttpHandler.store = {}
    _LocalS3HttpHandler.storage_ref = storage
    server = HTTPServer(("127.0.0.1", port), _LocalS3HttpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        key = f"tenants/{uuid.uuid4()}/{uuid.uuid4().hex}.pdf"
        payload = b"%PDF-1.4\nReal HTTP S3 Signed Test Payload\n"
        up_info = storage.generate_presigned_upload_url(key, "application/pdf", 1024 * 1024)
        put_resp = httpx.put(up_info["upload_url"], content=payload)
        assert put_resp.status_code == 200

        dl_url = storage.generate_presigned_download_url(key, "test.pdf")
        get_resp = httpx.get(dl_url)
        assert get_resp.status_code == 200
        assert get_resp.content == payload
        assert hashlib.sha256(get_resp.content).hexdigest() == hashlib.sha256(payload).hexdigest()

        # Tampered signature must be rejected (403)
        tampered = dl_url.replace("Signature=", "Signature=deadbeef")
        assert httpx.get(tampered).status_code == 403
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_phase9_clamav_real_socket_protocol_and_fail_closed():
    import socketserver

    ci_host = os.getenv("TEST_CLAMAV_HOST", "").strip()
    if ci_host:
        ci_port = int(os.getenv("TEST_CLAMAV_PORT", "3310"))
        scanner = ClamAVScanner(host=ci_host, port=ci_port)
        clean_res = await asyncio.to_thread(scanner.scan_bytes, b"Safe DocuSpace CI text content")
        assert clean_res.status == "CLEAN" and clean_res.is_clean is True

        eicar_res = await asyncio.to_thread(scanner.scan_bytes, EICAR_SIGNATURE)
        assert eicar_res.status == "INFECTED" and eicar_res.is_clean is False
        return

    port = find_free_port()
    mode = {"behavior": "normal"}

    class _Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                buf = bytearray()
                while b"\x00" not in buf:
                    chunk = self.request.recv(1024)
                    if not chunk:
                        return
                    buf.extend(chunk)
                idx = buf.index(0)
                assert bytes(buf[: idx + 1]) == b"zINSTREAM\x00"
                rest = bytearray(buf[idx + 1 :])

                def read_exact(n: int) -> bytes:
                    while len(rest) < n:
                        more = self.request.recv(4096)
                        if not more:
                            raise EOFError("unexpected EOF")
                        rest.extend(more)
                    out = bytes(rest[:n])
                    del rest[:n]
                    return out

                chunks = []
                while True:
                    sz = int.from_bytes(read_exact(4), "big")
                    if sz == 0:
                        break
                    chunks.append(read_exact(sz))
                data = b"".join(chunks)

                if mode["behavior"] == "timeout":
                    import time
                    time.sleep(1.2)
                    return
                if mode["behavior"] == "corrupt":
                    self.request.sendall(b"INVALID_DAEMON_FRAME\x00")
                elif EICAR_SIGNATURE in data:
                    self.request.sendall(b"stream: Eicar-Signature FOUND\x00")
                else:
                    self.request.sendall(b"stream: OK\x00")
            except Exception:
                pass

    class _ReusableTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    srv = _ReusableTCPServer(("127.0.0.1", port), _Handler)
    srv_thread = threading.Thread(target=srv.serve_forever, daemon=True)
    srv_thread.start()
    try:
        scanner = ClamAVScanner(host="127.0.0.1", port=port, timeout_seconds=0.35)

        clean: ScanResult = await asyncio.to_thread(scanner.scan_bytes, b"%PDF-1.4\nbenign")
        assert clean.status == "CLEAN" and clean.is_clean is True

        infected: ScanResult = await asyncio.to_thread(scanner.scan_bytes, EICAR_SIGNATURE)
        assert infected.status == "INFECTED" and infected.is_clean is False

        mode["behavior"] = "corrupt"
        corrupt: ScanResult = await asyncio.to_thread(scanner.scan_bytes, b"payload")
        assert corrupt.status == "SCAN_ERROR" and corrupt.is_clean is False

        mode["behavior"] = "timeout"
        timed_out: ScanResult = await asyncio.to_thread(scanner.scan_bytes, b"payload")
        assert timed_out.status == "SCAN_ERROR" and timed_out.is_clean is False
    finally:
        srv.shutdown()
        srv.server_close()
