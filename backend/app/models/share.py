import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.core.database import Base

class Share(Base):
    __tablename__ = "shares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    share_type = Column(String(32), nullable=False) # INTERNAL_USER or SECURE_LINK
    role = Column(String(32), ForeignKey("roles.name"), default="VIEWER", nullable=False)
    
    # Secure Link specifics
    token_hash = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    max_downloads = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(document_id IS NOT NULL AND folder_id IS NULL) OR (document_id IS NULL AND folder_id IS NOT NULL)",
            name="chk_share_target"
        ),
    )

    recipients = relationship("ShareRecipient", back_populates="share", cascade="all, delete-orphan")

class ShareRecipient(Base):
    __tablename__ = "share_recipients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    share_id = Column(UUID(as_uuid=True), ForeignKey("shares.id", ondelete="CASCADE"), nullable=False)
    recipient_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    recipient_email = Column(String(255), nullable=False)
    role = Column(String(32), ForeignKey("roles.name"), default="VIEWER", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("share_id", "recipient_email", name="uq_share_recipient"),
    )

    share = relationship("Share", back_populates="recipients")
