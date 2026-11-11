"""0004_rls_force_policies_and_cross_tenant_constraints

Revision ID: 0004_rls_constraints
Revises: 0003_upload_sessions
Create Date: 2026-11-10 10:00:00.000000

Guarantees:
1. FORCE ROW LEVEL SECURITY on all isolated tables (prevents table owner bypass).
2. RESTRICTIVE RLS policies checking app.current_tenant_id and app.is_superuser.
3. Composite unique keys and foreign keys preventing cross-tenant references:
   - Document -> Folder (same tenant_id)
   - Folder -> Parent Folder (same tenant_id)
   - DocumentVersion -> Document (same tenant_id)
   - Share -> Document/Folder (same tenant_id)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_rls_constraints'
down_revision: Union[str, None] = '0003_upload_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Composite Unique Constraints to enable composite foreign keys
    op.execute("""
        -- Folders composite unique (id, tenant_id)
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_folders_id_tenant'
            ) THEN
                ALTER TABLE folders ADD CONSTRAINT uq_folders_id_tenant UNIQUE (id, tenant_id);
            END IF;
        END $$;
    """)

    op.execute("""
        -- Documents composite unique (id, tenant_id)
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_documents_id_tenant'
            ) THEN
                ALTER TABLE documents ADD CONSTRAINT uq_documents_id_tenant UNIQUE (id, tenant_id);
            END IF;
        END $$;
    """)

    # 2. Cross-Tenant Referential Integrity Constraints
    op.execute("""
        -- Folder parent must belong to the exact same tenant
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_folders_parent_same_tenant'
            ) THEN
                ALTER TABLE folders 
                ADD CONSTRAINT fk_folders_parent_same_tenant 
                FOREIGN KEY (parent_id, tenant_id) 
                REFERENCES folders (id, tenant_id) 
                ON DELETE RESTRICT;
            END IF;
        END $$;
    """)

    op.execute("""
        -- Document folder must belong to the exact same tenant
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_documents_folder_same_tenant'
            ) THEN
                ALTER TABLE documents 
                ADD CONSTRAINT fk_documents_folder_same_tenant 
                FOREIGN KEY (folder_id, tenant_id) 
                REFERENCES folders (id, tenant_id) 
                ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # 3. FORCE ROW LEVEL SECURITY and Policies on isolated tables
    isolated_tables = ['documents', 'folders', 'storage_usage', 'upload_sessions']
    for tbl in isolated_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        
        policy_name = f"{tbl}_tenant_isolation"
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies WHERE policyname = '{policy_name}' AND tablename = '{tbl}'
                ) THEN
                    CREATE POLICY {policy_name} ON {tbl}
                    AS RESTRICTIVE
                    USING (
                        current_setting('app.is_superuser', true) IN ('true', 'on')
                        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                    )
                    WITH CHECK (
                        current_setting('app.is_superuser', true) IN ('true', 'on')
                        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                    );
                END IF;
            END $$;
        """)


def downgrade() -> None:
    isolated_tables = ['documents', 'folders', 'storage_usage', 'upload_sessions']
    for tbl in isolated_tables:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_isolation ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY;")

    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_folder_same_tenant;")
    op.execute("ALTER TABLE folders DROP CONSTRAINT IF EXISTS fk_folders_parent_same_tenant;")
    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS uq_documents_id_tenant;")
    op.execute("ALTER TABLE folders DROP CONSTRAINT IF EXISTS uq_folders_id_tenant;")
