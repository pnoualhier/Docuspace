from sqlalchemy import Column, String, BigInteger, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from backend.app.core.database import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(String(32), primary_key=True) # FREE, PERSONAL, PREMIUM
    name = Column(String(64), nullable=False)
    max_storage_bytes = Column(BigInteger, nullable=False)
    max_file_size_bytes = Column(BigInteger, nullable=False)
    max_members = Column(Integer, nullable=False, default=1)
    max_versions_per_file = Column(Integer, nullable=False, default=5)
    features = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
