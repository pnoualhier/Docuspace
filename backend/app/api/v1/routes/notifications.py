"""
DocuSpace Notifications API Routes
Authenticated, tenant-scoped in-app notifications backed by PostgreSQL with Row-Level Security.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update

from backend.app.middleware.tenant_context import TenantContext, get_tenant_context
from backend.app.models.audit import Notification
from backend.app.services.quota_service import quota_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class CheckQuotaRequest(BaseModel):
    used_bytes: Optional[int] = None
    max_bytes: Optional[int] = None


def _serialize_notification(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "tenant_id": str(n.tenant_id),
        "user_id": str(n.user_id),
        "category": n.category,
        "level": n.level,
        "title": n.title,
        "message": n.message,
        "action_url": n.action_url or n.link,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
async def get_notifications(
    unread_only: bool = Query(False),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(get_tenant_context),
):
    """Retrieve persisted notifications for the authenticated user within the active tenant."""
    filters = [
        Notification.tenant_id == ctx.tenant.id,
        Notification.user_id == ctx.user.id,
    ]
    if unread_only:
        filters.append(Notification.is_read == False)
    if category and category.lower() != "all":
        filters.append(Notification.category == category.strip().upper())

    rows = (
        await ctx.db.execute(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    total = (
        await ctx.db.execute(select(func.count(Notification.id)).where(*filters))
    ).scalar() or 0

    unread_count = (
        await ctx.db.execute(
            select(func.count(Notification.id)).where(
                Notification.tenant_id == ctx.tenant.id,
                Notification.user_id == ctx.user.id,
                Notification.is_read == False,
            )
        )
    ).scalar() or 0

    return {
        "items": [_serialize_notification(n) for n in rows],
        "total": int(total),
        "unread_count": int(unread_count),
    }


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID = Path(...),
    ctx: TenantContext = Depends(get_tenant_context),
):
    """Mark a single notification belonging to the current tenant & user as read."""
    notif = (
        await ctx.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.tenant_id == ctx.tenant.id,
                Notification.user_id == ctx.user.id,
            )
        )
    ).scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification introuvable")

    notif.is_read = True
    await ctx.db.commit()
    return {"success": True, "id": str(notification_id)}


@router.post("/read-all")
async def mark_all_read(ctx: TenantContext = Depends(get_tenant_context)):
    """Mark all notifications for the current user and tenant as read."""
    res = await ctx.db.execute(
        update(Notification)
        .where(
            Notification.tenant_id == ctx.tenant.id,
            Notification.user_id == ctx.user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await ctx.db.commit()
    return {"success": True, "marked_count": res.rowcount or 0}


@router.post("/check-quota")
async def check_quota(
    req: Optional[CheckQuotaRequest] = None,
    ctx: TenantContext = Depends(get_tenant_context),
):
    """
    Evaluate real PostgreSQL tenant quota usage and persist a notification
    when consumption reaches >= 80% or >= 100%.
    """
    quota = await quota_service.get_quota_status_db(ctx.db, ctx.tenant.id)
    if quota.max_storage_bytes <= 0:
        return {"alert_created": False, "notification": None}

    ratio = quota.used_bytes / quota.max_storage_bytes
    percent = int(ratio * 100)

    notif: Optional[Notification] = None
    if ratio >= 1.0:
        notif = Notification(
            tenant_id=ctx.tenant.id,
            user_id=ctx.user.id,
            category="STORAGE",
            level="CRITICAL",
            type="CRITICAL",
            title="Quota de stockage 100% atteint !",
            message=(
                f"Votre espace documentaire a atteint sa capacité maximale ({percent}%). "
                "Les nouveaux imports sont bloqués. Libérez de l'espace ou passez à l'offre supérieure."
            ),
            action_url="/storage",
            link="/storage",
        )
    elif ratio >= 0.80:
        notif = Notification(
            tenant_id=ctx.tenant.id,
            user_id=ctx.user.id,
            category="STORAGE",
            level="WARNING",
            type="WARNING",
            title="Attention : Seuil de stockage à 80%",
            message=(
                f"Votre espace documentaire a dépassé 80% de sa capacité ({percent}% utilisés). "
                "Pensez à vérifier vos quotas."
            ),
            action_url="/storage",
            link="/storage",
        )

    if notif is None:
        return {"alert_created": False, "notification": None}

    ctx.db.add(notif)
    await ctx.db.flush()
    await ctx.db.refresh(notif)
    await ctx.db.commit()
    return {"alert_created": True, "notification": _serialize_notification(notif)}
