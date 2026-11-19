# DocuSpace — Spécification de l'API REST v1

Base URL: `/api/v1`

## 1. Santé & Observabilité (`/api/v1/health`)
- `GET /api/v1/health` : Sonde concurrente réelle PostgreSQL (`SELECT 1`), Redis (`PING`), MinIO (`bucket_exists`) et ClamAV (`zPING`).

## 2. Authentification (`/api/v1/auth`)
- `POST /api/v1/auth/register` : Crée un utilisateur et initialise son tenant personnel de manière transactionnelle.
- `POST /api/v1/auth/login` : Authentification Argon2id avec limitation de débit distribuée Redis (`SlidingRateLimiter`), délivrance JWT + cookies HttpOnly + rotation de `refresh_token`.
- `POST /api/v1/auth/refresh` : Rotation sécurisée du jeton de rafraîchissement.
- `POST /api/v1/auth/logout` : Révocation de session et suppression des cookies.
- `GET /api/v1/auth/me` : Profil de l'utilisateur authentifié.
- `GET /api/v1/auth/sessions` / `DELETE /api/v1/auth/sessions/{session_id}` / `POST /api/v1/auth/sessions/revoke-all` : Gestion des sessions actives.

## 3. Espaces & Tenants (`/api/v1/tenants`)
- `GET /api/v1/tenants/my-tenants` : Liste les espaces documentaires accessibles à l'utilisateur.
- `GET /api/v1/tenants/current` : Détails du tenant actif (contexte validé côté serveur).
- `GET /api/v1/tenants/current/members` / `POST` / `PATCH /{user_id}` / `DELETE /{user_id}` : Gestion RBAC des membres (`OWNER`, `EDITOR`, `VIEWER`, `GUEST`).
- `GET /api/v1/tenants/plans` : Catalogue des forfaits (`FREE`, `PERSONAL`, `PREMIUM`).

## 4. Dossiers, Documents, Versions & Corbeille (`/api/v1/documents`)
- `GET /api/v1/documents/folders`, `GET /api/v1/documents/folders/tree`, `POST /api/v1/documents/folders`, `PATCH /api/v1/documents/folders/{folder_id}`, `PATCH /api/v1/documents/folders/{folder_id}/move`, `POST /api/v1/documents/folders/{folder_id}/copy`, `DELETE /api/v1/documents/folders/{folder_id}` (suppression récursive + désactivation des partages).
- `GET /api/v1/documents/documents`, `GET /api/v1/documents/documents/search`, `GET /api/v1/documents/documents/{document_id}`, `PATCH /api/v1/documents/documents/{document_id}`, `POST /api/v1/documents/documents/{document_id}/copy`, `DELETE /api/v1/documents/documents/{document_id}` (mise en corbeille), `POST /api/v1/documents/documents/{document_id}/restore`, `DELETE /api/v1/documents/documents/{document_id}/purge`.
- `POST /api/v1/documents/documents/bulk/{move,trash,restore,purge}` : Opérations groupées atomiques.
- `GET / POST /api/v1/documents/documents/{id}/versions`, `POST .../versions/{version_id}/restore`, `DELETE .../versions/{version_id}` : Gestion des versions bornée par `Plan.max_versions_per_file`.
- `GET /api/v1/documents/trash`, `POST /api/v1/documents/trash/empty`, `POST /api/v1/documents/trash/auto-purge` : Corbeille et rétention 30 jours.

## 5. Stockage S3 MinIO, Quotas & Antivirus (`/api/v1/storage`)
- `POST /api/v1/storage/upload/initiate` : Valide l'extension/MIME, réserve le quota (`SELECT ... FOR UPDATE`), crée une `UploadSession` en PostgreSQL et génère une URL pré-signée MinIO.
- `POST /api/v1/storage/upload/direct` : Upload streaming par blocs (64 Ko), empreinte SHA-256, détection MIME magique, scan ClamAV fail-closed et persistance MinIO/PostgreSQL.
- `POST /api/v1/storage/upload/complete` : Finalise une session initiée après contrôle SHA-256 et ClamAV.
- `POST /api/v1/storage/upload/cleanup` : Libère les sessions expirées et leurs quotas réservés.
- `GET /api/v1/storage/download/{document_id}` : Délivre une URL pré-signée (15 min) uniquement si `status == 'READY'` et `antivirus_status == 'CLEAN'`.
- `POST /api/v1/storage/scan/{document_id}` & `GET /api/v1/storage/quarantine` : Analyse à la demande et suivi PostgreSQL des quarantaines (`quarantine_events`).
- `GET /api/v1/storage/quota` & `POST /api/v1/storage/reconcile` : Suivi et réconciliation exacte (documents + versions) avec MinIO.

## 6. Partages Sécurisés (`/api/v1/shares`)
- `GET /api/v1/shares`, `POST /api/v1/shares/internal`, `POST /api/v1/shares/link`, `PATCH /api/v1/shares/{share_id}`, `DELETE /api/v1/shares/{share_id}`
- `GET /api/v1/shares/received`, `GET /api/v1/shares/received/{share_id}/download`
- `GET /api/v1/shares/public/{token}`, `POST /api/v1/shares/public/{token}/access`, `POST /api/v1/shares/public/{token}/download`

## 7. Notifications, Facturation, Administration & RGPD
- **Notifications** : `GET /api/v1/notifications`, `POST /api/v1/notifications/{notification_id}/read`, `POST /api/v1/notifications/read-all`, `POST /api/v1/notifications/check-quota`
- **Facturation** : `GET /api/v1/billing/plans`, `POST /api/v1/billing/checkout`, `POST /api/v1/billing/webhook`
- **Administration** (`is_superuser=True`) : `GET /api/v1/admin/stats`, `GET /api/v1/admin/audit-logs` (`json`/`csv`), `PATCH /api/v1/admin/users/{target_user_id}/status`, `PATCH /api/v1/admin/tenants/{target_tenant_id}/plan`
- **RGPD** : `GET /api/v1/gdpr/export` (Art. 20), `POST /api/v1/gdpr/delete-account` (Art. 17)
