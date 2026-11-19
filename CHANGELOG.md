# Changelog — DocuSpace

Toutes les modifications notables de fiabilisation, sécurité et fonctionnalité sont documentées ci-dessous.

---

## [1.1.0] — 2026-11-19 — Audit, Durcissement P0/P1/P2 & Phase 10

### Sécurité & Multi-Tenancy (P0)
- **Migration Alembic `0008_notif_rls_quarantine`** :
  - Ajout de `tenant_id`, `category`, `level`, `action_url` sur `notifications` avec `ENABLE` + `FORCE ROW LEVEL SECURITY`.
  - Création de la table `quarantine_events` sous `ENABLE` + `FORCE ROW LEVEL SECURITY` pour tracer les menaces détectées par ClamAV.
  - Ajout des colonnes `subscription_status` et `restricted_read_only` sur `tenants`.
- **Contexte RLS destinataires** : Injection et réinitialisation de `app.current_user_id` et `app.current_user_email` via `set_user_recipient_context` (`backend/app/core/database.py`, `backend/app/middleware/tenant_context.py`).
- **Validation des fichiers & stockage S3 MinIO** :
  - Durcissement de `S3Storage` (`backend/app/storage/s3_storage.py`) : SDK `minio.Minio` réel, mode *fail-closed* strict hors tests (`StorageBackendError` -> HTTP 503), implémentation complète de `copy_object`.
  - Normalisation stricte `sanitize_filename()` (rejet octets nuls et traversées `..`) et détection des doubles extensions exécutables (`is_prohibited_extension`, ex. `facture.exe.pdf`).
  - Suppression de l'état en mémoire `_ACTIVE_UPLOAD_SESSIONS` dans `storage.py`, persistance des quarantaines dans `quarantine_events` et `audit_logs`, inclusion de `DocumentVersion` dans la réconciliation de quota (`quota_service.py`).
- **Cycle de vie Documents, Dossiers, Versions & Corbeille (`documents.py`)** :
  - Pagination (`limit`/`offset`) sur les listes de dossiers, documents et recherches.
  - Suppression récursive `delete_folder` avec mise en corbeille des sous-dossiers/documents et désactivation automatique des partages liés.
  - Copie S3 + DB atomique (`copy_document`), restauration unitaire (`restore_document`), purge unitaire/groupée/corbeille (`purge_document`, `bulk_purge_documents`, `empty_trash`) avec suppression des objets MinIO et restitution de quota.
  - Plafonnement dynamique des versions selon `Plan.max_versions_per_file` avec éviction DB et MinIO de la version la plus ancienne.
- **Routes `admin`, `gdpr`, `notifications`, `billing` & Correction routage** :
  - Réécriture avec contrôle strict Auth/RBAC/Superuser, persistance PostgreSQL sous RLS, vérification HMAC-SHA256 Stripe + bascule `restricted_read_only`, neutralisation des formules CSV (`=`, `+`, `-`, `@`) et purge RGPD DB + MinIO (Art. 17 & 20).
  - Suppression du double préfixe de montage dans `backend/app/main.py` (`/api/v1/billing/*`, `/api/v1/notifications/*`, `/api/v1/admin/*`, `/api/v1/gdpr/*`).

### Partage, Rate Limiting, Observabilité & Frontend (P1)
- **Modification de partage** : Ajout du schéma `ShareUpdate` et de `PATCH /api/v1/shares/{share_id}` avec `SELECT ... FOR UPDATE`, contrôle créateur/`OWNER` et audit `SHARE_UPDATED`.
- **Rate Limiting Distribué Redis** : Création de `SlidingRateLimiter` (`backend/app/core/rate_limit.py`) avec pipeline atomique `INCR` + `TTL`/`EXPIRE`, intégré dans `auth.py` et `password.py`.
- **Observabilité** : Sondes concurrentes réelles PostgreSQL, Redis, MinIO et ClamAV (`zPING`) dans `GET /api/v1/health`, et formateur de logs JSON structurés (`_StructuredJsonFormatter`) sans exposition de secrets ni stacktraces HTTP.
- **Frontend React / TypeScript** :
  - Suppression de tous les appels `window.alert`/`confirm`/`prompt`/`open` au profit de modales accessibles (`ConfirmActionModal.tsx`, `RenameModal.tsx`, bannières d'état, téléchargement Blob JSON pour reçus Stripe).
  - Contrôle client des doubles extensions, octets nuls et traversées dans `FileUploadModal.tsx` et téléchargement présigné sécurisé dans `FilePreviewModal.tsx`.
  - Alignement complet de `src/services/api.ts` avec les endpoints FastAPI réels (dont `POST /gdpr/delete-account` et `ApiUploadCompleteResponse.document`).

### Tests, CI/CD & Documentation (P2)
- Ajout de `backend/tests/test_phase10_hardening_and_audit.py` (incluant exercice réel `pg_dump` / `sha256sum` / `pg_restore` sur PostgreSQL 15 et `SlidingRateLimiter` sur `redis-server` réel) — **93 tests backend réussis**.
- Extension de `src/__tests__/docuspace.test.tsx` — **10 tests Vitest réussis**, `tsc --noEmit` et build Vite validés.
- Ajout du job `docker-validation` dans `.github/workflows/ci.yml` et mise à jour de `README.md`, `CONTEXT.md`, `CHANGELOG.md` et `docs/`.

---

## [1.0.0] — Phases 1 à 9 (Socle Initial & Intégration Services Réels)
- Mise en place du monolithe modulaire FastAPI + React 19 + PostgreSQL 16 RLS + MinIO + ClamAV + Redis + Nginx.
- Implémentation des migrations Alembic `0001` à `0007`, harnais d'intégration PostgreSQL (`PostgresHarness`), scripts `generate_env.sh`, `backup.sh`, `restore.sh` et guides de déploiement Debian.
