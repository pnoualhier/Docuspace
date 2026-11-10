"""
DocuSpace Notification Service
Handles in-app notification dispatch, quota threshold monitoring (80% warning / 100% blocker),
security intrusion alerts, and email notifications.
"""
import uuid
import datetime
from typing import Dict, Any, List, Optional

class NotificationService:
    def __init__(self):
        # In-memory notification store for demonstration and fast testing
        self._notifications: List[Dict[str, Any]] = []

    def create_notification(
        self,
        tenant_id: str,
        user_id: str,
        category: str, # 'STORAGE', 'SECURITY', 'BILLING', 'SHARING'
        title: str,
        message: str,
        level: str = "INFO", # 'INFO', 'WARNING', 'CRITICAL', 'SUCCESS'
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create and store a new in-app notification"""
        notif = {
            "id": f"notif-{uuid.uuid4()}",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "category": category,
            "title": title,
            "message": message,
            "level": level,
            "action_url": action_url,
            "is_read": False,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        self._notifications.insert(0, notif)
        return notif

    def list_notifications(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        unread_only: bool = False,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List notifications with filtering"""
        res = [n for n in self._notifications if n["tenant_id"] == tenant_id]
        if user_id:
            res = [n for n in res if n["user_id"] == user_id or n["user_id"] == "all"]
        if unread_only:
            res = [n for n in res if not n["is_read"]]
        if category and category != "all":
            res = [n for n in res if n["category"] == category]
        return res

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark a notification as read"""
        for n in self._notifications:
            if n["id"] == notification_id:
                n["is_read"] = True
                return True
        return False

    def mark_all_as_read(self, tenant_id: str, user_id: Optional[str] = None) -> int:
        """Mark all matching notifications as read"""
        count = 0
        for n in self._notifications:
            if n["tenant_id"] == tenant_id and (not user_id or n["user_id"] in (user_id, "all")):
                if not n["is_read"]:
                    n["is_read"] = True
                    count += 1
        return count

    def check_quota_thresholds(
        self,
        tenant_id: str,
        user_id: str,
        used_bytes: int,
        max_bytes: int
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate storage usage against threshold policies:
        - Alert at 80% (Warning)
        - Blocker alert at 100% (Critical)
        """
        if max_bytes <= 0:
            return None

        ratio = used_bytes / max_bytes
        percent = int(ratio * 100)

        if ratio >= 1.0:
            return self.create_notification(
                tenant_id=tenant_id,
                user_id=user_id,
                category="STORAGE",
                title="Quota de stockage 100% atteint !",
                message=f"Votre espace documentaire a atteint sa capacité maximale ({percent}%). Les nouveaux imports sont bloqués. Libérez de l'espace ou passez à l'offre supérieure.",
                level="CRITICAL",
                action_url="/storage"
            )
        elif ratio >= 0.80:
            return self.create_notification(
                tenant_id=tenant_id,
                user_id=user_id,
                category="STORAGE",
                title="Attention : Seuil de stockage à 80%",
                message=f"Votre espace documentaire a dépassé 80% de sa capacité ({percent}% utilisés). Pensez à vérifier vos quotas.",
                level="WARNING",
                action_url="/storage"
            )

        return None

notification_service = NotificationService()
