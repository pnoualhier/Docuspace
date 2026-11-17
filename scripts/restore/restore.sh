#!/usr/bin/env bash
# =========================================================================
# DocuSpace Disaster Recovery & Restore Script
# Usage: ./scripts/restore/restore.sh /var/backups/docuspace/20261108_120000
# =========================================================================
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <path_to_backup_folder>"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"

if [ -f "${ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo "Error: POSTGRES_PASSWORD is not set. Load ${ENV_FILE} or export POSTGRES_PASSWORD." >&2
    exit 1
fi

BACKUP_PATH="$1"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-docuspace-postgres}"
MINIO_CONTAINER="${MINIO_CONTAINER:-docuspace-minio}"
DB_NAME="${POSTGRES_DB:-docuspace}"
DB_USER="${POSTGRES_USER:-docuspace_user}"

if [ ! -d "${BACKUP_PATH}" ]; then
    echo "Error: Directory ${BACKUP_PATH} does not exist!" >&2
    exit 1
fi

echo "[!] WARNING: This will overwrite active database and storage data."
echo "[*] Verifying SHA256 checksums..."
if [ -f "${BACKUP_PATH}/SHA256SUMS" ]; then
    (
        cd "${BACKUP_PATH}"
        sha256sum -c SHA256SUMS
    )
fi

echo "[*] Step 1: Restoring PostgreSQL Database..."
DUMP_FILE=$(find "${BACKUP_PATH}" -name "postgres_*.dump" | head -n 1 || true)
if [ -n "${DUMP_FILE}" ] && [ -f "${DUMP_FILE}" ]; then
    docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD}" "${POSTGRES_CONTAINER}" \
        pg_restore -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists -v < "${DUMP_FILE}"
    echo "[✓] PostgreSQL database restored."
else
    echo "[-] Warning: No postgres dump found in ${BACKUP_PATH}"
fi

echo "[*] Step 2: Restoring MinIO Object Storage..."
MINIO_FILE=$(find "${BACKUP_PATH}" -name "minio_data_*.tar.gz" | head -n 1 || true)
if [ -n "${MINIO_FILE}" ] && [ -f "${MINIO_FILE}" ]; then
    docker exec -i "${MINIO_CONTAINER}" tar -xzf - -C / < "${MINIO_FILE}"
    echo "[✓] MinIO storage restored."
fi

echo "[✓] Restore procedure completed successfully."
