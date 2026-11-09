from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from backend.app.models.document import Document, Folder
from backend.app.schemas.document import DocumentRead, FolderRead, FolderCreate, FolderUpdate
from backend.app.middleware.tenant_context import (
    get_current_tenant_context, 
    TenantContext, 
    require_permission, 
    Permission
)

router = APIRouter()

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

@router.post("/folders", response_model=FolderRead, status_code=status.HTTP_201_CREATED, tags=["Dossiers & Documents"])
async def create_folder(
    payload: FolderCreate,
    ctx: TenantContext = Depends(require_permission(Permission.FOLDER_CREATE))
):
    """Creates a new folder within the active tenant with cycle and parent verification."""
    # Check parent folder existence & ownership
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
        # Prevent self-parenting
        if new_parent_id == folder_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un dossier ne peut pas être son propre parent.")

        # Verify destination belongs to same tenant
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
    await ctx.db.commit()
    return None

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

@router.get("/documents/{document_id}", response_model=DocumentRead, tags=["Dossiers & Documents"])
async def get_document_by_id(
    document_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """
    Direct document retrieval by ID.
    Enforces strict RLS and tenant barrier.
    Returns 404/403 if requested document belongs to another tenant.
    """
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

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dossiers & Documents"])
async def trash_document(
    document_id: UUID = Path(...),
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_DELETE))
):
    """Moves document to trash (requires DOCUMENT_DELETE permission)."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant.id
    )
    res = await ctx.db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")

    doc.is_trashed = True
    await ctx.db.commit()
    return None
