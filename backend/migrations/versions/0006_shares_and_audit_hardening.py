"""0006_shares_and_audit_hardening

Revision ID: 0006_shares_audit
Revises: 0005_seed_plans
Create Date: 2026-11-17 06:00:00.000000

Creates and secures sharing & audit tables in PostgreSQL:
1. shares (with composite cross-tenant FKs to documents & folders, SHA-256 token_hash, role checks)
2. share_recipients (linked with CASCADE, unique email per share)
3. audit_logs (immutable security and share audit trail)
4. FORCE ROW LEVEL SECURITY + strict isolation policies on shares and share_recipients
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0006_shares_audit'
down_revision: Union[str, None] = '0005_seed_plans'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create shares table
    op.create_table(
        'shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('share_type', sa.String(length=32), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='VIEWER'),
        sa.Column('token_hash', sa.String(length=255), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('max_downloads', sa.Integer(), nullable=True),
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['role'], ['roles.name']),
        sa.ForeignKeyConstraint(
            ['document_id', 'tenant_id'],
            ['documents.id', 'documents.tenant_id'],
            name='fk_shares_document_same_tenant',
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['folder_id', 'tenant_id'],
            ['folders.id', 'folders.tenant_id'],
            name='fk_shares_folder_same_tenant',
            ondelete='CASCADE'
        ),
        sa.CheckConstraint(
            "(document_id IS NOT NULL AND folder_id IS NULL) OR (document_id IS NULL AND folder_id IS NOT NULL)",
            name='chk_share_target'
        ),
        sa.CheckConstraint(
            "share_type IN ('INTERNAL_USER', 'SECURE_LINK')",
            name='chk_share_type'
        ),
        sa.CheckConstraint(
            "role IN ('VIEWER', 'EDITOR', 'GUEST')",
            name='chk_share_role'
        ),
    )
    op.create_index('ix_shares_tenant_id', 'shares', ['tenant_id'])
    op.create_index('ix_shares_token_hash', 'shares', ['token_hash'])

    # 2. Create share_recipients table
    op.create_table(
        'share_recipients',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('share_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recipient_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='VIEWER'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['share_id'], ['shares.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role'], ['roles.name']),
        sa.UniqueConstraint('share_id', 'recipient_email', name='uq_share_recipient'),
        sa.CheckConstraint(
            "role IN ('VIEWER', 'EDITOR', 'GUEST')",
            name='chk_share_recipient_role'
        ),
    )
    op.create_index('ix_share_recipients_user_id', 'share_recipients', ['recipient_user_id'])
    op.create_index('ix_share_recipients_email', 'share_recipients', ['recipient_email'])

    # 3. Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.String(length=64), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])

    # 4. Enable & Force Row-Level Security on shares & share_recipients
    op.execute("ALTER TABLE shares ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE shares FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY shares_isolation_policy ON shares
        FOR ALL
        USING (
            current_setting('app.is_superuser', true) IN ('true', 'on')
            OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            OR (
                share_type = 'SECURE_LINK'
                AND token_hash = NULLIF(current_setting('app.public_share_token_hash', true), '')
            )
            OR EXISTS (
                SELECT 1 FROM share_recipients sr
                WHERE sr.share_id = shares.id
                  AND (
                      sr.recipient_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                      OR lower(sr.recipient_email) = lower(NULLIF(current_setting('app.current_user_email', true), ''))
                  )
            )
        )
        WITH CHECK (
            current_setting('app.is_superuser', true) IN ('true', 'on')
            OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            OR (
                share_type = 'SECURE_LINK'
                AND token_hash = NULLIF(current_setting('app.public_share_token_hash', true), '')
            )
        );
    """)

    op.execute("ALTER TABLE share_recipients ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE share_recipients FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY share_recipients_isolation_policy ON share_recipients
        FOR ALL
        USING (
            current_setting('app.is_superuser', true) IN ('true', 'on')
            OR recipient_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            OR lower(recipient_email) = lower(NULLIF(current_setting('app.current_user_email', true), ''))
            OR EXISTS (
                SELECT 1 FROM shares s
                WHERE s.id = share_recipients.share_id
                  AND s.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
        )
        WITH CHECK (
            current_setting('app.is_superuser', true) IN ('true', 'on')
            OR EXISTS (
                SELECT 1 FROM shares s
                WHERE s.id = share_recipients.share_id
                  AND s.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
        );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS share_recipients_isolation_policy ON share_recipients;")
    op.execute("ALTER TABLE share_recipients NO FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS shares_isolation_policy ON shares;")
    op.execute("ALTER TABLE shares NO FORCE ROW LEVEL SECURITY;")

    op.drop_table('audit_logs')
    op.drop_table('share_recipients')
    op.drop_table('shares')
