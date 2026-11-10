# DocuSpace — Feuille de Route par Phases

| Phase | Intitulé | Statut | Objectifs Clés |
|---|---|---|---|
| **Phase 1** | **Architecture & Socle Initial** | **TERMINÉ** | Monolithe modulaire, Docker Compose, PostgreSQL 16, RLS, Alembic, FastAPI, React 19, Argon2id, documentation initiale |
| **Phase 2** | **Multi-Tenancy, Isolation RLS & RBAC** | **TERMINÉ** | Double barrière d'étanchéité, tests anti-IDOR, protection en-têtes forgés, gestion des membres et matrice RBAC, simulateur de sécurité interactif |
| **Phase 3** | **Gestion des Dossiers & Documents** | **TERMINÉ** | Arborescence récursive, déplacement interactif, prévention des cycles, duplication, actions groupées, moteur de recherche multi-critères |
| **Phase 4** | **Stockage S3 MinIO, Quotas & Antivirus** | **TERMINÉ** | Upload multipart streaming, URLs pré-signées, ClamAV fail-closed, calcul SHA-256, verrous quotas |
| **Phase 5** | **Partage Sécurisé & Permissions** | **TERMINÉ** | Partage d'utilisateur à utilisateur, liens publics tokenisés avec mot de passe et expiration, audit d'accès |
| **Phase 6** | **Versions, Corbeille & Prévisualisation** | **TERMINÉ** | Historique des révisions, restauration, libération de quota, purge automatique 30 jours, vider corbeille, visionneuse PDF.js paginée/zoom, tableur CSV/Excel, coloration syntaxique, Markdown sécurisé, LibreOffice headless |
| **Phase 7** | **Notifications, Facturation & Administration**| **TERMINÉ** | Centre de notifications in-app/e-mail (seuils 80%/100%), souscription Stripe (Free/Personal/Premium), webhooks HMAC-SHA256, restriction fail-safe lecture seule, console Superadmin avec gestion utilisateurs et export d'audit CSV/JSON |
| **Phase 8** | **RGPD, Sauvegardes & Déploiement Debian** | **TERMINÉ** | Export d'archive intégrale de portabilité RGPD (Art. 20), droit à l'effacement et purge de compte (Art. 17), scripts automatisés de sauvegarde pg_dump + MinIO S3 avec sommes SHA-256 et rotation 14 jours, guide complet de déploiement Debian 12 Bookworm durci (UFW, Fail2ban, Nginx SSL Let's Encrypt) |
