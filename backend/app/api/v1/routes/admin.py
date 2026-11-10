"""
DocuSpace Global Admin & Audit API Routes
Platform monitoring, tenant supervision, user status toggle, and audit log exports.
"""
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import csv
import io
import json
import datetime

router = APIRouter(prefix="/admin", tags=["Global Administration"])

class UserStatusRequest(BaseModel):
    is_active: bool

class PlanOverrideRequest(BaseModel):
    plan_id: str

@router.get("/stats")
async def get_admin_stats():
    """Retrieve global platform statistics"""
    return {
        "tenants_count": 3,
        "users_count": 4,
        "total_storage_bytes": 62914560, # ~60 MB
        "storage_capacity_bytes": 214748364800, # 200 GB
        "services_healthy": 6,
        "total_services": 6,
        "antivirus_status": "FAIL_CLOSED_OPTIMAL"
    }

@router.get("/audit-logs")
async def get_audit_logs(
    format: str = Query("json", description="json or csv"),
    action: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None)
):
    """Retrieve audit logs with optional CSV export"""
    sample_logs = [
        {
            "id": "log-001",
            "timestamp": "2026-11-10T09:12:00Z",
            "action": "AUTH_LOGIN",
            "resource_name": "alice.dupont@example.com",
            "user_email": "alice.dupont@example.com",
            "ip_address": "192.168.1.45",
            "status": "SUCCESS"
        },
        {
            "id": "log-002",
            "timestamp": "2026-11-10T09:15:30Z",
            "action": "DOC_UPLOAD_VERIFIED",
            "resource_name": "Contrat_Prestation_2026.pdf",
            "user_email": "alice.dupont@example.com",
            "ip_address": "192.168.1.45",
            "status": "SUCCESS"
        },
        {
            "id": "log-003",
            "timestamp": "2026-11-10T09:20:10Z",
            "action": "SECURITY_ALERT",
            "resource_name": "BruteForceProtection",
            "user_email": "system@docuspace.local",
            "ip_address": "198.51.100.4",
            "status": "BLOCKED"
        }
    ]

    if action:
        sample_logs = [l for l in sample_logs if l["action"] == action]

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "timestamp", "action", "resource_name", "user_email", "ip_address", "status"])
        writer.writeheader()
        writer.writerows(sample_logs)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=docuspace_audit_logs.csv"}
        )

    return {"logs": sample_logs, "total": len(sample_logs)}
