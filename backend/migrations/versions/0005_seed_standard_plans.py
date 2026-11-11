"""0005_seed_standard_plans

Revision ID: 0005_seed_plans
Revises: 0004_rls_constraints
Create Date: 2026-11-11 10:00:00.000000

Seeds canonical SaaS storage plans in PostgreSQL:
- FREE: 500 MB max_storage, 100 MB max_file
- PERSONAL: 20 GB max_storage, 2 GB max_file
- PREMIUM: 100 GB max_storage, 5 GB max_file
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005_seed_plans'
down_revision: Union[str, None] = '0004_rls_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO plans (id, name, max_storage_bytes, max_file_size_bytes, max_members, max_versions_per_file, features, is_active)
        VALUES
            ('FREE', 'DocuSpace Gratuit', 524288000, 104857600, 1, 3, '{"description": "500 Mo stockage, 100 Mo max/fichier, Antivirus ClamAV"}'::jsonb, true),
            ('PERSONAL', 'DocuSpace Personnel', 21474836480, 2147483648, 3, 10, '{"description": "20 Go stockage, 2 Go max/fichier, Antivirus ClamAV, 3 membres"}'::jsonb, true),
            ('PREMIUM', 'DocuSpace Famille / Pro', 107374182400, 5368709120, 10, 100, '{"description": "100 Go stockage, 5 Go max/fichier, Antivirus ClamAV, 10 membres, Support 24/7"}'::jsonb, true)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            max_storage_bytes = EXCLUDED.max_storage_bytes,
            max_file_size_bytes = EXCLUDED.max_file_size_bytes,
            max_members = EXCLUDED.max_members,
            max_versions_per_file = EXCLUDED.max_versions_per_file,
            features = EXCLUDED.features,
            is_active = EXCLUDED.is_active,
            updated_at = now();
    """)


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE id IN ('FREE', 'PERSONAL', 'PREMIUM');")
