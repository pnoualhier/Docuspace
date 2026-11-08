"""0001_initial_schema_and_rls

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-08 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # 2. Plans
    op.create_table(
        'plans',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('max_storage_bytes', sa.BigInteger(), nullable=False),
        sa.Column('max_file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('max_members', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('max_versions_per_file', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Users & Sessions
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verification_token', sa.String(length=255), nullable=True),
        sa.Column('verification_token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reset_password_token', sa.String(length=255), nullable=True),
        sa.Column('reset_password_token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    # 4. Tenants
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', sa.String(length=32), nullable=False, server_default='FREE'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # 5. Roles & Members
    op.create_table(
        'roles',
        sa.Column('name', sa.String(length=32), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('name')
    )
    op.create_table(
        'tenant_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='VIEWER'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['role'], ['roles.name']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_user')
    )

    # 6. Storage usage
    op.create_table(
        'storage_usage',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('used_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('reserved_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('document_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_recalculated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id')
    )

    # 7. Folders
    op.create_table(
        'folders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('color', sa.String(length=32), nullable=True, server_default='#3B82F6'),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_trashed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('trashed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['folders.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. Documents & Versions
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('mime_type', sa.String(length=128), nullable=False),
        sa.Column('extension', sa.String(length=32), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='READY'),
        sa.Column('antivirus_status', sa.String(length=32), nullable=False, server_default='CLEAN'),
        sa.Column('antivirus_details', sa.Text(), nullable=True),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_trashed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('trashed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key')
    )

    # Row-Level Security Enactments
    op.execute('ALTER TABLE folders ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE documents ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE storage_usage ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table('documents')
    op.drop_table('folders')
    op.drop_table('storage_usage')
    op.drop_table('tenant_members')
    op.drop_table('roles')
    op.drop_table('tenants')
    op.drop_table('users')
    op.drop_table('plans')
