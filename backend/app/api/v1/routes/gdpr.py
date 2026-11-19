"""
DocuSpace GDPR API Routes
Implements authenticated Data Portability Export (Art. 20) and Account Erasure (Art. 17)
backed by PostgreSQL and MinIO S3 storage.
"""
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db, set_tenant_context
from backend.app.middleware.tenant_context import get_current_user
from backend.app.models.audit import AuditLog, QuarantineEvent
from backend.app.models.document import Document, DocumentVersion
from backend.app.models.share import Share
from backend.app.models.tenant import StorageUsage, Tenant
from backend.app.models.user import Session, User
from backend.app.services.gdpr_service import gdpr_service
from backend.app.storage.s3_storage import storage_client

router = APIRouter(prefix="/gdpr", tags=["GDPR Compliance"])


class DeleteAccountRequest(BaseModel):
    user_id: Optional[str] = None
    confirmation_phrase: str = Field(..., description="Must equal 'SUPPRIMER'")


@router.get("/export")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all personal data, owned spaces, documents metadata, version hashes, shares,
    and audit trail for the authenticated user pursuant to Article 20 of GDPR.
    """
    await set_tenant_context(db, "", is_superuser=True)

    tenants = (
        await db.execute(select(Tenant).where(Tenant.owner_id == current_user.id))
    ).scalars().all()
    tenant_ids = [t.id for t in tenants]

    usage_map: Dict[UUID, int] = {}
    if tenant_ids:
        usage_rows = (
            await db.execute(select(StorageUsage).where(StorageUsage.tenant_id.in_(tenant_ids)))
        ).scalars().all()
        usage_map = {u.tenant_id: u.used_bytes for u in usage_rows}

    docs: List[Document] = []
    versions_by_doc: Dict[UUID, List[DocumentVersion]] = {}
    shares: List[Share] = []
    if tenant_ids:
        docs = list(
            (await db.execute(select(Document).where(Document.tenant_id.in_(tenant_ids)))).scalars().all()
        )
        doc_ids = [d.id for d in docs]
        if doc_ids:
            ver_rows = (
                await db.execute(select(DocumentVersion).where(DocumentVersion.document_id.in_(doc_ids)))
            ).scalars().all()
            for v in ver_rows:
                versions_by_doc.setdefault(v.document_id, []).append(v)
        shares = list(
            (await db.execute(select(Share).where(Share.tenant_id.in_(tenant_ids)))).scalars().all()
        )

    logs = (
        await db.execute(
            select(AuditLog).where(AuditLog.user_id == current_user.id).order_by(AuditLog.created_at.desc())
        )
    ).scalars().all()

    user_dict = {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "is_verified": current_user.is_verified,
        "is_active": current_user.is_active,
    }
    tenants_data = [
        {
            "id": str(t.id),
            "name": t.name,
            "plan_id": t.plan_id,
            "used_bytes": usage_map.get(t.id, 0),
            "owner_id": str(t.owner_id),
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tenants
    ]
    docs_data = [
        {
            "id": str(d.id),
            "original_name": d.original_name,
            "extension": d.extension,
            "mime_type": d.mime_type,
            "size_bytes": d.size_bytes,
            "sha256_hash": d.sha256_hash,
            "antivirus_status": d.antivirus_status,
            "tenant_id": str(d.tenant_id),
            "created_by": str(d.created_by),
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            "versions": [
                {
                    "version_number": v.version_number,
                    "size_bytes": v.size_bytes,
                    "sha256_hash": v.sha256_hash,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions_by_doc.get(d.id, [])
            ],
        }
        for d in docs
    ]
    shares_data = [
        {
            "id": str(s.id),
            "document_name": str(s.document_id or s.folder_id or ""),
            "share_type": s.share_type,
            "download_count": s.download_count,
            "created_by": str(s.created_by),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in shares
    ]
    logs_data = [
        {
            "timestamp": l.created_at.isoformat() if l.created_at else None,
            "action": l.action,
            "resource_name": l.resource_type,
            "user_id": str(l.user_id) if l.user_id else None,
            "user_email": current_user.email,
            "status": "SUCCESS",
        }
        for l in logs
    ]

    bundle = gdpr_service.generate_portability_export(
        user=user_dict,
        tenants=tenants_data,
        documents=docs_data,
        shares=shares_data,
        audit_logs=logs_data,
    )

    db.add(AuditLog(
        user_id=current_user.id,
        action="GDPR_DATA_EXPORT",
        resource_type="USER",
        resource_id=current_user.id,
        details={"tenants_exported": len(tenants_data), "documents_exported": len(docs_data)},
    ))
    await db.commit()

    json_str = json.dumps(bundle, indent=2, ensure_ascii=False)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=docuspace_gdpr_export_{current_user.id}.json"},
    )


@router.post("/delete-account")
async def delete_user_account(
    req: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Completely and irreversibly purge authenticated user's owned data in PostgreSQL and MinIO S3
    pursuant to Article 17 of GDPR.
    """
    if req.user_id and req.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Interdit : vous ne pouvez supprimer que votre propre compte.",
        )

    if req.confirmation_phrase.strip().upper() != "SUPPRIMER":
        raise HTTPException(status_code=400, detail="Confirmation phrase must be 'SUPPRIMER'")

    await set_tenant_context(db, "", is_superuser=True)

    owned_tenants = (
        await db.execute(select(Tenant).where(Tenant.owner_id == current_user.id))
    ).scalars().all()
    tenant_ids = [t.id for t in owned_tenants]

    docs_summary: List[Dict[str, Any]] = []
    storage_keys: List[str] = []

    if tenant_ids:
        docs = (
            await db.execute(select(Document).where(Document.tenant_id.in_(tenant_ids)))
        ).scalars().all()
        for d in docs:
            docs_summary.append({
                "id": str(d.id),
                "tenant_id": str(d.tenant_id),
                "size_bytes": d.size_bytes,
                "created_by": str(d.created_by),
            })
            if d.storage_key:
                storage_keys.append(d.storage_key)

        vers = (
            await db.execute(select(DocumentVersion).where(DocumentVersion.tenant_id.in_(tenant_ids)))
        ).scalars().all()
        for v in vers:
            if v.storage_key and v.storage_key not in storage_keys:
                storage_keys.append(v.storage_key)

        q_events = (
            await db.execute(select(QuarantineEvent).where(QuarantineEvent.tenant_id.in_(tenant_ids)))
        ).scalars().all()
        for q in q_events:
            if q.quarantine_key and q.quarantine_key not in storage_keys:
                storage_keys.append(q.quarantine_key)

    res = gdpr_service.purge_user_account(
        user_id=str(current_user.id),
        user_tenants=[str(tid) for tid in tenant_ids],
        documents=docs_summary,
    )

    # Purge owned tenants (cascades folders, documents, versions, shares, storage_usage, notifications)
    for t in owned_tenants:
        await db.delete(t)

    # Revoke active sessions and delete user record
    await db.execute(delete(Session).where(Session.user_id == current_user.id))
    await db.delete(current_user)
    await db.commit()

    for key in storage_keys:
        try:
            storage_client.delete_object(key)
        except Exception:
            pass

    return res
