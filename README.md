# DocuSpace 🛡️📁

> **Plateforme SaaS B2C de gestion documentaire personnelle, stockage chiffré, multi-tenant et partage sécurisé.**

Conçue comme un **monolithe modulaire multi-tenant**, DocuSpace garantit une souveraineté totale des données personnelles grâce à l'isolation par tenant et à la sécurité au niveau des lignes de base de données (**PostgreSQL Row-Level Security**).

---

## 🚀 Fonctionnalités Clés (Phase 1 & Architecture)

- **Architecture Modulaire Multi-Tenant** : Chaque utilisateur dispose d'un espace documentaire étanche, avec contexte PostgreSQL RLS dédié.
- **Sécurité Fail-Closed** : Hachage de mot de passe par **Argon2id**, sessions sécurisées, en-têtes HTTP stricts, contrôle d'intégrité SHA-256.
- **Stockage S3 / MinIO** : Clés de stockage opaques (noms internes UUID), URLs pré-signées, streaming direct.
- **Protection Antivirus ClamAV** : Scan systématique en flux pour neutraliser toute menace avant mise à disposition.
- **Gestion des Quotas Transactionnels** : Suivi fin des octets réservés et consommés selon les forfaits (Gratuit 500 Mo, Personnel 20 Go, Premium 100 Go).
- **Interface Utilisateur Moderne (React 19, TypeScript, Tailwind CSS)** : Navigation fluide, visualiseur de documents (PDF, images, tableur, code), glisser-déposer, console d'administration et explorateur d'architecture intégrés.

---

## 🛠️ Stack Technique

- **Frontend** : React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Motion.
- **Backend** : Python 3.11, FastAPI, SQLAlchemy 2 (Async), Pydantic v2, Alembic.
- **Base de données** : PostgreSQL 16 avec extensions `uuid-ossp`, `pgcrypto` et RLS.
- **Stockage Objets** : MinIO S3-compatible.
- **Antivirus & Cache** : ClamAV Daemon & Redis 7.
- **Déploiement** : Docker & Docker Compose sur Debian 12 avec Nginx en reverse proxy.

---

## ⚡ Démarrage Rapide (Docker Compose sur Debian)

```bash
# 1. Générer automatiquement les variables d'environnement chiffrées
./scripts/init/generate_env.sh docker.env

# 2. Démarrer l'ensemble des services (Postgres, MinIO, ClamAV, Redis, Backend, Frontend, Nginx)
docker compose up -d --build

# 3. Appliquer les migrations de base de données
docker compose exec backend alembic upgrade head
```

L'application est disponible sur :
- **Application Web** : `http://localhost`
- **Documentation API (Swagger UI)** : `http://localhost/docs`
- **Console MinIO** : `http://localhost:9001`

---

## 📚 Documentation Détaillée

- [Architecture Globale](docs/architecture/ARCHITECTURE.md)
- [Modèle de Données & RLS](docs/architecture/DATABASE.md)
- [Politique de Sécurité & Antivirus](docs/security/SECURITY.md)
- [Isolation Multi-Tenant](docs/security/TENANT_ISOLATION.md)
- [Spécification de l'API REST](docs/api/API.md)
- [Guide d'Installation Debian 12](docs/deployment/INSTALL_DEBIAN.md)
- [Procédure de Sauvegarde et Restauration](docs/deployment/BACKUP_RESTORE.md)
- [Feuille de Route](docs/ROADMAP.md)
- [Stratégie de Tests](docs/TESTING.md)
