"""
DocuSpace Billing API Routes
Authenticated Stripe Checkout, HMAC-verified Webhook Processing backed by PostgreSQL.
"""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.billing.stripe_service import PLAN_CATALOG, stripe_service
from backend.app.core.database import get_db, set_tenant_context
from backend.app.middleware.tenant_context import Permission, TenantContext, require_permission
from backend.app.models.audit import AuditLog, Notification
from backend.app.models.plan import Plan
from backend.app.models.tenant import StorageUsage, Tenant

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., description="Target plan (PERSONAL, PREMIUM)")
    billing_interval: str = Field("monthly", description="monthly or yearly")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class WebhookResponse(BaseModel):
    received: bool
    event_type: str
    status: str
    message: Optional[str] = None


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Return available SaaS subscription plans from PostgreSQL enriched with billing catalog."""
    rows = (
        await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.max_storage_bytes.asc()))
    ).scalars().all()
    if not rows:
        return list(PLAN_CATALOG.values())

    plans = []
    for p in rows:
        cat = PLAN_CATALOG.get(p.id, {})
        plans.append({
            "id": p.id,
            "name": p.name,
            "price_monthly": cat.get("price_monthly", 0.0),
            "price_yearly": cat.get("price_yearly", 0.0),
            "max_storage_bytes": p.max_storage_bytes,
            "max_file_size_bytes": p.max_file_size_bytes,
            "max_members": p.max_members,
            "max_versions_per_file": p.max_versions_per_file,
            "features": cat.get("features", p.features or []),
        })
    return plans


@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    ctx: TenantContext = Depends(require_permission(Permission.TENANT_SETTINGS)),
):
    """Create Stripe Checkout session bound to the authenticated tenant & owner."""
    try:
        session = stripe_service.create_checkout_session(
            tenant_id=str(ctx.tenant.id),
            user_email=ctx.user.email,
            plan_id=req.plan_id.upper(),
            billing_interval=req.billing_interval,
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook with HMAC-SHA256 signature verification and persist subscription updates in PostgreSQL.
    """
    payload = await request.body()

    if not stripe_signature or not stripe_service.verify_webhook_signature(payload, stripe_signature):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")

    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON payload")

    event_type = event.get("type", "")
    event_data = event.get("data", {}).get("object", {})
    raw_tenant_id = event_data.get("tenant_id") or (event_data.get("metadata") or {}).get("tenant_id")
    if not raw_tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant_id in Stripe webhook event")

    try:
        tenant_uuid = UUID(str(raw_tenant_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id UUID in Stripe webhook event")

    await set_tenant_context(db, str(tenant_uuid), is_superuser=True)

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant introuvable pour ce webhook Stripe.")

    usage = (
        await db.execute(select(StorageUsage).where(StorageUsage.tenant_id == tenant_uuid))
    ).scalar_one_or_none()
    used_bytes = usage.used_bytes if usage else 0

    current_tenant_state = {
        "id": str(tenant.id),
        "plan_id": tenant.plan_id,
        "used_bytes": used_bytes,
        "subscription_status": tenant.subscription_status,
    }

    result = stripe_service.process_webhook_event(event_type, event_data, current_tenant_state)

    new_plan = result.get("new_plan")
    if new_plan and new_plan in PLAN_CATALOG:
        plan_exists = (await db.execute(select(Plan.id).where(Plan.id == new_plan))).scalar_one_or_none()
        if plan_exists:
            tenant.plan_id = new_plan

    tenant.subscription_status = result.get("status", tenant.subscription_status)
    tenant.restricted_read_only = bool(result.get("restricted_read_only", False))

    if result.get("notification_required"):
        db.add(Notification(
            tenant_id=tenant.id,
            user_id=tenant.owner_id,
            category="BILLING",
            level="INFO" if result.get("status") == "ACTIVE" else "WARNING",
            type="INFO" if result.get("status") == "ACTIVE" else "WARNING",
            title=f"Notification Facturation : {event_type}",
            message=result.get("notification_message", ""),
            action_url="/billing",
            link="/billing",
        ))

    db.add(AuditLog(
        tenant_id=tenant.id,
        user_id=tenant.owner_id,
        action="BILLING_WEBHOOK_PROCESSED",
        resource_type="TENANT",
        resource_id=tenant.id,
        details={
            "event_type": event_type,
            "old_plan": current_tenant_state["plan_id"],
            "new_plan": tenant.plan_id,
            "subscription_status": tenant.subscription_status,
            "restricted_read_only": tenant.restricted_read_only,
        },
    ))
    await db.commit()

    return {
        "received": True,
        "event_type": event_type,
        "status": result.get("status", "OK"),
        "message": result.get("notification_message"),
    }
