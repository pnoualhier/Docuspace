import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.app.models.document import Document, Folder
from backend.app.models.share import Share, ShareRecipient
from backend.app.models.audit import AuditLog
from backend.app.models.user import User
from backend.app.models.tenant import Tenant
from backend.app.middleware.tenant_context import TenantContext, Permission
from backend.app.schemas.share import (
    InternalShareCreate,
    SecureLinkCreate,
    PublicShareAccessRequest,
)
from backend.app.security.password import hash_share_token, share_rate_limiter
import backend.app.api.v1.routes.shares as shares_module
from backend.app.api.v1.routes.shares import (
    list_tenant_shares,
    create_internal_share,
    create_secure_link,
    revoke_share,
    list_received_shares,
    download_received_share,
    get_public_share_info,
    access_public_share,
    download_public_share,
)


def make_fake_request(ip: str = "203.0.113.10", ua: str = "DocuSpace-Test-Agent/1.0") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/shares",
        "headers": [(b"user-agent", ua.encode("utf-8"))],
        "client": (ip, 54321),
    }
    return Request(scope)


class InMemoryPostgresStore:
    """Shared relational store simulating PostgreSQL tables across independent sessions."""
    def __init__(self):
        self.users: Dict[uuid.UUID, User] = {}
        self.tenants: Dict[uuid.UUID, Tenant] = {}
        self.folders: Dict[uuid.UUID, Folder] = {}
        self.documents: Dict[uuid.UUID, Document] = {}
        self.shares: Dict[uuid.UUID, Share] = {}
        self.recipients: Dict[uuid.UUID, ShareRecipient] = {}
        self.audit_logs: List[AuditLog] = []


class StatefulAsyncSession:
    """
    Simulates independent AsyncSession connections backed by InMemoryPostgresStore.
    Enforces parameterized filtering and allows simulating DB commit failures.
    """
    def __init__(self, store: InMemoryPostgresStore, fail_on_commit: bool = False):
        self.store = store
        self.fail_on_commit = fail_on_commit
        self.pending: List[Any] = []
        self.committed = False
        self.rolled_back = False
        self.locked_for_update = False
        self.rls_vars: Dict[str, str] = {}

    def add(self, obj: Any):
        self.pending.append(obj)

    async def commit(self):
        if self.fail_on_commit:
            raise RuntimeError("PostgreSQL disk full / serialization failure simulated")
        now = datetime.now(timezone.utc)
        for obj in self.pending:
            if isinstance(obj, Share):
                if obj.created_at is None:
                    obj.created_at = now
                if obj.updated_at is None:
                    obj.updated_at = now
                if obj.recipients is None:
                    obj.recipients = []
                self.store.shares[obj.id] = obj
            elif isinstance(obj, ShareRecipient):
                if obj.created_at is None:
                    obj.created_at = now
                self.store.recipients[obj.id] = obj
                if obj.share_id in self.store.shares:
                    share = self.store.shares[obj.share_id]
                    if obj not in share.recipients:
                        share.recipients.append(obj)
            elif isinstance(obj, AuditLog):
                if obj.created_at is None:
                    obj.created_at = now
                self.store.audit_logs.append(obj)
        self.pending.clear()
        self.committed = True

    async def rollback(self):
        self.pending.clear()
        self.rolled_back = True

    async def refresh(self, obj: Any):
        pass

    async def execute(self, stmt, params: dict = None):
        stmt_str = str(stmt)
        stmt_lower = stmt_str.lower()

        if "set_config" in stmt_lower and params:
            for k, v in params.items():
                self.rls_vars[k] = str(v)
            class NoopRes:
                def scalar_one_or_none(self): return None
            return NoopRes()

        if "for update" in stmt_lower:
            self.locked_for_update = True

        # Compile literal/bound values from SQLAlchemy statement
        compiled = stmt.compile()
        bound_params = compiled.params

        def _extract_values():
            return list(bound_params.values())

        vals = _extract_values()

        class QueryResult:
            def __init__(self, rows):
                self._rows = rows

            def scalar_one_or_none(self):
                return self._rows[0] if self._rows else None

            def scalars(self):
                rows = self._rows
                class ScalarsWrap:
                    def unique(self):
                        return self
                    def all(self):
                        return rows
                return ScalarsWrap()

        # 1. Documents query
        if "from documents" in stmt_lower:
            matched_docs = []
            for d in self.store.documents.values():
                if d.id in vals and d.tenant_id in vals:
                    if "is_trashed" in stmt_lower and d.is_trashed:
                        continue
                    matched_docs.append(d)
            if stmt_lower.startswith("select documents.original_name"):
                return QueryResult([d.original_name for d in matched_docs])
            return QueryResult(matched_docs)

        # 2. Folders query
        if "from folders" in stmt_lower:
            matched_folders = []
            for f in self.store.folders.values():
                if f.id in vals and f.tenant_id in vals:
                    if "is_trashed" in stmt_lower and f.is_trashed:
                        continue
                    matched_folders.append(f)
            if stmt_lower.startswith("select folders.name"):
                return QueryResult([f.name for f in matched_folders])
            return QueryResult(matched_folders)

        # 3. Users query
        if "from users" in stmt_lower:
            emails = [v.lower() for v in vals if isinstance(v, str)]
            matched_users = [u for u in self.store.users.values() if u.email.lower() in emails]
            return QueryResult(matched_users)

        # 4. Shares query
        if "from shares" in stmt_lower:
            # Attach recipients cleanly from store
            for s in self.store.shares.values():
                s.recipients = [r for r in self.store.recipients.values() if r.share_id == s.id]

            # Public share lookup by token_hash
            if "shares.token_hash =" in stmt_lower:
                hashes = [v for v in vals if isinstance(v, str) and len(v) == 64]
                matched = [
                    s for s in self.store.shares.values()
                    if s.token_hash in hashes and s.share_type == "SECURE_LINK"
                ]
                return QueryResult(matched)

            # Received shares join ShareRecipient
            if "join share_recipients" in stmt_lower:
                uuids = [v for v in vals if isinstance(v, uuid.UUID)]
                strs = [v.lower() for v in vals if isinstance(v, str)]
                now = datetime.now(timezone.utc)
                matched = []
                for s in self.store.shares.values():
                    if s.share_type != "INTERNAL_USER" or not s.is_active:
                        continue
                    if s.expires_at and s.expires_at <= now:
                        continue
                    is_recip = any(
                        (r.recipient_user_id in uuids) or (r.recipient_email.lower() in strs)
                        for r in s.recipients
                    )
                    if is_recip:
                        matched.append(s)
                return QueryResult(matched)

            # Lookup by Share.id (+ optional Share.tenant_id)
            uuids = [v for v in vals if isinstance(v, uuid.UUID)]
            if "shares.id =" in stmt_lower:
                matched = []
                for s in self.store.shares.values():
                    if s.id in uuids:
                        if "shares.tenant_id =" in stmt_lower and s.tenant_id not in uuids:
                            continue
                        matched.append(s)
                return QueryResult(matched)

            # Tenant shares list
            if "shares.tenant_id =" in stmt_lower:
                matched = [s for s in self.store.shares.values() if s.tenant_id in uuids]
                if "shares.document_id =" in stmt_lower:
                    matched = [s for s in matched if s.document_id in uuids]
                if "shares.folder_id =" in stmt_lower:
                    matched = [s for s in matched if s.folder_id in uuids]
                if "shares.is_active =" in stmt_lower:
                    matched = [s for s in matched if s.is_active]
                matched.sort(key=lambda x: x.created_at or datetime.now(timezone.utc), reverse=True)
                return QueryResult(matched)

        return QueryResult([])


def build_test_fixtures():
    store = InMemoryPostgresStore()
    share_rate_limiter._attempts.clear()

    alice_id = uuid.uuid4()
    bob_id = uuid.uuid4()
    charlie_id = uuid.uuid4()
    editor_id = uuid.uuid4()

    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    alice = User(id=alice_id, email="alice@example.com", hashed_password="h", full_name="Alice", is_active=True, is_verified=True, is_superuser=False)
    bob = User(id=bob_id, email="bob@example.com", hashed_password="h", full_name="Bob", is_active=True, is_verified=True, is_superuser=False)
    charlie = User(id=charlie_id, email="charlie@example.com", hashed_password="h", full_name="Charlie", is_active=True, is_verified=True, is_superuser=False)
    other_editor = User(id=editor_id, email="editor@example.com", hashed_password="h", full_name="Editor", is_active=True, is_verified=True, is_superuser=False)

    for u in (alice, bob, charlie, other_editor):
        store.users[u.id] = u

    tenant_a = Tenant(id=tenant_a_id, name="Espace Alice", owner_id=alice_id, plan_id="PERSONAL", is_active=True)
    tenant_b = Tenant(id=tenant_b_id, name="Espace Bob", owner_id=bob_id, plan_id="FREE", is_active=True)
    store.tenants[tenant_a_id] = tenant_a
    store.tenants[tenant_b_id] = tenant_b

    doc_alice = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        original_name="Contrat_Confidentiel_2026.pdf",
        storage_key=f"tenants/{tenant_a_id}/random_key_alice.pdf",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=425000,
        sha256_hash="a" * 64,
        status="READY",
        antivirus_status="CLEAN",
        is_trashed=False,
        created_by=alice_id,
    )
    doc_infected = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        original_name="Facture_Piegee.pdf",
        storage_key=f"tenants/{tenant_a_id}/infected_doc.pdf",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=2048,
        sha256_hash="b" * 64,
        status="QUARANTINED",
        antivirus_status="INFECTED",
        is_trashed=False,
        created_by=alice_id,
    )
    doc_bob = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_b_id,
        original_name="Secret_Bob.pdf",
        storage_key=f"tenants/{tenant_b_id}/secret_bob.pdf",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=99000,
        sha256_hash="c" * 64,
        status="READY",
        antivirus_status="CLEAN",
        is_trashed=False,
        created_by=bob_id,
    )
    for d in (doc_alice, doc_infected, doc_bob):
        store.documents[d.id] = d

    ctx_alice_owner = TenantContext(user=alice, tenant=tenant_a, role="OWNER", db=None)
    ctx_editor = TenantContext(user=other_editor, tenant=tenant_a, role="EDITOR", db=None)
    ctx_bob_owner = TenantContext(user=bob, tenant=tenant_b, role="OWNER", db=None)

    return store, {
        "alice": alice,
        "bob": bob,
        "charlie": charlie,
        "other_editor": other_editor,
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "doc_alice": doc_alice,
        "doc_infected": doc_infected,
        "doc_bob": doc_bob,
        "ctx_alice_owner": ctx_alice_owner,
        "ctx_editor": ctx_editor,
        "ctx_bob_owner": ctx_bob_owner,
    }


# =========================================================================
# TEST 1: No in-memory storage & PostgreSQL token digest hashing
# =========================================================================

@pytest.mark.asyncio
async def test_phase7_no_in_memory_cache_and_token_hash_storage():
    """
    Verify _LOCAL_SHARES is completely removed, PostgreSQL is the sole source of truth
    across fresh sessions, tokens have high entropy, and only SHA-256 digests are persisted.
    """
    assert not hasattr(shares_module, "_LOCAL_SHARES"), "_LOCAL_SHARES must be completely removed!"

    store, f = build_test_fixtures()
    db_write = StatefulAsyncSession(store)

    req = SecureLinkCreate(
        document_id=f["doc_alice"].id,
        password="LinkPassword2026!",
        expires_in_hours=48,
        max_downloads=3,
        role="VIEWER",
    )
    created = await create_secure_link(req, make_fake_request(), context=f["ctx_alice_owner"], db=db_write)

    assert created.token is not None and len(created.token) >= 40
    assert created.has_password is True
    assert created.target_name == "Contrat_Confidentiel_2026.pdf"

    # Inspect persisted DB row: raw token must NEVER be stored
    persisted = store.shares[created.id]
    assert persisted.token_hash != created.token
    assert persisted.token_hash == hash_share_token(created.token)
    assert len(persisted.token_hash) == 64
    assert persisted.password_hash != "LinkPassword2026!"

    # A brand new DB session must retrieve real metadata directly from PostgreSQL
    db_read = StatefulAsyncSession(store)
    info = await get_public_share_info(created.token, make_fake_request(), db=db_read)
    assert info.resource_name == "Contrat_Confidentiel_2026.pdf"
    assert info.size_bytes == 425000
    assert info.mime_type == "application/pdf"
    assert info.has_password is True
    assert info.can_download is True

    # Listing shares in tenant must never expose raw token
    db_list = StatefulAsyncSession(store)
    listed = await list_tenant_shares(document_id=None, folder_id=None, active_only=False, context=f["ctx_alice_owner"], db=db_list)
    assert len(listed) == 1
    assert listed[0].token is None
    assert listed[0].public_url is None


# =========================================================================
# TEST 2: Passwords, brute-force lock, download limits & atomic locking
# =========================================================================

@pytest.mark.asyncio
async def test_phase7_password_bruteforce_and_download_limits():
    """
    Verify Argon2id password check, rate limiting after 5 wrong attempts,
    row-locked download_count increments, and blocking when max_downloads is reached.
    """
    store, f = build_test_fixtures()
    db = StatefulAsyncSession(store)

    created = await create_secure_link(
        SecureLinkCreate(
            document_id=f["doc_alice"].id,
            password="CorrectPassword#99",
            max_downloads=2,
            role="VIEWER",
        ),
        make_fake_request(),
        context=f["ctx_alice_owner"],
        db=db,
    )
    raw_token = created.token

    # 1. Missing password rejected
    with pytest.raises(HTTPException) as exc_missing:
        await access_public_share(raw_token, PublicShareAccessRequest(password=None), make_fake_request(), db=StatefulAsyncSession(store))
    assert exc_missing.value.status_code == 401

    # 2. Wrong password attempts -> 5 failures trigger 429 lock
    for attempt in range(5):
        with pytest.raises(HTTPException) as exc_bad:
            await access_public_share(
                raw_token,
                PublicShareAccessRequest(password=f"wrong-{attempt}"),
                make_fake_request(ip="198.51.100.77"),
                db=StatefulAsyncSession(store),
            )
        assert exc_bad.value.status_code == 401

    with pytest.raises(HTTPException) as exc_locked:
        await access_public_share(
            raw_token,
            PublicShareAccessRequest(password="CorrectPassword#99"),
            make_fake_request(ip="198.51.100.77"),
            db=StatefulAsyncSession(store),
        )
    assert exc_locked.value.status_code == 429

    # 3. Legitimate IP downloads twice (max_downloads=2)
    legit_ip = "203.0.113.55"
    dl_db1 = StatefulAsyncSession(store)
    dl1 = await download_public_share(
        raw_token,
        PublicShareAccessRequest(password="CorrectPassword#99"),
        make_fake_request(ip=legit_ip),
        db=dl_db1,
    )
    assert dl_db1.locked_for_update is True
    assert dl1.download_count == 1
    assert dl1.size_bytes == 425000
    assert "Signature=" in dl1.download_url

    dl2 = await download_public_share(
        raw_token,
        PublicShareAccessRequest(password="CorrectPassword#99"),
        make_fake_request(ip=legit_ip),
        db=StatefulAsyncSession(store),
    )
    assert dl2.download_count == 2

    # 4. 3rd download must be blocked with 403 Forbidden
    with pytest.raises(HTTPException) as exc_quota:
        await download_public_share(
            raw_token,
            PublicShareAccessRequest(password="CorrectPassword#99"),
            make_fake_request(ip=legit_ip),
            db=StatefulAsyncSession(store),
        )
    assert exc_quota.value.status_code == 403
    assert any(log.action == "PUBLIC_SHARE_QUOTA_EXCEEDED" for log in store.audit_logs)


# =========================================================================
# TEST 3: Expirations & immediate revocation
# =========================================================================

@pytest.mark.asyncio
async def test_phase7_expiration_and_immediate_revocation():
    """Verify expired links return 410 Gone and revoked links immediately return 404 Not Found."""
    store, f = build_test_fixtures()
    db = StatefulAsyncSession(store)

    created = await create_secure_link(
        SecureLinkCreate(document_id=f["doc_alice"].id, expires_in_hours=24, role="VIEWER"),
        make_fake_request(),
        context=f["ctx_alice_owner"],
        db=db,
    )
    raw_token = created.token

    # Force expiration in DB
    store.shares[created.id].expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(HTTPException) as exc_exp:
        await get_public_share_info(raw_token, make_fake_request(), db=StatefulAsyncSession(store))
    assert exc_exp.value.status_code == 410

    with pytest.raises(HTTPException) as exc_exp_dl:
        await download_public_share(raw_token, PublicShareAccessRequest(), make_fake_request(), db=StatefulAsyncSession(store))
    assert exc_exp_dl.value.status_code == 410

    # Restore valid expiry then revoke immediately as owner
    store.shares[created.id].expires_at = datetime.now(timezone.utc) + timedelta(hours=12)
    await revoke_share(created.id, make_fake_request(), context=f["ctx_alice_owner"], db=StatefulAsyncSession(store))

    assert store.shares[created.id].is_active is False
    assert any(log.action == "SHARE_REVOKE" for log in store.audit_logs)

    # All public endpoints must immediately deny revoked share with 404
    for call in (
        get_public_share_info(raw_token, make_fake_request(), db=StatefulAsyncSession(store)),
        access_public_share(raw_token, PublicShareAccessRequest(), make_fake_request(), db=StatefulAsyncSession(store)),
        download_public_share(raw_token, PublicShareAccessRequest(), make_fake_request(), db=StatefulAsyncSession(store)),
    ):
        with pytest.raises(HTTPException) as exc_rev:
            await call
        assert exc_rev.value.status_code == 404


# =========================================================================
# TEST 4: Owner rights, recipient rights & cross-tenant isolation
# =========================================================================

@pytest.mark.asyncio
async def test_phase7_owner_recipient_and_cross_tenant_protection():
    """
    Verify:
    - Role escalation via share creation (e.g., role='OWNER') is rejected.
    - Recipient receives internal share and can download.
    - Third-party unauthorized user (Charlie) gets 403 Forbidden + audit log.
    - Non-creator Editor cannot revoke Alice's share (403 Forbidden), while Tenant OWNER can.
    - Cross-tenant user (Bob in Tenant B) cannot share or revoke Alice's Tenant A resources (404).
    """
    store, f = build_test_fixtures()

    # 1. Reject OWNER role escalation
    with pytest.raises(HTTPException) as exc_role:
        await create_internal_share(
            InternalShareCreate(document_id=f["doc_alice"].id, recipient_email="bob@example.com", role="OWNER"),
            make_fake_request(),
            context=f["ctx_alice_owner"],
            db=StatefulAsyncSession(store),
        )
    assert exc_role.value.status_code == 400

    # 2. Cross-tenant share creation blocked (Bob tries sharing Alice's doc from Tenant B)
    with pytest.raises(HTTPException) as exc_cross_create:
        await create_internal_share(
            InternalShareCreate(document_id=f["doc_alice"].id, recipient_email="charlie@example.com", role="VIEWER"),
            make_fake_request(),
            context=f["ctx_bob_owner"],
            db=StatefulAsyncSession(store),
        )
    assert exc_cross_create.value.status_code == 404

    # 3. Legitimate internal share from Alice (Tenant A) -> Bob
    created = await create_internal_share(
        InternalShareCreate(document_id=f["doc_alice"].id, recipient_email="Bob@Example.com", role="VIEWER"),
        make_fake_request(),
        context=f["ctx_alice_owner"],
        db=StatefulAsyncSession(store),
    )
    assert created.recipients[0].recipient_email == "bob@example.com"
    assert created.recipients[0].recipient_user_id == f["bob"].id

    # 4. Bob lists received shares and downloads
    received = await list_received_shares(current_user=f["bob"], db=StatefulAsyncSession(store))
    assert len(received) == 1
    assert received[0].id == created.id

    bob_dl = await download_received_share(created.id, make_fake_request(), current_user=f["bob"], db=StatefulAsyncSession(store))
    assert bob_dl.filename == "Contrat_Confidentiel_2026.pdf"
    assert "Signature=" in bob_dl.download_url

    # 5. Unauthorized user Charlie cannot download Bob's received share (403 + audit)
    with pytest.raises(HTTPException) as exc_unauth:
        await download_received_share(created.id, make_fake_request(), current_user=f["charlie"], db=StatefulAsyncSession(store))
    assert exc_unauth.value.status_code == 403
    assert any(log.action == "INTERNAL_SHARE_ACCESS_DENIED" for log in store.audit_logs)

    # 6. Cross-tenant user cannot revoke Alice's share (404)
    with pytest.raises(HTTPException) as exc_cross_rev:
        await revoke_share(created.id, make_fake_request(), context=f["ctx_bob_owner"], db=StatefulAsyncSession(store))
    assert exc_cross_rev.value.status_code == 404

    # 7. Different EDITOR who did not create the share cannot revoke it (403)
    with pytest.raises(HTTPException) as exc_editor_rev:
        await revoke_share(created.id, make_fake_request(), context=f["ctx_editor"], db=StatefulAsyncSession(store))
    assert exc_editor_rev.value.status_code == 403

    # 8. Owner Alice CAN revoke it, and Bob immediately loses download access (404)
    await revoke_share(created.id, make_fake_request(), context=f["ctx_alice_owner"], db=StatefulAsyncSession(store))
    with pytest.raises(HTTPException) as exc_after_rev:
        await download_received_share(created.id, make_fake_request(), current_user=f["bob"], db=StatefulAsyncSession(store))
    assert exc_after_rev.value.status_code == 404


# =========================================================================
# TEST 5: Persistence errors are NEVER ignored & antivirus fail-closed on shares
# =========================================================================

@pytest.mark.asyncio
async def test_phase7_persistence_errors_never_ignored_and_antivirus_barrier():
    """
    Verify:
    - Database commit failure raises HTTP 500 with rollback (never swallowed).
    - Infected document cannot be downloaded even via valid share link.
    """
    store, f = build_test_fixtures()

    # 1. Failing DB commit on create_secure_link must roll back and raise HTTP 500
    failing_db = StatefulAsyncSession(store, fail_on_commit=True)
    with pytest.raises(HTTPException) as exc_db:
        await create_secure_link(
            SecureLinkCreate(document_id=f["doc_alice"].id, role="VIEWER"),
            make_fake_request(),
            context=f["ctx_alice_owner"],
            db=failing_db,
        )
    assert exc_db.value.status_code == 500
    assert failing_db.rolled_back is True
    assert len(store.shares) == 0

    # 2. Infected document blocked on public download
    ok_db = StatefulAsyncSession(store)
    infected_link = await create_secure_link(
        SecureLinkCreate(document_id=f["doc_infected"].id, role="VIEWER"),
        make_fake_request(),
        context=f["ctx_alice_owner"],
        db=ok_db,
    )
    with pytest.raises(HTTPException) as exc_av:
        await download_public_share(
            infected_link.token,
            PublicShareAccessRequest(),
            make_fake_request(),
            db=StatefulAsyncSession(store),
        )
    assert exc_av.value.status_code == 403
    assert "quarantaine" in exc_av.value.detail.lower()
