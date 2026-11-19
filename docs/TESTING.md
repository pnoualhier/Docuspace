# DocuSpace — Stratégie de Tests

## 1. Niveaux de Tests Backend (`backend/tests/`)

1. **Tests Unitaires & Sécurité Applicative** :
   - Hachage de mot de passe Argon2id et vérification.
   - Contrôle de cycle sur les répertoires, normalisation de noms (`sanitize_filename`) et blocage des doubles extensions (`facture.exe.pdf`).
   - Calcul d'empreinte SHA-256 et inspection magique MIME (`detect_real_mime_type`).
   - Validation fail-closed de `S3Storage` et `ClamAVScanner`.

2. **Tests d'Intégration PostgreSQL Réelle & RLS (`test_phase9_*.py`, `test_phase10_hardening_and_audit.py`)** :
   - Exécution sur une véritable instance PostgreSQL 15/16 via `PostgresHarness` avec rôle applicatif non-privilégié `docuspace_app` (`NOSUPERUSER NOBYPASSRLS`) et migrations Alembic jusqu'à `0008_notif_rls_quarantine`.
   - Vérification de `FORCE ROW LEVEL SECURITY` sur `tenants`, `folders`, `documents`, `document_versions`, `shares`, `share_recipients`, `notifications` et `quarantine_events`.
   - Validation anti-IDOR, en-têtes `X-Tenant-ID` forgés, RBAC (`OWNER`/`EDITOR`/`VIEWER`), rotation de `refresh_token`, quotas atomiques, versioning borné par `Plan.max_versions_per_file`, suppression récursive, purge MinIO/DB, webhooks Stripe HMAC-SHA256, console Superadmin avec neutralisation d'injection CSV, et conformité RGPD (Art. 17 & 20).

3. **Tests Services Réels (Redis, MinIO, ClamAV, Sauvegarde/Restauration)** :
   - `test_phase9_redis_integration.py` & `test_phase10_hardening_and_audit.py` : tests sur `redis-server` réel (`requirepass`, `SlidingRateLimiter` distribué, TTL).
   - `test_phase9_minio_clamav_integration.py` : tests MinIO S3 & ClamAV TCP (`TEST_MINIO_ENDPOINT` / `TEST_CLAMAV_HOST` en CI GitHub Actions).
   - `test_phase10_hardening_and_audit.py` : exercice complet `pg_dump -F c` + `sha256sum -c` + `pg_restore` sur PostgreSQL réel + `bash -n` sur les scripts d'exploitation.

4. **Tests Frontend React / TypeScript (`src/__tests__/docuspace.test.tsx`)** :
   - Suite Vitest + Testing Library (`npm test`), compilation Vite (`npm run build`) et contrôle TypeScript (`npm run lint`).

## 2. Exécution des Suites

```bash
python3 -m pytest backend/tests/ -v
npm test
npm run lint
npm run build
```
