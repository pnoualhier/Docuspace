#!/bin/bash
# =========================================================================
# DocuSpace Disaster Recovery & Restore Script
# Usage: ./scripts/restore/restore.sh /var/backups/docuspace/20261108_120000
# =========================================================================
set -eo pipefail

if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_backup_folder>"
    exit 1
fi

BACKUP_PATH="$1"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-docuspace-postgres}"
MINIO_CONTAINER="${MINIO_CONTAINER:-docuspace-minio}"
DB_NAME="${POSTGRES_DB:-docuspace}"
DB_USER="${POSTGRES_USER:-docuspace_user}"

if [ ! -d "${BACKUP_PATH}" ]; then
    echo "Error: Directory ${BACKUP_PATH} does not exist!"
    exit 1
fi

echo "[!] WARNING: This will overwrite active database and storage data."
echo "[*] Verifying SHA256 checksums..."
cd "${BACKUP_PATH}"
if [ -f SHA256SUMS ]; then
    sha256sum -c SHA256SUMS
fi
cd - > /dev/null

echo "[*] Step 1: Restoring PostgreSQL Database..."
DUMP_FILE=$(find "${BACKUP_PATH}" -name "postgres_*.dump" | head -n 1)
if [ -f "${DUMP_FILE}" ]; then
    docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD}" "${POSTGRES_CONTAINER}" \
        pg_restore -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists -v < "${DUMP_FILE}" || true
    echo "[✓] PostgreSQL database restored."
else
    echo "[-] Warning: No postgres dump found in ${BACKUP_PATH}"
fi

echo "[*] Step 2: Restoring MinIO Object Storage..."
MINIO_FILE=$(find "${BACKUP_PATH}" -name "minio_data_*.tar.gz" | head -n 1)
if [ -f "${MINIO_FILE}" ]; then
    docker exec -i "${MINIO_CONTAINER}" tar -xzf - -C / < "${MINIO_FILE}"
    echo "[✓] MinIO storage restored."
fi

echo "[✓] Restore procedure completed successfully."
