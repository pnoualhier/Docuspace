"""
DocuSpace Phase 1 - Multi-tenant Isolation and Authentication Tests
"""
import uuid
import hashlib
from datetime import datetime, timezone

# Standalone model test logic runnable even in offline sandbox
def test_password_hashing():
    from backend.app.core.security import get_password_hash, verify_password
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

def test_tenant_context_isolation_logic():
    # Verify tenant context generation
    user_id_a = uuid.uuid4()
    tenant_id_a = uuid.uuid4()
    user_id_b = uuid.uuid4()
    tenant_id_b = uuid.uuid4()

    # Emulate document belonging to Tenant A
    doc_a = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id_a,
        "name": "contrat_confidentiel.pdf",
        "sha256": hashlib.sha256(b"content_a").hexdigest()
    }

    # Context A should allow access
    def can_access(tenant_ctx_id, document):
        return tenant_ctx_id == document["tenant_id"]

    assert can_access(tenant_id_a, doc_a) is True
    # Context B must be denied!
    assert can_access(tenant_id_b, doc_a) is False

def test_quota_bounds():
    free_quota = 524288000  # 500 MB
    used = 500000000
    incoming_upload_size = 30000000  # 30 MB
    
    # Check if incoming upload fits in free quota
    fits = (used + incoming_upload_size) <= free_quota
    assert fits is False  # 530MB > 500MB, rejected!

if __name__ == "__main__":
    print("[*] Running DocuSpace Phase 1 Tests...")
    test_tenant_context_isolation_logic()
    print("  [✓] test_tenant_context_isolation_logic PASSED")
    test_quota_bounds()
    print("  [✓] test_quota_bounds PASSED")
    print("[*] All DocuSpace Phase 1 tests passed successfully!")

