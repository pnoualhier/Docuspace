# DocuSpace — Spécification de l'API REST v1

Base URL: `/api/v1`

## 1. Authentification (`/api/v1/auth`)

### POST `/api/v1/auth/register`
Crée un compte utilisateur et initialise son espace documentaire personnel de manière transactionnelle.
- **Corps** : `{ "email": "user@example.com", "password": "...", "full_name": "Jean Dupont" }`
- **Réponse** : 201 Created `{ "id": "...", "email": "...", "full_name": "..." }`

### POST `/api/v1/auth/login`
Authentifie l'utilisateur via Argon2id et délivre les jetons d'accès et cookies HttpOnly.
- **Corps** : `{ "email": "user@example.com", "password": "..." }`
- **Réponse** : 200 OK `{ "access_token": "...", "token_type": "bearer", "user_id": "...", "tenant_id": "..." }`

### POST `/api/v1/auth/logout`
Révoque la session et purge les cookies sécurisés.

### GET `/api/v1/auth/me`
Retourne le profil de l'utilisateur connecté.

---

## 2. Espaces & Tenants (`/api/v1/tenants`)

### GET `/api/v1/tenants/my-tenants`
Liste tous les espaces documentaires accessibles à l'utilisateur.

### GET `/api/v1/tenants/current`
Fournit l'état détaillé de l'espace courant et l'utilisation de son quota (`used_bytes`, `reserved_bytes`, `max_storage_bytes`).

### GET `/api/v1/tenants/plans`
Liste les forfaits disponibles (Gratuit 500 Mo, Personnel 20 Go, Premium 100 Go).

---

## 3. Dossiers & Documents (`/api/v1/documents`)

### GET `/api/v1/documents/folders`
Liste les dossiers filtrés par `parent_id` et statut `is_trashed`.

### POST `/api/v1/documents/folders`
Crée un dossier dans l'espace actif avec contrôle de cycle et contrainte d'unicité.

### GET `/api/v1/documents/documents`
Liste les fichiers d'un dossier avec pagination, filtres et tri.

### POST `/api/v1/documents/upload/initiate`
Initie une session d'upload, réserve les octets de quota et retourne l'URL pré-signée S3.

### POST `/api/v1/documents/upload/finalize`
Valide le transfert MinIO, calcule l'empreinte SHA-256 et déclenche l'analyse ClamAV.
