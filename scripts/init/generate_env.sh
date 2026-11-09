#!/usr/bin/env bash
# =========================================================================
# DocuSpace Automated Environment Generator
# Generates high-entropy cryptographic secrets and populates docker.env
# =========================================================================
set -euo pipefail

TARGET_ENV="${1:-docker.env}"
echo "[*] Generating cryptographically secure configuration in ${TARGET_ENV}..."

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DB_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))")
MINIO_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))")
REDIS_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))")

cat <<EOF > "${TARGET_ENV}"
# Generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

APP_NAME=DocuSpace
APP_ENV=production
APP_URL=http://localhost
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

HTTP_PORT=80
HTTPS_PORT=443
FRONTEND_PORT=3000
BACKEND_PORT=8000
POSTGRES_PORT=5432
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001
CLAMAV_PORT=3310
REDIS_PORT=6379

POSTGRES_DB=docuspace
POSTGRES_USER=docuspace_user
POSTGRES_PASSWORD=${DB_PASS}
DATABASE_URL=postgresql+asyncpg://docuspace_user:${DB_PASS}@postgres:5432/docuspace

MINIO_ROOT_USER=docuspace_minio_admin
MINIO_ROOT_PASSWORD=${MINIO_PASS}
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET_NAME=docuspace-documents
MINIO_SECURE=false

CLAMAV_HOST=clamav
CLAMAV_PORT=3310
CLAMAV_FAIL_CLOSED=true

REDIS_PASSWORD=${REDIS_PASS}
REDIS_URL=redis://:${REDIS_PASS}@redis:6379/0

SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@docuspace.local
SMTP_PASSWORD=demo_smtp_token
SMTP_FROM_EMAIL=no-reply@docuspace.io
SMTP_TLS=true

BACKUP_DIR=/var/backups/docuspace
RETENTION_DAYS=14
EOF

chmod 600 "${TARGET_ENV}"
echo "[✓] Configuration successfully created at ${TARGET_ENV}"
