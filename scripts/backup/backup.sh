#!/bin/bash
# =========================================================================
# DocuSpace Backup Script - Automated Backup for PostgreSQL & MinIO S3
# =========================================================================
set -eo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/docuspace}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-docuspace-postgres}"
MINIO_CONTAINER="${MINIO_CONTAINER:-docuspace-minio}"
DB_NAME="${POSTGRES_DB:-docuspace}"
DB_USER="${POSTGRES_USER:-docuspace_user}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "${BACKUP_DIR}/${TIMESTAMP}"
echo "[*] [${TIMESTAMP}] Starting DocuSpace system backup..."

# 1. PostgreSQL Database Dump (Custom format with compression)
echo "[*] Dumping PostgreSQL database '${DB_NAME}'..."
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" "${POSTGRES_CONTAINER}" \
    pg_dump -U "${DB_USER}" -d "${DB_NAME}" -F c -b -v \
    > "${BACKUP_DIR}/${TIMESTAMP}/postgres_${DB_NAME}_${TIMESTAMP}.dump"

# 2. MinIO S3 Bucket Data Backup
echo "[*] Archiving MinIO Object Storage..."
docker exec "${MINIO_CONTAINER}" tar -czf - /data \
    > "${BACKUP_DIR}/${TIMESTAMP}/minio_data_${TIMESTAMP}.tar.gz"

# 3. Environment configuration backup (sanitized or encrypted recommended)
if [ -f .env ]; then
    cp .env "${BACKUP_DIR}/${TIMESTAMP}/env_backup_${TIMESTAMP}.bak"
    chmod 600 "${BACKUP_DIR}/${TIMESTAMP}/env_backup_${TIMESTAMP}.bak"
fi

# 4. Generate SHA256 checksums
cd "${BACKUP_DIR}/${TIMESTAMP}"
sha256sum * > SHA256SUMS
cd - > /dev/null

# 5. Rotate backups older than RETENTION_DAYS
echo "[*] Pruning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} +

echo "[✓] Backup successfully completed at ${BACKUP_DIR}/${TIMESTAMP}"
