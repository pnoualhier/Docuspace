"""0003_upload_sessions_and_quota_hardening

Revision ID: 0003_upload_sessions
Revises: 0002_rbac_rls
Create Date: 2026-11-09 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003_upload_sessions'
down_revision: Union[str, None] = '0002_rbac_rls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create upload_sessions table
    op.create_table(
        'upload_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('folders.id', ondelete='SET NULL'), nullable=True),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('extension', sa.String(length=32), nullable=False),
        sa.Column('mime_type', sa.String(length=128), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('storage_key', sa.String(length=512), unique=True, nullable=False),
        sa.Column('upload_token', sa.String(length=128), unique=True, nullable=False),
        sa.Column('status', sa.String(length=32), server_default='INITIATED', nullable=False),
        sa.Column('antivirus_status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('antivirus_details', sa.Text(), nullable=True),
        sa.Column('sha256_hash', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index('ix_upload_sessions_tenant_id', 'upload_sessions', ['tenant_id'])
    op.create_index('ix_upload_sessions_upload_token', 'upload_sessions', ['upload_token'])
    op.create_index('ix_upload_sessions_status', 'upload_sessions', ['status'])

    # 2. Enable PostgreSQL Row-Level Security on upload_sessions
    op.execute("ALTER TABLE upload_sessions ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY upload_sessions_tenant_isolation ON upload_sessions
            AS RESTRICTIVE
            USING (
                current_setting('app.is_superuser', true) = 'on'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                current_setting('app.is_superuser', true) = 'on'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS upload_sessions_tenant_isolation ON upload_sessions;")
    op.drop_table('upload_sessions')
