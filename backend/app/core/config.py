import os
import secrets
import sys
from typing import Any, List
from pydantic import field_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _HAS_PYDANTIC_SETTINGS = True
except ImportError:
    from pydantic import BaseModel as BaseSettings  # type: ignore
    SettingsConfigDict = dict  # type: ignore
    _HAS_PYDANTIC_SETTINGS = False


_EPHEMERAL_TEST_SECRET: str | None = None

_FORBIDDEN_SECRET_PATTERNS = (
    "replace_with",
    "change_me",
    "super_secret",
    "demo_",
    "docuspace_secure_password",
    "docuspace_minio_secret_key",
    "redis_secure_pass",
    "1931f981e26267c862f352c516b5f2bb",
    "ab156e9361da7f2d77efb077221f5285",
    "323da47d5b7bcb3aa99b4322f3260ce7",
    "7bae32ca633293bc5fc5f36454c4817b1877bf91894d378cb27b6e874e018393",
)


def is_test_runtime() -> bool:
    """Returns True only when executing inside an automated test suite."""
    env = (os.getenv("APP_ENV") or "").strip().lower()
    if env in ("test", "testing"):
        return True
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ


def _get_default_secret_key() -> str:
    global _EPHEMERAL_TEST_SECRET
    env_val = os.getenv("SECRET_KEY", "").strip()
    if env_val:
        return env_val
    if is_test_runtime():
        if _EPHEMERAL_TEST_SECRET is None:
            _EPHEMERAL_TEST_SECRET = secrets.token_hex(32)
        return _EPHEMERAL_TEST_SECRET
    return ""


def _is_weak_or_placeholder(value: str) -> bool:
    lowered = (value or "").strip().lower()
    if not lowered:
        return True
    return any(pattern in lowered for pattern in _FORBIDDEN_SECRET_PATTERNS)


class Settings(BaseSettings):
    APP_NAME: str = "DocuSpace"
    APP_ENV: str = os.getenv("APP_ENV", "production")
    APP_URL: str = os.getenv("APP_URL", "http://localhost")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

    # Security — zero hardcoded secret defaults; required via environment in production
    SECRET_KEY: str = _get_default_secret_key()
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # Database — zero hardcoded password defaults
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://localhost:5432/docuspace_test" if is_test_runtime() else "postgresql+asyncpg://localhost:5432/docuspace",
    )

    # MinIO / S3 — zero hardcoded password defaults
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "docuspace-documents")

    # Antivirus (ClamAV) — strictly Fail-Closed
    CLAMAV_HOST: str = os.getenv("CLAMAV_HOST", "clamav")
    CLAMAV_PORT: int = int(os.getenv("CLAMAV_PORT", "3310"))
    CLAMAV_FAIL_CLOSED: bool = True

    # Redis — zero hardcoded password defaults
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Billing / Stripe — configured via environment
    STRIPE_API_KEY: str = os.getenv("STRIPE_API_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:3000",
    ]

    if _HAS_PYDANTIC_SETTINGS:
        model_config = SettingsConfigDict(
            case_sensitive=True,
            env_file=(".env", "../.env"),
            extra="ignore",
        )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            raw = v.strip()
            if raw.startswith("[") and raw.endswith("]"):
                import json
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if str(i).strip()]
                except Exception:
                    pass
            return [i.strip() for i in raw.split(",") if i.strip()]
        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return ["http://localhost"]

    def validate_production_secrets(self) -> None:
        """
        Fail-fast validation for production environments.
        Ensures no missing, weak, or placeholder secrets are accepted.
        """
        errors: List[str] = []

        if _is_weak_or_placeholder(self.SECRET_KEY) or len(self.SECRET_KEY.strip()) < 32:
            errors.append("SECRET_KEY doit être défini (>= 32 caractères aléatoires, sans valeur par défaut).")

        if _is_weak_or_placeholder(self.DATABASE_URL) or "@" not in self.DATABASE_URL or "://" not in self.DATABASE_URL:
            errors.append("DATABASE_URL doit inclure des identifiants PostgreSQL sécurisés.")
        else:
            # Verify non-empty password in DSN userinfo (scheme://user:password@host)
            after_scheme = self.DATABASE_URL.split("://", 1)[1]
            userinfo = after_scheme.split("@", 1)[0]
            if ":" not in userinfo or not userinfo.split(":", 1)[1]:
                errors.append("DATABASE_URL doit contenir un mot de passe PostgreSQL explicite.")

        if _is_weak_or_placeholder(self.MINIO_ACCESS_KEY):
            errors.append("MINIO_ACCESS_KEY doit être défini sans valeur par défaut.")

        if _is_weak_or_placeholder(self.MINIO_SECRET_KEY) or len(self.MINIO_SECRET_KEY.strip()) < 12:
            errors.append("MINIO_SECRET_KEY doit être défini (>= 12 caractères, sans valeur par défaut).")

        if _is_weak_or_placeholder(self.REDIS_URL) or "@" not in self.REDIS_URL:
            errors.append("REDIS_URL doit contenir un mot de passe Redis explicite.")

        if errors:
            raise RuntimeError(
                "Configuration de sécurité invalide pour l'environnement de production : "
                + " | ".join(errors)
            )


settings = Settings()

if settings.APP_URL and settings.APP_URL not in settings.BACKEND_CORS_ORIGINS:
    settings.BACKEND_CORS_ORIGINS.append(settings.APP_URL)
