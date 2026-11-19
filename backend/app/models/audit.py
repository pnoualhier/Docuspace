import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, BigInteger, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from backend.app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(64), nullable=False)  # e.g. AUTH_LOGIN, DOC_UPLOAD, DOC_DOWNLOAD, SHARE_CREATED
    resource_type = Column(String(64), nullable=False)  # e.g. DOCUMENT, FOLDER, SHARE, USER, TENANT
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(32), default="STORAGE", nullable=False)
    level = Column(String(32), default="INFO", nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(64), default="INFO", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    link = Column(String(512), nullable=True)
    action_url = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class QuarantineEvent(Base):
    __tablename__ = "quarantine_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    original_name = Column(String(255), nullable=False)
    threat_name = Column(String(255), nullable=False)
    quarantine_key = Column(String(512), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    status = Column(String(32), default="QUARANTINED", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
