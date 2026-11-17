# DocuSpace 🛡️📁

> **Plateforme SaaS B2C de gestion documentaire personnelle, stockage chiffré, multi-tenant et partage sécurisé.**

Conçue comme un **monolithe modulaire multi-tenant**, DocuSpace garantit une souveraineté totale des données personnelles grâce à l'isolation par tenant et à la sécurité au niveau des lignes de base de données (**PostgreSQL Row-Level Security**).

---

## 🚀 Fonctionnalités Clés

- **Architecture Modulaire Multi-Tenant** : Chaque utilisateur dispose d'un espace documentaire étanche, avec contexte PostgreSQL RLS dédié (`FORCE ROW LEVEL SECURITY`).
- **Sécurité Fail-Closed** : Hachage de mot de passe par **Argon2id**, sessions persistées avec rotation et révocation, cookies HttpOnly, en-têtes HTTP stricts, contrôle d'intégrité SHA-256.
- **Stockage S3 / MinIO** : Clés de stockage aléatoires, streaming direct par blocs, réconciliation des quotas en PostgreSQL.
- **Protection Antivirus ClamAV Fail-Closed** : Scan systématique en flux avec mise en quarantaine isolée et blocage strict de tout fichier non analysé (`SCAN_ERROR` / `INFECTED`).
- **Gestion des Quotas Transactionnels** : Suivi atomique des octets réservés et consommés selon les forfaits en base (Gratuit 500 Mo, Personnel 20 Go, Premium 100 Go).
- **Partage Persisté en PostgreSQL** : Liens publics hachés SHA-256, protection par mot de passe Argon2id, limite atomique de téléchargements et journaux d'audit.
- **Interface Utilisateur Moderne (React 19, TypeScript, Tailwind CSS)** : Navigation fluide, visualiseur de documents, glisser-déposer et console d'administration.

---

## 🛠️ Stack Technique

- **Frontend** : React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Motion.
- **Backend** : Python 3.11, FastAPI, SQLAlchemy 2 (Async), Pydantic v2, Alembic.
- **Base de données** : PostgreSQL 16 avec extensions `uuid-ossp`, `pgcrypto` et RLS (`FORCE ROW LEVEL SECURITY`).
- **Stockage Objets** : MinIO S3-compatible (réseau interne uniquement).
- **Antivirus & Cache** : ClamAV Daemon & Redis 7 (réseau interne uniquement).
- **Déploiement** : Docker & Docker Compose sur Debian 12 avec Nginx en reverse proxy (seuls les ports 80/443 sont exposés).

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

## 📚 Documentation Détaillée

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
