# DocuSpace — Architecture Globale

## 1. Vision et Modèle Architectural

**DocuSpace** est une plateforme SaaS de gestion documentaire personnelle B2C, conçue sous la forme d'un **monolithe modulaire multi-tenant**.

### 1.1 Objectifs
- **Souveraineté des données** : Isolation stricte de chaque utilisateur dans son espace documentaire (tenant).
- **Sécurité Fail-Closed** : Aucun fichier n'est téléchargeable ni accessible sans validation cryptographique et scan antivirus ClamAV préalable.
- **Portabilité** : Déploiement initial sur serveur local Debian via Docker Compose, avec architecture prête pour le cloud (AWS S3, Google Cloud Run, RDS PostgreSQL).
- **Performance & Scalabilité** : Streaming d'upload/download sans mise en cache intégrale en RAM, quotas gérés de façon transactionnelle avec verrous pessimistes.

---

## 2. Diagramme des Composants

```
[ Navigateur Client / React SPA ]
                │
                ▼
       [ Nginx Reverse Proxy ]
       (SSL, Rate Limiting, CSP)
        ├── / (Statique & SPA) ──▶ [ Frontend Vite / React 19 ]
        └── /api/v1/ ───────────▶ [ Backend FastAPI / Python ]
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                       ▼
      [ PostgreSQL 16 ]           [ MinIO S3 Object ]     [ ClamAV Daemon ]
       • Row-Level Security       • Bucket chiffré        • Scan de flux
       • Isolation Tenant         • Clés UUID opaques     • Quarantaine
       • Quotas & Métadonnées     • URLs pré-signées
```

---

## 3. Séparation Modulaire du Backend

Le backend FastAPI est découpé en modules étanches :
- **`app/core/`** : Configuration centralisée (`pydantic-settings`), sécurité (Argon2id, JWT), initialisation du moteur asynchrone SQLAlchemy 2.
- **`app/models/`** : Modèles de données déclaratifs SQLAlchemy avec typage UUID et contraintes d'intégrité référentielle.
- **`app/schemas/`** : Schémas de validation Pydantic v2 assurant l'étanchéité des entrées et sorties HTTP.
- **`app/middleware/tenant_context.py`** : Résolution infalsifiable de l'identité et du tenant, avec injection directe de la variable de session PostgreSQL `app.current_tenant_id`.
- **`app/api/v1/`** : Endpoints REST versionnés avec documentation OpenAPI automatique.
- **`app/storage/`** : Interface abstraite `StorageProvider` (MinIO pour le développement local, facilement commutable avec AWS S3).
