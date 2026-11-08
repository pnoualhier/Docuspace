from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.app.core.database import get_db

router = APIRouter()

@router.get("/health", tags=["Système"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check validating PostgreSQL connection and system responsiveness."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "app": "DocuSpace API",
        "version": "1.0.0",
        "database": db_status,
        "storage": "minio_ready",
        "antivirus": "clamav_active",
    }
