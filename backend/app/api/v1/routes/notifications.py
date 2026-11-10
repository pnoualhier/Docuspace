"""
DocuSpace Notifications API Routes
In-app notification listing, read receipts, and quota threshold checks.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from backend.app.notifications.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class CheckQuotaRequest(BaseModel):
    tenant_id: str
    user_id: str
    used_bytes: int
    max_bytes: int

@router.get("")
async def get_notifications(
    tenant_id: str = Query("tnt-alice-main"),
    user_id: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    category: Optional[str] = Query(None)
):
    """Retrieve notifications for the current tenant and user"""
    items = notification_service.list_notifications(
        tenant_id=tenant_id,
        user_id=user_id,
        unread_only=unread_only,
        category=category
    )
    unread_count = len(notification_service.list_notifications(tenant_id=tenant_id, unread_only=True))
    return {
        "items": items,
        "total": len(items),
        "unread_count": unread_count
    }

@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark a single notification as read"""
    success = notification_service.mark_as_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True, "id": notification_id}

@router.post("/read-all")
async def mark_all_read(tenant_id: str = Query("tnt-alice-main"), user_id: Optional[str] = Query(None)):
    """Mark all notifications as read"""
    count = notification_service.mark_all_as_read(tenant_id=tenant_id, user_id=user_id)
    return {"success": True, "marked_count": count}

@router.post("/check-quota")
async def check_quota(req: CheckQuotaRequest):
    """Evaluate tenant quota and trigger notifications if >= 80% or >= 100%"""
    alert = notification_service.check_quota_thresholds(
        tenant_id=req.tenant_id,
        user_id=req.user_id,
        used_bytes=req.used_bytes,
        max_bytes=req.max_bytes
    )
    return {"alert_created": alert is not None, "notification": alert}
