import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, BigInteger, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    plan_id = Column(String(32), ForeignKey("plans.id"), nullable=False, default="FREE")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("User", back_populates="owned_tenants", foreign_keys=[owner_id])
    plan = relationship("Plan")
    members = relationship("TenantMember", back_populates="tenant", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="tenant", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    storage_usage = relationship("StorageUsage", back_populates="tenant", uselist=False, cascade="all, delete-orphan")

class Role(Base):
    __tablename__ = "roles"

    name = Column(String(32), primary_key=True)
    description = Column(String(255), nullable=True)

class TenantMember(Base):
    __tablename__ = "tenant_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(32), ForeignKey("roles.name"), nullable=False, default="VIEWER")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_user"),
    )

    tenant = relationship("Tenant", back_populates="members")
    user = relationship("User", back_populates="memberships")

class StorageUsage(Base):
    __tablename__ = "storage_usage"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    used_bytes = Column(BigInteger, default=0, nullable=False)
    reserved_bytes = Column(BigInteger, default=0, nullable=False)
    document_count = Column(Integer, default=0, nullable=False)
    last_recalculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="storage_usage")
