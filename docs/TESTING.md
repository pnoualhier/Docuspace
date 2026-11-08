# DocuSpace — Stratégie de Tests

## 1. Niveaux de Tests

1. **Tests Unitaires (`backend/tests/`)** :
   - Hachage de mot de passe Argon2id et vérification.
   - Algorithmes de contrôle de cycle sur les répertoires.
   - Validation des calculs d'empreinte SHA-256.
   - Respect strict des limites de quotas de stockage.

2. **Tests d'Intégration & Multi-Tenancy** :
   - Isolation inter-tenants : vérification formelle qu'une requête effectuée avec le contexte du Tenant A ne peut en aucun cas lire ou modifier une ressource appartenant au Tenant B.
   - Déclenchement des politiques PostgreSQL Row-Level Security (RLS).
   - Validation de la résiliation de session et suppression des cookies HttpOnly.

3. **Exécution des Tests** :
   ```bash
   # Dans le conteneur backend ou environnement Python local :
   pytest -v backend/tests
   ```
