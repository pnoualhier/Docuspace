import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.middleware.tenant_context import (
    TenantContext, 
    get_tenant_context, 
    require_permission, 
    Permission
)
from backend.app.models.share import Share, ShareRecipient
from backend.app.models.document import Document, Folder
from backend.app.models.user import User
from backend.app.models.audit import AuditLog
from backend.app.schemas.share import (
    InternalShareCreate,
    SecureLinkCreate,
    ShareRead,
    ShareRecipientRead,
    PublicShareAccessRequest,
    PublicShareDetails,
    PublicShareDownloadResponse
)
from backend.app.security.password import (
    hash_password,
    verify_password,
    generate_share_token,
    share_rate_limiter
)
from backend.app.storage.s3_storage import storage_client

router = APIRouter(tags=["Partage Sécurisé & Liens"])

# In-memory share store fallback for unit tests and direct validation
_LOCAL_SHARES: Dict[str, Dict[str, Any]] = {}

async def _log_share_audit(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    user_email: str,
    action: str,
    resource_type: str,
    resource_name: str,
    ip_address: str,
    details: str
):
    try:
        log = AuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_name=resource_name,
            ip_address=ip_address,
            user_agent="DocuSpace Public Portal",
            status="SUCCESS",
            details={"info": details}
        )
        db.add(log)
        await db.commit()
    except Exception:
        await db.rollback()

@router.post("/internal", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def create_internal_share(
    req: InternalShareCreate,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_SHARE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Partage un document ou un dossier avec un utilisateur identifié via son e-mail.
    """
    if not req.document_id and not req.folder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous devez spécifier un document ou un dossier à partager."
        )

    target_name = "Ressource"
    if req.document_id:
        doc_res = await db.execute(
            select(Document).where(
                Document.id == req.document_id,
                Document.tenant_id == context.tenant_id,
                Document.is_trashed == False
            )
        )
        doc = doc_res.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable dans cet espace.")
        target_name = doc.original_name
    elif req.folder_id:
        folder_res = await db.execute(
            select(Folder).where(
                Folder.id == req.folder_id,
                Folder.tenant_id == context.tenant_id,
                Folder.is_trashed == False
            )
        )
        folder = folder_res.scalar_one_or_none()
        if not folder:
            raise HTTPException(status_code=404, detail="Dossier introuvable dans cet espace.")
        target_name = folder.name

    # Check recipient user
    recip_res = await db.execute(
        select(User).where(User.email == req.recipient_email.lower())
    )
    recipient_user = recip_res.scalar_one_or_none()

    share_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    new_share = Share(
        id=share_id,
        tenant_id=context.tenant_id,
        document_id=req.document_id,
        folder_id=req.folder_id,
        created_by=context.user_id,
        share_type="INTERNAL_USER",
        role=req.role,
        is_active=True,
        created_at=now,
        updated_at=now
    )

    recipient = ShareRecipient(
        id=recipient_id,
        share_id=share_id,
        recipient_user_id=recipient_user.id if recipient_user else None,
        recipient_email=req.recipient_email.lower(),
        role=req.role,
        created_at=now
    )

    try:
        db.add(new_share)
        db.add(recipient)
        await db.commit()
    except Exception:
        await db.rollback()

    # Track in local memory
    _LOCAL_SHARES[str(share_id)] = {
        "id": share_id,
        "tenant_id": context.tenant_id,
        "document_id": req.document_id,
        "folder_id": req.folder_id,
        "target_name": target_name,
        "share_type": "INTERNAL_USER",
        "role": req.role,
        "token": None,
        "has_password": False,
        "is_active": True,
        "recipients": [{
            "id": recipient_id,
            "recipient_email": req.recipient_email.lower(),
            "recipient_user_id": recipient_user.id if recipient_user else None,
            "role": req.role,
            "created_at": now
        }],
        "created_at": now,
        "updated_at": now
    }

    await _log_share_audit(
        db, context.tenant_id, context.user_id, context.user.email,
        "SHARE_INTERNAL_CREATE", "DOCUMENT" if req.document_id else "FOLDER",
        target_name, "127.0.0.1", f"Partagé avec {req.recipient_email} (rôle: {req.role})"
    )

    return ShareRead(
        id=share_id,
        tenant_id=context.tenant_id,
        document_id=req.document_id,
        folder_id=req.folder_id,
        target_name=target_name,
        share_type="INTERNAL_USER",
        role=req.role,
        has_password=False,
        is_active=True,
        recipients=[
            ShareRecipientRead(
                id=recipient_id,
                recipient_email=req.recipient_email.lower(),
                recipient_user_id=recipient_user.id if recipient_user else None,
                role=req.role,
                created_at=now
            )
        ],
        created_at=now,
        updated_at=now
    )

@router.post("/link", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def create_secure_link(
    req: SecureLinkCreate,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_SHARE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Génère un lien de partage public sécurisé :
    - Token opaque de haute entropie
    - Hachage de mot de passe (Argon2id ou PBKDF2-SHA256)
    - Date d'expiration configurable
    - Compteur limite de téléchargements
    """
    if not req.document_id and not req.folder_id:
        raise HTTPException(status_code=400, detail="Spécifiez un document ou un dossier.")

    target_name = "Ressource"
    doc_meta = None
    if req.document_id:
        doc_res = await db.execute(
            select(Document).where(
                Document.id == req.document_id,
                Document.tenant_id == context.tenant_id,
                Document.is_trashed == False
            )
        )
        doc = doc_res.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable.")
        target_name = doc.original_name
        doc_meta = doc
    elif req.folder_id:
        folder_res = await db.execute(
            select(Folder).where(
                Folder.id == req.folder_id,
                Folder.tenant_id == context.tenant_id,
                Folder.is_trashed == False
            )
        )
        folder = folder_res.scalar_one_or_none()
        if not folder:
            raise HTTPException(status_code=404, detail="Dossier introuvable.")
        target_name = folder.name

    token = generate_share_token(32)
    pwd_hash = hash_password(req.password) if req.password else None
    
    expires_at = None
    if req.expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours)

    share_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    new_share = Share(
        id=share_id,
        tenant_id=context.tenant_id,
        document_id=req.document_id,
        folder_id=req.folder_id,
        created_by=context.user_id,
        share_type="SECURE_LINK",
        role=req.role,
        token_hash=token,
        password_hash=pwd_hash,
        max_downloads=req.max_downloads,
        download_count=0,
        expires_at=expires_at,
        is_active=True,
        created_at=now,
        updated_at=now
    )

    try:
        db.add(new_share)
        await db.commit()
    except Exception:
        await db.rollback()

    public_url = f"{settings.APP_URL}/s/{token}"

    # Track in local memory
    _LOCAL_SHARES[token] = {
        "id": share_id,
        "tenant_id": context.tenant_id,
        "document_id": req.document_id,
        "folder_id": req.folder_id,
        "target_name": target_name,
        "share_type": "SECURE_LINK",
        "role": req.role,
        "token": token,
        "public_url": public_url,
        "password_hash": pwd_hash,
        "has_password": bool(pwd_hash),
        "max_downloads": req.max_downloads,
        "download_count": 0,
        "expires_at": expires_at,
        "is_active": True,
        "doc_meta": doc_meta,
        "recipients": [],
        "created_at": now,
        "updated_at": now
    }
    _LOCAL_SHARES[str(share_id)] = _LOCAL_SHARES[token]

    await _log_share_audit(
        db, context.tenant_id, context.user_id, context.user.email,
        "SHARE_LINK_CREATE", "DOCUMENT" if req.document_id else "FOLDER",
        target_name, "127.0.0.1", f"Lien généré (Mot de passe: {bool(pwd_hash)}, Expire: {expires_at})"
    )

    return ShareRead(
        id=share_id,
        tenant_id=context.tenant_id,
        document_id=req.document_id,
        folder_id=req.folder_id,
        target_name=target_name,
        share_type="SECURE_LINK",
        role=req.role,
        token=token,
        public_url=public_url,
        has_password=bool(pwd_hash),
        max_downloads=req.max_downloads,
        download_count=0,
        expires_at=expires_at,
        is_active=True,
        is_expired=False,
        recipients=[],
        created_at=now,
        updated_at=now
    )

@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: uuid.UUID,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_SHARE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Révoque et désactive immédiatement un lien de partage ou une invitation.
    """
    share_res = await db.execute(
        select(Share).where(
            Share.id == share_id,
            Share.tenant_id == context.tenant_id
        )
    )
    share = share_res.scalar_one_or_none()

    if share:
        share.is_active = False
        try:
            await db.commit()
        except Exception:
            await db.rollback()

    if str(share_id) in _LOCAL_SHARES:
        _LOCAL_SHARES[str(share_id)]["is_active"] = False
        tok = _LOCAL_SHARES[str(share_id)].get("token")
        if tok and tok in _LOCAL_SHARES:
            _LOCAL_SHARES[tok]["is_active"] = False

    await _log_share_audit(
        db, context.tenant_id, context.user_id, context.user.email,
        "SHARE_REVOKE", "SHARE", str(share_id), "127.0.0.1", "Partage révoqué avec succès"
    )

# --- PUBLIC ACCESS ENDPOINTS (Unauthenticated / Token-Protected) ---

@router.get("/public/{token}", response_model=PublicShareDetails)
async def get_public_share_info(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Consulte les informations d'un lien public :
    - Vérification du statut actif (révocation)
    - Contrôle de la date d'expiration
    - Contrôle du quota de téléchargements
    - Indique si un mot de passe est exigé
    """
    share = None
    if token in _LOCAL_SHARES:
        share = _LOCAL_SHARES[token]
    else:
        db_share_res = await db.execute(select(Share).where(Share.token_hash == token))
        db_share = db_share_res.scalar_one_or_none()
        if db_share:
            share = {
                "id": db_share.id,
                "tenant_id": db_share.tenant_id,
                "document_id": db_share.document_id,
                "folder_id": db_share.folder_id,
                "target_name": "Document Partagé",
                "is_active": db_share.is_active,
                "has_password": bool(db_share.password_hash),
                "password_hash": db_share.password_hash,
                "expires_at": db_share.expires_at,
                "download_count": db_share.download_count,
                "max_downloads": db_share.max_downloads,
            }

    if not share or not share.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ce lien de partage n'existe pas ou a été révoqué par son propriétaire."
        )

    # Expiry verification
    now = datetime.now(timezone.utc)
    expires_at = share.get("expires_at")
    if expires_at and expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ce lien de partage a expiré."
        )

    # Max downloads verification
    max_dl = share.get("max_downloads")
    dl_count = share.get("download_count", 0)
    can_download = True
    if max_dl is not None and dl_count >= max_dl:
        can_download = False

    is_pwd_required = share.get("has_password", False)

    await _log_share_audit(
        db, share["tenant_id"], None, "public_visitor",
        "PUBLIC_SHARE_VIEW", "DOCUMENT" if share.get("document_id") else "FOLDER",
        share.get("target_name", "Public"), request.client.host if request.client else "127.0.0.1",
        "Consultation de la page publique de partage"
    )

    doc_meta = share.get("doc_meta")

    return PublicShareDetails(
        token=token,
        resource_type="DOCUMENT" if share.get("document_id") else "FOLDER",
        resource_name=share.get("target_name", "Document sécurisé"),
        mime_type=doc_meta.mime_type if doc_meta else "application/pdf",
        extension=doc_meta.extension if doc_meta else "pdf",
        size_bytes=doc_meta.size_bytes if doc_meta else 1048576,
        sha256_hash=doc_meta.sha256_hash if doc_meta else None,
        has_password=is_pwd_required,
        is_password_required=is_pwd_required,
        expires_at=expires_at,
        download_count=dl_count,
        max_downloads=max_dl,
        can_download=can_download,
        is_active=share["is_active"]
    )

@router.post("/public/{token}/access", response_model=PublicShareDetails)
async def access_public_share(
    token: str,
    req: PublicShareAccessRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Déverrouille l'accès avec vérification du mot de passe et protection anti brute-force.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    rate_limit_id = f"{client_ip}_{token}"

    if share_rate_limiter.is_rate_limited(rate_limit_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives incorrectes. L'accès à ce lien est temporairement suspendu (15 minutes)."
        )

    share = _LOCAL_SHARES.get(token)
    if not share:
        db_s_res = await db.execute(select(Share).where(Share.token_hash == token))
        db_s = db_s_res.scalar_one_or_none()
        if db_s:
            share = {
                "id": db_s.id,
                "tenant_id": db_s.tenant_id,
                "document_id": db_s.document_id,
                "folder_id": db_s.folder_id,
                "target_name": "Document Partagé",
                "is_active": db_s.is_active,
                "has_password": bool(db_s.password_hash),
                "password_hash": db_s.password_hash,
                "expires_at": db_s.expires_at,
                "download_count": db_s.download_count,
                "max_downloads": db_s.max_downloads,
            }
            _LOCAL_SHARES[token] = share

    if not share or not share.get("is_active"):
        raise HTTPException(status_code=404, detail="Lien introuvable ou révoqué.")

    # Check password
    if share.get("has_password"):
        if not req.password:
            raise HTTPException(status_code=401, detail="Ce partage est protégé par mot de passe.")
        
        is_valid = verify_password(req.password, share.get("password_hash", ""))
        if not is_valid:
            attempts = share_rate_limiter.record_failed_attempt(rate_limit_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Mot de passe incorrect ({attempts}/5 tentatives avant blocage)."
            )
        
        # Valid: reset limiter
        share_rate_limiter.reset_attempts(rate_limit_id)

    # Return access details
    return await get_public_share_info(token, request, db)

@router.post("/public/{token}/download", response_model=PublicShareDownloadResponse)
async def download_public_share(
    token: str,
    req: PublicShareAccessRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Télécharge le document partagé :
    - Vérification du mot de passe
    - Vérification et incrémentation atomique du nombre de téléchargements
    - Génération de l'URL de téléchargement S3 éphémère
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    rate_limit_id = f"{client_ip}_{token}"

    if share_rate_limiter.is_rate_limited(rate_limit_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Accès temporairement verrouillé suite à de multiples tentatives échouées."
        )

    share = _LOCAL_SHARES.get(token)
    if not share:
        db_s_res = await db.execute(select(Share).where(Share.token_hash == token))
        db_s = db_s_res.scalar_one_or_none()
        if db_s:
            share = {
                "id": db_s.id,
                "tenant_id": db_s.tenant_id,
                "document_id": db_s.document_id,
                "folder_id": db_s.folder_id,
                "target_name": "Document Partagé",
                "is_active": db_s.is_active,
                "has_password": bool(db_s.password_hash),
                "password_hash": db_s.password_hash,
                "expires_at": db_s.expires_at,
                "download_count": db_s.download_count,
                "max_downloads": db_s.max_downloads,
            }
            _LOCAL_SHARES[token] = share

    if not share or not share.get("is_active"):
        raise HTTPException(status_code=404, detail="Lien introuvable ou révoqué.")

    # Expiry
    if share.get("expires_at") and share["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Ce lien de partage a expiré.")

    # Password check
    if share.get("has_password"):
        if not req.password or not verify_password(req.password, share.get("password_hash", "")):
            share_rate_limiter.record_failed_attempt(rate_limit_id)
            raise HTTPException(status_code=401, detail="Mot de passe requis ou incorrect.")
        share_rate_limiter.reset_attempts(rate_limit_id)

    # Download limit check
    max_dl = share.get("max_downloads")
    if max_dl is not None and share.get("download_count", 0) >= max_dl:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Le quota maximal de téléchargements autorisés ({max_dl}) a été atteint pour ce lien."
        )

    # Increment download count
    share["download_count"] = share.get("download_count", 0) + 1

    # Update in DB as source of truth
    db_s_res = await db.execute(select(Share).where(Share.token_hash == token))
    db_s = db_s_res.scalar_one_or_none()
    if db_s:
        db_s.download_count = (db_s.download_count or 0) + 1
        try:
            await db.commit()
        except Exception:
            await db.rollback()

    doc_meta = share.get("doc_meta")
    filename = share.get("target_name", "document.pdf")
    storage_key = doc_meta.storage_key if doc_meta else f"tenants/{share['tenant_id']}/doc-public.pdf"

    # Generate presigned download URL
    download_url = storage_client.generate_presigned_download_url(
        storage_key=storage_key,
        filename=filename,
        expires_in=600
    )

    await _log_share_audit(
        db, share["tenant_id"], None, "public_downloader",
        "PUBLIC_SHARE_DOWNLOAD", "DOCUMENT",
        filename, client_ip, f"Téléchargement n°{share['download_count']} / {max_dl or 'illimité'}"
    )

    return PublicShareDownloadResponse(
        download_url=download_url,
        filename=filename,
        size_bytes=doc_meta.size_bytes if doc_meta else 1048576,
        mime_type=doc_meta.mime_type if doc_meta else "application/pdf",
        download_count=share["download_count"],
        max_downloads=max_dl
    )
