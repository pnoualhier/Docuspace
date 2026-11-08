from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from backend.app.models.document import Document, Folder
from backend.app.schemas.document import DocumentRead, FolderRead, FolderCreate, FolderUpdate
from backend.app.middleware.tenant_context import get_current_tenant_context, TenantContext

router = APIRouter()

@router.get("/folders", response_model=List[FolderRead], tags=["Dossiers & Documents"])
async def list_folders(
    parent_id: Optional[UUID] = Query(None),
    is_trashed: bool = Query(False),
    ctx: TenantContext = Depends(get_current_tenant_context)
):
    """Lists folders within the active tenant and parent directory."""
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
    ctx: TenantContext = Depends(get_current_tenant_context)
):
    """Creates a new folder within the active tenant."""
    if ctx.role in ("VIEWER", "GUEST"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Droits insuffisants pour créer un dossier")

    # Cycle and existence check
    if payload.parent_id:
        parent_q = await ctx.db.execute(
            select(Folder).where(Folder.id == payload.parent_id, Folder.tenant_id == ctx.tenant.id)
        )
        if not parent_q.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier parent introuvable")

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

@router.get("/documents", response_model=List[DocumentRead], tags=["Dossiers & Documents"])
async def list_documents(
    folder_id: Optional[UUID] = Query(None),
    is_trashed: bool = Query(False),
    is_favorite: Optional[bool] = Query(None),
    ctx: TenantContext = Depends(get_current_tenant_context)
):
    """Lists files within the active tenant, filtered by folder or favorite status."""
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
