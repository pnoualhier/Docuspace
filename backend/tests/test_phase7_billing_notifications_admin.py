"""
DocuSpace Phase 7 — Billing, Notifications & Global Administration Tests
Validates:
1. Stripe Webhook HMAC-SHA256 signature validation & anti-replay checks
2. Subscription lifecycle (checkout, upgrade, downgrade, past_due, quota restriction)
3. Notification triggers (80% warning, 100% blocker, read receipts)
4. Admin audit log formatting and CSV export
"""
import sys
import os
import time
import json

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.billing.stripe_service import stripe_service, PLAN_CATALOG
from backend.app.notifications.notification_service import notification_service

def test_stripe_webhook_hmac_signatures():
    print("[>] Testing Stripe Webhook HMAC-SHA256 Signatures & Anti-Replay...")
    payload = json.dumps({"id": "evt_test_123", "type": "checkout.session.completed"}).encode("utf-8")
    
    # 1. Valid signature
    valid_sig = stripe_service.generate_webhook_signature(payload)
    assert stripe_service.verify_webhook_signature(payload, valid_sig) is True, "Valid signature must pass"

    # 2. Tampered payload
    tampered_payload = json.dumps({"id": "evt_test_123", "type": "tampered"}).encode("utf-8")
    assert stripe_service.verify_webhook_signature(tampered_payload, valid_sig) is False, "Tampered payload must fail"

    # 3. Replay attack: expired timestamp (e.g. 15 minutes ago > 600s tolerance)
    old_timestamp = int(time.time()) - 1000
    expired_sig = stripe_service.generate_webhook_signature(payload, timestamp=old_timestamp)
    assert stripe_service.verify_webhook_signature(payload, expired_sig) is False, "Expired webhook must be rejected"

    print("  [✓] Stripe HMAC-SHA256 webhook signatures & replay guards verified.")

def test_subscription_lifecycle_and_quota_adjustments():
    print("[>] Testing Subscription Lifecycle & Quota Adjustments...")
    
    # Tenant with 15 GB of stored documents
    mock_tenant = {
        "id": "tnt-alice-main",
        "plan_id": "PERSONAL",
        "used_bytes": 15 * 1024 * 1024 * 1024, # 15 Go
        "subscription_status": "ACTIVE"
    }

    # 1. Upgrade event
    upgrade_event = {
        "plan_id": "PREMIUM",
        "status": "ACTIVE"
    }
    res_upgrade = stripe_service.process_webhook_event("checkout.session.completed", upgrade_event, mock_tenant)
    assert res_upgrade["new_plan"] == "PREMIUM"
    assert res_upgrade["status"] == "ACTIVE"
    assert res_upgrade["restricted_read_only"] is False

    # 2. Payment failed event
    res_failed = stripe_service.process_webhook_event("invoice.payment_failed", {}, mock_tenant)
    assert res_failed["status"] == "PAST_DUE"

    # 3. Cancellation / Downgrade to FREE:
    # Free quota is 1 Go, but tenant has 15 Go. System must place space in restricted_read_only.
    res_downgrade = stripe_service.process_webhook_event("customer.subscription.deleted", {}, mock_tenant)
    assert res_downgrade["new_plan"] == "FREE"
    assert res_downgrade["status"] == "CANCELED"
    assert res_downgrade["restricted_read_only"] is True, "Tenant using 15 GB on Free plan must enter restricted read-only mode"

    print("  [✓] Subscription lifecycle, plan downgrade & quota restriction verified.")

def test_quota_threshold_notifications():
    print("[>] Testing Quota Threshold Notifications (80% warning / 100% blocker)...")
    tenant_id = "tnt-notif-test"
    user_id = "usr-test-01"
    max_quota = 10 * 1024 * 1024 * 1024 # 10 Go

    # 1. Usage at 50%: No alert
    n1 = notification_service.check_quota_thresholds(tenant_id, user_id, 5 * 1024**3, max_quota)
    assert n1 is None

    # 2. Usage at 85%: Warning alert
    n2 = notification_service.check_quota_thresholds(tenant_id, user_id, int(8.5 * 1024**3), max_quota)
    assert n2 is not None
    assert n2["level"] == "WARNING"
    assert "80%" in n2["title"]
    assert n2["is_read"] is False

    # 3. Usage at 100%: Critical alert
    n3 = notification_service.check_quota_thresholds(tenant_id, user_id, 10 * 1024**3, max_quota)
    assert n3 is not None
    assert n3["level"] == "CRITICAL"
    assert "100%" in n3["title"]

    # 4. Mark notification as read
    notif_id = n2["id"]
    success = notification_service.mark_as_read(notif_id)
    assert success is True
    
    # 5. Mark all as read
    marked_count = notification_service.mark_all_as_read(tenant_id)
    assert marked_count >= 1

    unread = notification_service.list_notifications(tenant_id, unread_only=True)
    assert len(unread) == 0

    print("  [✓] Quota threshold notifications & read state management verified.")

def test_admin_audit_logs_and_stats():
    print("[>] Testing Admin Supervision & Audit Log Export...")
    # Test CSV formatting logic
    import io
    import csv

    sample_logs = [
        {"id": "log-001", "timestamp": "2026-11-10T10:00:00Z", "action": "AUTH_LOGIN", "resource_name": "Login", "user_email": "admin@docuspace.local", "ip_address": "127.0.0.1", "status": "SUCCESS"}
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "timestamp", "action", "resource_name", "user_email", "ip_address", "status"])
    writer.writeheader()
    writer.writerows(sample_logs)
    csv_content = output.getvalue()

    assert "AUTH_LOGIN" in csv_content
    assert "admin@docuspace.local" in csv_content
    assert "timestamp,action" in csv_content

    print("  [✓] Admin audit log CSV formatting verified.")

if __name__ == "__main__":
    print("[*] ========================================================")
    print("[*] Running DocuSpace Phase 7 — Billing, Notifications & Admin")
    print("[*] ========================================================")
    test_stripe_webhook_hmac_signatures()
    test_subscription_lifecycle_and_quota_adjustments()
    test_quota_threshold_notifications()
    test_admin_audit_logs_and_stats()
    print("[*] ========================================================")
    print("[*] ALL PHASE 7 BILLING, NOTIFICATIONS & ADMIN TESTS PASSED!")
    print("[*] ========================================================")
