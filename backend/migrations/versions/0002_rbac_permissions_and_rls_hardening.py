"""0002_rbac_permissions_and_rls_hardening

Revision ID: 0002_rbac_rls
Revises: 0001_initial_schema
Create Date: 2026-11-09 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002_rbac_rls'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create permissions table
    op.create_table(
        'permissions',
        sa.Column('code', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True)
    )

    # 2. Create role_permissions join table
    op.create_table(
        'role_permissions',
        sa.Column('role_name', sa.String(length=32), sa.ForeignKey('roles.name', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_code', sa.String(length=64), sa.ForeignKey('permissions.code', ondelete='CASCADE'), primary_key=True)
    )

    # 3. Seed granular permissions
    op.execute("""
        INSERT INTO permissions (code, name, description) VALUES
            ('document:read', 'Lecture de documents', 'Permet de consulter et télécharger des fichiers'),
            ('document:write', 'Écriture de documents', 'Permet d''importer de nouveaux fichiers'),
            ('document:delete', 'Suppression de documents', 'Permet de déplacer vers la corbeille ou purger'),
            ('document:share', 'Partage de documents', 'Permet de créer des liens sécurisés ou inviter des tiers'),
            ('document:restore', 'Restauration de versions', 'Permet de rétablir une version antérieure'),
            ('folder:create', 'Création de dossiers', 'Permet de créer de nouveaux sous-dossiers'),
            ('folder:manage', 'Gestion de dossiers', 'Permet de renommer, déplacer ou supprimer des dossiers'),
            ('member:invite', 'Invitation de membres', 'Permet d''inviter un utilisateur dans l''espace'),
            ('member:manage', 'Gestion des membres', 'Permet de modifier les rôles ou retirer des membres'),
            ('tenant:settings', 'Paramètres de l''espace', 'Permet de modifier les options et le forfait du tenant'),
            ('audit:read', 'Consultation d''audit', 'Permet de lire les journaux de sécurité')
        ON CONFLICT (code) DO NOTHING;
    """)

    # 4. Associate permissions to roles
    op.execute("""
        -- OWNER has all permissions
        INSERT INTO role_permissions (role_name, permission_code)
        SELECT 'OWNER', code FROM permissions
        ON CONFLICT DO NOTHING;

        -- EDITOR permissions
        INSERT INTO role_permissions (role_name, permission_code) VALUES
            ('EDITOR', 'document:read'),
            ('EDITOR', 'document:write'),
            ('EDITOR', 'document:share'),
            ('EDITOR', 'folder:create'),
            ('EDITOR', 'folder:manage')
        ON CONFLICT DO NOTHING;

        -- VIEWER permissions
        INSERT INTO role_permissions (role_name, permission_code) VALUES
            ('VIEWER', 'document:read')
        ON CONFLICT DO NOTHING;

        -- GUEST permissions
        INSERT INTO role_permissions (role_name, permission_code) VALUES
            ('GUEST', 'document:read')
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_table('role_permissions')
    op.drop_table('permissions')
