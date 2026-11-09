# DocuSpace — Isolation Multi-Tenant & Row-Level Security (RLS)

## 1. Principes Fondamentaux
1. **Zéro confiance envers le client** : Aucun `tenant_id` envoyé par le client n'est réputé authentique sans validation d'appartenance préalable en base de données dans la table `tenant_members`.
2. **Double barrière de défense** :
   - **Couche Middleware FastAPI** : vérification formelle de l'association de l'utilisateur avec le tenant demandé. Rejet immédiat par `403 Forbidden` en cas d'en-tête `X-Tenant-ID` falsifié.
   - **Couche Moteur PostgreSQL (RLS)** : Politiques de Row-Level Security activées sur toutes les tables de données.

## 2. Déroulement Transactionnel & PostgreSQL RLS
1. Le client présente son jeton JWT Bearer ou son cookie HttpOnly `access_token`.
2. Le middleware FastAPI décode le jeton et extrait le `user_id`.
3. Si un en-tête `X-Tenant-ID` est spécifié, l'API valide l'appartenance dans `tenant_members`. Si l'en-tête est omis, l'API sélectionne le tenant personnel de l'utilisateur.
4. Dans la transaction SQLAlchemy, la variable de session PostgreSQL est initialisée :
   ```sql
   SET LOCAL app.current_tenant_id = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx';
   ```
5. En fin de transaction ou lors de la libération de connexion au pool, la commande `RESET app.current_tenant_id` est exécutée pour éliminer tout risque de fuite inter-requêtes.
6. Même si une requête SQL omet accidentellement une clause `WHERE tenant_id = ...`, PostgreSQL RLS n'autorise l'accès qu'aux lignes correspondant à `app_tenant_id()`.

## 3. Protection Anti-IDOR (Insecure Direct Object Reference)
Toute tentative d'accès direct à un document (`/api/v1/documents/{document_id}`) appartenant à un autre tenant échoue systématiquement :
- L'identifiant demandé est filtré par le contexte du tenant actif.
- La réponse retournée est systématiquement un **`404 Not Found`** ou **`403 Forbidden`**, sans révéler l'existence ou les métadonnées du document cible à l'attaquant.

## 4. Prévention des Cycles et Barrières Transversales
Lors du déplacement d'un dossier :
- Une vérification récursive ascendante interdit qu'un dossier devienne son propre parent ou l'enfant d'un de ses sous-dossiers.
- Les dossiers source et destination doivent obligatoirement appartenir au même `tenant_id` sous peine de rejet immédiat.

