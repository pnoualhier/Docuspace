# DocuSpace — Stratégie de Tests

## 1. Niveaux de Tests

1. **Tests Unitaires (`backend/tests/`)** :
   - Hachage de mot de passe Argon2id et vérification.
   - Algorithmes de contrôle de cycle sur les répertoires.
   - Validation des calculs d'empreinte SHA-256.
   - Respect strict des limites de quotas de stockage.

2. **Tests d'Intégration & Multi-Tenancy (`backend/tests/test_multi_tenancy_security.py`)** :
   - `test_idor_cross_tenant_document_access_denied` : tentative d'accès direct par UUID à un document d'un autre tenant -> Rejet immédiat 403 Forbidden / 404 Not Found.
   - `test_forged_x_tenant_id_header_injection_denied` : injection d'un en-tête `X-Tenant-ID` malveillant -> Rejet immédiat 403 Forbidden.
   - `test_rbac_viewer_write_forbidden` : vérification que le rôle `VIEWER` ne peut en aucun cas importer, modifier ou supprimer un document.
   - `test_rbac_editor_administrative_forbidden` : vérification que le rôle `EDITOR` ne peut pas modifier les membres ou les paramètres administratifs du tenant.
   - `test_folder_tree_cycle_detection` : contrôle récursif interdisant les boucles d'arborescence (déplacement d'un dossier parent vers son sous-dossier).
   - `test_cross_tenant_folder_move_barrier` : barrière infranchissable empêchant le déplacement d'un dossier vers un tenant différent.
   - `test_rls_sql_query_filtering_simulation` : isolation PostgreSQL Row-Level Security au niveau de la requête SQL sans WHERE tenant_id.

3. **Exécution des Tests de Sécurité** :
   ```bash
   python3 backend/tests/test_multi_tenancy_security.py
   pytest -v backend/tests
   ```
