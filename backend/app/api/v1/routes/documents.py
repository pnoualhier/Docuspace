import uuid
from typing import List, Optional, Dict, Tuple, Set
from uuid import UUID
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from backend.app.models.document import Document, Folder, DocumentVersion
from backend.app.models.share import Share
from backend.app.models.audit import AuditLog
from backend.app.models.tenant import StorageUsage
from backend.app.schemas.document import (
    DocumentRead, 
    DocumentUpdate,
    DocumentCopyRequest,
    FolderRead, 
    FolderCreate, 
    FolderUpdate,
    FolderCopyRequest,
    FolderTreeItem,
    BulkDocumentMoveRequest,
    BulkDocumentActionRequest,
    BulkOperationResult
)
from backend.app.schemas.version import (
    VersionCreate,
    VersionRead,
    VersionRestoreResponse,
    VersionPurgeResponse,
    TrashItemRead,
    TrashPurgeSummary
)
from backend.app.services.preview_service import preview_service
from backend.app.services.quota_service import (
    quota_service,
    QuotaExceededError,
    FileSizeLimitExceededError,
)
from backend.app.storage.s3_storage import storage_client, StorageBackendError
from backend.app.storage.upload_service import sanitize_filename
from backend.app.middleware.tenant_context import (
    get_current_tenant_context, 
    TenantContext, 
    require_permission, 
    Permission
)

router = APIRouter()


async def _collect_descendant_folder_ids(
    db: AsyncSession,
    tenant_id: UUID,
    root_folder_id: UUID,
) -> List[UUID]:
    """Collects root_folder_id and all descendant subfolder IDs within the tenant."""
    collected: List[UUID] = [root_folder_id]
    frontier: List[UUID] = [root_folder_id]
    seen: Set[UUID] = {root_folder_id}
    while frontier:
        res = await db.execute(
            select(Folder.id).where(
                Folder.tenant_id == tenant_id,
                Folder.parent_id.in_(frontier),
            )
        )
        next_level = [fid for fid in res.scalars().all() if fid not in seen]
        if not next_level:
            break
        seen.update(next_level)
        collected.extend(next_level)
        frontier = next_level
    return collected


async def _deactivate_shares_for_targets(
    db: AsyncSession,
    tenant_id: UUID,
    document_ids: Optional[List[UUID]] = None,
    folder_ids: Optional[List[UUID]] = None,
) -> None:
    """Deactivates active shares pointing to trashed/deleted documents or folders."""
    conditions = []
    if document_ids:
        conditions.append(Share.document_id.in_(document_ids))
    if folder_ids:
        conditions.append(Share.folder_id.in_(folder_ids))
    if not conditions:
        return
    await db.execute(
        update(Share)
        .where(
            Share.tenant_id == tenant_id,
            Share.is_active == True,
            or_(*conditions),
        )
        .values(is_active=False)
    )


async def _collect_storage_keys_and_freed_bytes(
    db: AsyncSession,
    tenant_id: UUID,
    docs: List[Document],
) -> Tuple[List[str], int]:
    """Collects all unique MinIO keys (documents + versions) and exact bytes to reclaim."""
    if not docs:
        return [], 0
    doc_ids = [d.id for d in docs]
    ver_res = await db.execute(
        select(DocumentVersion.storage_key, DocumentVersion.size_bytes).where(
            DocumentVersion.tenant_id == tenant_id,
            DocumentVersion.document_id.in_(doc_ids),
        )
    )
    size_by_key: Dict[str, int] = {}
    for d in docs:
        if d.storage_key:
            size_by_key[d.storage_key] = d.size_bytes
    for storage_key, size_bytes in ver_res.all():
        if storage_key and storage_key not in size_by_key:
            size_by_key[storage_key] = size_bytes
    return list(size_by_key.keys()), sum(size_by_key.values())


def _delete_storage_keys_best_effort(keys: List[str]) -> None:
    for key in keys:
        try:
            storage_client.delete_object(key)
        except Exception:
            pass

# =========================================================================
# 1. DOSSIERS & ARBORESCENCE RÉCURSIVE
# =========================================================================

@router.get("/folders", response_model=List[FolderRead], tags=["Dossiers & Documents"])
async def list_folders(
    parent_id: Optional[UUID] = Query(None),
    is_trashed: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """Lists folders within the active tenant and parent directory (enforced by RLS)."""
    stmt = (
        select(Folder)
        .where(
            Folder.tenant_id == ctx.tenant.id,
            Folder.parent_id == parent_id,
            Folder.is_trashed == is_trashed
        )
        .order_by(Folder.name.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await ctx.db.execute(stmt)
    return result.scalars().all()

@router.get("/folders/tree", response_model=List[FolderTreeItem], tags=["Dossiers & Documents"])
async def get_folder_tree(
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """
    Returns the complete hierarchical recursive folder tree for the active tenant.
    Includes document counts per folder.
    """
    folders_q = await ctx.db.execute(
        select(Folder).where(
            Folder.tenant_id == ctx.tenant.id,
            Folder.is_trashed == False
        ).order_by(Folder.name.asc())
    )
    all_folders = folders_q.scalars().all()

    # Get document count per folder
    count_q = await ctx.db.execute(
        select(Document.folder_id, func.count(Document.id))
        .where(Document.tenant_id == ctx.tenant.id, Document.is_trashed == False)
        .group_by(Document.folder_id)
    )
    doc_counts = {row[0]: row[1] for row in count_q.all()}

    # Build hierarchical tree in memory
    folder_map: Dict[UUID, FolderTreeItem] = {}
    for f in all_folders:
        folder_map[f.id] = FolderTreeItem(
            id=f.id,
            tenant_id=f.tenant_id,
            parent_id=f.parent_id,
            name=f.name,
            color=f.color or "#3B82F6",
            is_favorite=f.is_favorite,
            document_count=doc_counts.get(f.id, 0),
            subfolders=[]
        )

    root_items: List[FolderTreeItem] = []
    for f in all_folders:
        node = folder_map[f.id]
        if f.parent_id and f.parent_id in folder_map:
            folder_map[f.parent_id].subfolders.append(node)
        else:
            root_items.append(node)

    return root_items

@router.post("/folders", response_model=FolderRead, status_code=status.HTTP_201_CREATED, tags=["Dossiers & Documents"])
async def create_folder(
    payload: FolderCreate,
    ctx: TenantContext = Depends(require_permission(Permission.FOLDER_CREATE))
):
    """Creates a new folder within the active tenant with cycle and parent verification."""
    if payload.parent_id:
        parent_q = await ctx.db.execute(
            select(Folder).where(Folder.id == payload.parent_id, Folder.tenant_id == ctx.tenant.id)
        )
        parent = parent_q.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Dossier parent introuvable dans cet espace documentaire (interdiction cross-tenant)."
            )

    folder = Folder(
        tenant_id=ctx.tenant.id,
        parent_id=payload.parent_id,
        name=payload.name.strip(),
        color=payload.color or "#3B82F6",
        created_by=ctx.user.id
    )
    ctx.db.add(folder)
    await ctx.db.flush()
    await ctx.db.refresh(folder)
    await ctx.db.commit()
    return folder

@router.patch("/folders/{folder_id}", response_model=FolderRead, tags=["Dossiers & Documents"])
async def update_folder(
    folder_id: UUID = Path(...),
    payload: FolderUpdate = None,
    ctx: TenantContext = Depends(require_permission(Permission.FOLDER_MANAGE))
):
    """Renames folder, changes color, or toggles favorite status."""
    folder_q = await ctx.db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.tenant_id == ctx.tenant.id)
    )
    folder = folder_q.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")

    if payload.name is not None:
        folder.name = payload.name.strip()
    if payload.color is not None:
        folder.color = payload.color
    if payload.is_favorite is not None:
        folder.is_favorite = payload.is_favorite

    await ctx.db.flush()
    await ctx.db.refresh(folder)
    await ctx.db.commit()
    return folder

@router.patch("/folders/{folder_id}/move", response_model=FolderRead, tags=["Dossiers & Documents"])
async def move_folder(
    folder_id: UUID = Path(...),
    new_parent_id: Optional[UUID] = Query(None),
    ctx: TenantContext = Depends(require_permission(Permission.FOLDER_MANAGE))
):
    """
    Moves a folder to another parent with cycle prevention and cross-tenant barrier.
    """
    folder_q = await ctx.db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.tenant_id == ctx.tenant.id)
    )
    folder = folder_q.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")

    if new_parent_id:
        if new_parent_id == folder_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un dossier ne peut pas être son propre parent.")

        dest_q = await ctx.db.execute(
            select(Folder).where(Folder.id == new_parent_id, Folder.tenant_id == ctx.tenant.id)
        )
        dest = dest_q.scalar_one_or_none()
        if not dest:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Le dossier de destination n'appartient pas au même espace documentaire."
            )

        # Recursive cycle detection
        curr = dest
        while curr and curr.parent_id:
            if curr.parent_id == folder_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Déplacement impossible : création d'un cycle dans l'arborescence."
                )
            parent_check = await ctx.db.execute(
                select(Folder).where(Folder.id == curr.parent_id, Folder.tenant_id == ctx.tenant.id)
            )
            curr = parent_check.scalar_one_or_none()

    folder.parent_id = new_parent_id
    await ctx.db.flush()
    await ctx.db.refresh(folder)
    await ctx.db.commit()
    return folder

@router.post("/folders/{folder_id}/copy", response_model=FolderRead, tags=["Dossiers & Documents"])
async def copy_folder(
    folder_id: UUID = Path(...),
    payload: FolderCopyRequest = None,
    ctx: TenantContext = Depends(require_permission(Permission.FOLDER_CREATE))
):
    """Duplicates a folder and its metadata into a target parent."""
    folder_q = await ctx.db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.tenant_id == ctx.tenant.id)
    )
    folder = folder_q.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier source introuvable")

    target_parent = payload.target_parent_id if payload else folder.parent_id
    new_name = payload.new_name if (payload and payload.new_name) else f"{folder.name} (Copie)"

    copied_folder = Folder(
        tenant_id=ctx.tenant.id,
        parent_id=target_parent,
        name=new_name,
        color=folder.color,
        created_by=ctx.user.id
    )
    ctx.db.add(copied_folder)
    await ctx.db.flush()
    await ctx.db.refresh(copied_folder)
    await ctx.db.commit()
    return copied_folder

@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dossiers & Documents"])
async def delete_folder(
    folder_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.FOLDER_MANAGE))
):
    """Soft-deletes a folder recursively (subfolders + contained documents) and deactivates linked shares."""
    folder_q = await ctx.db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.tenant_id == ctx.tenant.id)
    )
    folder = folder_q.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")

    now = datetime.now(timezone.utc)
    all_folder_ids = await _collect_descendant_folder_ids(ctx.db, ctx.tenant.id, folder_id)

    doc_ids_res = await ctx.db.execute(
        select(Document.id).where(
            Document.tenant_id == ctx.tenant.id,
            Document.folder_id.in_(all_folder_ids),
            Document.is_trashed == False,
        )
    )
    doc_ids = list(doc_ids_res.scalars().all())

    await ctx.db.execute(
        update(Folder)
        .where(Folder.tenant_id == ctx.tenant.id, Folder.id.in_(all_folder_ids))
        .values(is_trashed=True, trashed_at=now)
    )
    if doc_ids:
        await ctx.db.execute(
            update(Document)
            .where(Document.tenant_id == ctx.tenant.id, Document.id.in_(doc_ids))
            .values(is_trashed=True, trashed_at=now)
        )

    await _deactivate_shares_for_targets(
        ctx.db,
        ctx.tenant.id,
        document_ids=doc_ids,
        folder_ids=all_folder_ids,
    )
    ctx.db.add(AuditLog(
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="FOLDER_TRASH",
        resource_type="FOLDER",
        resource_id=folder_id,
        details={"trashed_folders": len(all_folder_ids), "trashed_documents": len(doc_ids)},
    ))
    await ctx.db.commit()
    return None

# =========================================================================
# 2. GESTION DES DOCUMENTS & OPÉRATIONS UNITAIRES
# =========================================================================

@router.get("/documents", response_model=List[DocumentRead], tags=["Dossiers & Documents"])
async def list_documents(
    folder_id: Optional[UUID] = Query(None),
    is_trashed: bool = Query(False),
    is_favorite: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """Lists files within the active tenant with RLS enforcement and pagination."""
    filters = [
        Document.tenant_id == ctx.tenant.id,
        Document.is_trashed == is_trashed
    ]
    if folder_id is not None:
        filters.append(Document.folder_id == folder_id)
    if is_favorite is not None:
        filters.append(Document.is_favorite == is_favorite)

    stmt = (
        select(Document)
        .where(and_(*filters))
        .order_by(Document.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await ctx.db.execute(stmt)
    return result.scalars().all()

@router.get("/documents/search", response_model=List[DocumentRead], tags=["Dossiers & Documents"])
async def search_documents(
    query: Optional[str] = Query(None),
    extension: Optional[str] = Query(None),
    mime_type: Optional[str] = Query(None),
    min_size_bytes: Optional[int] = Query(None),
    max_size_bytes: Optional[int] = Query(None),
    folder_id: Optional[UUID] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """
    Advanced multi-criteria search engine across document metadata, tags, and dates.
    """
    filters = [
        Document.tenant_id == ctx.tenant.id,
        Document.is_trashed == False
    ]
    if query:
        q_like = f"%{query.strip().lower()}%"
        filters.append(or_(
            func.lower(Document.original_name).like(q_like),
            func.lower(Document.extension).like(q_like),
            func.lower(Document.sha256_hash).like(q_like)
        ))
    if extension:
        filters.append(func.lower(Document.extension) == extension.strip().lower())
    if mime_type:
        filters.append(func.lower(Document.mime_type).like(f"%{mime_type.strip().lower()}%"))
    if min_size_bytes is not None:
        filters.append(Document.size_bytes >= min_size_bytes)
    if max_size_bytes is not None:
        filters.append(Document.size_bytes <= max_size_bytes)
    if folder_id is not None:
        filters.append(Document.folder_id == folder_id)
    if is_favorite is not None:
        filters.append(Document.is_favorite == is_favorite)
    if from_date is not None:
        filters.append(Document.updated_at >= from_date)
    if to_date is not None:
        filters.append(Document.updated_at <= to_date)

    stmt = (
        select(Document)
        .where(and_(*filters))
        .order_by(Document.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await ctx.db.execute(stmt)
    return res.scalars().all()

@router.get("/documents/{document_id}", response_model=DocumentRead, tags=["Dossiers & Documents"])
async def get_document_by_id(
    document_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """Direct document retrieval by ID with RLS enforcement."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant.id
    )
    res = await ctx.db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable ou accès non autorisé dans cet espace."
        )
    return doc

@router.patch("/documents/{document_id}", response_model=DocumentRead, tags=["Dossiers & Documents"])
async def update_document(
    document_id: UUID = Path(...),
    payload: DocumentUpdate = None,
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE))
):
    """Renames document, moves to a folder, or toggles favorite status."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant.id
    )
    res = await ctx.db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")

    if payload.original_name is not None:
        doc.original_name = sanitize_filename(payload.original_name)
    if payload.is_favorite is not None:
        doc.is_favorite = payload.is_favorite
    if payload.folder_id is not None:
        # Verify folder belongs to same tenant
        folder_check = await ctx.db.execute(
            select(Folder).where(
                Folder.id == payload.folder_id,
                Folder.tenant_id == ctx.tenant.id,
                Folder.is_trashed == False,
            )
        )
        if not folder_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier cible introuvable")
        doc.folder_id = payload.folder_id

    await ctx.db.flush()
    await ctx.db.refresh(doc)
    await ctx.db.commit()
    return doc

@router.post("/documents/{document_id}/copy", response_model=DocumentRead, tags=["Dossiers & Documents"])
async def copy_document(
    document_id: UUID = Path(...),
    payload: DocumentCopyRequest = None,
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE))
):
    """
    Creates a duplicate of a clean document: validates target folder, checks & reserves quota,
    copies the underlying S3/MinIO object, creates Document + initial DocumentVersion, and commits quota.
    """
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant.id,
        Document.is_trashed == False,
    )
    res = await ctx.db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document source introuvable")

    if doc.antivirus_status != "CLEAN" or doc.status != "READY":
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Impossible de copier un document qui n'est pas certifié sain et prêt."
        )

    target_folder = payload.target_folder_id if (payload and payload.target_folder_id is not None) else doc.folder_id
    if target_folder is not None:
        folder_check = await ctx.db.execute(
            select(Folder).where(
                Folder.id == target_folder,
                Folder.tenant_id == ctx.tenant.id,
                Folder.is_trashed == False,
            )
        )
        if not folder_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier de destination introuvable")

    new_name = sanitize_filename(payload.new_name) if (payload and payload.new_name) else f"{doc.original_name} (Copie)"
    new_uuid = uuid.uuid4()
    new_storage_key = f"tenants/{ctx.tenant.id}/{new_uuid}.{doc.extension}" if doc.extension else f"tenants/{ctx.tenant.id}/{new_uuid}"

    # 1. Check & reserve quota atomically in PostgreSQL
    try:
        await quota_service.check_and_reserve_quota_db(ctx.db, ctx.tenant.id, doc.size_bytes)
    except (QuotaExceededError, FileSizeLimitExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))

    # 2. Copy physical object in S3 / MinIO
    try:
        storage_client.copy_object(doc.storage_key, new_storage_key)
    except FileNotFoundError:
        await quota_service.release_reservation_db(ctx.db, ctx.tenant.id, doc.size_bytes)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet source introuvable sur le stockage S3/MinIO.")
    except StorageBackendError as exc:
        await quota_service.release_reservation_db(ctx.db, ctx.tenant.id, doc.size_bytes)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Erreur copie stockage S3/MinIO : {exc}")

    # 3. Commit quota & persist document + initial version
    await quota_service.commit_quota_db(ctx.db, ctx.tenant.id, doc.size_bytes)

    copied_doc = Document(
        id=new_uuid,
        tenant_id=ctx.tenant.id,
        folder_id=target_folder,
        original_name=new_name,
        storage_key=new_storage_key,
        mime_type=doc.mime_type,
        extension=doc.extension,
        size_bytes=doc.size_bytes,
        sha256_hash=doc.sha256_hash,
        status="READY",
        antivirus_status="CLEAN",
        antivirus_details=doc.antivirus_details,
        created_by=ctx.user.id
    )
    initial_version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=new_uuid,
        tenant_id=ctx.tenant.id,
        version_number=1,
        storage_key=new_storage_key,
        size_bytes=doc.size_bytes,
        mime_type=doc.mime_type,
        sha256_hash=doc.sha256_hash,
        change_summary=f"Copie de {doc.original_name}",
        created_by=ctx.user.id,
    )

    try:
        ctx.db.add(copied_doc)
        ctx.db.add(initial_version)
        ctx.db.add(AuditLog(
            tenant_id=ctx.tenant.id,
            user_id=ctx.user.id,
            action="DOC_COPY",
            resource_type="DOCUMENT",
            resource_id=new_uuid,
            details={"source_document_id": str(doc.id), "size_bytes": doc.size_bytes},
        ))
        await ctx.db.flush()
        await ctx.db.refresh(copied_doc)
        await ctx.db.commit()
    except Exception:
        _delete_storage_keys_best_effort([new_storage_key])
        await quota_service.reclaim_quota_db(ctx.db, ctx.tenant.id, doc.size_bytes)
        await ctx.db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur lors de la copie du document.")
    return copied_doc

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dossiers & Documents"])
async def trash_document(
    document_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Moves document to trash (soft-delete) and deactivates any active shares."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant.id
    )
    res = await ctx.db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")

    doc.is_trashed = True
    doc.trashed_at = datetime.now(timezone.utc)
    await _deactivate_shares_for_targets(ctx.db, ctx.tenant.id, document_ids=[document_id])
    ctx.db.add(AuditLog(
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="DOC_TRASH",
        resource_type="DOCUMENT",
        resource_id=document_id,
        details={"filename": doc.original_name},
    ))
    await ctx.db.commit()
    return None

@router.post("/documents/{document_id}/restore", response_model=DocumentRead, tags=["Dossiers & Documents"])
async def restore_document(
    document_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_RESTORE))
):
    """Restores a single document from trash."""
    res = await ctx.db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == ctx.tenant.id,
            Document.is_trashed == True,
        )
    )
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable dans la corbeille")

    # If parent folder is still trashed, detach to root so restored doc is visible
    if doc.folder_id is not None:
        fld_res = await ctx.db.execute(
            select(Folder.is_trashed).where(Folder.id == doc.folder_id, Folder.tenant_id == ctx.tenant.id)
        )
        fld_trashed = fld_res.scalar_one_or_none()
        if fld_trashed is True or fld_trashed is None:
            doc.folder_id = None

    doc.is_trashed = False
    doc.trashed_at = None
    ctx.db.add(AuditLog(
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="DOC_RESTORE",
        resource_type="DOCUMENT",
        resource_id=document_id,
        details={"filename": doc.original_name},
    ))
    await ctx.db.flush()
    await ctx.db.refresh(doc)
    await ctx.db.commit()
    return doc

@router.delete("/documents/{document_id}/purge", tags=["Dossiers & Documents"])
async def purge_document(
    document_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Permanently deletes a document, all its versions in PostgreSQL & MinIO, and reclaims storage quota."""
    res = await ctx.db.execute(
        select(Document).where(Document.id == document_id, Document.tenant_id == ctx.tenant.id)
    )
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")

    keys_to_delete, freed_bytes = await _collect_storage_keys_and_freed_bytes(ctx.db, ctx.tenant.id, [doc])
    await ctx.db.delete(doc)
    if freed_bytes > 0:
        await ctx.db.execute(
            update(StorageUsage)
            .where(StorageUsage.tenant_id == ctx.tenant.id)
            .values(
                used_bytes=func.greatest(0, StorageUsage.used_bytes - freed_bytes),
                document_count=func.greatest(0, StorageUsage.document_count - 1),
            )
        )
    ctx.db.add(AuditLog(
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="DOC_PURGE",
        resource_type="DOCUMENT",
        resource_id=document_id,
        details={"filename": doc.original_name, "freed_bytes": freed_bytes},
    ))
    await ctx.db.commit()
    _delete_storage_keys_best_effort(keys_to_delete)
    return {
        "purged_document_id": str(document_id),
        "freed_bytes": freed_bytes,
        "message": f"Document détruit définitivement. {freed_bytes} octets libérés.",
    }

# =========================================================================
# 3. OPÉRATIONS GROUPÉES (BULK ACTIONS)
# =========================================================================

@router.post("/documents/bulk/move", response_model=BulkOperationResult, tags=["Opérations Groupées"])
async def bulk_move_documents(
    payload: BulkDocumentMoveRequest,
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE))
):
    """Atomically moves multiple documents to a target folder in the same tenant."""
    if payload.target_folder_id:
        folder_check = await ctx.db.execute(
            select(Folder).where(Folder.id == payload.target_folder_id, Folder.tenant_id == ctx.tenant.id)
        )
        if not folder_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier cible introuvable")

    stmt = (
        update(Document)
        .where(
            Document.id.in_(payload.document_ids),
            Document.tenant_id == ctx.tenant.id
        )
        .values(folder_id=payload.target_folder_id)
    )
    res = await ctx.db.execute(stmt)
    await ctx.db.commit()

    return BulkOperationResult(
        success_count=res.rowcount,
        failed_count=len(payload.document_ids) - res.rowcount,
        message=f"{res.rowcount} document(s) déplacé(s) avec succès.",
        affected_ids=payload.document_ids
    )

@router.post("/documents/bulk/trash", response_model=BulkOperationResult, tags=["Opérations Groupées"])
async def bulk_trash_documents(
    payload: BulkDocumentActionRequest,
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Moves multiple documents to trash simultaneously and deactivates linked shares."""
    stmt = (
        update(Document)
        .where(
            Document.id.in_(payload.document_ids),
            Document.tenant_id == ctx.tenant.id
        )
        .values(is_trashed=True, trashed_at=datetime.now(timezone.utc))
    )
    res = await ctx.db.execute(stmt)
    await _deactivate_shares_for_targets(ctx.db, ctx.tenant.id, document_ids=payload.document_ids)
    await ctx.db.commit()

    return BulkOperationResult(
        success_count=res.rowcount,
        failed_count=len(payload.document_ids) - res.rowcount,
        message=f"{res.rowcount} document(s) placé(s) en corbeille.",
        affected_ids=payload.document_ids
    )

@router.post("/documents/bulk/restore", response_model=BulkOperationResult, tags=["Opérations Groupées"])
async def bulk_restore_documents(
    payload: BulkDocumentActionRequest,
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_RESTORE))
):
    """Restores multiple documents from trash."""
    stmt = (
        update(Document)
        .where(
            Document.id.in_(payload.document_ids),
            Document.tenant_id == ctx.tenant.id
        )
        .values(is_trashed=False, trashed_at=None)
    )
    res = await ctx.db.execute(stmt)
    await ctx.db.commit()

    return BulkOperationResult(
        success_count=res.rowcount,
        failed_count=len(payload.document_ids) - res.rowcount,
        message=f"{res.rowcount} document(s) restauré(s).",
        affected_ids=payload.document_ids
    )

@router.post("/documents/bulk/purge", response_model=BulkOperationResult, tags=["Opérations Groupées"])
async def bulk_purge_documents(
    payload: BulkDocumentActionRequest,
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Permanently purges multiple documents, deletes MinIO objects & versions, and frees tenant quota."""
    docs_q = await ctx.db.execute(
        select(Document).where(
            Document.id.in_(payload.document_ids),
            Document.tenant_id == ctx.tenant.id
        )
    )
    docs = docs_q.scalars().all()
    keys_to_delete, freed_bytes = await _collect_storage_keys_and_freed_bytes(ctx.db, ctx.tenant.id, docs)
    del_count = len(docs)

    for d in docs:
        await ctx.db.delete(d)

    # Reclaim storage
    if freed_bytes > 0 or del_count > 0:
        await ctx.db.execute(
            update(StorageUsage)
            .where(StorageUsage.tenant_id == ctx.tenant.id)
            .values(
                used_bytes=func.greatest(0, StorageUsage.used_bytes - freed_bytes),
                document_count=func.greatest(0, StorageUsage.document_count - del_count)
            )
        )

    await ctx.db.commit()
    _delete_storage_keys_best_effort(keys_to_delete)

    return BulkOperationResult(
        success_count=del_count,
        failed_count=len(payload.document_ids) - del_count,
        message=f"{del_count} document(s) définitivement purgé(s). {freed_bytes} octets libérés.",
        affected_ids=[d.id for d in docs]
    )

# =========================================================================
# 4. GESTION DES VERSIONS & RESTAURATION (PHASE 6)
# =========================================================================

@router.get("/documents/{id}/versions", response_model=List[VersionRead], tags=["Versions & Révisions"])
async def list_document_versions(
    id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """Retourne l'historique complet des versions pour un document donné."""
    doc_q = await ctx.db.execute(
        select(Document).where(
            Document.id == id,
            Document.tenant_id == ctx.tenant.id
        )
    )
    doc = doc_q.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    versions_q = await ctx.db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == id,
            DocumentVersion.tenant_id == ctx.tenant.id
        ).order_by(DocumentVersion.version_number.desc())
    )
    return versions_q.scalars().all()

@router.post("/documents/{id}/versions", response_model=VersionRead, status_code=status.HTTP_201_CREATED, tags=["Versions & Révisions"])
async def create_document_version(
    payload: VersionCreate,
    id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE))
):
    """
    Ajoute une nouvelle révision d'un document existant :
    - Contrôle de taille unitaire et de quota selon le forfait (Plan)
    - Contrôle du plafond de versions par fichier (Plan.max_versions_per_file) avec purge de la plus ancienne
    - Enregistrement de la nouvelle version avec son empreinte SHA-256
    - Mise à jour atomique des métadonnées du document principal et de StorageUsage
    """
    doc_q = await ctx.db.execute(
        select(Document).where(
            Document.id == id,
            Document.tenant_id == ctx.tenant.id,
            Document.is_trashed == False
        )
    )
    doc = doc_q.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document actif introuvable.")

    storage_usage, plan = await quota_service.get_or_create_db_usage(ctx.db, ctx.tenant.id)

    if payload.size_bytes > plan.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Cette révision dépasse la taille maximale autorisée par votre forfait ({plan.max_file_size_bytes} octets)."
        )

    # Determine max version number
    max_ver_q = await ctx.db.execute(
        select(func.coalesce(func.max(DocumentVersion.version_number), 0))
        .where(DocumentVersion.document_id == id)
    )
    current_max_ver = max_ver_q.scalar() or 0
    next_ver = current_max_ver + 1

    # Check max versions per file limit dynamically from tenant Plan
    max_allowed = max(1, int(getattr(plan, "max_versions_per_file", 5) or 5))
    total_versions_q = await ctx.db.execute(
        select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == id)
    )
    total_versions = total_versions_q.scalar() or 0

    reclaimed_from_oldest = 0
    evicted_storage_key: Optional[str] = None
    if total_versions >= max_allowed:
        oldest_ver_q = await ctx.db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == id
            ).order_by(DocumentVersion.version_number.asc()).limit(1)
        )
        oldest = oldest_ver_q.scalar_one_or_none()
        if oldest and oldest.version_number < current_max_ver:
            reclaimed_from_oldest = oldest.size_bytes
            if oldest.storage_key != doc.storage_key:
                evicted_storage_key = oldest.storage_key
            await ctx.db.delete(oldest)

    projected_used = storage_usage.used_bytes + storage_usage.reserved_bytes - reclaimed_from_oldest + payload.size_bytes
    if projected_used > plan.max_storage_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Quota de stockage dépassé pour l'ajout de cette nouvelle version."
        )

    storage_key = (
        f"tenants/{ctx.tenant.id}/{doc.id}_v{next_ver}.{doc.extension}"
        if doc.extension else f"tenants/{ctx.tenant.id}/{doc.id}_v{next_ver}"
    )

    new_version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        tenant_id=ctx.tenant.id,
        version_number=next_ver,
        storage_key=storage_key,
        size_bytes=payload.size_bytes,
        mime_type=payload.mime_type,
        sha256_hash=payload.sha256_hash,
        change_summary=payload.change_summary,
        created_by=ctx.user.id
    )

    # Update document master properties
    doc.size_bytes = payload.size_bytes
    doc.sha256_hash = payload.sha256_hash
    doc.mime_type = payload.mime_type
    doc.storage_key = storage_key
    doc.updated_at = datetime.now(timezone.utc)

    storage_usage.used_bytes = max(0, storage_usage.used_bytes - reclaimed_from_oldest + payload.size_bytes)
    storage_usage.updated_at = datetime.now(timezone.utc)

    ctx.db.add(new_version)
    await ctx.db.flush()
    await ctx.db.refresh(new_version)
    await ctx.db.commit()

    if evicted_storage_key:
        _delete_storage_keys_best_effort([evicted_storage_key])

    return new_version

@router.post("/documents/{id}/versions/{version_id}/restore", response_model=VersionRestoreResponse, tags=["Versions & Révisions"])
async def restore_document_version(
    id: UUID = Path(...),
    version_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE))
):
    """Restaure un document vers une version antérieure."""
    ver_q = await ctx.db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == id,
            DocumentVersion.tenant_id == ctx.tenant.id
        )
    )
    ver = ver_q.scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="Version demandée introuvable.")

    doc_q = await ctx.db.execute(
        select(Document).where(
            Document.id == id,
            Document.tenant_id == ctx.tenant.id
        )
    )
    doc = doc_q.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    doc.size_bytes = ver.size_bytes
    doc.sha256_hash = ver.sha256_hash
    doc.mime_type = ver.mime_type
    doc.storage_key = ver.storage_key
    doc.updated_at = datetime.now(timezone.utc)

    await ctx.db.commit()

    return VersionRestoreResponse(
        document_id=doc.id,
        restored_version_number=ver.version_number,
        size_bytes=ver.size_bytes,
        sha256_hash=ver.sha256_hash,
        message=f"Document restauré avec succès vers la version {ver.version_number}."
    )

@router.delete("/documents/{id}/versions/{version_id}", response_model=VersionPurgeResponse, tags=["Versions & Révisions"])
async def purge_document_version(
    id: UUID = Path(...),
    version_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Purger une version intermédiaire (PostgreSQL + MinIO) et récupérer l'espace quota associé."""
    ver_q = await ctx.db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == id,
            DocumentVersion.tenant_id == ctx.tenant.id
        )
    )
    ver = ver_q.scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="Version introuvable.")

    doc_q = await ctx.db.execute(
        select(Document).where(Document.id == id, Document.tenant_id == ctx.tenant.id)
    )
    doc = doc_q.scalar_one_or_none()
    if doc and doc.storage_key == ver.storage_key:
        raise HTTPException(
            status_code=400,
            detail="Impossible de purger la version active courante du document ; restaurez d'abord une autre version."
        )

    # Check total versions remaining
    cnt_q = await ctx.db.execute(
        select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == id)
    )
    total = cnt_q.scalar() or 0
    if total <= 1:
        raise HTTPException(status_code=400, detail="Impossible de supprimer la seule version existante du document.")

    freed = ver.size_bytes
    ver_storage_key = ver.storage_key
    await ctx.db.delete(ver)

    # Reclaim storage
    await ctx.db.execute(
        update(StorageUsage)
        .where(StorageUsage.tenant_id == ctx.tenant.id)
        .values(used_bytes=func.greatest(0, StorageUsage.used_bytes - freed))
    )
    await ctx.db.commit()
    if ver_storage_key:
        _delete_storage_keys_best_effort([ver_storage_key])

    return VersionPurgeResponse(
        purged_version_id=version_id,
        freed_bytes=freed,
        remaining_version_count=total - 1,
        message=f"Version supprimée. {freed} octets récupérés sur votre quota."
    )

# =========================================================================
# 5. CORBEILLE AVANCÉE & RÉTENTION 30 JOURS (PHASE 6)
# =========================================================================

@router.get("/trash", response_model=List[TrashItemRead], tags=["Corbeille & Rétention"])
async def list_trash_items(
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """
    Retourne la liste des éléments placés en corbeille avec calcul du compte à rebours de rétention (30 jours).
    """
    now = datetime.now(timezone.utc)
    docs_q = await ctx.db.execute(
        select(Document).where(
            Document.tenant_id == ctx.tenant.id,
            Document.is_trashed == True
        )
    )
    docs = docs_q.scalars().all()

    flds_q = await ctx.db.execute(
        select(Folder).where(
            Folder.tenant_id == ctx.tenant.id,
            Folder.is_trashed == True
        )
    )
    folders = flds_q.scalars().all()

    items: List[TrashItemRead] = []

    for d in docs:
        trashed_at = d.trashed_at or now
        diff_days = (now - trashed_at).days
        days_left = max(0, 30 - diff_days)
        items.append(TrashItemRead(
            id=d.id,
            item_type="DOCUMENT",
            name=d.original_name,
            size_bytes=d.size_bytes,
            trashed_at=trashed_at,
            days_remaining=days_left,
            can_restore=True
        ))

    for f in folders:
        trashed_at = f.trashed_at or now
        diff_days = (now - trashed_at).days
        days_left = max(0, 30 - diff_days)
        items.append(TrashItemRead(
            id=f.id,
            item_type="FOLDER",
            name=f.name,
            size_bytes=None,
            trashed_at=trashed_at,
            days_remaining=days_left,
            can_restore=True
        ))

    return items

@router.post("/trash/empty", response_model=TrashPurgeSummary, tags=["Corbeille & Rétention"])
async def empty_trash(
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Vide l'intégralité de la corbeille pour le tenant actif (PostgreSQL + MinIO) et libère le quota."""
    docs_q = await ctx.db.execute(
        select(Document).where(
            Document.tenant_id == ctx.tenant.id,
            Document.is_trashed == True
        )
    )
    docs = docs_q.scalars().all()
    keys_to_delete, freed_bytes = await _collect_storage_keys_and_freed_bytes(ctx.db, ctx.tenant.id, docs)
    del_docs_count = len(docs)

    for d in docs:
        await ctx.db.delete(d)

    flds_q = await ctx.db.execute(
        select(Folder).where(
            Folder.tenant_id == ctx.tenant.id,
            Folder.is_trashed == True
        )
    )
    folders = flds_q.scalars().all()
    del_flds_count = len(folders)
    for f in folders:
        await ctx.db.delete(f)

    # Reclaim storage
    if freed_bytes > 0 or del_docs_count > 0:
        await ctx.db.execute(
            update(StorageUsage)
            .where(StorageUsage.tenant_id == ctx.tenant.id)
            .values(
                used_bytes=func.greatest(0, StorageUsage.used_bytes - freed_bytes),
                document_count=func.greatest(0, StorageUsage.document_count - del_docs_count)
            )
        )

    await ctx.db.commit()
    _delete_storage_keys_best_effort(keys_to_delete)

    return TrashPurgeSummary(
        purged_documents_count=del_docs_count,
        purged_folders_count=del_flds_count,
        freed_bytes=freed_bytes,
        message=f"Corbeille vidée : {del_docs_count} fichier(s) et {del_flds_count} dossier(s) détruits. {freed_bytes} octets libérés."
    )

@router.post("/trash/auto-purge", response_model=TrashPurgeSummary, tags=["Corbeille & Rétention"])
async def auto_purge_expired_trash(
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Tâche de purge automatique des éléments en corbeille depuis plus de 30 jours (PostgreSQL + MinIO)."""
    threshold = datetime.now(timezone.utc) - timedelta(days=30)

    docs_q = await ctx.db.execute(
        select(Document).where(
            Document.tenant_id == ctx.tenant.id,
            Document.is_trashed == True,
            Document.trashed_at <= threshold
        )
    )
    docs = docs_q.scalars().all()
    keys_to_delete, freed = await _collect_storage_keys_and_freed_bytes(ctx.db, ctx.tenant.id, docs)
    for d in docs:
        await ctx.db.delete(d)

    flds_q = await ctx.db.execute(
        select(Folder).where(
            Folder.tenant_id == ctx.tenant.id,
            Folder.is_trashed == True,
            Folder.trashed_at <= threshold
        )
    )
    flds = flds_q.scalars().all()
    for f in flds:
        await ctx.db.delete(f)

    if freed > 0 or len(docs) > 0:
        await ctx.db.execute(
            update(StorageUsage)
            .where(StorageUsage.tenant_id == ctx.tenant.id)
            .values(
                used_bytes=func.greatest(0, StorageUsage.used_bytes - freed),
                document_count=func.greatest(0, StorageUsage.document_count - len(docs))
            )
        )

    await ctx.db.commit()
    _delete_storage_keys_best_effort(keys_to_delete)

    return TrashPurgeSummary(
        purged_documents_count=len(docs),
        purged_folders_count=len(flds),
        freed_bytes=freed,
        message=f"Purge automatique des 30 jours exécutée : {len(docs)} document(s) et {len(flds)} dossier(s) purgés."
    )

