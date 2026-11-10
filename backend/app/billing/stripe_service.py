"""
DocuSpace SaaS Billing & Stripe Service
Handles Stripe Checkout Sessions, Customer Portal, Webhook HMAC Verification,
Subscription Lifecycles, and Plan Quota Adjustments.
"""
import hmac
import hashlib
import time
import json
from typing import Dict, Any, Optional

PLAN_CATALOG = {
    "FREE": {
        "id": "FREE",
        "name": "DocuSpace Gratuit",
        "price_monthly": 0.00,
        "price_yearly": 0.00,
        "max_storage_bytes": 1073741824,         # 1 Go
        "max_file_size_bytes": 52428800,         # 50 Mo
        "max_members": 1,
        "max_versions_per_file": 3,
        "features": ["1 Go stockage", "ClamAV Antivirus", "3 versions", "Partage sécurisé"]
    },
    "PERSONAL": {
        "id": "PERSONAL",
        "name": "DocuSpace Particulier",
        "price_monthly": 4.99,
        "price_yearly": 49.90,
        "max_storage_bytes": 21474836480,        # 20 Go
        "max_file_size_bytes": 536870912,        # 500 Mo
        "max_members": 3,
        "max_versions_per_file": 10,
        "features": ["20 Go stockage", "ClamAV Antivirus", "10 versions", "Multi-comptes 3 membres", "Support prioritaire"]
    },
    "PREMIUM": {
        "id": "PREMIUM",
        "name": "DocuSpace Famille / Pro",
        "price_monthly": 14.99,
        "price_yearly": 149.90,
        "max_storage_bytes": 214748364800,      # 200 Go
        "max_file_size_bytes": 2147483648,       # 2 Go
        "max_members": 10,
        "max_versions_per_file": 100,
        "features": ["200 Go stockage", "ClamAV Antivirus", "Versions illimitées", "10 membres", "Support dédié 24/7"]
    }
}

class StripeService:
    def __init__(self, webhook_secret: str = "whsec_docuspace_secure_stripe_webhook_2026"):
        self.webhook_secret = webhook_secret

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> bool:
        """
        Verify Stripe webhook signature using HMAC-SHA256 (Stripe protocol v1).
        Format of sig_header: 't=1612345678,v1=5257a869e7ecebeef225ef2ec...'
        """
        if not sig_header:
            return False
        
        try:
            parts = dict(item.split("=", 1) for item in sig_header.split(","))
            timestamp = parts.get("t")
            v1_signature = parts.get("v1")

            if not timestamp or not v1_signature:
                return False

            # Prevent replay attacks: tolerance 10 minutes (600s)
            now = int(time.time())
            if abs(now - int(timestamp)) > 600:
                return False

            # Signed payload = timestamp + '.' + payload
            signed_payload = f"{timestamp}.".encode("utf-8") + payload
            expected_sig = hmac.new(
                self.webhook_secret.encode("utf-8"),
                signed_payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected_sig, v1_signature)
        except Exception:
            return False

    def generate_webhook_signature(self, payload: bytes, timestamp: Optional[int] = None) -> str:
        """Utility to generate a valid v1 signature for testing/simulation"""
        if timestamp is None:
            timestamp = int(time.time())
        signed_payload = f"{timestamp}.".encode("utf-8") + payload
        sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={sig}"

    def create_checkout_session(
        self,
        tenant_id: str,
        user_email: str,
        plan_id: str,
        billing_interval: str = "monthly",
        success_url: str = "https://docuspace.local/billing/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url: str = "https://docuspace.local/billing/cancel"
    ) -> Dict[str, Any]:
        """
        Simulate/create a Stripe Checkout Session for subscription
        """
        if plan_id not in PLAN_CATALOG or plan_id == "FREE":
            raise ValueError(f"Plan {plan_id} is not eligible for paid subscription")

        plan = PLAN_CATALOG[plan_id]
        amount = plan["price_yearly"] if billing_interval == "yearly" else plan["price_monthly"]
        session_id = f"cs_test_{hashlib.sha256(f'{tenant_id}_{time.time()}'.encode()).hexdigest()[:24]}"

        return {
            "session_id": session_id,
            "url": f"https://checkout.stripe.com/c/pay/{session_id}",
            "tenant_id": tenant_id,
            "plan_id": plan_id,
            "billing_interval": billing_interval,
            "amount_eur": amount,
            "currency": "eur",
            "customer_email": user_email,
            "status": "open",
            "expires_at": int(time.time()) + 3600
        }

    def process_webhook_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        current_tenant: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process verified Stripe event and return quota/status adjustments
        """
        result = {
            "event": event_type,
            "processed": True,
            "tenant_id": current_tenant.get("id"),
            "old_plan": current_tenant.get("plan_id"),
            "new_plan": current_tenant.get("plan_id"),
            "status": current_tenant.get("subscription_status", "ACTIVE"),
            "restricted_read_only": False,
            "notification_required": True,
            "notification_message": ""
        }

        if event_type == "checkout.session.completed":
            plan_id = event_data.get("plan_id", "PERSONAL")
            result["new_plan"] = plan_id
            result["status"] = "ACTIVE"
            result["restricted_read_only"] = False
            result["notification_message"] = f"Abonnement {plan_id} validé ! Votre quota passe à {PLAN_CATALOG[plan_id]['name']}."

        elif event_type == "customer.subscription.updated":
            plan_id = event_data.get("plan_id", current_tenant.get("plan_id"))
            sub_status = event_data.get("status", "ACTIVE")
            result["new_plan"] = plan_id
            result["status"] = sub_status
            result["notification_message"] = f"Abonnement mis à jour (Statut: {sub_status})."

        elif event_type == "customer.subscription.deleted":
            # Downgrade to FREE
            result["new_plan"] = "FREE"
            result["status"] = "CANCELED"
            free_quota = PLAN_CATALOG["FREE"]["max_storage_bytes"]
            used_bytes = current_tenant.get("used_bytes", 0)

            # If user has more data than Free plan allows, activate read-only restriction
            if used_bytes > free_quota:
                result["restricted_read_only"] = True
                result["notification_message"] = (
                    f"Abonnement résilié. Votre consommation ({used_bytes / 1024**3:.2f} Go) dépasse le quota gratuit (1 Go). "
                    "Votre espace est placé en lecture seule."
                )
            else:
                result["notification_message"] = "Votre abonnement a pris fin. Vous basculez sur l'offre gratuite."

        elif event_type == "invoice.payment_failed":
            result["status"] = "PAST_DUE"
            result["notification_message"] = "Échec du prélèvement bancaire pour votre abonnement DocuSpace. Veuillez mettre à jour votre moyen de paiement."

        return result

stripe_service = StripeService()
