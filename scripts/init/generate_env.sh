#!/usr/bin/env bash
# =========================================================================
# DocuSpace Automated Environment Generator
# Generates high-entropy cryptographic secrets and populates .env
# =========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET_ENV="${1:-${PROJECT_ROOT}/.env}"
APP_URL_ARG="${2:-http://localhost}"

echo "[*] Generating cryptographically secure configuration in ${TARGET_ENV}..."

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DB_PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")
MINIO_USER="docuspace_s3_$(python3 -c "import secrets; print(secrets.token_hex(6))")"
MINIO_PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")
REDIS_PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")

umask 077
cat <<EOF > "${TARGET_ENV}"
# Generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

APP_NAME=DocuSpace
APP_ENV=production
APP_URL=${APP_URL_ARG}
API_V1_STR=/api/v1
VITE_API_URL=/api/v1
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

HTTP_PORT=80
HTTPS_PORT=443

POSTGRES_DB=docuspace
POSTGRES_USER=docuspace_user
POSTGRES_PASSWORD=${DB_PASS}
DATABASE_URL=postgresql+asyncpg://docuspace_user:${DB_PASS}@postgres:5432/docuspace

MINIO_ROOT_USER=${MINIO_USER}
MINIO_ROOT_PASSWORD=${MINIO_PASS}
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=${MINIO_USER}
MINIO_SECRET_KEY=${MINIO_PASS}
MINIO_BUCKET_NAME=docuspace-documents
MINIO_SECURE=false

CLAMAV_HOST=clamav
CLAMAV_PORT=3310
CLAMAV_FAIL_CLOSED=true

REDIS_PASSWORD=${REDIS_PASS}
REDIS_URL=redis://:${REDIS_PASS}@redis:6379/0

BACKEND_CORS_ORIGINS=["${APP_URL_ARG}"]

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=no-reply@example.com
SMTP_TLS=true

BACKUP_DIR=/var/backups/docuspace
RETENTION_DAYS=14
EOF

chmod 600 "${TARGET_ENV}"
echo "[✓] Configuration successfully created at ${TARGET_ENV} (mode 600)"
