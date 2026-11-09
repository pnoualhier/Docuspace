from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Path
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from backend.app.core.database import get_db
from backend.app.models.tenant import Tenant, TenantMember, StorageUsage, Role
from backend.app.models.plan import Plan
from backend.app.models.user import User
from backend.app.schemas.tenant import TenantRead, StorageUsageRead, PlanRead
from backend.app.middleware.tenant_context import (
    get_current_user, 
    get_current_tenant_context, 
    TenantContext, 
    require_permission, 
    Permission
)

router = APIRouter()

class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: str = "VIEWER"

class MemberUpdateRequest(BaseModel):
    role: str

class MemberRead(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: str
    joined_at: str

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

@router.get("/current/members", response_model=List[MemberRead], tags=["Espaces & Tenants"])
async def list_tenant_members(
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """Lists all members and their roles in the current active tenant."""
    query = await ctx.db.execute(
        select(TenantMember, User)
        .join(User, User.id == TenantMember.user_id)
        .where(TenantMember.tenant_id == ctx.tenant.id)
    )
    members = []
    for member, user in query.all():
        members.append(MemberRead(
            id=member.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=member.role,
            joined_at=member.created_at.isoformat()
        ))
    return members

@router.post("/current/members", status_code=status.HTTP_201_CREATED, tags=["Espaces & Tenants"])
async def invite_member(
    payload: MemberInviteRequest,
    ctx: TenantContext = Depends(require_permission(Permission.MEMBER_INVITE))
):
    """Invites a user to the active tenant space with specified role."""
    target_user_q = await ctx.db.execute(select(User).where(User.email == payload.email.lower()))
    target_user = target_user_q.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Aucun utilisateur trouvé avec l'adresse {payload.email}"
        )

    # Check if already member
    existing_m = await ctx.db.execute(
        select(TenantMember).where(
            TenantMember.tenant_id == ctx.tenant.id, 
            TenantMember.user_id == target_user.id
        )
    )
    if existing_m.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cet utilisateur est déjà membre de cet espace")

    # Verify role validity
    role_check = await ctx.db.execute(select(Role).where(Role.name == payload.role.upper()))
    if not role_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rôle spécifié invalide")

    new_member = TenantMember(
        tenant_id=ctx.tenant.id,
        user_id=target_user.id,
        role=payload.role.upper()
    )
    ctx.db.add(new_member)
    await ctx.db.commit()
    return {"message": f"Utilisateur {target_user.email} invité avec succès avec le rôle {payload.role.upper()}"}

@router.patch("/current/members/{user_id}", tags=["Espaces & Tenants"])
async def update_member_role(
    user_id: UUID = Path(...),
    payload: MemberUpdateRequest = None,
    ctx: TenantContext = Depends(require_permission(Permission.MEMBER_MANAGE))
):
    """Updates a member's role in the active tenant."""
    if user_id == ctx.tenant.owner_id and payload.role != "OWNER":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Impossible de révoquer le rôle du propriétaire initial.")

    member_q = await ctx.db.execute(
        select(TenantMember).where(TenantMember.tenant_id == ctx.tenant.id, TenantMember.user_id == user_id)
    )
    member = member_q.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membre introuvable dans cet espace")

    member.role = payload.role.upper()
    await ctx.db.commit()
    return {"message": f"Rôle mis à jour : {member.role}"}

@router.delete("/current/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Espaces & Tenants"])
async def remove_member(
    user_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.MEMBER_MANAGE))
):
    """Removes a member from the active tenant space."""
    if user_id == ctx.tenant.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Impossible de supprimer le propriétaire de l'espace.")

    member_q = await ctx.db.execute(
        select(TenantMember).where(TenantMember.tenant_id == ctx.tenant.id, TenantMember.user_id == user_id)
    )
    member = member_q.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membre introuvable")

    await ctx.db.delete(member)
    await ctx.db.commit()
    return None

@router.get("/plans", response_model=List[PlanRead], tags=["Espaces & Tenants"])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Lists available subscription plans (Free, Personal, Premium)."""
    plans = await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.max_storage_bytes))
    return plans.scalars().all()
