import uuid
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from backend.app.models.document import Document, Folder, DocumentVersion
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
from backend.app.services.quota_service import quota_service
from backend.app.middleware.tenant_context import (
    get_current_tenant_context, 
    TenantContext, 
    require_permission, 
    Permission
)

router = APIRouter()

# =========================================================================
# 1. DOSSIERS & ARBORESCENCE RÉCURSIVE
# =========================================================================

@router.get("/folders", response_model=List[FolderRead], tags=["Dossiers & Documents"])
async def list_folders(
    parent_id: Optional[UUID] = Query(None),
    is_trashed: bool = Query(False),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """Lists folders within the active tenant and parent directory (enforced by RLS)."""
    stmt = select(Folder).where(
        Folder.tenant_id == ctx.tenant.id,
        Folder.parent_id == parent_id,
        Folder.is_trashed == is_trashed
    ).order_by(Folder.name.asc())
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
    await ctx.db.commit()
    await ctx.db.refresh(folder)
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

    await ctx.db.commit()
    await ctx.db.refresh(folder)
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
    await ctx.db.commit()
    await ctx.db.refresh(folder)
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
    await ctx.db.commit()
    await ctx.db.refresh(copied_folder)
    return copied_folder

@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dossiers & Documents"])
async def delete_folder(
    folder_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.FOLDER_MANAGE))
):
    """Soft-deletes a folder (moves to trash)."""
    folder_q = await ctx.db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.tenant_id == ctx.tenant.id)
    )
    folder = folder_q.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")

    folder.is_trashed = True
    folder.trashed_at = func.now()
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
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """Lists files within the active tenant with RLS enforcement."""
    filters = [
        Document.tenant_id == ctx.tenant.id,
        Document.is_trashed == is_trashed
    ]
    if folder_id is not None:
        filters.append(Document.folder_id == folder_id)
    if is_favorite is not None:
        filters.append(Document.is_favorite == is_favorite)

    stmt = select(Document).where(and_(*filters)).order_by(Document.updated_at.desc())
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

    stmt = select(Document).where(and_(*filters)).order_by(Document.updated_at.desc())
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
        doc.original_name = payload.original_name.strip()
    if payload.is_favorite is not None:
        doc.is_favorite = payload.is_favorite
    if payload.folder_id is not None:
        # Verify folder belongs to same tenant
        folder_check = await ctx.db.execute(
            select(Folder).where(Folder.id == payload.folder_id, Folder.tenant_id == ctx.tenant.id)
        )
        if not folder_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier cible introuvable")
        doc.folder_id = payload.folder_id

    await ctx.db.commit()
    await ctx.db.refresh(doc)
    return doc

@router.post("/documents/{document_id}/copy", response_model=DocumentRead, tags=["Dossiers & Documents"])
async def copy_document(
    document_id: UUID = Path(...),
    payload: DocumentCopyRequest = None,
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE))
):
    """
    Creates a duplicate of a document with a new unique storage key and accounts for quota.
    """
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant.id
    )
    res = await ctx.db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document source introuvable")

    target_folder = payload.target_folder_id if payload else doc.folder_id
    new_name = payload.new_name if (payload and payload.new_name) else f"{doc.original_name} (Copie)"
    new_uuid = uuid.uuid4()
    new_storage_key = f"tenants/{ctx.tenant.id}/{new_uuid}.{doc.extension}"

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
        created_by=ctx.user.id
    )
    ctx.db.add(copied_doc)

    # Update storage usage
    await ctx.db.execute(
        update(StorageUsage)
        .where(StorageUsage.tenant_id == ctx.tenant.id)
        .values(
            used_bytes=StorageUsage.used_bytes + doc.size_bytes,
            document_count=StorageUsage.document_count + 1
        )
    )

    await ctx.db.commit()
    await ctx.db.refresh(copied_doc)
    return copied_doc

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dossiers & Documents"])
async def trash_document(
    document_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Moves document to trash (soft-delete)."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant.id
    )
    res = await ctx.db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")

    doc.is_trashed = True
    doc.trashed_at = func.now()
    await ctx.db.commit()
    return None

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
    """Moves multiple documents to trash simultaneously."""
    stmt = (
        update(Document)
        .where(
            Document.id.in_(payload.document_ids),
            Document.tenant_id == ctx.tenant.id
        )
        .values(is_trashed=True, trashed_at=func.now())
    )
    res = await ctx.db.execute(stmt)
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
    """Permanently purges multiple documents and frees tenant quota."""
    docs_q = await ctx.db.execute(
        select(Document).where(
            Document.id.in_(payload.document_ids),
            Document.tenant_id == ctx.tenant.id
        )
    )
    docs = docs_q.scalars().all()
    freed_bytes = sum(d.size_bytes for d in docs)
    del_count = len(docs)

    for d in docs:
        await ctx.db.delete(d)

    # Reclaim storage
    if freed_bytes > 0:
        await ctx.db.execute(
            update(StorageUsage)
            .where(StorageUsage.tenant_id == ctx.tenant.id)
            .values(
                used_bytes=func.greatest(0, StorageUsage.used_bytes - freed_bytes),
                document_count=func.greatest(0, StorageUsage.document_count - del_count)
            )
        )

    await ctx.db.commit()

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
    - Contrôle du plafond de versions par fichier selon le forfait (Plan.max_versions_per_file)
    - Enregistrement de la nouvelle version avec son empreinte SHA-256
    - Mise à jour atomique des métadonnées du document principal
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

    # Determine max version number
    max_ver_q = await ctx.db.execute(
        select(func.coalesce(func.max(DocumentVersion.version_number), 0))
        .where(DocumentVersion.document_id == id)
    )
    current_max_ver = max_ver_q.scalar() or 0
    next_ver = current_max_ver + 1

    # Check max versions per file limit (default 10)
    max_allowed = 10
    total_versions_q = await ctx.db.execute(
        select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == id)
    )
    total_versions = total_versions_q.scalar() or 0
    if total_versions >= max_allowed:
        # Purge oldest intermediate version to make room
        oldest_ver_q = await ctx.db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == id
            ).order_by(DocumentVersion.version_number.asc()).limit(1)
        )
        oldest = oldest_ver_q.scalar_one_or_none()
        if oldest and oldest.version_number < current_max_ver:
            await ctx.db.delete(oldest)

    storage_key = f"tenants/{ctx.tenant.id}/{doc.id}_v{next_ver}.{doc.extension}"

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

    ctx.db.add(new_version)
    await ctx.db.commit()
    await ctx.db.refresh(new_version)
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
    """Purger une version intermédiaire et récupérer l'espace quota associé."""
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

    # Check total versions remaining
    cnt_q = await ctx.db.execute(
        select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == id)
    )
    total = cnt_q.scalar() or 0
    if total <= 1:
        raise HTTPException(status_code=400, detail="Impossible de supprimer la seule version existante du document.")

    freed = ver.size_bytes
    await ctx.db.delete(ver)

    # Reclaim storage
    await ctx.db.execute(
        update(StorageUsage)
        .where(StorageUsage.tenant_id == ctx.tenant.id)
        .values(used_bytes=func.greatest(0, StorageUsage.used_bytes - freed))
    )
    await ctx.db.commit()

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
    """Vide l'intégralité de la corbeille pour le tenant actif et libère le quota."""
    docs_q = await ctx.db.execute(
        select(Document).where(
            Document.tenant_id == ctx.tenant.id,
            Document.is_trashed == True
        )
    )
    docs = docs_q.scalars().all()
    freed_bytes = sum(d.size_bytes for d in docs)
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
    if freed_bytes > 0:
        await ctx.db.execute(
            update(StorageUsage)
            .where(StorageUsage.tenant_id == ctx.tenant.id)
            .values(
                used_bytes=func.greatest(0, StorageUsage.used_bytes - freed_bytes),
                document_count=func.greatest(0, StorageUsage.document_count - del_docs_count)
            )
        )

    await ctx.db.commit()

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
    """Tâche de purge automatique des éléments en corbeille depuis plus de 30 jours."""
    threshold = datetime.now(timezone.utc) - timedelta(days=30)

    docs_q = await ctx.db.execute(
        select(Document).where(
            Document.tenant_id == ctx.tenant.id,
            Document.is_trashed == True,
            Document.trashed_at <= threshold
        )
    )
    docs = docs_q.scalars().all()
    freed = sum(d.size_bytes for d in docs)
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

    if freed > 0:
        await ctx.db.execute(
            update(StorageUsage)
            .where(StorageUsage.tenant_id == ctx.tenant.id)
            .values(
                used_bytes=func.greatest(0, StorageUsage.used_bytes - freed),
                document_count=func.greatest(0, StorageUsage.document_count - len(docs))
            )
        )

    await ctx.db.commit()

    return TrashPurgeSummary(
        purged_documents_count=len(docs),
        purged_folders_count=len(flds),
        freed_bytes=freed,
        message=f"Purge automatique des 30 jours exécutée : {len(docs)} document(s) et {len(flds)} dossier(s) purgés."
    )

