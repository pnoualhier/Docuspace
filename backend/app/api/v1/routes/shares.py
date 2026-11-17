import uuid
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload

from backend.app.core.database import (
    get_db,
    set_public_share_context,
    set_tenant_context,
    set_user_recipient_context,
)
from backend.app.core.config import settings
from backend.app.middleware.tenant_context import (
    TenantContext,
    get_current_user,
    require_permission,
    Permission,
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
    PublicShareDownloadResponse,
)
from backend.app.security.password import (
    hash_password,
    verify_password,
    generate_share_token,
    hash_share_token,
    share_rate_limiter,
)
from backend.app.storage.s3_storage import storage_client

router = APIRouter(tags=["Partage Sécurisé & Liens"])

ALLOWED_SHARE_ROLES = {"VIEWER", "EDITOR", "GUEST"}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_client_meta(request: Optional[Request]) -> Tuple[str, str]:
    if not request:
        return "127.0.0.1", "DocuSpace Client"
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "DocuSpace Client")[:512]
    return client_ip, user_agent


def _build_audit_log(
    tenant_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
    user_email: str,
    action: str,
    resource_type: str,
    resource_id: Optional[uuid.UUID],
    resource_name: str,
    ip_address: str,
    user_agent: str,
    details: str,
    audit_status: str = "SUCCESS",
) -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "user_email": user_email,
            "resource_name": resource_name,
            "status": audit_status,
            "info": details,
        },
    )


async def _commit_or_fail(db: AsyncSession, context_message: str) -> None:
    """
    Commits PostgreSQL transaction strictly.
    Never ignores persistence errors: rolls back and raises HTTP 500 on failure.
    """
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{context_message} : échec de persistance PostgreSQL.",
        ) from exc


async def _resolve_share_target(
    db: AsyncSession,
    share: Share,
) -> Tuple[str, Optional[Document], Optional[Folder]]:
    """
    Resolves the shared Document or Folder strictly from PostgreSQL,
    enforcing same-tenant integrity and excluding trashed resources.
    """
    await set_tenant_context(db, str(share.tenant_id))
    if share.document_id:
        res = await db.execute(
            select(Document).where(
                Document.id == share.document_id,
                Document.tenant_id == share.tenant_id,
                Document.is_trashed == False,
            )
        )
        doc = res.scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La ressource partagée est introuvable ou a été supprimée.",
            )
        return doc.original_name, doc, None

    if share.folder_id:
        res = await db.execute(
            select(Folder).where(
                Folder.id == share.folder_id,
                Folder.tenant_id == share.tenant_id,
                Folder.is_trashed == False,
            )
        )
        folder = res.scalar_one_or_none()
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Le dossier partagé est introuvable ou a été supprimé.",
            )
        return folder.name, None, folder

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Aucune cible valide associée à ce partage.",
    )


def _share_to_read(
    share: Share,
    target_name: str,
    raw_token: Optional[str] = None,
) -> ShareRead:
    now = datetime.now(timezone.utc)
    expires_at = _ensure_utc(share.expires_at)
    is_expired = bool(expires_at and expires_at < now)
    public_url = f"{settings.APP_URL}/s/{raw_token}" if raw_token else None

    recipients_list = [
        ShareRecipientRead(
            id=r.id,
            recipient_email=r.recipient_email,
            recipient_user_id=r.recipient_user_id,
            role=r.role,
            created_at=r.created_at,
        )
        for r in (share.recipients or [])
    ]

    return ShareRead(
        id=share.id,
        tenant_id=share.tenant_id,
        document_id=share.document_id,
        folder_id=share.folder_id,
        created_by=share.created_by,
        target_name=target_name,
        share_type=share.share_type,
        role=share.role,
        token=raw_token,
        public_url=public_url,
        has_password=bool(share.password_hash),
        max_downloads=share.max_downloads,
        download_count=share.download_count or 0,
        expires_at=expires_at,
        is_active=share.is_active,
        is_expired=is_expired,
        recipients=recipients_list,
        created_at=share.created_at,
        updated_at=share.updated_at,
    )


# =========================================================================
# 1. AUTHENTICATED TENANT SHARE MANAGEMENT (PostgreSQL Source of Truth)
# =========================================================================

@router.get("", response_model=List[ShareRead])
@router.get("/", response_model=List[ShareRead], include_in_schema=False)
async def list_tenant_shares(
    document_id: Optional[uuid.UUID] = Query(None),
    folder_id: Optional[uuid.UUID] = Query(None),
    active_only: bool = Query(False),
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste les partages appartenant au tenant actif directement depuis PostgreSQL.
    Les jetons bruts ne sont jamais exposés (seule l'empreinte SHA-256 existe en base).
    """
    stmt = (
        select(Share)
        .options(selectinload(Share.recipients))
        .where(Share.tenant_id == context.tenant_id)
    )
    if document_id:
        stmt = stmt.where(Share.document_id == document_id)
    if folder_id:
        stmt = stmt.where(Share.folder_id == folder_id)
    if active_only:
        stmt = stmt.where(Share.is_active == True)

    stmt = stmt.order_by(Share.created_at.desc())
    res = await db.execute(stmt)
    shares = res.scalars().all()

    items: List[ShareRead] = []
    for s in shares:
        target_name = "Ressource"
        if s.document_id:
            d_res = await db.execute(
                select(Document.original_name).where(
                    Document.id == s.document_id,
                    Document.tenant_id == context.tenant_id,
                )
            )
            name_val = d_res.scalar_one_or_none()
            if name_val:
                target_name = name_val
        elif s.folder_id:
            f_res = await db.execute(
                select(Folder.name).where(
                    Folder.id == s.folder_id,
                    Folder.tenant_id == context.tenant_id,
                )
            )
            name_val = f_res.scalar_one_or_none()
            if name_val:
                target_name = name_val
        items.append(_share_to_read(s, target_name=target_name, raw_token=None))

    return items


@router.post("/internal", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def create_internal_share(
    req: InternalShareCreate,
    request: Request,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_SHARE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Partage un document ou un dossier avec un utilisateur identifié via son e-mail.
    Persistance atomique dans PostgreSQL (Share + ShareRecipient + AuditLog).
    """
    if bool(req.document_id) == bool(req.folder_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous devez spécifier exactement un document ou un dossier à partager.",
        )

    role = req.role.upper().strip()
    if role not in ALLOWED_SHARE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rôle de partage invalide '{req.role}'. Rôles autorisés : VIEWER, EDITOR, GUEST.",
        )

    target_name = "Ressource"
    resource_id: Optional[uuid.UUID] = None
    if req.document_id:
        doc_res = await db.execute(
            select(Document).where(
                Document.id == req.document_id,
                Document.tenant_id == context.tenant_id,
                Document.is_trashed == False,
            )
        )
        doc = doc_res.scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document introuvable dans cet espace documentaire.",
            )
        target_name = doc.original_name
        resource_id = doc.id
    elif req.folder_id:
        folder_res = await db.execute(
            select(Folder).where(
                Folder.id == req.folder_id,
                Folder.tenant_id == context.tenant_id,
                Folder.is_trashed == False,
            )
        )
        folder = folder_res.scalar_one_or_none()
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dossier introuvable dans cet espace documentaire.",
            )
        target_name = folder.name
        resource_id = folder.id

    normalized_email = req.recipient_email.strip().lower()
    recip_res = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
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
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    recipient = ShareRecipient(
        id=recipient_id,
        share_id=share_id,
        recipient_user_id=recipient_user.id if recipient_user else None,
        recipient_email=normalized_email,
        role=role,
        created_at=now,
    )

    client_ip, user_agent = _extract_client_meta(request)
    audit_entry = _build_audit_log(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        user_email=context.user.email,
        action="SHARE_INTERNAL_CREATE",
        resource_type="DOCUMENT" if req.document_id else "FOLDER",
        resource_id=resource_id,
        resource_name=target_name,
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Partage interne créé avec {normalized_email} (rôle: {role})",
    )

    db.add(new_share)
    db.add(recipient)
    db.add(audit_entry)
    await _commit_or_fail(db, "Création du partage interne")

    return ShareRead(
        id=share_id,
        tenant_id=context.tenant_id,
        document_id=req.document_id,
        folder_id=req.folder_id,
        created_by=context.user_id,
        target_name=target_name,
        share_type="INTERNAL_USER",
        role=role,
        has_password=False,
        is_active=True,
        recipients=[
            ShareRecipientRead(
                id=recipient_id,
                recipient_email=normalized_email,
                recipient_user_id=recipient_user.id if recipient_user else None,
                role=role,
                created_at=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )


@router.post("/link", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def create_secure_link(
    req: SecureLinkCreate,
    request: Request,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_SHARE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Génère un lien de partage public sécurisé persisté dans PostgreSQL :
    - Jeton cryptographique à haute entropie (>= 256 bits)
    - Stockage exclusif de l'empreinte SHA-256 du jeton en base (jamais le jeton brut)
    - Hachage Argon2id / PBKDF2 du mot de passe éventuel
    - Expiration et quota limite de téléchargements
    """
    if bool(req.document_id) == bool(req.folder_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spécifiez exactement un document ou un dossier.",
        )

    role = req.role.upper().strip()
    if role not in ALLOWED_SHARE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rôle de partage invalide '{req.role}'.",
        )

    target_name = "Ressource"
    resource_id: Optional[uuid.UUID] = None
    if req.document_id:
        doc_res = await db.execute(
            select(Document).where(
                Document.id == req.document_id,
                Document.tenant_id == context.tenant_id,
                Document.is_trashed == False,
            )
        )
        doc = doc_res.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable.")
        target_name = doc.original_name
        resource_id = doc.id
    elif req.folder_id:
        folder_res = await db.execute(
            select(Folder).where(
                Folder.id == req.folder_id,
                Folder.tenant_id == context.tenant_id,
                Folder.is_trashed == False,
            )
        )
        folder = folder_res.scalar_one_or_none()
        if not folder:
            raise HTTPException(status_code=404, detail="Dossier introuvable.")
        target_name = folder.name
        resource_id = folder.id

    raw_token = generate_share_token(32)
    token_digest = hash_share_token(raw_token)
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
        role=role,
        token_hash=token_digest,
        password_hash=pwd_hash,
        max_downloads=req.max_downloads,
        download_count=0,
        expires_at=expires_at,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    client_ip, user_agent = _extract_client_meta(request)
    audit_entry = _build_audit_log(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        user_email=context.user.email,
        action="SHARE_LINK_CREATE",
        resource_type="DOCUMENT" if req.document_id else "FOLDER",
        resource_id=resource_id,
        resource_name=target_name,
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Lien sécurisé généré (Mot de passe: {bool(pwd_hash)}, Max DL: {req.max_downloads}, Expire: {expires_at})",
    )

    db.add(new_share)
    db.add(audit_entry)
    await _commit_or_fail(db, "Création du lien de partage sécurisé")

    public_url = f"{settings.APP_URL}/s/{raw_token}"

    return ShareRead(
        id=share_id,
        tenant_id=context.tenant_id,
        document_id=req.document_id,
        folder_id=req.folder_id,
        created_by=context.user_id,
        target_name=target_name,
        share_type="SECURE_LINK",
        role=role,
        token=raw_token,
        public_url=public_url,
        has_password=bool(pwd_hash),
        max_downloads=req.max_downloads,
        download_count=0,
        expires_at=expires_at,
        is_active=True,
        is_expired=False,
        recipients=[],
        created_at=now,
        updated_at=now,
    )


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: uuid.UUID,
    request: Request,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_SHARE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Révoque et désactive immédiatement un partage dans PostgreSQL.
    Seul le créateur du partage ou le propriétaire (OWNER) du tenant peut révoquer.
    """
    share_res = await db.execute(
        select(Share)
        .where(
            Share.id == share_id,
            Share.tenant_id == context.tenant_id,
        )
        .with_for_update()
    )
    share = share_res.scalar_one_or_none()

    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partage introuvable ou n'appartenant pas à cet espace documentaire.",
        )

    is_owner = context.role == "OWNER" or context.user.is_superuser
    is_creator = share.created_by == context.user_id
    if not is_owner and not is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits insuffisants : seul le créateur du partage ou le propriétaire de l'espace peut le révoquer.",
        )

    share.is_active = False
    share.updated_at = datetime.now(timezone.utc)

    client_ip, user_agent = _extract_client_meta(request)
    audit_entry = _build_audit_log(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        user_email=context.user.email,
        action="SHARE_REVOKE",
        resource_type="SHARE",
        resource_id=share.id,
        resource_name=str(share.id),
        ip_address=client_ip,
        user_agent=user_agent,
        details="Partage révoqué immédiatement par le propriétaire",
    )
    db.add(audit_entry)
    await _commit_or_fail(db, "Révocation du partage")


# =========================================================================
# 2. RECIPIENT ACCESS ENDPOINTS (Authenticated Internal Shares)
# =========================================================================

@router.get("/received", response_model=List[ShareRead])
async def list_received_shares(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste les partages internes actifs et non expirés reçus par l'utilisateur authentifié.
    """
    await set_user_recipient_context(db, str(current_user.id), current_user.email)
    now = datetime.now(timezone.utc)

    stmt = (
        select(Share)
        .join(ShareRecipient, ShareRecipient.share_id == Share.id)
        .options(selectinload(Share.recipients))
        .where(
            Share.share_type == "INTERNAL_USER",
            Share.is_active == True,
            or_(Share.expires_at == None, Share.expires_at > now),
            or_(
                ShareRecipient.recipient_user_id == current_user.id,
                func.lower(ShareRecipient.recipient_email) == current_user.email.lower(),
            ),
        )
        .order_by(Share.created_at.desc())
    )
    res = await db.execute(stmt)
    shares = res.scalars().unique().all()

    results: List[ShareRead] = []
    for s in shares:
        try:
            target_name, _, _ = await _resolve_share_target(db, s)
            results.append(_share_to_read(s, target_name=target_name, raw_token=None))
        except HTTPException:
            # Skip trashed or deleted target documents
            continue
    return results


@router.get("/received/{share_id}/download", response_model=PublicShareDownloadResponse)
async def download_received_share(
    share_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permet au destinataire autorisé d'un partage interne de télécharger le document partagé.
    Vérifie les droits du destinataire, le statut actif, l'expiration et l'analyse ClamAV.
    """
    await set_user_recipient_context(db, str(current_user.id), current_user.email)
    client_ip, user_agent = _extract_client_meta(request)

    res = await db.execute(
        select(Share)
        .options(selectinload(Share.recipients))
        .where(Share.id == share_id)
    )
    share = res.scalar_one_or_none()

    if not share or share.share_type != "INTERNAL_USER" or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partage interne introuvable ou révoqué.",
        )

    is_recipient = any(
        (r.recipient_user_id == current_user.id)
        or (r.recipient_email.lower() == current_user.email.lower())
        for r in (share.recipients or [])
    )
    if not is_recipient:
        audit_denied = _build_audit_log(
            tenant_id=share.tenant_id,
            user_id=current_user.id,
            user_email=current_user.email,
            action="INTERNAL_SHARE_ACCESS_DENIED",
            resource_type="SHARE",
            resource_id=share.id,
            resource_name=str(share.id),
            ip_address=client_ip,
            user_agent=user_agent,
            details="Tentative d'accès non autorisé à un partage interne par un tiers",
            audit_status="DENIED",
        )
        db.add(audit_denied)
        await _commit_or_fail(db, "Journalisation du refus d'accès au partage")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : vous n'êtes pas destinataire de ce partage.",
        )

    now = datetime.now(timezone.utc)
    expires_at = _ensure_utc(share.expires_at)
    if expires_at and expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ce partage interne a expiré.",
        )

    if not share.document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le téléchargement direct est réservé aux documents partagés.",
        )

    target_name, doc, _ = await _resolve_share_target(db, share)
    assert doc is not None

    if doc.antivirus_status != "CLEAN":
        if doc.antivirus_status == "INFECTED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Téléchargement interdit : ce fichier est infecté et mis en quarantaine.",
            )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Téléchargement bloqué (Fail-Closed) : document non certifié sain ({doc.antivirus_status}).",
        )

    download_url = storage_client.generate_presigned_download_url(
        storage_key=doc.storage_key,
        filename=doc.original_name,
        expires_in=600,
    )

    audit_entry = _build_audit_log(
        tenant_id=share.tenant_id,
        user_id=current_user.id,
        user_email=current_user.email,
        action="INTERNAL_SHARE_DOWNLOAD",
        resource_type="DOCUMENT",
        resource_id=doc.id,
        resource_name=target_name,
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Téléchargement par le destinataire autorisé {current_user.email}",
    )
    db.add(audit_entry)
    await _commit_or_fail(db, "Journalisation du téléchargement interne")

    return PublicShareDownloadResponse(
        download_url=download_url,
        filename=doc.original_name,
        size_bytes=doc.size_bytes,
        mime_type=doc.mime_type,
        download_count=share.download_count or 0,
        max_downloads=share.max_downloads,
    )


# =========================================================================
# 3. PUBLIC ACCESS ENDPOINTS (Token Hash Lookup, PostgreSQL Source of Truth)
# =========================================================================

@router.get("/public/{token}", response_model=PublicShareDetails)
async def get_public_share_info(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Consulte les informations d'un lien public exclusivement depuis PostgreSQL :
    - Recherche par empreinte SHA-256 du jeton (jamais par jeton brut)
    - Vérification du statut actif (révocation immédiate)
    - Contrôle strict de la date d'expiration
    - Contrôle du quota de téléchargements
    - Métadonnées réelles issues de PostgreSQL
    """
    token_digest = hash_share_token(token)
    await set_public_share_context(db, token_digest)

    res = await db.execute(
        select(Share).where(
            Share.token_hash == token_digest,
            Share.share_type == "SECURE_LINK",
        )
    )
    share = res.scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ce lien de partage n'existe pas ou a été révoqué par son propriétaire.",
        )

    now = datetime.now(timezone.utc)
    expires_at = _ensure_utc(share.expires_at)
    if expires_at and expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ce lien de partage a expiré.",
        )

    target_name, doc, _ = await _resolve_share_target(db, share)

    max_dl = share.max_downloads
    dl_count = share.download_count or 0
    can_download = True
    if max_dl is not None and dl_count >= max_dl:
        can_download = False

    is_pwd_required = bool(share.password_hash)

    client_ip, user_agent = _extract_client_meta(request)
    audit_entry = _build_audit_log(
        tenant_id=share.tenant_id,
        user_id=None,
        user_email="public_visitor",
        action="PUBLIC_SHARE_VIEW",
        resource_type="DOCUMENT" if share.document_id else "FOLDER",
        resource_id=share.document_id or share.folder_id,
        resource_name=target_name,
        ip_address=client_ip,
        user_agent=user_agent,
        details="Consultation de la page publique de partage",
    )
    db.add(audit_entry)
    await _commit_or_fail(db, "Journalisation de consultation publique")

    return PublicShareDetails(
        token=token,
        resource_type="DOCUMENT" if share.document_id else "FOLDER",
        resource_name=target_name,
        mime_type=doc.mime_type if doc else "inode/directory",
        extension=doc.extension if doc else "folder",
        size_bytes=doc.size_bytes if doc else 0,
        sha256_hash=doc.sha256_hash if doc else None,
        has_password=is_pwd_required,
        is_password_required=is_pwd_required,
        expires_at=expires_at,
        download_count=dl_count,
        max_downloads=max_dl,
        can_download=can_download,
        is_active=share.is_active,
    )


@router.post("/public/{token}/access", response_model=PublicShareDetails)
async def access_public_share(
    token: str,
    req: PublicShareAccessRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Déverrouille l'accès au lien public avec vérification du mot de passe
    et protection anti brute-force.
    """
    client_ip, user_agent = _extract_client_meta(request)
    token_digest = hash_share_token(token)
    rate_limit_id = f"{client_ip}_{token_digest}"

    if share_rate_limiter.is_rate_limited(rate_limit_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives incorrectes. L'accès à ce lien est temporairement suspendu (15 minutes).",
        )

    await set_public_share_context(db, token_digest)
    res = await db.execute(
        select(Share).where(
            Share.token_hash == token_digest,
            Share.share_type == "SECURE_LINK",
        )
    )
    share = res.scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lien introuvable ou révoqué.",
        )

    now = datetime.now(timezone.utc)
    expires_at = _ensure_utc(share.expires_at)
    if expires_at and expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ce lien de partage a expiré.",
        )

    if share.password_hash:
        if not req.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Ce partage est protégé par mot de passe.",
            )

        is_valid = verify_password(req.password, share.password_hash)
        if not is_valid:
            attempts = share_rate_limiter.record_failed_attempt(rate_limit_id)
            audit_fail = _build_audit_log(
                tenant_id=share.tenant_id,
                user_id=None,
                user_email="public_visitor",
                action="PUBLIC_SHARE_AUTH_FAILED",
                resource_type="SHARE",
                resource_id=share.id,
                resource_name=str(share.id),
                ip_address=client_ip,
                user_agent=user_agent,
                details=f"Mot de passe public erroné (tentative {attempts}/5)",
                audit_status="FAILED",
            )
            db.add(audit_fail)
            await _commit_or_fail(db, "Journalisation de tentative échouée")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Mot de passe incorrect ({attempts}/5 tentatives avant blocage).",
            )

        share_rate_limiter.reset_attempts(rate_limit_id)

    target_name, doc, _ = await _resolve_share_target(db, share)
    max_dl = share.max_downloads
    dl_count = share.download_count or 0
    can_download = True if (max_dl is None or dl_count < max_dl) else False

    audit_unlock = _build_audit_log(
        tenant_id=share.tenant_id,
        user_id=None,
        user_email="public_visitor",
        action="PUBLIC_SHARE_UNLOCK",
        resource_type="DOCUMENT" if share.document_id else "FOLDER",
        resource_id=share.document_id or share.folder_id,
        resource_name=target_name,
        ip_address=client_ip,
        user_agent=user_agent,
        details="Déverrouillage réussi du lien de partage public",
    )
    db.add(audit_unlock)
    await _commit_or_fail(db, "Journalisation du déverrouillage public")

    return PublicShareDetails(
        token=token,
        resource_type="DOCUMENT" if share.document_id else "FOLDER",
        resource_name=target_name,
        mime_type=doc.mime_type if doc else "inode/directory",
        extension=doc.extension if doc else "folder",
        size_bytes=doc.size_bytes if doc else 0,
        sha256_hash=doc.sha256_hash if doc else None,
        has_password=bool(share.password_hash),
        is_password_required=bool(share.password_hash),
        expires_at=expires_at,
        download_count=dl_count,
        max_downloads=max_dl,
        can_download=can_download,
        is_active=share.is_active,
    )


@router.post("/public/{token}/download", response_model=PublicShareDownloadResponse)
async def download_public_share(
    token: str,
    req: PublicShareAccessRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Télécharge le document partagé via PostgreSQL avec verrouillage atomique :
    - Recherche et verrouillage de ligne (SELECT ... FOR UPDATE) par token_hash SHA-256
    - Vérification de révocation, expiration, mot de passe, ClamAV et quota max_downloads
    - Incrémentation atomique de download_count et journalisation AuditLog obligatoires
    """
    client_ip, user_agent = _extract_client_meta(request)
    token_digest = hash_share_token(token)
    rate_limit_id = f"{client_ip}_{token_digest}"

    if share_rate_limiter.is_rate_limited(rate_limit_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Accès temporairement verrouillé suite à de multiples tentatives échouées.",
        )

    await set_public_share_context(db, token_digest)
    res = await db.execute(
        select(Share)
        .where(
            Share.token_hash == token_digest,
            Share.share_type == "SECURE_LINK",
        )
        .with_for_update()
    )
    share = res.scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lien introuvable ou révoqué.",
        )

    now = datetime.now(timezone.utc)
    expires_at = _ensure_utc(share.expires_at)
    if expires_at and expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ce lien de partage a expiré.",
        )

    if share.password_hash:
        if not req.password or not verify_password(req.password, share.password_hash):
            attempts = share_rate_limiter.record_failed_attempt(rate_limit_id)
            audit_fail = _build_audit_log(
                tenant_id=share.tenant_id,
                user_id=None,
                user_email="public_visitor",
                action="PUBLIC_SHARE_AUTH_FAILED",
                resource_type="SHARE",
                resource_id=share.id,
                resource_name=str(share.id),
                ip_address=client_ip,
                user_agent=user_agent,
                details=f"Tentative de téléchargement avec mot de passe invalide ({attempts}/5)",
                audit_status="FAILED",
            )
            db.add(audit_fail)
            await _commit_or_fail(db, "Journalisation d'échec mot de passe")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Mot de passe requis ou incorrect.",
            )
        share_rate_limiter.reset_attempts(rate_limit_id)

    max_dl = share.max_downloads
    current_dl = share.download_count or 0
    if max_dl is not None and current_dl >= max_dl:
        audit_quota = _build_audit_log(
            tenant_id=share.tenant_id,
            user_id=None,
            user_email="public_visitor",
            action="PUBLIC_SHARE_QUOTA_EXCEEDED",
            resource_type="SHARE",
            resource_id=share.id,
            resource_name=str(share.id),
            ip_address=client_ip,
            user_agent=user_agent,
            details=f"Quota de téléchargements atteint ({current_dl}/{max_dl})",
            audit_status="DENIED",
        )
        db.add(audit_quota)
        await _commit_or_fail(db, "Journalisation de dépassement de quota")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Le quota maximal de téléchargements autorisés ({max_dl}) a été atteint pour ce lien.",
        )

    if not share.document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le téléchargement direct n'est disponible que pour un document.",
        )

    target_name, doc, _ = await _resolve_share_target(db, share)
    assert doc is not None

    if doc.antivirus_status != "CLEAN":
        if doc.antivirus_status == "INFECTED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Téléchargement interdit : ce fichier est infecté et placé en quarantaine.",
            )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Téléchargement bloqué (Fail-Closed) : fichier non certifié sain ({doc.antivirus_status}).",
        )

    # Atomic increment in PostgreSQL
    share.download_count = current_dl + 1
    share.updated_at = now

    audit_dl = _build_audit_log(
        tenant_id=share.tenant_id,
        user_id=None,
        user_email="public_downloader",
        action="PUBLIC_SHARE_DOWNLOAD",
        resource_type="DOCUMENT",
        resource_id=doc.id,
        resource_name=target_name,
        ip_address=client_ip,
        user_agent=user_agent,
        details=f"Téléchargement n°{share.download_count} / {max_dl or 'illimité'}",
    )
    db.add(audit_dl)
    await _commit_or_fail(db, "Incrémentation du compteur et audit de téléchargement")

    download_url = storage_client.generate_presigned_download_url(
        storage_key=doc.storage_key,
        filename=doc.original_name,
        expires_in=600,
    )

    return PublicShareDownloadResponse(
        download_url=download_url,
        filename=doc.original_name,
        size_bytes=doc.size_bytes,
        mime_type=doc.mime_type,
        download_count=share.download_count,
        max_downloads=max_dl,
    )
