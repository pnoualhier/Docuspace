# DocuSpace 🛡️📁

> **Plateforme SaaS B2C de gestion documentaire personnelle, stockage chiffré, multi-tenant et partage sécurisé.**

Conçue comme un **monolithe modulaire multi-tenant**, DocuSpace garantit une souveraineté totale des données personnelles grâce à l'isolation par tenant et à la sécurité au niveau des lignes de base de données (**PostgreSQL Row-Level Security**).

---

## 🚀 Fonctionnalités Clés

- **Architecture Modulaire Multi-Tenant & RLS (`FORCE ROW LEVEL SECURITY`)** : Chaque utilisateur dispose d'un espace documentaire étanche sous rôle PostgreSQL non-privilégié (`NOSUPERUSER NOBYPASSRLS`) couvrant `tenants`, `folders`, `documents`, `document_versions`, `shares`, `share_recipients`, `notifications` et `quarantine_events`.
- **Sécurité Fail-Closed & Rate Limiting Distribué** : Hachage **Argon2id**, sessions avec rotation de `refresh_token` et révocation, cookies HttpOnly, en-têtes HTTP stricts, logs JSON structurés sans fuite de secrets, et limitation de débit distribuée via Redis (`SlidingRateLimiter`).
- **Stockage S3 / MinIO Fail-Closed** : SDK `minio.Minio` strict (HTTP 503 si indisponible), clés cryptographiques aléatoires, streaming par blocs (64 Ko), normalisation des noms (`sanitize_filename`), rejet des doubles extensions exécutables (`facture.exe.pdf`), copie S3/DB et réconciliation exacte documents + versions.
- **Protection Antivirus ClamAV Fail-Closed** : Scan systématique en flux (`zINSTREAM`) avec mise en quarantaine isolée persistée (`quarantine_events`) et blocage strict de tout fichier non certifié (`SCAN_ERROR` / `INFECTED`).
- **Gestion des Dossiers, Versions, Corbeille & Quotas** : Arborescence récursive sans cycles, suppression récursive avec désactivation des partages, historique des versions borné par forfait (`Plan.max_versions_per_file`), corbeille 30 jours avec purge MinIO et restitution de quota atomique.
- **Partage Persisté en PostgreSQL** : Partages internes (`set_user_recipient_context` RLS) et liens publics hachés SHA-256 avec mot de passe Argon2id, limite de téléchargements, expiration et modification via `PATCH /api/v1/shares/{share_id}`.
- **Facturation, Notifications, Admin & RGPD** : Abonnements Stripe (webhooks HMAC-SHA256, mode lecture seule automatique sur dépassement), notifications in-app sous RLS (seuils 80%/100%), console Superadmin (export CSV protégé contre l'injection de formules) et conformité RGPD (Art. 17 & 20).
- **Interface Utilisateur Moderne (React 19, TypeScript, Tailwind CSS)** : Zéro popup native (`ConfirmActionModal`, `RenameModal` accessibles), progression XHR temps réel, client API synchronisé (`src/services/api.ts`) et mode aperçu hors-ligne.

---

## 🛠️ Stack Technique

- **Frontend** : React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Motion, Vitest.
- **Backend** : Python 3.11, FastAPI, SQLAlchemy 2 (Async), Pydantic v2, Alembic (`0008_notif_rls_quarantine`).
- **Base de données** : PostgreSQL 16 avec extensions `uuid-ossp`, `pgcrypto` et `FORCE ROW LEVEL SECURITY`.
- **Stockage Objets** : MinIO S3-compatible (réseau interne uniquement).
- **Antivirus & Cache** : ClamAV Daemon & Redis 7 (réseau interne uniquement).
- **Déploiement & CI/CD** : Docker & Docker Compose sur Debian 12/13 avec Nginx en reverse proxy (seuls les ports 80/443 sont exposés), GitHub Actions (`backend-real-services`, `frontend-tests-and-build`, `docker-validation`).

---

## ⚡ Démarrage Rapide (Docker Compose sur Debian)

```bash
# 1. Générer automatiquement les secrets cryptographiques dans .env (mode 600)
chmod +x scripts/init/generate_env.sh
./scripts/init/generate_env.sh

# 2. Démarrer l'ensemble des services (Postgres, MinIO, ClamAV, Redis, Backend, Frontend, Nginx)
docker compose up -d --build

# 3. Appliquer les migrations de base de données (incluant RLS et forfaits)
docker compose exec backend alembic upgrade head
```

L'application est disponible uniquement via le reverse proxy Nginx :
- **Application Web** : `http://localhost` (ou `https://<votre-domaine>`)
- **Documentation API (Swagger UI)** : `http://localhost/docs`
- **Sonde de santé API** : `http://localhost/api/v1/health`

> Les services internes (**PostgreSQL**, **Redis**, **MinIO**, **ClamAV**, **Backend**, **Frontend**) sont isolés sur les réseaux Docker internes (`docuspace-internal` / `docuspace-edge`) et ne sont pas exposés publiquement.

---

## 🧪 Tests & Vérification

```bash
# Backend (93 tests : unitaires, PostgreSQL RLS réel, Redis réel, pg_dump/pg_restore)
python3 -m pytest backend/tests/ -v

# Frontend (10 tests Vitest, contrôle TypeScript & build production)
npm test
npm run lint
npm run build
```

---

## 📚 Documentation Détaillée

- [Contexte Technique & État du Projet](CONTEXT.md)
- [Journal des Modifications (Changelog)](CHANGELOG.md)
- [Architecture Globale](docs/architecture/ARCHITECTURE.md)
- [Modèle de Données & RLS](docs/architecture/DATABASE.md)
- [Politique de Sécurité & Antivirus](docs/security/SECURITY.md)
- [Isolation Multi-Tenant](docs/security/TENANT_ISOLATION.md)
- [Spécification de l'API REST](docs/api/API.md)
- [Guide d'Installation Debian 12](docs/deployment/INSTALL_DEBIAN.md)
- [Durcissement & Production Debian 12](docs/deployment/DEBIAN_PRODUCTION.md)
- [Procédure de Sauvegarde et Restauration](docs/deployment/BACKUP_RESTORE.md)
- [Feuille de Route](docs/ROADMAP.md)
- [Stratégie de Tests](docs/TESTING.md)
