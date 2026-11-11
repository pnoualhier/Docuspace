import uuid
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.middleware.tenant_context import (
    TenantContext, 
    get_tenant_context, 
    require_permission, 
    Permission
)
from backend.app.storage.s3_storage import storage_client
from backend.app.storage.storage_interface import (
    is_prohibited_extension, 
    is_prohibited_mime_type, 
    PROHIBITED_EXTENSIONS
)
from backend.app.storage.upload_service import (
    stream_and_verify_upload,
    generate_secure_storage_key,
    validate_folder_ownership,
    create_persisted_upload_session,
    get_valid_persisted_upload_session,
    cleanup_expired_sessions
)
from backend.app.security.antivirus import clamav_scanner, ScanResult, quarantine_manager
from backend.app.services.quota_service import (
    quota_service, 
    QuotaExceededError, 
    FileSizeLimitExceededError
)
from backend.app.models.document import Document, DocumentVersion, UploadSession, Folder
from backend.app.models.tenant import StorageUsage
from backend.app.models.plan import Plan
from backend.app.schemas.storage import (
    UploadInitiateRequest,
    UploadInitiateResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
    DownloadUrlResponse,
    QuotaInfoResponse,
    ScanReportResponse
)
from backend.app.schemas.document import DocumentRead

router = APIRouter(tags=["Stockage & Antivirus"])

# In-memory upload session registry for fast test lookup fallback
_ACTIVE_UPLOAD_SESSIONS: Dict[str, Dict[str, Any]] = {}

@router.post("/upload/initiate", response_model=UploadInitiateResponse, status_code=status.HTTP_201_CREATED)
async def initiate_upload(
    req: UploadInitiateRequest,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Initialise une session d'import sécurisée :
    1. Contrôle strict de l'extension et du type MIME (refus des exécutables).
    2. Vérification de l'appartenance du dossier au tenant.
    3. Réservation atomique du quota dans PostgreSQL (SELECT FOR UPDATE).
    4. Clé de stockage cryptographiquement aléatoire et URL pré-signée S3 / MinIO.
    5. Persistance de la session d'upload dans la table upload_sessions.
    """
    # 1. File extension validation
    if is_prohibited_extension(req.original_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format de fichier interdit pour des raisons de sécurité. Les exécutables et scripts ne sont pas autorisés."
        )

    if is_prohibited_mime_type(req.mime_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type MIME interdit : {req.mime_type} est classé comme exécutable binaire non autorisé."
        )

    # 2. Folder ownership validation
    if req.folder_id:
        await validate_folder_ownership(db, req.folder_id, context.tenant.id)

    # 3. Storage Quota validation & atomic reservation in PostgreSQL
    try:
        await quota_service.check_and_reserve_quota_db(
            db=db,
            tenant_id=context.tenant.id,
            file_size_bytes=req.size_bytes
        )
    except FileSizeLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=e.message
        )
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=e.message
        )

    # 4. Generate isolated cryptographically random S3 storage key & pre-signed URL
    storage_key, clean_ext = generate_secure_storage_key(context.tenant.id, req.original_name)
    upload_token = f"upl_tok_{uuid.uuid4().hex}"

    presigned = storage_client.generate_presigned_upload_url(
        storage_key=storage_key,
        content_type=req.mime_type,
        max_size_bytes=req.size_bytes,
        expires_in=1800
    )

    # 5. Persist upload session in PostgreSQL
    session_record = await create_persisted_upload_session(
        db=db,
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        folder_id=req.folder_id,
        original_name=req.original_name,
        extension=clean_ext,
        mime_type=req.mime_type,
        size_bytes=req.size_bytes,
        storage_key=storage_key,
        upload_token=upload_token,
        expires_minutes=30
    )

    # Sync test fallback
    _ACTIVE_UPLOAD_SESSIONS[str(session_record.id)] = {
        "id": session_record.id,
        "tenant_id": context.tenant.id,
        "user_id": context.user.id,
        "folder_id": req.folder_id,
        "original_name": req.original_name,
        "extension": clean_ext,
        "mime_type": req.mime_type,
        "size_bytes": req.size_bytes,
        "storage_key": storage_key,
        "upload_token": upload_token,
        "status": "INITIATED",
        "expires_at": presigned["expires_at"]
    }

    return UploadInitiateResponse(
        session_id=session_record.id,
        upload_url=presigned["upload_url"],
        upload_token=upload_token,
        storage_key=storage_key,
        headers=presigned["headers"],
        expires_at=presigned["expires_at"],
        max_size_bytes=req.size_bytes
    )

@router.post("/upload/direct", response_model=UploadCompleteResponse, status_code=status.HTTP_201_CREATED)
async def direct_upload(
    file: UploadFile = File(...),
    folder_id: Optional[uuid.UUID] = Form(None),
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Import direct en streaming par blocs avec :
    - Pas de lecture intégrale non bornée
    - Calcul de l'empreinte SHA-256 au fil de l'eau
    - Détection MIME réelle par analyse des signatures (magic bytes)
    - Contrôle strict de l'appartenance du dossier au tenant
    - Réservation atomique du quota en base
    - Contrôle antivirus ClamAV temps-réel (politique fail-closed)
    - Stockage MinIO avec clé aléatoire et enregistrement Document + Version
    """
    filename = file.filename or "sans-nom"

    # 1. Folder ownership validation
    if folder_id:
        await validate_folder_ownership(db, folder_id, context.tenant.id)

    # 2. Get active plan limits to constrain the stream
    quota_status = await quota_service.get_quota_status_db(db, context.tenant.id)

    # 3. Stream in chunks, calculate SHA-256 on the fly, inspect magic bytes, enforce real size ceiling
    content, sha256_hash, file_size, real_mime = await stream_and_verify_upload(
        file=file,
        max_allowed_bytes=quota_status.max_storage_bytes
    )

    # 4. Storage Quota check & atomic reservation in PostgreSQL
    try:
        await quota_service.check_and_reserve_quota_db(
            db=db,
            tenant_id=context.tenant.id,
            file_size_bytes=file_size
        )
    except (QuotaExceededError, FileSizeLimitExceededError) as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )

    # 5. Antivirus Scan (Strict Fail-Closed)
    scan_result: ScanResult = clamav_scanner.scan_bytes(content)

    if not scan_result.is_clean:
        # Threat or scan error: release reserved quota in DB immediately
        await quota_service.release_reservation_db(db, context.tenant.id, file_size)
        if scan_result.status == "INFECTED":
            # Isolate in secure quarantine storage
            quarantine_manager.quarantine_file(
                storage_client=storage_client,
                tenant_id=context.tenant.id,
                storage_key="",
                original_name=filename,
                threat_name=scan_result.threat_name or "Menace détectée",
                content=content
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Alerte de sécurité ClamAV : {scan_result.threat_name or 'Menace détectée'}. Fichier placé en quarantaine isolée. {scan_result.details}"
            )
        else: # SCAN_ERROR (ClamAV unavailable, timeout, invalid response)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Échec de l'analyse antivirus (Fail-Closed) : {scan_result.details}. Aucun fichier non analysé ne peut être importé."
            )

    # 6. Store in S3 / MinIO with secure random key
    storage_key, clean_ext = generate_secure_storage_key(context.tenant.id, filename)
    doc_id = uuid.uuid4()
    
    storage_client.put_object(storage_key, content, real_mime)

    # 7. Commit storage quota in PostgreSQL
    await quota_service.commit_quota_db(db, context.tenant.id, file_size)

    # 8. Create Document & Version in Database
    new_doc = Document(
        id=doc_id,
        tenant_id=context.tenant.id,
        folder_id=folder_id,
        original_name=filename,
        storage_key=storage_key,
        mime_type=real_mime,
        extension=clean_ext,
        size_bytes=file_size,
        sha256_hash=sha256_hash,
        status="READY",
        antivirus_status=scan_result.status,
        antivirus_details=scan_result.details,
        is_favorite=False,
        is_trashed=False,
        created_by=context.user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    initial_version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_id,
        tenant_id=context.tenant.id,
        version_number=1,
        storage_key=storage_key,
        size_bytes=file_size,
        mime_type=real_mime,
        sha256_hash=sha256_hash,
        change_summary="Import direct streaming certifié par ClamAV",
        created_by=context.user.id,
        created_at=datetime.now(timezone.utc)
    )

    try:
        db.add(new_doc)
        db.add(initial_version)
        await db.commit()
        await db.refresh(new_doc)
    except Exception:
        # Atomic rollback and object removal
        storage_client.delete_object(storage_key)
        await quota_service.reclaim_quota_db(db, context.tenant.id, file_size)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur transactionnelle lors de la création du document en base."
        )

    return UploadCompleteResponse(
        document=DocumentRead(
            id=new_doc.id,
            tenant_id=new_doc.tenant_id,
            folder_id=new_doc.folder_id,
            original_name=new_doc.original_name,
            mime_type=new_doc.mime_type,
            extension=new_doc.extension,
            size_bytes=new_doc.size_bytes,
            sha256_hash=new_doc.sha256_hash,
            status=new_doc.status,
            antivirus_status=new_doc.antivirus_status,
            is_favorite=new_doc.is_favorite,
            is_trashed=new_doc.is_trashed,
            created_at=new_doc.created_at,
            updated_at=new_doc.updated_at
        ),
        antivirus_status=scan_result.status,
        threat_detected=scan_result.threat_name,
        details=scan_result.details or "Certifié sain par ClamAV"
    )

@router.post("/upload/complete", response_model=UploadCompleteResponse)
async def complete_upload(
    req: UploadCompleteRequest,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db)
):
    """
    Finalise l'importation après téléversement direct vers S3 MinIO :
    - Récupération et verrouillage de la session d'upload dans PostgreSQL
    - Vérification de l'intégrité SHA-256
    - Exécution de l'analyse ClamAV sur l'objet stocké
    - Quarantaine et suppression si infection détectée
    - Création du document et confirmation des quotas
    """
    # 1. Fetch and row-lock persisted UploadSession from PostgreSQL
    session = await get_valid_persisted_upload_session(db, req.session_id, context.tenant.id)
    storage_key = session.storage_key

    # 2. Read object bytes for scanning - fail explicitly if missing, never fabricate content
    try:
        content = storage_client.get_object(storage_key)
    except FileNotFoundError:
        session.status = "FAILED"
        await quota_service.release_reservation_db(db, context.tenant.id, session.size_bytes)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier téléversé introuvable sur le stockage S3/MinIO."
        )

    # 3. Verify SHA-256
    actual_hash = storage_client.compute_sha256(content)
    if req.sha256_hash and req.sha256_hash.lower() != actual_hash.lower():
        storage_client.delete_object(storage_key)
        session.status = "FAILED"
        await quota_service.release_reservation_db(db, context.tenant.id, session.size_bytes)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Échec de validation d'intégrité : l'empreinte SHA-256 calculée ne correspond pas au hachage déclaré."
        )

    # 4. ClamAV Scan (Strict Fail-Closed)
    scan_result: ScanResult = clamav_scanner.scan_bytes(content)
    if not scan_result.is_clean:
        storage_client.delete_object(storage_key)
        await quota_service.release_reservation_db(db, context.tenant.id, session.size_bytes)
        _ACTIVE_UPLOAD_SESSIONS.pop(str(req.session_id), None)

        if scan_result.status == "INFECTED":
            session.status = "INFECTED"
            session.antivirus_status = scan_result.status
            session.antivirus_details = scan_result.details
            await db.commit()
            quarantine_manager.quarantine_file(
                storage_client=storage_client,
                tenant_id=context.tenant.id,
                storage_key=storage_key,
                original_name=session.original_name,
                threat_name=scan_result.threat_name or "Menace détectée",
                content=content
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Fichier rejeté et mis en quarantaine. Menace ClamAV détectée : {scan_result.threat_name}"
            )
        else: # SCAN_ERROR (ClamAV unavailable, timeout, invalid response)
            session.status = "SCAN_ERROR"
            session.antivirus_status = scan_result.status
            session.antivirus_details = scan_result.details
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Échec de l'analyse antivirus (Fail-Closed) : {scan_result.details}. Importation annulée."
            )

    # 5. Commit quota in PostgreSQL and mark session COMPLETED
    await quota_service.commit_quota_db(db, context.tenant.id, session.size_bytes)
    session.status = "COMPLETED"
    session.antivirus_status = scan_result.status
    session.sha256_hash = actual_hash
    session.completed_at = datetime.now(timezone.utc)
    _ACTIVE_UPLOAD_SESSIONS.pop(str(req.session_id), None)

    doc_id = uuid.uuid4()
    new_doc = Document(
        id=doc_id,
        tenant_id=context.tenant.id,
        folder_id=session.folder_id,
        original_name=session.original_name,
        storage_key=storage_key,
        mime_type=session.mime_type,
        extension=session.extension,
        size_bytes=session.size_bytes,
        sha256_hash=actual_hash,
        status="READY",
        antivirus_status=scan_result.status,
        antivirus_details=scan_result.details,
        is_favorite=False,
        is_trashed=False,
        created_by=context.user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    initial_version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_id,
        tenant_id=context.tenant.id,
        version_number=1,
        storage_key=storage_key,
        size_bytes=session.size_bytes,
        mime_type=session.mime_type,
        sha256_hash=actual_hash,
        change_summary="Import validé via session sécurisée",
        created_by=context.user.id,
        created_at=datetime.now(timezone.utc)
    )

    try:
        db.add(new_doc)
        db.add(initial_version)
        await db.commit()
        await db.refresh(new_doc)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création définitive du document en base."
        )

    return UploadCompleteResponse(
        document=DocumentRead(
            id=new_doc.id,
            tenant_id=new_doc.tenant_id,
            folder_id=new_doc.folder_id,
            original_name=new_doc.original_name,
            mime_type=new_doc.mime_type,
            extension=new_doc.extension,
            size_bytes=new_doc.size_bytes,
            sha256_hash=new_doc.sha256_hash,
            status=new_doc.status,
            antivirus_status=new_doc.antivirus_status,
            is_favorite=new_doc.is_favorite,
            is_trashed=new_doc.is_trashed,
            created_at=new_doc.created_at,
            updated_at=new_doc.updated_at
        ),
        antivirus_status=scan_result.status,
        threat_detected=None,
        details="Document stocké sur MinIO S3 et certifié 100% sain par ClamAV."
    )

@router.post("/upload/cleanup", tags=["Stockage & Antivirus"])
async def cleanup_upload_sessions(
    context: TenantContext = Depends(require_permission(Permission.TENANT_SETTINGS)),
    db: AsyncSession = Depends(get_db)
):
    """
    Nettoie les sessions d'upload expirées :
    - Libère le quota réservé orphelin
    - Supprime les objets temporaires S3 non finalisés
    - Met à jour le statut en EXPIRED
    """
    result = await cleanup_expired_sessions(db, storage_client)
    return result

@router.get("/download/{document_id}", response_model=DownloadUrlResponse)
async def get_download_url(
    document_id: uuid.UUID,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    Génère une URL de téléchargement pré-signée S3 / MinIO, éphémère (15 minutes),
    protégée par signature cryptographique HMAC-SHA256 et limitée au tenant actif.
    """
    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == context.tenant_id,
            Document.is_trashed == False
        )
    )
    doc = doc_res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable dans cet espace documentaire."
        )

    # Strict Fail-Closed download barrier:
    # Aucun fichier non analysé ne doit être rendu disponible au téléchargement
    if doc.antivirus_status != "CLEAN":
        if doc.antivirus_status == "INFECTED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Téléchargement strictement interdit : ce fichier est infecté ({doc.antivirus_details or 'Menace détectée'}) et placé en quarantaine."
            )
        else: # SCAN_ERROR, PENDING
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Téléchargement bloqué (Fail-Closed) : le fichier n'a pas été certifié sain par ClamAV (statut antivirus: {doc.antivirus_status})."
            )

    filename = doc.original_name
    storage_key = doc.storage_key

    # Generate 15-minute presigned download URL
    download_url = storage_client.generate_presigned_download_url(
        storage_key=storage_key,
        filename=filename,
        expires_in=900
    )

    return DownloadUrlResponse(
        document_id=document_id,
        filename=filename,
        download_url=download_url,
        expires_in_seconds=900
    )

@router.post("/scan/{document_id}", response_model=ScanReportResponse)
async def trigger_antivirus_scan(
    document_id: uuid.UUID,
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db)
):
    """
    Déclenche une analyse antivirus ClamAV à la demande pour un document existant.
    Si une menace est détectée, le fichier est immédiatement isolé en quarantaine.
    """
    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == context.tenant_id
        )
    )
    doc = doc_res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable dans cet espace documentaire."
        )

    storage_key = doc.storage_key
    try:
        content = storage_client.get_object(storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier introuvable sur le stockage."
        )

    scan_result = clamav_scanner.scan_bytes(content)

    doc.antivirus_status = scan_result.status
    doc.antivirus_details = scan_result.details

    if scan_result.status == "INFECTED":
        doc.status = "QUARANTINED"
        quarantine_manager.quarantine_file(
            storage_client=storage_client,
            tenant_id=context.tenant_id,
            storage_key=storage_key,
            original_name=doc.original_name,
            threat_name=scan_result.threat_name or "Menace détectée",
            content=content
        )

    try:
        await db.commit()
    except Exception:
        await db.rollback()

    return ScanReportResponse(
        document_id=document_id,
        status=scan_result.status,
        is_clean=scan_result.is_clean,
        threat_name=scan_result.threat_name,
        details=scan_result.details,
        engine=scan_result.engine
    )

@router.get("/quarantine", tags=["Stockage & Antivirus"])
async def list_quarantine_records(
    context: TenantContext = Depends(require_permission(Permission.DOCUMENT_READ))
):
    """
    Liste les fichiers placés en quarantaine isolée pour cet espace documentaire.
    """
    return quarantine_manager.list_quarantined_files(context.tenant_id)

@router.get("/quota", response_model=QuotaInfoResponse)
async def get_tenant_quota(
    context: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne la consommation et les limites d'espace de stockage pour l'espace actif,
    directement calculées et extraites de PostgreSQL.
    """
    quota_status = await quota_service.get_quota_status_db(db, context.tenant.id)

    return QuotaInfoResponse(
        tenant_id=context.tenant_id,
        max_storage_bytes=quota_status.max_storage_bytes,
        used_bytes=quota_status.used_bytes,
        reserved_bytes=quota_status.reserved_bytes,
        available_bytes=quota_status.available_bytes,
        document_count=quota_status.document_count,
        usage_percent=quota_status.usage_percent
    )

@router.post("/reconcile", tags=["Stockage & Antivirus"])
async def reconcile_storage(
    context: TenantContext = Depends(require_permission(Permission.TENANT_SETTINGS)),
    db: AsyncSession = Depends(get_db)
):
    """
    Exécute la tâche de réconciliation entre les métadonnées PostgreSQL et les objets réels stockés sur MinIO :
    - Recalcul exact de used_bytes et document_count depuis les documents actifs
    - Détection des objets manquants ou orphelins
    - Libération des réservations non finalisées
    - Synchronisation atomique dans PostgreSQL
    """
    report = await quota_service.reconcile_tenant_storage(
        db=db,
        tenant_id=context.tenant.id,
        storage_client=storage_client
    )
    return report
