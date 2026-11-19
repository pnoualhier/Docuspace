# DocuSpace — Contexte Technique & Architecture Active

Ce document synthétise l'état technique courant de **DocuSpace** après l'exécution des phases 1 à 10 (audit, fiabilisation et sécurisation).

---

## 1. Vue d'Ensemble & Principes d'Architecture

DocuSpace est un **monolithe modulaire multi-tenant** destiné à la gestion documentaire personnelle B2C :
- **Frontend SPA** (`src/`) : React 19, TypeScript, Vite, Tailwind CSS. Communication exclusivement via `src/services/api.ts` (base `/api/v1` configurable via `VITE_API_URL`) et fallback mode aperçu hors-ligne si l'API est inaccessible.
- **Backend API** (`backend/app/`) : FastAPI + SQLAlchemy 2 Async (`asyncpg`) + Pydantic v2.
- **Stockage S3** (`backend/app/storage/`) : Client `S3Storage` basé sur `minio.Minio` avec mode *fail-closed* strict hors runtime de test (`StorageBackendError` -> HTTP 503).
- **Antivirus** (`backend/app/security/antivirus.py`) : Scan TCP ClamAV (`zINSTREAM`) *fail-closed* et persistance des incidents dans `quarantine_events`.
- **Rate Limiting & Cache** (`backend/app/core/rate_limit.py`) : `SlidingRateLimiter` distribué sur Redis (`INCR` + `TTL`/`EXPIRE`) utilisé pour `/api/v1/auth/login` et les partages publics protégés.

---

## 2. Base de Données & Isolation Multi-Tenant (PostgreSQL RLS)

- **Chaîne Alembic** : Tête linéaire unique **`0008_notif_rls_quarantine`** (`backend/migrations/versions/`).
- **Rôle applicatif non-privilégié** : Les tests d'intégration et l'exploitation utilisent un rôle `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` (`docuspace_app`).
- **Tables protégées par `ENABLE` + `FORCE ROW LEVEL SECURITY`** :
  - `tenants`, `folders`, `documents`, `document_versions`, `shares`, `share_recipients`, `notifications`, `quarantine_events`.
- **Variables de session transactionnelles (`set_config(..., true)`)** gérées dans `backend/app/core/database.py` et `backend/app/middleware/tenant_context.py` :
  - `app.current_tenant_id`
  - `app.is_superuser`
  - `app.public_share_token_hash`
  - `app.current_user_id` & `app.current_user_email` (accès aux partages internes reçus)
  - Réinitialisation systématique via `reset_tenant_context()` à la fin de chaque session pour prévenir toute fuite dans le pool de connexions.
- **Intégrité cross-tenant** : Contraintes composites `(tenant_id, id)` entre dossiers, documents et versions.

---

## 3. Cartographie des Routes API (`/api/v1`)

Montage vérifié dans `backend/app/main.py` :
- **Système** : `GET /api/v1/health` (sondes concurrentes PostgreSQL, Redis, MinIO, ClamAV).
- **Authentification (`/api/v1/auth`)** : `register`, `login`, `refresh` (rotation), `logout`, `me`, `verify-email`, `sessions`, `password-reset/*`.
- **Tenants (`/api/v1/tenants`)** : `my-tenants`, `current`, `current/members`, `plans`.
- **Dossiers & Documents (`/api/v1/documents`)** : `folders`, `folders/tree`, `folders/{id}/move|copy`, `DELETE /folders/{id}` (récursif + révocation partages), `documents`, `documents/search`, `documents/{id}/copy|restore|purge`, `bulk/{move,trash,restore,purge}`, `documents/{id}/versions`, `trash`, `trash/empty`, `trash/auto-purge`.
- **Stockage & Antivirus (`/api/v1/storage`)** : `upload/initiate`, `upload/direct`, `upload/complete`, `upload/cleanup`, `download/{id}`, `scan/{id}`, `quarantine`, `quota`, `reconcile`.
- **Partages (`/api/v1/shares`)** : `GET /shares`, `POST /internal`, `POST /link`, `PATCH /{share_id}`, `DELETE /{share_id}`, `GET /received`, `GET /received/{id}/download`, `GET|POST /public/{token}/*`.
- **Notifications (`/api/v1/notifications`)** : `GET /`, `POST /{id}/read`, `POST /read-all`, `POST /check-quota`.
- **Facturation (`/api/v1/billing`)** : `GET /plans`, `POST /checkout`, `POST /webhook` (HMAC-SHA256 + mode lecture seule `restricted_read_only`).
- **Administration (`/api/v1/admin`)** : `GET /stats`, `GET /audit-logs` (`json`/`csv` avec neutralisation d'injection de formules), `PATCH /users/{id}/status`, `PATCH /tenants/{id}/plan` (protégés par `is_superuser`).
- **RGPD (`/api/v1/gdpr`)** : `GET /export` (Art. 20), `POST /delete-account` (Art. 17 avec purge PG + MinIO).

---

## 4. Infrastructure, Sauvegardes & CI/CD

- **Docker Compose** (`docker-compose.yml`) : 7 services (`postgres`, `minio`, `clamav`, `redis`, `backend`, `frontend`, `nginx`) répartis sur `docuspace-internal` (`internal: true`) et `docuspace-edge`. Seul `nginx` publie les ports `HTTP_PORT`/`HTTPS_PORT`.
- **Variables d'environnement** : `.env` local en mode `0600` (générable via `scripts/init/generate_env.sh`), validation fail-fast au démarrage production (`Settings.validate_production_secrets()`).
- **Sauvegardes** : `scripts/backup/backup.sh` (`pg_dump -F c`, archive MinIO, `.env`, `SHA256SUMS`, rotation 14 jours) et `scripts/restore/restore.sh`.
- **CI GitHub Actions** (`.github/workflows/ci.yml`) :
  1. `backend-real-services` (PostgreSQL 16, MinIO, ClamAV, Redis réels)
  2. `frontend-tests-and-build` (`lint`, `test`, `build`)
  3. `docker-validation` (`bash -n` scripts, `docker compose config -q`, build des Dockerfiles)

---

## 5. État Vérifié & Limites d'Environnement

- **Suites validées** : `93/93` tests `pytest` (`backend/tests/`), `10/10` tests `vitest` (`npm test`), `tsc --noEmit` et build Vite sans erreur.
- **Note environnement de développement** : Le conteneur preview exécute réellement PostgreSQL 15.20, Redis 7 et les outils `pg_dump`/`pg_restore`, mais ne dispose ni de daemon Docker ni de répertoire `.git` local ; la validation complète avec les conteneurs live MinIO et ClamAV est assurée par le pipeline `.github/workflows/ci.yml` ou sur l'hôte Debian cible.
