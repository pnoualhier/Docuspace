import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, BigInteger, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.core.database import Base

class Folder(Base):
    __tablename__ = "folders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    color = Column(String(32), default="#3B82F6")
    is_favorite = Column(Boolean, default=False, nullable=False)
    is_trashed = Column(Boolean, default=False, nullable=False)
    trashed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="folders")
    parent = relationship("Folder", remote_side=[id], backref="subfolders")
    documents = relationship("Document", back_populates="folder")

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True)
    original_name = Column(String(255), nullable=False)
    storage_key = Column(String(512), unique=True, nullable=False)
    mime_type = Column(String(128), nullable=False)
    extension = Column(String(32), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    
    # Status: INITIATED, UPLOADING, PENDING_SCAN, READY, REJECTED, FAILED, EXPIRED
    status = Column(String(32), default="READY", nullable=False)
    # Antivirus: PENDING, CLEAN, INFECTED, SCAN_ERROR
    antivirus_status = Column(String(32), default="CLEAN", nullable=False)
    antivirus_details = Column(Text, nullable=True)
    
    is_favorite = Column(Boolean, default=False, nullable=False)
    is_trashed = Column(Boolean, default=False, nullable=False)
    trashed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="documents")
    folder = relationship("Folder", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentVersion.version_number)")

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    storage_key = Column(String(512), unique=True, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(128), nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    change_summary = Column(String(255), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )

    document = relationship("Document", back_populates="versions")
