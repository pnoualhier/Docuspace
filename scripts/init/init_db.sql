-- =========================================================================
-- DocuSpace Initial Database Schema with PostgreSQL Row-Level Security (RLS)
-- Version: 1.0.0 - Modular Multi-Tenant Personal Cloud Storage
-- =========================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -------------------------------------------------------------------------
-- 1. PLANS & TIERS
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plans (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    max_storage_bytes BIGINT NOT NULL,
    max_file_size_bytes BIGINT NOT NULL,
    max_members INT NOT NULL DEFAULT 1,
    max_versions_per_file INT NOT NULL DEFAULT 5,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default plans
INSERT INTO plans (id, name, max_storage_bytes, max_file_size_bytes, max_members, max_versions_per_file, features)
VALUES 
    ('FREE', 'Gratuit', 524288000, 26214400, 1, 3, '{"clamav_scan": true, "share_links": true, "preview": true}'::jsonb),
    ('PERSONAL', 'Personnel', 21474836480, 262144000, 1, 10, '{"clamav_scan": true, "share_links": true, "preview": true, "priority_conversion": true}'::jsonb),
    ('PREMIUM', 'Premium', 107374182400, 1073741824, 1, 30, '{"clamav_scan": true, "share_links": true, "preview": true, "priority_conversion": true, "full_audit": true}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- -------------------------------------------------------------------------
-- 2. USERS & SESSIONS
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    is_superuser BOOLEAN NOT NULL DEFAULT false,
    verification_token VARCHAR(255),
    verification_token_expires_at TIMESTAMPTZ,
    reset_password_token VARCHAR(255),
    reset_password_token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL UNIQUE,
    user_agent VARCHAR(512),
    ip_address VARCHAR(45),
    is_revoked BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

-- -------------------------------------------------------------------------
-- 3. TENANTS (Personal Document Spaces) & MEMBERSHIPS
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    plan_id VARCHAR(32) NOT NULL REFERENCES plans(id) DEFAULT 'FREE',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_owner ON tenants(owner_id);

CREATE TABLE IF NOT EXISTS roles (
    name VARCHAR(32) PRIMARY KEY,
    description TEXT
);

INSERT INTO roles (name, description) VALUES
    ('OWNER', 'Propriétaire complet de l''espace documentaire'),
    ('EDITOR', 'Éditeur avec droits de modification et d''import'),
    ('VIEWER', 'Lecteur seul sans droit de modification'),
    ('GUEST', 'Invité avec accès restreint à des fichiers ciblés')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS tenant_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL REFERENCES roles(name) DEFAULT 'VIEWER',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_user UNIQUE (tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_members_user ON tenant_members(user_id);
CREATE INDEX IF NOT EXISTS idx_tenant_members_tenant ON tenant_members(tenant_id);

-- -------------------------------------------------------------------------
-- 4. STORAGE USAGE (Per-Tenant Quota Tracker)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS storage_usage (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    used_bytes BIGINT NOT NULL DEFAULT 0,
    reserved_bytes BIGINT NOT NULL DEFAULT 0,
    document_count INT NOT NULL DEFAULT 0,
    last_recalculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------------------
-- 5. FOLDERS (Hierarchical isolation by tenant)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES folders(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    color VARCHAR(32) DEFAULT '#3B82F6',
    is_favorite BOOLEAN NOT NULL DEFAULT false,
    is_trashed BOOLEAN NOT NULL DEFAULT false,
    trashed_at TIMESTAMPTZ,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_folder_name_per_parent UNIQUE NULLS NOT DISTINCT (tenant_id, parent_id, name)
);

CREATE INDEX IF NOT EXISTS idx_folders_tenant ON folders(tenant_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);

-- -------------------------------------------------------------------------
-- 6. DOCUMENTS & VERSIONS
-- -------------------------------------------------------------------------
CREATE TYPE document_status AS ENUM ('INITIATED', 'UPLOADING', 'PENDING_SCAN', 'READY', 'REJECTED', 'FAILED', 'EXPIRED');
CREATE TYPE antivirus_status AS ENUM ('PENDING', 'CLEAN', 'INFECTED', 'SCAN_ERROR');

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    original_name VARCHAR(255) NOT NULL,
    storage_key VARCHAR(512) NOT NULL UNIQUE,
    mime_type VARCHAR(128) NOT NULL,
    extension VARCHAR(32) NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'READY',
    antivirus_status VARCHAR(32) NOT NULL DEFAULT 'CLEAN',
    antivirus_details TEXT,
    is_favorite BOOLEAN NOT NULL DEFAULT false,
    is_trashed BOOLEAN NOT NULL DEFAULT false,
    trashed_at TIMESTAMPTZ,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(tenant_id, status, is_trashed);

CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    storage_key VARCHAR(512) NOT NULL UNIQUE,
    size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    change_summary VARCHAR(255),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_doc_version UNIQUE (document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON document_versions(document_id);

-- -------------------------------------------------------------------------
-- 7. SHARING (User permissions & Secure Public Links)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    share_type VARCHAR(32) NOT NULL, -- 'INTERNAL_USER' or 'SECURE_LINK'
    role VARCHAR(32) NOT NULL REFERENCES roles(name) DEFAULT 'VIEWER',
    -- Secure Link parameters
    token_hash VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    max_downloads INT,
    download_count INT NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_share_target CHECK (
        (document_id IS NOT NULL AND folder_id IS NULL) OR
        (document_id IS NULL AND folder_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_shares_token_hash ON shares(token_hash);
CREATE INDEX IF NOT EXISTS idx_shares_tenant ON shares(tenant_id);

CREATE TABLE IF NOT EXISTS share_recipients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_id UUID NOT NULL REFERENCES shares(id) ON DELETE CASCADE,
    recipient_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL REFERENCES roles(name) DEFAULT 'VIEWER',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_share_recipient UNIQUE (share_id, recipient_email)
);

-- -------------------------------------------------------------------------
-- 8. AUDIT LOGS & NOTIFICATIONS
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    user_agent VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(64) NOT NULL DEFAULT 'INFO',
    is_read BOOLEAN NOT NULL DEFAULT false,
    link VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);

-- -------------------------------------------------------------------------
-- 9. POSTGRESQL ROW-LEVEL SECURITY (RLS) POLICIES
-- -------------------------------------------------------------------------
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE shares ENABLE ROW LEVEL SECURITY;
ALTER TABLE storage_usage ENABLE ROW LEVEL SECURITY;

-- Helper function to read the transaction-scoped tenant ID
CREATE OR REPLACE FUNCTION app_tenant_id() RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
EXCEPTION
    WHEN OTHERS THEN RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- RLS Policy: Folders isolated by tenant
CREATE POLICY tenant_isolation_folders ON folders
    FOR ALL
    USING (tenant_id = app_tenant_id() OR current_setting('app.is_superuser', true) = 'true');

-- RLS Policy: Documents isolated by tenant
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL
    USING (tenant_id = app_tenant_id() OR current_setting('app.is_superuser', true) = 'true');

-- RLS Policy: Document versions isolated by tenant
CREATE POLICY tenant_isolation_doc_versions ON document_versions
    FOR ALL
    USING (tenant_id = app_tenant_id() OR current_setting('app.is_superuser', true) = 'true');

-- RLS Policy: Shares isolated by tenant
CREATE POLICY tenant_isolation_shares ON shares
    FOR ALL
    USING (tenant_id = app_tenant_id() OR current_setting('app.is_superuser', true) = 'true');

-- RLS Policy: Storage usage isolated by tenant
CREATE POLICY tenant_isolation_storage ON storage_usage
    FOR ALL
    USING (tenant_id = app_tenant_id() OR current_setting('app.is_superuser', true) = 'true');
