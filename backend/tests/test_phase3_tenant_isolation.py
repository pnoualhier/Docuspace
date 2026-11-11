import uuid
import pytest
from datetime import datetime, timezone
from backend.app.middleware.tenant_context import TenantContext, Permission, ROLE_PERMISSIONS

class FakeUser:
    def __init__(self, id_str: str, email: str, is_superuser: bool = False):
        self.id = uuid.UUID(id_str)
        self.email = email
        self.is_superuser = is_superuser

class FakeTenant:
    def __init__(self, id_str: str, name: str, owner_id: uuid.UUID):
        self.id = uuid.UUID(id_str)
        self.name = name
        self.owner_id = owner_id
        self.is_active = True

class InMemoryMultiTenantRepository:
    """Simulates PostgreSQL tables with RLS and composite tenant constraints."""
    def __init__(self):
        self.documents = {} # id -> dict
        self.folders = {}   # id -> dict
        self.shares = {}    # id -> dict

    def add_folder(self, tenant_id: uuid.UUID, folder_id: uuid.UUID, name: str, parent_id: uuid.UUID = None):
        if parent_id and parent_id in self.folders:
            if self.folders[parent_id]["tenant_id"] != tenant_id:
                raise ValueError("Violation de contrainte RLS: Impossible d'associer un dossier à un parent d'un autre tenant.")
        self.folders[folder_id] = {
            "id": folder_id,
            "tenant_id": tenant_id,
            "name": name,
            "parent_id": parent_id,
            "is_trashed": False
        }

    def add_document(self, tenant_id: uuid.UUID, doc_id: uuid.UUID, name: str, folder_id: uuid.UUID = None):
        if folder_id and folder_id in self.folders:
            if self.folders[folder_id]["tenant_id"] != tenant_id:
                raise ValueError("Violation de contrainte RLS: Le document et le dossier doivent appartenir au même tenant.")
        self.documents[doc_id] = {
            "id": doc_id,
            "tenant_id": tenant_id,
            "folder_id": folder_id,
            "name": name,
            "is_trashed": False
        }

    def get_document(self, ctx: TenantContext, doc_id: uuid.UUID):
        doc = self.documents.get(doc_id)
        if not doc:
            return None
        # RLS Engine Filtering:
        if not ctx.user.is_superuser and doc["tenant_id"] != ctx.tenant_id:
            return None # Hidden by PostgreSQL Row-Level Security
        return doc

    def delete_document(self, ctx: TenantContext, doc_id: uuid.UUID):
        doc = self.get_document(ctx, doc_id)
        if not doc:
            raise PermissionError("Accès refusé ou document introuvable")
        del self.documents[doc_id]
        return True

    def move_document(self, ctx: TenantContext, doc_id: uuid.UUID, target_folder_id: uuid.UUID):
        doc = self.get_document(ctx, doc_id)
        if not doc:
            raise PermissionError("Accès refusé au document")
        target_folder = self.folders.get(target_folder_id)
        if not target_folder or target_folder["tenant_id"] != ctx.tenant_id:
            raise ValueError("Tentative d'évasion multi-tenant: Dossier cible invalide ou appartenant à un autre tenant.")
        doc["folder_id"] = target_folder_id
        return True

    def search_documents(self, ctx: TenantContext, query: str):
        results = []
        for doc in self.documents.values():
            if not ctx.user.is_superuser and doc["tenant_id"] != ctx.tenant_id:
                continue
            if query.lower() in doc["name"].lower():
                results.append(doc)
        return results


def test_phase3_two_users_two_tenants_isolation():
    """Verify that User A cannot read, modify or delete User B's documents."""
    repo = InMemoryMultiTenantRepository()

    user_a = FakeUser("11111111-1111-1111-1111-111111111111", "alice@example.com")
    tenant_a = FakeTenant("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Espace Alice", user_a.id)
    ctx_a = TenantContext(user=user_a, tenant=tenant_a, role="OWNER", db=None)

    user_b = FakeUser("22222222-2222-2222-2222-222222222222", "bob@example.com")
    tenant_b = FakeTenant("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "Espace Bob", user_b.id)
    ctx_b = TenantContext(user=user_b, tenant=tenant_b, role="OWNER", db=None)

    # Bob creates a document in Tenant B
    doc_b_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    repo.add_document(tenant_b.id, doc_b_id, "Bilan_Financier_Confidentiel_Bob.pdf")

    # 1. Direct UUID read attempt by Alice
    assert repo.get_document(ctx_b, doc_b_id) is not None
    assert repo.get_document(ctx_a, doc_b_id) is None, "Alice must NOT see Bob's document"

    # 2. Deletion attempt by Alice
    with pytest.raises(PermissionError):
        repo.delete_document(ctx_a, doc_b_id)

    # 3. Search isolation
    results_alice = repo.search_documents(ctx_a, "Bilan")
    assert len(results_alice) == 0, "Alice's search must never return Bob's files"

    results_bob = repo.search_documents(ctx_b, "Bilan")
    assert len(results_bob) == 1
    assert results_bob[0]["id"] == doc_b_id


def test_phase3_cross_tenant_folder_and_document_barriers():
    """Verify relational integrity constraints preventing cross-tenant links."""
    repo = InMemoryMultiTenantRepository()
    tenant_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    folder_a = uuid.UUID("44444444-4444-4444-4444-444444444444")
    folder_b = uuid.UUID("55555555-5555-5555-5555-555555555555")

    repo.add_folder(tenant_a, folder_a, "Dossier Alice")
    repo.add_folder(tenant_b, folder_b, "Dossier Bob")

    # Attempt to create folder in Tenant A with parent in Tenant B
    with pytest.raises(ValueError, match="Violation de contrainte RLS"):
        repo.add_folder(tenant_a, uuid.uuid4(), "Sous-dossier illégal", parent_id=folder_b)

    # Attempt to create document in Tenant A referencing folder in Tenant B
    with pytest.raises(ValueError, match="Violation de contrainte RLS"):
        repo.add_document(tenant_a, uuid.uuid4(), "Fichier illégal", folder_id=folder_b)


def test_phase3_move_document_across_tenants_blocked():
    """Verify moving document into another tenant's folder raises security exception."""
    repo = InMemoryMultiTenantRepository()

    user_a = FakeUser("11111111-1111-1111-1111-111111111111", "alice@example.com")
    tenant_a = FakeTenant("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Espace Alice", user_a.id)
    ctx_a = TenantContext(user=user_a, tenant=tenant_a, role="OWNER", db=None)

    folder_a = uuid.UUID("44444444-4444-4444-4444-444444444444")
    folder_b = uuid.UUID("55555555-5555-5555-5555-555555555555")
    repo.add_folder(tenant_a.id, folder_a, "Dossier Alice")
    repo.add_folder(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), folder_b, "Dossier Bob")

    doc_a = uuid.UUID("66666666-6666-6666-6666-666666666666")
    repo.add_document(tenant_a.id, doc_a, "Document_Alice.pdf", folder_id=folder_a)

    with pytest.raises(ValueError, match="Tentative d'évasion multi-tenant"):
        repo.move_document(ctx_a, doc_a, folder_b)
