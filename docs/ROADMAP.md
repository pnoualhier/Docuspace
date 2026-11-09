# DocuSpace — Feuille de Route par Phases

| Phase | Intitulé | Statut | Objectifs Clés |
|---|---|---|---|
| **Phase 1** | **Architecture & Socle Initial** | **TERMINÉ** | Monolithe modulaire, Docker Compose, PostgreSQL 16, RLS, Alembic, FastAPI, React 19, Argon2id, documentation initiale |
| **Phase 2** | **Multi-Tenancy, Isolation RLS & RBAC** | **TERMINÉ** | Double barrière d'étanchéité, tests anti-IDOR, protection en-têtes forgés, gestion des membres et matrice RBAC, simulateur de sécurité interactif |
| **Phase 3** | **Gestion des Dossiers & Documents** | Suivant | Arborescence récursive, déplacement, renommage, favoris, tris, filtres, drag & drop |
| **Phase 4** | **Stockage S3 MinIO, Quotas & Antivirus** | Planifié | Upload multipart streaming, URLs pré-signées, ClamAV fail-closed, calcul SHA-256, verrous quotas |
| **Phase 5** | **Partage Sécurisé & Permissions** | Planifié | Partage d'utilisateur à utilisateur, liens publics tokenisés avec mot de passe et expiration, audit d'accès |
| **Phase 6** | **Versions, Corbeille & Prévisualisation** | Planifié | Historique des révisions, restauration, purge automatique 30 jours, visionneuse PDF.js, tableur, LibreOffice |
| **Phase 7** | **Notifications, Facturation & Administration**| Planifié | Console d'administration globale, simulation Stripe, alertes de quotas, journal d'audit complet |
| **Phase 8** | **RGPD, Sauvegardes & Déploiement Debian** | Planifié | Export d'archive RGPD, purge de compte, rotation automatisée des sauvegardes, durcissement serveur |
