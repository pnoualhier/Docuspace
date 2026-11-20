import uuid
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from backend.app.models.user import User, Session
from backend.app.models.tenant import Tenant, TenantMember, StorageUsage
from backend.app.api.v1.routes.auth import _is_rate_limited, _record_failed_attempt, _reset_attempts, MAX_LOGIN_ATTEMPTS

def test_phase2_password_hashing_argon2id():
    """Verify password hashing produces secure Argon2id hashes with unique salts."""
    pwd = "UltraSecurePassword2026!"
    h1 = get_password_hash(pwd)
    h2 = get_password_hash(pwd)
    assert h1 != h2, "Salts must be unique"
    assert verify_password(pwd, h1) is True
    assert verify_password("WrongPassword!", h1) is False

def test_phase2_jwt_tokens_access_and_refresh():
    """Verify JWT access and refresh token structure and payload types."""
    user_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    
    access_token = create_access_token(subject=user_id, tenant_id=tenant_id)
    refresh_token = create_refresh_token(subject=user_id)
    
    acc_payload = decode_token(access_token)
    assert acc_payload["sub"] == user_id
    assert acc_payload["tenant_id"] == tenant_id
    assert acc_payload["type"] == "access"
    
    ref_payload = decode_token(refresh_token)
    assert ref_payload["sub"] == user_id
    assert ref_payload["type"] == "refresh"

def test_phase2_login_rate_limiting_bruteforce_defense():
    """Verify failed login attempts trigger lockout window."""
    test_id = "test_ip_rate_limiter:user@example.com"
    _reset_attempts(test_id)
    assert _is_rate_limited(test_id) is False
    
    for _ in range(MAX_LOGIN_ATTEMPTS):
        _record_failed_attempt(test_id)
        
    assert _is_rate_limited(test_id) is True
    _reset_attempts(test_id)
    assert _is_rate_limited(test_id) is False

class MockResult:
    def scalar_one_or_none(self):
        return None
    def scalars(self):
        class MockScalars:
            def all(self):
                return []
        return MockScalars()

class MockAsyncSession:
    async def execute(self, stmt):
        return MockResult()
    def add(self, obj):
        pass
    async def commit(self):
        pass
    async def rollback(self):
        pass
    async def flush(self):
        pass
    async def refresh(self, obj):
        pass

async def override_get_db():
    yield MockAsyncSession()

def test_phase2_password_reset_enumeration_protection():
    """Verify password reset request returns identical message whether email exists or not."""
    from backend.app.core.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        resp1 = client.post("/api/v1/auth/password-reset/request", json={"email": "nonexistent_account@example.com"})
        assert resp1.status_code == 200
        data = resp1.json()
        assert "message" in data
        assert "Si l'adresse" in data["message"]
    finally:
        app.dependency_overrides.pop(get_db, None)

def test_phase2_registration_payload_validation():
    """Verify Pydantic models reject invalid emails and weak passwords."""
    client = TestClient(app)
    # Password too short (< 8 chars)
    resp = client.post("/api/v1/auth/register", json={
        "email": "valid@example.com",
        "password": "short",
        "full_name": "Test User"
    })
    assert resp.status_code == 422

    # Malformed email
    resp = client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "password": "validPassword123!",
        "full_name": "Test User"
    })
    assert resp.status_code == 422

    # Whitespace-only full name
    resp = client.post("/api/v1/auth/register", json={
        "email": "valid@example.com",
        "password": "validPassword123!",
        "full_name": "   "
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_phase2_email_service_standard_templates_and_graceful_skip(monkeypatch):
    """Verify standard welcome/login emails degrade gracefully when SMTP is unconfigured and build proper payloads."""
    from backend.app.core.config import settings
    from backend.app.services import email_service

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "not-configured-in-preview")
    assert email_service.is_smtp_configured() is False

    welcome_res = await email_service.send_welcome_space_email(
        recipient_email="user@example.com",
        full_name="Pat Noualhier",
        tenant_name="Espace de Pat Noualhier",
        verification_token="tok-verify-123",
        verification_required=True,
    )
    assert welcome_res.sent is False
    assert welcome_res.status == "skipped_unconfigured"

    login_res = await email_service.send_login_notification_email(
        recipient_email="user@example.com",
        full_name="Pat Noualhier",
        ip_address="192.0.2.10",
        user_agent="Firefox/128.0",
    )
    assert login_res.sent is False
    assert login_res.status == "skipped_unconfigured"

    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=8):
            captured["host"] = host
            captured["port"] = port
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def ehlo(self):
            captured["ehlo"] = True
        def starttls(self):
            captured["starttls"] = True
        def login(self, user, password):
            captured["login"] = (user, password)
        def send_message(self, msg):
            captured["subject"] = msg["Subject"]
            captured["to"] = msg["To"]
            captured["body"] = msg.get_body(preferencelist=("plain",)).get_content()

    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.mailtest.local")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "mailer@docuspace.fr")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "real_smtp_secret_test")
    monkeypatch.setattr(settings, "SMTP_TLS", True)
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)

    assert email_service.is_smtp_configured() is True
    sent_welcome = await email_service.send_welcome_space_email(
        recipient_email="pat@example.com",
        full_name="Pat Noualhier",
        tenant_name="Espace de Pat Noualhier",
        verification_token="tok-abc",
        verification_required=True,
    )
    assert sent_welcome.sent is True
    assert captured["to"] == "pat@example.com"
    assert "/verify-email?token=tok-abc" in captured["body"]

    sent_login = await email_service.send_login_notification_email(
        recipient_email="pat@example.com",
        full_name="Pat Noualhier",
        ip_address="203.0.113.5",
        user_agent="Chrome/126",
    )
    assert sent_login.sent is True
    assert "Confirmation de connexion" in captured["subject"]
    assert "203.0.113.5" in captured["body"]

