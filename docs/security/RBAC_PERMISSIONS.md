# DocuSpace — Rôles et Permissions Granulaires (RBAC)

## 1. Principes du Moindre Privilège

L'accès à chaque ressource documentaire est soumis à un contrôle basé sur les rôles (**Role-Based Access Control - RBAC**). 
Aucune action de modification, suppression ou partage ne peut être exécutée sans que le rôle du membre ne contienne explicitement la permission requise.

---

## 2. Rôles Disponibles

| Rôle | Libellé | Périmètre et Responsabilités |
|---|---|---|
| **`OWNER`** | Propriétaire de l'espace | Contrôle total du tenant, gestion des forfaits, invitation et révocation de membres, suppression et purge de documents, consultation d'audit. |
| **`EDITOR`** | Éditeur | Téléversement de nouveaux documents, création et organisation des dossiers, partage avec d'autres utilisateurs. |
| **`VIEWER`** | Lecteur | Consultation et téléchargement des documents en lecture seule. Toute tentative de téléversement, renommage ou suppression est rejetée (403 Forbidden). |
| **`GUEST`** | Invité | Accès restreint en lecture seule aux seuls documents explicitement partagés. |

---

## 3. Matrice des Permissions Granulaires

| Permission | Description | OWNER | EDITOR | VIEWER | GUEST |
|---|---|:---:|:---:|:---:|:---:|
| `document:read` | Consultation et téléchargement des fichiers | ✅ | ✅ | ✅ | ✅ |
| `document:write` | Téléversement et ajout de nouveaux fichiers | ✅ | ✅ | ❌ | ❌ |
| `document:delete` | Déplacement en corbeille et purge | ✅ | ❌ | ❌ | ❌ |
| `document:share` | Création de liens partagés et invitations | ✅ | ✅ | ❌ | ❌ |
| `document:restore`| Rétablissement de versions antérieures | ✅ | ❌ | ❌ | ❌ |
| `folder:create` | Création de sous-dossiers | ✅ | ✅ | ❌ | ❌ |
| `folder:manage` | Renommage et déplacement de dossiers | ✅ | ✅ | ❌ | ❌ |
| `member:invite` | Invitation de nouveaux membres dans le tenant | ✅ | ❌ | ❌ | ❌ |
| `member:manage` | Modification des rôles et suppression de membres | ✅ | ❌ | ❌ | ❌ |
| `tenant:settings`| Modification du forfait et options de l'espace | ✅ | ❌ | ❌ | ❌ |
| `audit:read` | Consultation des journaux d'accès et d'audit | ✅ | ❌ | ❌ | ❌ |

---

## 4. Vérification Systématique côté Backend

Toutes les routes FastAPI sensibles appliquent la dépendance de sécurité :
```python
@router.post("/documents/upload", tags=["Documents"])
async def upload_document(
    ctx: TenantContext = Depends(require_permission(Permission.DOCUMENT_WRITE))
):
    ...
```
Le frontend adapte son interface visuellement mais n'a **aucune autorité** : même en cas de requête curl ou de script forgé, l'API backend rejette l'appel avec un code **`403 FORBIDDEN`**.
