from enum import Enum
from typing import Optional, Set
from uuid import UUID
from fastapi import Depends, HTTPException, status, Header, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from backend.app.core.database import get_db, set_tenant_context, reset_tenant_context
from backend.app.core.security import decode_token
from backend.app.models.user import User
from backend.app.models.tenant import Tenant, TenantMember

security = HTTPBearer(auto_error=False)

class Permission(str, Enum):
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_SHARE = "document:share"
    DOCUMENT_RESTORE = "document:restore"
    FOLDER_CREATE = "folder:create"
    FOLDER_MANAGE = "folder:manage"
    MEMBER_INVITE = "member:invite"
    MEMBER_MANAGE = "member:manage"
    TENANT_SETTINGS = "tenant:settings"
    AUDIT_READ = "audit:read"

ROLE_PERMISSIONS: dict[str, Set[Permission]] = {
    "OWNER": {
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_SHARE,
        Permission.DOCUMENT_RESTORE,
        Permission.FOLDER_CREATE,
        Permission.FOLDER_MANAGE,
        Permission.MEMBER_INVITE,
        Permission.MEMBER_MANAGE,
        Permission.TENANT_SETTINGS,
        Permission.AUDIT_READ,
    },
    "EDITOR": {
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_WRITE,
        Permission.DOCUMENT_SHARE,
        Permission.FOLDER_CREATE,
        Permission.FOLDER_MANAGE,
    },
    "VIEWER": {
        Permission.DOCUMENT_READ,
    },
    "GUEST": {
        Permission.DOCUMENT_READ,
    },
}

class TenantContext:
    def __init__(self, user: User, tenant: Tenant, role: str, db: AsyncSession):
        self.user = user
        self.tenant = tenant
        self.role = role
        self.db = db

    @property
    def tenant_id(self) -> UUID:
        return self.tenant.id

    @property
    def user_id(self) -> UUID:
        return self.user.id

    def has_permission(self, permission: Permission) -> bool:
        if self.user.is_superuser:
            return True
        allowed = ROLE_PERMISSIONS.get(self.role, set())
        return permission in allowed

async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token"),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session non authentifiée. Jeton d'accès manquant.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton invalide")
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton expiré ou corrompu")

    user_query = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = user_query.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur inexistant ou désactivé")

    return user

async def get_current_tenant_context(
    current_user: User = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db)
) -> TenantContext:
    """
    Guarantees strict multi-tenant isolation and prevents cross-tenant access.
    1. Checks if the requested tenant exists and the user is verified member.
    2. Fallbacks safely to the user's personal owned tenant if no header provided.
    3. Injects PostgreSQL Row-Level Security (RLS) variable via `SET LOCAL app.current_tenant_id`.
    """
    target_tenant_id: Optional[UUID] = None
    if x_tenant_id:
        try:
            target_tenant_id = UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Format d'identifiant de tenant invalide")

    if target_tenant_id:
        membership_query = await db.execute(
            select(TenantMember, Tenant)
            .join(Tenant, Tenant.id == TenantMember.tenant_id)
            .where(
                TenantMember.tenant_id == target_tenant_id,
                TenantMember.user_id == current_user.id,
                Tenant.is_active == True
            )
        )
        row = membership_query.first()
        if not row:
            # If user is superuser, allow explicit read with audited owner rights
            if current_user.is_superuser:
                tenant_q = await db.execute(select(Tenant).where(Tenant.id == target_tenant_id))
                t = tenant_q.scalar_one_or_none()
                if t:
                    await set_tenant_context(db, str(t.id), is_superuser=True)
                    return TenantContext(user=current_user, tenant=t, role="OWNER", db=db)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Accès interdit : vous n'êtes pas membre de cet espace documentaire ou tentative de violation d'isolation RLS."
            )
        member, tenant = row
        role = member.role
    else:
        # Default to owned personal tenant
        owned_query = await db.execute(
            select(Tenant).where(Tenant.owner_id == current_user.id, Tenant.is_active == True).limit(1)
        )
        tenant = owned_query.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun espace documentaire trouvé pour ce compte")
        role = "OWNER"

    # Enforce PostgreSQL Row-Level Security
    await set_tenant_context(db, str(tenant.id), is_superuser=current_user.is_superuser)

    return TenantContext(user=current_user, tenant=tenant, role=role, db=db)

def require_permission(required_perm: Permission):
    """
    Enforces granular RBAC permissions on endpoints.
    Denies access with 403 Forbidden if user role does not possess the capability.
    """
    async def permission_checker(ctx: TenantContext = Depends(get_current_tenant_context)):
        if not ctx.has_permission(required_perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission insuffisante : l'action requiert '{required_perm.value}', votre rôle est '{ctx.role}'."
            )
        return ctx
    return permission_checker

# Alias for backward compatibility across route handlers
get_tenant_context = get_current_tenant_context
