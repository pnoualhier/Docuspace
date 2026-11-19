"""0008_notifications_rls_and_quarantine

Revision ID: 0008_notif_rls_quarantine
Revises: 0007_complete_schema_rls
Create Date: 2026-11-19 02:00:00.000000

Hardens tenant isolation and schema completeness:
1. Adds tenant_id, category, level, action_url to notifications + FORCE ROW LEVEL SECURITY.
2. Creates quarantine_events table with FORCE ROW LEVEL SECURITY for ClamAV incident persistence.
3. Adds subscription_status and restricted_read_only columns to tenants for Stripe billing persistence.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0008_notif_rls_quarantine'
down_revision: Union[str, None] = '0007_complete_schema_rls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend tenants with billing status columns
    op.add_column('tenants', sa.Column('subscription_status', sa.String(length=32), nullable=False, server_default='ACTIVE'))
    op.add_column('tenants', sa.Column('restricted_read_only', sa.Boolean(), nullable=False, server_default='false'))

    # 2. Extend notifications with tenant_id & metadata + FORCE ROW LEVEL SECURITY
    op.add_column('notifications', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('notifications', sa.Column('category', sa.String(length=32), nullable=False, server_default='STORAGE'))
    op.add_column('notifications', sa.Column('level', sa.String(length=32), nullable=False, server_default='INFO'))
    op.add_column('notifications', sa.Column('action_url', sa.String(length=512), nullable=True))

    op.execute(
        "UPDATE notifications n SET tenant_id = t.id "
        "FROM tenants t WHERE t.owner_id = n.user_id AND n.tenant_id IS NULL;"
    )
    op.alter_column('notifications', 'tenant_id', nullable=False)
    op.create_foreign_key(
        'fk_notifications_tenant_id',
        'notifications',
        'tenants',
        ['tenant_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_notifications_tenant_id', 'notifications', ['tenant_id'])

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS notifications_tenant_isolation ON notifications;")
    op.execute("""
        CREATE POLICY notifications_tenant_isolation ON notifications
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

    # 3. Create quarantine_events table with FORCE ROW LEVEL SECURITY
    op.create_table(
        'quarantine_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('threat_name', sa.String(length=255), nullable=False),
        sa.Column('quarantine_key', sa.String(length=512), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='QUARANTINED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_quarantine_events_tenant_id', 'quarantine_events', ['tenant_id'])

    op.execute("ALTER TABLE quarantine_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE quarantine_events FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY quarantine_events_tenant_isolation ON quarantine_events
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


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS quarantine_events_tenant_isolation ON quarantine_events;")
    op.execute("ALTER TABLE quarantine_events NO FORCE ROW LEVEL SECURITY;")
    op.drop_table('quarantine_events')

    op.execute("DROP POLICY IF EXISTS notifications_tenant_isolation ON notifications;")
    op.execute("ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY;")
    op.drop_index('ix_notifications_tenant_id', table_name='notifications')
    op.drop_constraint('fk_notifications_tenant_id', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'action_url')
    op.drop_column('notifications', 'level')
    op.drop_column('notifications', 'category')
    op.drop_column('notifications', 'tenant_id')

    op.drop_column('tenants', 'restricted_read_only')
    op.drop_column('tenants', 'subscription_status')
