#!/usr/bin/env bash
# =========================================================================
# DocuSpace One-Command Debian Bootstrap
# Ensures .env is populated automatically, starts stack, and runs Alembic.
# =========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

cd "${PROJECT_ROOT}"

if [ ! -f "${ENV_FILE}" ]; then
    echo "[*] Aucun fichier .env détecté — génération automatique des variables d'environnement..."
    bash "${SCRIPT_DIR}/generate_env.sh" "${ENV_FILE}" "${1:-http://localhost}"
else
    echo "[✓] Fichier .env existant détecté (${ENV_FILE})."
fi

echo "[*] Démarrage de la stack Docker Compose..."
docker compose up -d --build

echo "[*] Application des migrations PostgreSQL (Alembic)..."
docker compose exec backend alembic upgrade head

echo "[✓] DocuSpace est prêt."
