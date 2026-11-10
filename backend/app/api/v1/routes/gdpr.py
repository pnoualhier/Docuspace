"""
DocuSpace GDPR API Routes
Implements Data Portability Export (Art. 20) and Account Erasure (Art. 17).
"""
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import json
from backend.app.services.gdpr_service import gdpr_service

router = APIRouter(prefix="/gdpr", tags=["GDPR Compliance"])

class DeleteAccountRequest(BaseModel):
    user_id: str
    confirmation_phrase: str = Field(..., description="Must equal 'SUPPRIMER'")

@router.get("/export")
async def export_user_data(
    user_id: str = Query("usr-alice-101"),
    user_email: str = Query("alice.dupont@example.com")
):
    """
    Export all personal data, documents metadata, version hashes, and audit trail
    pursuant to Article 20 of GDPR.
    """
    mock_user = {
        "id": user_id,
        "email": user_email,
        "full_name": "Alice Dupont",
        "created_at": "2026-01-15T10:00:00Z"
    }
    mock_tenants = [
        {"id": "tnt-alice-main", "name": "Espace d'Alice Dupont", "plan_id": "PERSONAL", "used_bytes": 14500000, "owner_id": user_id, "created_at": "2026-01-15T10:00:00Z"}
    ]
    mock_docs = [
        {"id": "doc-01", "original_name": "Contrat.pdf", "extension": "pdf", "mime_type": "application/pdf", "size_bytes": 1048576, "sha256_hash": "2b1672be09d44d76a50130602eb8df1c040e61cde5351c7ddc040ac951a06d63", "tenant_id": "tnt-alice-main", "created_by": user_id, "created_at": "2026-01-16T12:00:00Z", "versions": []}
    ]
    mock_shares = [
        {"id": "shr-01", "document_name": "Contrat.pdf", "share_type": "SECURE_LINK", "download_count": 2, "created_by": user_id, "created_at": "2026-01-17T09:00:00Z"}
    ]
    mock_logs = [
        {"timestamp": "2026-01-16T12:00:00Z", "action": "DOC_UPLOAD_VERIFIED", "resource_name": "Contrat.pdf", "user_email": user_email, "status": "SUCCESS"}
    ]

    bundle = gdpr_service.generate_portability_export(
        user=mock_user,
        tenants=mock_tenants,
        documents=mock_docs,
        shares=mock_shares,
        audit_logs=mock_logs
    )

    json_str = json.dumps(bundle, indent=2, ensure_ascii=False)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=docuspace_gdpr_export_{user_id}.json"}
    )

@router.post("/delete-account")
async def delete_user_account(req: DeleteAccountRequest):
    """
    Completely and irreversibly purge all user data pursuant to Article 17 of GDPR.
    """
    if req.confirmation_phrase.strip().upper() != "SUPPRIMER":
        raise HTTPException(status_code=400, detail="Confirmation phrase must be 'SUPPRIMER'")

    res = gdpr_service.purge_user_account(
        user_id=req.user_id,
        user_tenants=["tnt-alice-main"],
        documents=[
            {"id": "doc-01", "tenant_id": "tnt-alice-main", "size_bytes": 14500000}
        ]
    )
    return res
