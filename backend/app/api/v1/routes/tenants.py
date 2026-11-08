from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.models.tenant import Tenant, TenantMember, StorageUsage
from backend.app.models.plan import Plan
from backend.app.schemas.tenant import TenantRead, StorageUsageRead, PlanRead
from backend.app.middleware.tenant_context import get_current_user, get_current_tenant_context, TenantContext
from backend.app.models.user import User

router = APIRouter()

@router.get("/my-tenants", response_model=List[TenantRead], tags=["Espaces & Tenants"])
async def list_user_tenants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists all tenants/workspaces accessible to the authenticated user."""
    query = await db.execute(
        select(Tenant, TenantMember.role)
        .join(TenantMember, TenantMember.tenant_id == Tenant.id)
        .where(TenantMember.user_id == current_user.id, Tenant.is_active == True)
    )
    results = []
    for tenant, role in query.all():
        results.append(TenantRead(
            id=tenant.id,
            name=tenant.name,
            owner_id=tenant.owner_id,
            plan_id=tenant.plan_id,
            role=role,
            is_active=tenant.is_active,
            created_at=tenant.created_at
        ))
    return results

@router.get("/current", response_model=TenantRead, tags=["Espaces & Tenants"])
async def get_current_tenant(
    ctx: TenantContext = Depends(get_current_tenant_context)
):
    """Returns details and quota usage of the currently active tenant space."""
    storage_q = await ctx.db.execute(select(StorageUsage).where(StorageUsage.tenant_id == ctx.tenant.id))
    storage = storage_q.scalar_one_or_none()
    
    plan_q = await ctx.db.execute(select(Plan).where(Plan.id == ctx.tenant.plan_id))
    plan = plan_q.scalar_one_or_none()
    max_bytes = plan.max_storage_bytes if plan else 524288000
    
    used = storage.used_bytes if storage else 0
    reserved = storage.reserved_bytes if storage else 0
    doc_count = storage.document_count if storage else 0

    return TenantRead(
        id=ctx.tenant.id,
        name=ctx.tenant.name,
        owner_id=ctx.tenant.owner_id,
        plan_id=ctx.tenant.plan_id,
        role=ctx.role,
        is_active=ctx.tenant.is_active,
        created_at=ctx.tenant.created_at,
        storage_usage=StorageUsageRead(
            tenant_id=ctx.tenant.id,
            used_bytes=used,
            reserved_bytes=reserved,
            document_count=doc_count,
            max_storage_bytes=max_bytes,
            percent_used=round((used / max_bytes) * 100, 2) if max_bytes > 0 else 0.0
        )
    )

@router.get("/plans", response_model=List[PlanRead], tags=["Espaces & Tenants"])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Lists available subscription plans (Free, Personal, Premium)."""
    plans = await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.max_storage_bytes))
    return plans.scalars().all()
