# DocuSpace — Isolation Multi-Tenant

## 1. Principes Fondamentaux
1. **Zéro confiance envers le client** : Aucun `tenant_id` envoyé par le client n'est réputé authentique sans validation d'appartenance préalable en base de données.
2. **Double barrière de défense** :
   - Couche Middleware FastAPI : vérification de l'association de l'utilisateur avec le tenant demandé dans `tenant_members`.
   - Couche Moteur PostgreSQL : Politiques de Row-Level Security (RLS) activées sur toutes les tables de données.

## 2. Déroulement d'une Requête
1. Le client présente un jeton JWT Bearer ou un cookie `access_token`.
2. Le middleware FastAPI décode le jeton et extrait le `user_id`.
3. Si un en-tête `X-Tenant-ID` est spécifié, l'API vérifie que l'utilisateur possède une entrée valide dans `tenant_members` pour ce tenant. Si l'en-tête est omis, l'API sélectionne le tenant personnel dont l'utilisateur est `OWNER`.
4. La transaction SQLAlchemy initialise immédiatement le contexte PostgreSQL :
   ```sql
   SET LOCAL app.current_tenant_id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx';
   ```
5. Toute requête SQL (y compris les jointures ou sous-requêtes) est restreinte aux données du tenant.

## 3. Prévention des Cycles dans les Dossiers
Lors du déplacement d'un dossier, une vérification récursive ascendante garantit qu'un dossier ne peut jamais devenir son propre parent ou l'enfant d'un de ses sous-dossiers. De plus, les dossiers source et destination doivent obligatoirement appartenir au même `tenant_id`.
