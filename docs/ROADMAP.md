# DocuSpace — Feuille de Route par Phases

| Phase | Intitulé | Statut | Objectifs Clés |
|---|---|---|---|
| **Phase 1** | **Architecture & Socle Initial** | **TERMINÉ** | Monolithe modulaire, Docker Compose, PostgreSQL 16, RLS, Alembic, FastAPI, React 19, Argon2id, documentation initiale |
| **Phase 2** | **Multi-Tenancy, Isolation RLS & RBAC** | **TERMINÉ** | Double barrière d'étanchéité, tests anti-IDOR, protection en-têtes forgés, gestion des membres et matrice RBAC |
| **Phase 3** | **Gestion des Dossiers & Documents** | **TERMINÉ** | Arborescence récursive, déplacement interactif, prévention des cycles, duplication S3/DB, actions groupées, moteur de recherche multi-critères |
| **Phase 4** | **Stockage S3 MinIO, Quotas & Antivirus** | **TERMINÉ** | Upload multipart streaming, SDK MinIO fail-closed, URLs pré-signées, ClamAV fail-closed, calcul SHA-256, verrous quotas atomiques |
| **Phase 5** | **Partage Sécurisé & Permissions** | **TERMINÉ** | Partage d'utilisateur à utilisateur, liens publics tokenisés avec mot de passe/expiration/quota, modification `PATCH /shares/{id}`, audit d'accès |
| **Phase 6** | **Versions, Corbeille & Prévisualisation** | **TERMINÉ** | Historique des révisions borné par forfait (`Plan.max_versions_per_file`), restauration, libération de quota et purge MinIO, corbeille 30 jours, visionneuse sécurisée |
| **Phase 7** | **Notifications, Facturation & Administration** | **TERMINÉ** | Centre de notifications PostgreSQL sous RLS (seuils 80%/100%), Stripe Checkout & webhooks HMAC-SHA256 persistés, restriction lecture seule, console Superadmin avec export CSV protégé |
| **Phase 8** | **RGPD, Sauvegardes & Déploiement Debian** | **TERMINÉ** | Export de portabilité RGPD (Art. 20), droit à l'effacement DB + MinIO (Art. 17), scripts `backup.sh`/`restore.sh` avec SHA-256 et rotation 14 jours, guide Debian |
| **Phase 9** | **Intégration Services Réels (PG, MinIO, ClamAV, Redis)** | **TERMINÉ** | Harnais PostgreSQL 15/16 réel avec `FORCE ROW LEVEL SECURITY` (`docuspace_app` non-superuser), tests MinIO S3, ClamAV `zINSTREAM`, Redis `requirepass` |
| **Phase 10** | **Audit, Fiabilisation & Sécurisation Avancée** | **TERMINÉ** | Migration `0008_notif_rls_quarantine`, rate limiting distribué Redis (`SlidingRateLimiter`), santé réelle `/api/v1/health`, rejet double-extensions, modalités UX accessibles sans popups natives, exercice réel `pg_dump`/`pg_restore` |
