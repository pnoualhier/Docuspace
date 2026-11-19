import asyncio
import socket
from typing import Any, Dict

import redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import is_test_runtime, settings
from backend.app.core.database import get_db
from backend.app.storage.s3_storage import storage_client

router = APIRouter()


def _probe_redis() -> str:
    url = (settings.REDIS_URL or "").strip()
    if not url:
        return "not_configured"
    if is_test_runtime() and "@redis:" in url:
        return "test_skipped"
    try:
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        return "healthy" if client.ping() else "unhealthy"
    except Exception as exc:
        return f"unhealthy: {type(exc).__name__}"


def _probe_minio() -> str:
    try:
        res: Dict[str, Any] = storage_client.check_health()
        st = res.get("status")
        if st == "ok":
            return "healthy"
        if st == "test_mode":
            return "test_mode"
        return str(st or "unhealthy")
    except Exception as exc:
        return f"unhealthy: {type(exc).__name__}"


def _probe_clamav() -> str:
    host = (settings.CLAMAV_HOST or "").strip()
    port = int(settings.CLAMAV_PORT or 0)
    if not host or port <= 0:
        return "not_configured"
    if is_test_runtime() and host == "clamav":
        return "test_skipped"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            sock.connect((host, port))
            sock.sendall(b"zPING\0")
            resp = sock.recv(64).decode("utf-8", errors="ignore").strip("\x00 \r\n")
            return "healthy" if "PONG" in resp else f"unexpected_response: {resp[:32]}"
    except Exception as exc:
        return f"unreachable: {type(exc).__name__}"


@router.get("/health", tags=["Système"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Real health check probing PostgreSQL, Redis, MinIO S3, and ClamAV TCP daemon."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {type(exc).__name__}"

    redis_status, storage_status, antivirus_status = await asyncio.gather(
        asyncio.to_thread(_probe_redis),
        asyncio.to_thread(_probe_minio),
        asyncio.to_thread(_probe_clamav),
    )

    critical_ok = (
        db_status == "healthy"
        and storage_status in ("healthy", "test_mode")
        and antivirus_status in ("healthy", "test_skipped")
        and redis_status in ("healthy", "not_configured", "test_skipped")
    )

    return {
        "status": "healthy" if critical_ok else "degraded",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "database": db_status,
        "redis": redis_status,
        "storage": storage_status,
        "antivirus": antivirus_status,
    }
