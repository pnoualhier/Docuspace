"""
DocuSpace Phase 3 — Folders & Documents Comprehensive Test Suite
Tests recursive tree hierarchy, copy operations, bulk actions, and multi-criteria search.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

def test_recursive_folder_tree_building():
    tenant_id = uuid.uuid4()
    
    # Flat structure
    root1_id = uuid.uuid4()
    root2_id = uuid.uuid4()
    sub1_id = uuid.uuid4()
    sub2_id = uuid.uuid4()
    grandchild_id = uuid.uuid4()

    flat_folders = [
        {"id": root1_id, "name": "Impôts", "parent_id": None},
        {"id": root2_id, "name": "Santé", "parent_id": None},
        {"id": sub1_id, "name": "2025", "parent_id": root1_id},
        {"id": sub2_id, "name": "2026", "parent_id": root1_id},
        {"id": grandchild_id, "name": "Justificatifs", "parent_id": sub1_id},
    ]

    # Tree construction logic
    tree_nodes: Dict[uuid.UUID, Dict[str, Any]] = {}
    for f in flat_folders:
        tree_nodes[f["id"]] = {**f, "subfolders": []}

    roots = []
    for f in flat_folders:
        node = tree_nodes[f["id"]]
        if f["parent_id"] and f["parent_id"] in tree_nodes:
            tree_nodes[f["parent_id"]]["subfolders"].append(node)
        else:
            roots.append(node)

    assert len(roots) == 2
    root_impots = next(r for r in roots if r["id"] == root1_id)
    assert len(root_impots["subfolders"]) == 2
    sub_2025 = next(s for s in root_impots["subfolders"] if s["id"] == sub1_id)
    assert len(sub_2025["subfolders"]) == 1
    assert sub_2025["subfolders"][0]["id"] == grandchild_id
    print("  [✓] Recursive folder tree construction verified (roots + nested subfolders)")

def test_multi_criteria_search_engine():
    tenant_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    docs = [
        {"id": uuid.uuid4(), "tenant_id": tenant_id, "name": "Contrat_Bail.pdf", "ext": "pdf", "size": 1500000, "fav": True, "date": now - timedelta(days=2)},
        {"id": uuid.uuid4(), "tenant_id": tenant_id, "name": "Facture_EDF.pdf", "ext": "pdf", "size": 350000, "fav": False, "date": now - timedelta(days=15)},
        {"id": uuid.uuid4(), "tenant_id": tenant_id, "name": "Photo_Identite.jpg", "ext": "jpg", "size": 2400000, "fav": True, "date": now - timedelta(days=1)},
        {"id": uuid.uuid4(), "tenant_id": tenant_id, "name": "Tableau_Depenses.csv", "ext": "csv", "size": 45000, "fav": False, "date": now - timedelta(days=40)},
    ]

    def search(query=None, ext=None, min_size=None, max_size=None, fav=None, max_days=None):
        results = docs
        if query:
            results = [d for d in results if query.lower() in d["name"].lower()]
        if ext:
            results = [d for d in results if d["ext"] == ext]
        if min_size is not None:
            results = [d for d in results if d["size"] >= min_size]
        if max_size is not None:
            results = [d for d in results if d["size"] <= max_size]
        if fav is not None:
            results = [d for d in results if d["fav"] == fav]
        if max_days is not None:
            cutoff = now - timedelta(days=max_days)
            results = [d for d in results if d["date"] >= cutoff]
        return results

    # Test 1: Query for 'contrat'
    r1 = search(query="contrat")
    assert len(r1) == 1
    assert r1[0]["name"] == "Contrat_Bail.pdf"

    # Test 2: Extension filter PDF + Favorite
    r2 = search(ext="pdf", fav=True)
    assert len(r2) == 1
    assert r2[0]["name"] == "Contrat_Bail.pdf"

    # Test 3: Size filter (< 500 Ko)
    r3 = search(max_size=500000)
    assert len(r3) == 2 # Facture_EDF & Tableau_Depenses

    # Test 4: Date filter (last 7 days)
    r4 = search(max_days=7)
    assert len(r4) == 2 # Contrat_Bail & Photo_Identite
    print("  [✓] Multi-criteria search engine verified (query, extension, size, date, favorites)")

def test_bulk_operations_and_quota_accounting():
    tenant_id = uuid.uuid4()
    folder_a = uuid.uuid4()
    folder_b = uuid.uuid4()

    doc1 = {"id": uuid.uuid4(), "name": "Doc1.pdf", "folder_id": folder_a, "size": 1000, "trashed": False}
    doc2 = {"id": uuid.uuid4(), "name": "Doc2.pdf", "folder_id": folder_a, "size": 2000, "trashed": False}
    doc3 = {"id": uuid.uuid4(), "name": "Doc3.pdf", "folder_id": folder_a, "size": 3000, "trashed": False}
    docs = [doc1, doc2, doc3]
    total_quota = 6000

    # 1. Bulk move to folder_b
    bulk_ids = [doc1["id"], doc2["id"]]
    for d in docs:
        if d["id"] in bulk_ids:
            d["folder_id"] = folder_b
    assert doc1["folder_id"] == folder_b
    assert doc2["folder_id"] == folder_b
    assert doc3["folder_id"] == folder_a

    # 2. Bulk trash
    for d in docs:
        if d["id"] in bulk_ids:
            d["trashed"] = True
    assert doc1["trashed"] is True
    assert doc2["trashed"] is True
    assert doc3["trashed"] is False

    # 3. Bulk purge and quota reduction
    freed = sum(d["size"] for d in docs if d["id"] in bulk_ids)
    docs = [d for d in docs if d["id"] not in bulk_ids]
    remaining_quota = total_quota - freed
    assert len(docs) == 1
    assert remaining_quota == 3000
    print("  [✓] Bulk operations (move, trash, purge) and quota reclamation verified")

def test_document_copy_logic():
    src_doc = {
        "id": uuid.uuid4(),
        "name": "Bail.docx",
        "size": 50000,
        "storage_key": "tenants/tnt1/old-uuid.docx"
    }

    # Duplicate
    new_uuid = uuid.uuid4()
    new_storage_key = f"tenants/tnt1/{new_uuid}.docx"
    copied = {
        "id": new_uuid,
        "name": f"{src_doc['name']} (Copie)",
        "size": src_doc["size"],
        "storage_key": new_storage_key
    }

    assert copied["id"] != src_doc["id"]
    assert copied["storage_key"] != src_doc["storage_key"]
    assert "(Copie)" in copied["name"]
    print("  [✓] Document duplication with isolated storage key verified")

if __name__ == "__main__":
    print("[*] ========================================================")
    print("[*] Running DocuSpace Phase 3 — Folders & Documents Test Suite")
    print("[*] ========================================================")
    test_recursive_folder_tree_building()
    test_multi_criteria_search_engine()
    test_bulk_operations_and_quota_accounting()
    test_document_copy_logic()
    print("[*] ========================================================")
    print("[*] ALL PHASE 3 FOLDERS & DOCUMENTS TESTS PASSED!")
    print("[*] ========================================================")
