"""
DocuSpace Billing API Routes
Stripe Checkout, Webhook Processing, and Subscription Management.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from backend.app.billing.stripe_service import stripe_service, PLAN_CATALOG
from backend.app.notifications.notification_service import notification_service

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
async def list_plans():
    """Return available SaaS subscription plans"""
    return list(PLAN_CATALOG.values())

@router.post("/checkout")
async def create_checkout(req: CheckoutRequest):
    """Create Stripe Checkout session"""
    try:
        session = stripe_service.create_checkout_session(
            tenant_id="tnt-alice-main",
            user_email="alice.dupont@example.com",
            plan_id=req.plan_id.upper(),
            billing_interval=req.billing_interval
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")
):
    """
    Handle Stripe webhook with HMAC-SHA256 signature verification.
    """
    payload = await request.body()
    
    if not stripe_signature or not stripe_service.verify_webhook_signature(payload, stripe_signature):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")

    import json
    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON payload")

    event_type = event.get("type", "")
    event_data = event.get("data", {}).get("object", {})

    mock_tenant = {
        "id": "tnt-alice-main",
        "plan_id": "FREE",
        "used_bytes": 1500000000,
        "subscription_status": "ACTIVE"
    }

    result = stripe_service.process_webhook_event(event_type, event_data, mock_tenant)

    if result.get("notification_required"):
        notification_service.create_notification(
            tenant_id=mock_tenant["id"],
            user_id="usr-alice-01",
            category="BILLING",
            title=f"Notification Facturation : {event_type}",
            message=result.get("notification_message", ""),
            level="INFO" if result.get("status") == "ACTIVE" else "WARNING"
        )

    return {
        "received": True,
        "event_type": event_type,
        "status": result.get("status", "OK"),
        "message": result.get("notification_message")
    }
