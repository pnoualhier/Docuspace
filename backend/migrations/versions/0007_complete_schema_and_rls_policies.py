"""0007_complete_schema_and_rls_policies

Revision ID: 0007_complete_schema_rls
Revises: 0006_shares_audit
Create Date: 2026-11-17 08:00:00.000000

Ensures 100% Alembic parity with SQLAlchemy models and fixes PostgreSQL RLS:
1. Seeds canonical RBAC roles (OWNER, EDITOR, VIEWER, GUEST) required by FKs.
2. Creates missing tables: sessions, document_versions (with cross-tenant FK), notifications.
3. Replaces standalone AS RESTRICTIVE policies on tenant tables with proper PERMISSIVE
   policies alongside ENABLE + FORCE ROW LEVEL SECURITY so authenticated tenant queries
   succeed while cross-tenant rows remain strictly blocked.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0007_complete_schema_rls'
down_revision: Union[str, None] = '0006_shares_audit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Seed canonical roles required by tenant_members, role_permissions, shares
    op.execute("""
        INSERT INTO roles (name, description) VALUES
            ('OWNER', 'Propriétaire complet de l''espace documentaire'),
            ('EDITOR', 'Éditeur avec droits de modification et d''import'),
            ('VIEWER', 'Lecteur seul sans droit de modification'),
            ('GUEST', 'Invité avec accès restreint à des fichiers ciblés')
        ON CONFLICT (name) DO NOTHING;
    """)

    # 2. Create sessions table (persisted refresh token sessions)
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=255), nullable=False),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refresh_token_hash'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])

    # 3. Create document_versions table with composite cross-tenant FK to documents
    op.create_table(
        'document_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=128), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('change_summary', sa.String(length=255), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key'),
        sa.UniqueConstraint('document_id', 'version_number', name='uq_doc_version'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(
            ['document_id', 'tenant_id'],
            ['documents.id', 'documents.tenant_id'],
            name='fk_doc_versions_document_same_tenant',
            ondelete='CASCADE',
        ),
    )
    op.create_index('ix_document_versions_document_id', 'document_versions', ['document_id'])
    op.create_index('ix_document_versions_tenant_id', 'document_versions', ['tenant_id'])

    # 4. Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=False, server_default='INFO'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('link', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])

    # 5. Enforce PERMISSIVE tenant isolation + FORCE ROW LEVEL SECURITY on all tenant-scoped tables
    tenant_tables = ['documents', 'folders', 'document_versions', 'storage_usage', 'upload_sessions']
    for tbl in tenant_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_isolation ON {tbl};")
        op.execute(f"""
            CREATE POLICY {tbl}_tenant_isolation ON {tbl}
            FOR ALL
            USING (
                current_setting('app.is_superuser', true) IN ('true', 'on')
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                current_setting('app.is_superuser', true) IN ('true', 'on')
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            );
        """)

    # 6. Break mutual RLS recursion between shares and share_recipients via SECURITY DEFINER helpers
    op.execute("""
        CREATE OR REPLACE FUNCTION public.is_share_recipient(p_share_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.share_recipients sr
                WHERE sr.share_id = p_share_id
                  AND (
                      sr.recipient_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                      OR lower(sr.recipient_email) = lower(NULLIF(current_setting('app.current_user_email', true), ''))
                  )
            );
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.is_share_in_current_tenant(p_share_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.shares s
                WHERE s.id = p_share_id
                  AND s.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            );
        $$;
    """)
    op.execute("DROP POLICY IF EXISTS shares_isolation_policy ON shares;")
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
            OR public.is_share_recipient(shares.id)
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
    op.execute("DROP POLICY IF EXISTS share_recipients_isolation_policy ON share_recipients;")
    op.execute("""
        CREATE POLICY share_recipients_isolation_policy ON share_recipients
        FOR ALL
        USING (
            current_setting('app.is_superuser', true) IN ('true', 'on')
            OR recipient_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            OR lower(recipient_email) = lower(NULLIF(current_setting('app.current_user_email', true), ''))
            OR public.is_share_in_current_tenant(share_recipients.share_id)
        )
        WITH CHECK (
            current_setting('app.is_superuser', true) IN ('true', 'on')
            OR public.is_share_in_current_tenant(share_recipients.share_id)
        );
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.is_share_in_current_tenant(uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.is_share_recipient(uuid);")
    op.execute("DROP POLICY IF EXISTS document_versions_tenant_isolation ON document_versions;")
    op.execute("ALTER TABLE document_versions NO FORCE ROW LEVEL SECURITY;")
    op.drop_table('notifications')
    op.drop_table('document_versions')
    op.drop_table('sessions')
