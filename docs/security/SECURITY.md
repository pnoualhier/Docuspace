# DocuSpace — Politique de Sécurité

## 1. Isolation Multi-Tenant & Row-Level Security (PostgreSQL RLS)
- **Contexte transactionnel** : Chaque requête authentifiée injecte `app.current_tenant_id`, `app.is_superuser`, `app.current_user_id` et `app.current_user_email` via `set_config(..., true)` (portée locale à la transaction) et réinitialise le contexte à la fermeture de session pour éviter toute fuite dans le pool SQLAlchemy.
- **Rôle applicatif non-privilégié** : L'application s'exécute sous un rôle PostgreSQL `NOSUPERUSER NOBYPASSRLS` avec `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY` sur `tenants`, `folders`, `documents`, `document_versions`, `shares`, `share_recipients`, `notifications` et `quarantine_events`.
- **Intégrité référentielle cross-tenant** : Contraintes composites `(tenant_id, id)` empêchant tout lien entre un document/dossier d'un tenant A et un parent d'un tenant B.

## 2. Mots de Passe, Sessions & Limitation de Débit
- **Argon2id** pour le hachage des mots de passe utilisateurs et des mots de passe de liens de partage.
- **JWT HS256** (clé vérifiée au démarrage en production) + cookies **HttpOnly**, **SameSite=Lax** et **Secure** sous HTTPS + rotation des jetons de rafraîchissement (`sessions`).
- **Rate Limiting distribué Redis** (`SlidingRateLimiter` dans `backend/app/core/rate_limit.py`) sur l'authentification (`/api/v1/auth/login`) et l'accès aux partages publics protégés.

## 3. Sécurité du Stockage, Antivirus & Traitement des Fichiers
- **Clés opaques & normalisation** : `sanitize_filename()` rejette octets nuls et traversées de chemin (`..`), les clés S3 utilisent des jetons cryptographiques `tenants/<tenant_id>/<token>.<ext>`.
- **Blocage d'extensions & double-extensions** : `is_prohibited_extension()` bloque les exécutables finaux et masqués (`facture.exe.pdf`, `run.sh.txt`).
- **Inspection magique MIME & streaming** : Lecture par blocs de 64 Ko, rejet des signatures binaires dangereuses (`MZ`, `\x7fELF`, `#!`, `<?php`, `<script`) et calcul SHA-256 à la volée.
- **Fail-Closed MinIO & ClamAV** : `S3Storage` échoue explicitement (`StorageBackendError` -> HTTP 503) hors runtime de test si MinIO est inaccessible ; `ClamAVScanner` rejette tout fichier si ClamAV est indisponible ou détecte une menace (quarantaine tracée dans `quarantine_events` et `audit_logs`).
- **Barrière de téléchargement** : Les URLs pré-signées ne sont délivrées que pour les documents `status == 'READY'` et `antivirus_status == 'CLEAN'`, avec `Content-Disposition: attachment`.

## 4. Quotas, Facturation, Administration & RGPD
- **Quotas atomiques** : Réservation pessimiste (`SELECT ... FOR UPDATE`) sur `storage_usage` lors des uploads et réconciliation exacte documents + versions.
- **Webhooks Stripe** : Vérification HMAC-SHA256 avec fenêtre anti-rejeu (600s) et passage automatique en mode lecture seule (`restricted_read_only`) si la consommation dépasse le forfait `FREE`.
- **Protection Exports & UI** : Neutralisation des formules CSV (`=`, `+`, `-`, `@`) dans les exports d'audit Superadmin ; aucune utilisation de `window.alert`/`confirm`/`prompt` dans le frontend React.
