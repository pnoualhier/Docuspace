"""
DocuSpace Global Admin & Audit API Routes
Requires authenticated superuser privileges. Queries real PostgreSQL tables under audited superuser context.
"""
import csv
import io
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db, set_tenant_context
from backend.app.middleware.tenant_context import get_current_user
from backend.app.models.audit import AuditLog
from backend.app.models.document import Document
from backend.app.models.plan import Plan
from backend.app.models.tenant import StorageUsage, Tenant
from backend.app.models.user import User

router = APIRouter(prefix="/admin", tags=["Global Administration"])


class UserStatusRequest(BaseModel):
    is_active: bool


class PlanOverrideRequest(BaseModel):
    plan_id: str


def _sanitize_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


async def require_superuser(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs système DocuSpace.",
        )
    await set_tenant_context(db, "", is_superuser=True)
    return current_user


@router.get("/stats")
async def get_admin_stats(
    admin_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve global platform statistics from PostgreSQL."""
    tenants_count = (await db.execute(select(func.count(Tenant.id)))).scalar() or 0
    users_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    documents_count = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    total_storage_bytes = (
        await db.execute(select(func.coalesce(func.sum(StorageUsage.used_bytes), 0)))
    ).scalar() or 0
    total_capacity_bytes = (
        await db.execute(
            select(func.coalesce(func.sum(Plan.max_storage_bytes), 0))
            .select_from(Tenant)
            .join(Plan, Tenant.plan_id == Plan.id)
        )
    ).scalar() or 0

    return {
        "tenants_count": int(tenants_count),
        "users_count": int(users_count),
        "documents_count": int(documents_count),
        "total_storage_bytes": int(total_storage_bytes),
        "storage_capacity_bytes": int(total_capacity_bytes),
        "antivirus_status": "FAIL_CLOSED_ACTIVE",
    }


@router.get("/audit-logs")
async def get_audit_logs(
    format: str = Query("json", description="json or csv"),
    action: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    tenant_id: Optional[UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve real persisted audit logs from PostgreSQL with pagination and optional CSV export."""
    stmt = (
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
    )
    count_stmt = select(func.count(AuditLog.id))

    if action:
        stmt = stmt.where(AuditLog.action == action.strip())
        count_stmt = count_stmt.where(AuditLog.action == action.strip())
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if tenant_id:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
        count_stmt = count_stmt.where(AuditLog.tenant_id == tenant_id)

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt.limit(limit).offset(offset))).all()

    logs = [
        {
            "id": str(log.id),
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "tenant_id": str(log.tenant_id) if log.tenant_id else None,
            "user_id": str(log.user_id) if log.user_id else None,
            "user_email": email or "system",
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "details": log.details or {},
            "ip_address": log.ip_address,
        }
        for log, email in rows
    ]

    if format.lower() == "csv":
        output = io.StringIO()
        fieldnames = ["id", "timestamp", "action", "resource_type", "resource_id", "user_email", "ip_address"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in logs:
            writer.writerow({k: _sanitize_csv_cell(row.get(k)) for k in fieldnames})
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=docuspace_audit_logs.csv"},
        )

    return {"logs": logs, "total": int(total), "limit": limit, "offset": offset}


@router.patch("/users/{target_user_id}/status")
async def update_user_status(
    payload: UserStatusRequest,
    target_user_id: UUID = Path(...),
    admin_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a user account (audited superuser action)."""
    if target_user_id == admin_user.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="Impossible de désactiver votre propre compte administrateur.")

    user_row = (await db.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    if not user_row:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    user_row.is_active = payload.is_active
    db.add(AuditLog(
        user_id=admin_user.id,
        action="ADMIN_USER_STATUS_UPDATED",
        resource_type="USER",
        resource_id=target_user_id,
        details={"is_active": payload.is_active},
    ))
    await db.commit()
    return {"id": str(user_row.id), "is_active": user_row.is_active}


@router.patch("/tenants/{target_tenant_id}/plan")
async def override_tenant_plan(
    payload: PlanOverrideRequest,
    target_tenant_id: UUID = Path(...),
    admin_user: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Override a tenant's subscription plan (audited superuser action)."""
    plan_id = payload.plan_id.strip().upper()
    plan = (await db.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=400, detail=f"Forfait inconnu : {plan_id}")

    tenant = (await db.execute(select(Tenant).where(Tenant.id == target_tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Espace documentaire introuvable.")

    old_plan = tenant.plan_id
    tenant.plan_id = plan_id
    db.add(AuditLog(
        tenant_id=target_tenant_id,
        user_id=admin_user.id,
        action="ADMIN_PLAN_OVERRIDE",
        resource_type="TENANT",
        resource_id=target_tenant_id,
        details={"old_plan": old_plan, "new_plan": plan_id},
    ))
    await db.commit()
    return {"tenant_id": str(tenant.id), "plan_id": tenant.plan_id}
