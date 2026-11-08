# DocuSpace — Modèle de Données & Schéma PostgreSQL

## 1. Schéma Relationnel

Toutes les entités primaires utilisent des identifiants **UUID v4** générés via `gen_random_uuid()` et des horodatages `TIMESTAMPTZ`.

### 1.1 Tables Principales

1. **`plans`** : Plans de souscription (FREE: 500 Mo / 25 Mo max, PERSONAL: 20 Go / 250 Mo max, PREMIUM: 100 Go / 1 Go max).
2. **`users`** : Comptes d'utilisateurs avec empreintes Argon2id, statuts de vérification et rôles d'administration globale.
3. **`sessions`** : Sessions actives avec révocation unitaire, empreinte de jeton de rafraîchissement, IP et User-Agent.
4. **`tenants`** : Espaces documentaires isolés. Chaque utilisateur se voit attribuer un espace personnel dès son inscription.
5. **`tenant_members`** : Rôles au sein d'un tenant (`OWNER`, `EDITOR`, `VIEWER`, `GUEST`).
6. **`storage_usage`** : Suivi en temps réel des octets consommés (`used_bytes`), réservés (`reserved_bytes`) et du quota maximal.
7. **`folders`** : Arborescence hiérarchique avec détection de cycles et contrainte d'unicité `(tenant_id, parent_id, name)`.
8. **`documents`** : Métadonnées documentaires (nom original, clé de stockage opaque S3, hash SHA-256, type MIME certifié, statut ClamAV).
9. **`document_versions`** : Historique versionné avec conservation de la taille et du hash cryptographique.
10. **`shares`** & **`share_recipients`** : Partages ciblés ou liens sécurisés protégés par token cryptographique, mot de passe et limite d'accès.
11. **`audit_logs`** : Journalisation d'audit immuable des accès et actions critiques.

---

## 2. PostgreSQL Row-Level Security (RLS)

L'isolation multi-tenant est garantie à deux niveaux :
1. **Niveau Applicatif** : Résolution du `tenant_id` à partir de l'identité du jeton JWT.
2. **Niveau Base de Données (RLS)** : Dans chaque transaction, le middleware exécute :
   ```sql
   SET LOCAL app.current_tenant_id = '<uuid_tenant>';
   ```
   Les politiques PostgreSQL filtrent automatiquement les lignes :
   ```sql
   CREATE POLICY tenant_isolation_documents ON documents
       FOR ALL
       USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID 
              OR current_setting('app.is_superuser', true) = 'true');
   ```
   Toute tentative de sélection croisée est rejetée par le moteur PostgreSQL, même en cas de bug de filtrage dans une requête SQL applicative.
