"""
DocuSpace Phase 8 — Docker, Debian Deployment, Secrets & Configuration Hardening Tests
Validates:
1. docker-compose.yml network isolation, internal-only DB/Redis/MinIO/ClamAV, healthchecks, and required env secrets
2. backend.Dockerfile & frontend.Dockerfile import paths, workdir, non-root users, valid Debian packages, and healthchecks
3. Zero hardcoded/default passwords across config.py, alembic.ini, .env.example, docker-compose.yml, templates
4. Production fail-fast validation in Settings.validate_production_secrets()
5. Alembic linear single-head migration chain (0001 -> 0007)
6. Automated generate_env.sh script output, entropy, and 0600 file permissions
7. README.md & INSTALL_DEBIAN.md command/path coherence
"""
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
import yaml
import pytest

from backend.app.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_phase8_docker_compose_hardening_and_isolation():
    compose_path = REPO_ROOT / "docker-compose.yml"
    raw_text = compose_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_text)

    # No hardcoded fallback passwords in compose interpolation
    forbidden_defaults = [
        "change_me",
        "1931f981e26267c862f352c516b5f2bb",
        "ab156e9361da7f2d77efb077221f5285",
        "323da47d5b7bcb3aa99b4322f3260ce7",
        "docuspace_secure_password",
        "docuspace_minio_secret_key",
        "redis_secure_pass",
    ]
    for pattern in forbidden_defaults:
        assert pattern not in raw_text, f"Mot de passe par défaut interdit détecté dans docker-compose.yml : {pattern}"

    # Required secrets must fail interpolation if missing
    assert "${POSTGRES_PASSWORD:?" in raw_text
    assert "${MINIO_ROOT_PASSWORD:?" in raw_text
    assert "${REDIS_PASSWORD:?" in raw_text
    assert "${SECRET_KEY:?" in raw_text

    services = data["services"]
    expected_services = {"postgres", "minio", "clamav", "redis", "backend", "frontend", "nginx"}
    assert set(services.keys()) == expected_services

    # Internal services must NOT publish host ports
    for internal_svc in ("postgres", "minio", "clamav", "redis", "backend", "frontend"):
        assert "ports" not in services[internal_svc], (
            f"Le service interne '{internal_svc}' ne doit pas exposer de ports publics"
        )
        assert "healthcheck" in services[internal_svc], (
            f"Le service '{internal_svc}' doit disposer d'un healthcheck"
        )

    # Only nginx exposes public HTTP/HTTPS ports
    assert "ports" in services["nginx"]
    assert "healthcheck" in services["nginx"]

    # Internal network must be marked internal: true
    networks = data["networks"]
    assert networks["docuspace-internal"].get("internal") is True
    assert "docuspace-internal" in services["postgres"]["networks"]
    assert "docuspace-internal" in services["minio"]["networks"]
    assert "docuspace-internal" in services["redis"]["networks"]
    assert "docuspace-edge" not in services["postgres"]["networks"]
    assert "docuspace-edge" not in services["minio"]["networks"]
    assert "docuspace-edge" not in services["redis"]["networks"]

    # Persistent volumes declared
    volumes = data["volumes"]
    for vol in ("postgres_data", "minio_data", "clamav_db", "redis_data", "nginx_logs"):
        assert vol in volumes

    # Postgres mounts extension-only SQL so alembic upgrade head never collides with pre-created tables
    pg_vols = " ".join(services["postgres"]["volumes"])
    assert "01_extensions.sql" in pg_vols

    # Backend env_file points to root .env
    assert services["backend"]["env_file"] == [".env"]


def test_phase8_dockerfiles_import_paths_and_non_root_users():
    backend_df = (REPO_ROOT / "infrastructure/docker/backend.Dockerfile").read_text(encoding="utf-8")
    assert "PYTHONPATH=/app" in backend_df
    assert "WORKDIR /app/backend" in backend_df
    assert "clamdscan" in backend_df
    assert "clamav-client" not in backend_df, "Paquet Debian Bookworm inexistant 'clamav-client'"
    assert "USER docuspace" in backend_df, "Le conteneur backend doit s'exécuter avec un utilisateur non-root"
    assert "HEALTHCHECK" in backend_df
    assert "backend.app.main:app" in backend_df

    frontend_df = (REPO_ROOT / "infrastructure/docker/frontend.Dockerfile").read_text(encoding="utf-8")
    assert "ARG VITE_API_URL=/api/v1" in frontend_df
    assert "USER nginx" in frontend_df, "Le conteneur frontend doit s'exécuter en non-root (nginx)"
    assert "HEALTHCHECK" in frontend_df
    assert re.search(r"if \[ -f package-lock\.json \]", frontend_df), (
        "frontend.Dockerfile doit gérer l'absence de package-lock.json"
    )


def test_phase8_no_committed_secrets_or_default_passwords():
    # Committed docker.env with hardcoded keys must not exist
    assert not (REPO_ROOT / "infrastructure/docker/docker.env").exists()

    files_to_scan = [
        REPO_ROOT / ".env.example",
        REPO_ROOT / "backend/.env.example",
        REPO_ROOT / "infrastructure/docker/docker.env.template",
        REPO_ROOT / "backend/alembic.ini",
        REPO_ROOT / "backend/app/core/config.py",
    ]
    forbidden_literals = [
        "1931f981e26267c862f352c516b5f2bb",
        "ab156e9361da7f2d77efb077221f5285",
        "323da47d5b7bcb3aa99b4322f3260ce7",
        "7bae32ca633293bc5fc5f36454c4817b1877bf91894d378cb27b6e874e018393",
        "docuspace_secure_password_change_me",
        "docuspace_minio_secret_key_change_me",
        "super_secret_docuspace_jwt_and_session_key_minimum_32_chars",
        "demo_smtp_secure_token",
    ]
    # Note: config.py intentionally lists forbidden patterns inside _FORBIDDEN_SECRET_PATTERNS
    # so for config.py we specifically assert no default password in Settings attributes.
    for path in files_to_scan:
        content = path.read_text(encoding="utf-8")
        if path.name == "config.py":
            assert 'os.getenv("SECRET_KEY", "super_secret' not in content
            assert 'docuspace_secure_password_change_me@' not in content
            assert 'os.getenv("MINIO_SECRET_KEY", "docuspace' not in content
            assert Settings.model_fields["MINIO_ACCESS_KEY"].default == ""
            assert Settings.model_fields["MINIO_SECRET_KEY"].default == ""
            assert Settings.model_fields["REDIS_URL"].default == ""
        else:
            for lit in forbidden_literals:
                assert lit not in content, f"Secret statique interdit trouvé dans {path}: {lit}"

    # Root .env.example must define full stack variables
    root_env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for required_var in (
        "APP_ENV=",
        "APP_URL=",
        "SECRET_KEY=",
        "POSTGRES_DB=",
        "POSTGRES_USER=",
        "POSTGRES_PASSWORD=",
        "DATABASE_URL=",
        "MINIO_ROOT_USER=",
        "MINIO_ROOT_PASSWORD=",
        "MINIO_ACCESS_KEY=",
        "MINIO_SECRET_KEY=",
        "CLAMAV_HOST=",
        "CLAMAV_FAIL_CLOSED=",
        "REDIS_PASSWORD=",
        "REDIS_URL=",
        "BACKEND_CORS_ORIGINS=",
    ):
        assert required_var in root_env_example, f"{required_var} manquant dans .env.example"


def test_phase8_production_secrets_validation_fail_fast():
    bad_settings = Settings(
        APP_ENV="production",
        SECRET_KEY="short_weak_secret",
        DATABASE_URL="postgresql+asyncpg://localhost:5432/docuspace",
        MINIO_ACCESS_KEY="",
        MINIO_SECRET_KEY="REPLACE_WITH_STRONG_MINIO_SECRET",
        REDIS_URL="redis://localhost:6379/0",
    )
    with pytest.raises(RuntimeError, match="Configuration de sécurité invalide"):
        bad_settings.validate_production_secrets()

    valid_settings = Settings(
        APP_ENV="production",
        SECRET_KEY="a" * 64,
        DATABASE_URL="postgresql+asyncpg://docuspace_user:Str0ngPgPass!99@postgres:5432/docuspace",
        MINIO_ACCESS_KEY="docuspace_s3_admin",
        MINIO_SECRET_KEY="Str0ngMinioSecret!99",
        REDIS_URL="redis://:Str0ngRedisPass!99@redis:6379/0",
    )
    valid_settings.validate_production_secrets()


def test_phase8_generate_env_script_and_permissions():
    script_path = REPO_ROOT / "scripts/init/generate_env.sh"
    assert os.access(script_path, os.X_OK), "generate_env.sh doit être exécutable"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_env = Path(tmpdir) / ".env"
        proc = subprocess.run(
            ["bash", str(script_path), str(out_env), "https://files.example.org"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert out_env.exists()
        mode = stat.S_IMODE(out_env.stat().st_mode)
        assert mode == 0o600, f"Permissions attendues 0600, obtenu {oct(mode)}"

        content = out_env.read_text(encoding="utf-8")
        assert "APP_URL=https://files.example.org" in content
        assert "CLAMAV_FAIL_CLOSED=true" in content
        assert "demo_smtp" not in content
        assert "change_me" not in content

        env_map = {}
        for line in content.splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_map[k] = v

        assert len(env_map["SECRET_KEY"]) == 64
        assert len(env_map["POSTGRES_PASSWORD"]) >= 32
        assert len(env_map["MINIO_ROOT_PASSWORD"]) >= 32
        assert len(env_map["REDIS_PASSWORD"]) >= 32
        assert env_map["POSTGRES_PASSWORD"] in env_map["DATABASE_URL"]
        assert env_map["REDIS_PASSWORD"] in env_map["REDIS_URL"]


def test_phase8_alembic_single_head_and_backend_imports():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    proc = subprocess.run(
        ["alembic", "-c", str(REPO_ROOT / "backend/alembic.ini"), "heads"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        check=True,
    )
    heads = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert len(heads) == 1, f"Une seule tête Alembic attendue, trouvé : {heads}"
    assert heads[0].startswith("0007_complete_schema_rls")

    # Verify backend.app.main imports cleanly using PYTHONPATH=/app style from backend/ dir
    imp_proc = subprocess.run(
        ["python3", "-c", "from backend.app.main import app; assert app.title"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT / "backend"),
        check=True,
    )
    assert imp_proc.returncode == 0


def test_phase8_readme_and_debian_guide_match_repo():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    install_doc = (REPO_ROOT / "docs/deployment/INSTALL_DEBIAN.md").read_text(encoding="utf-8")

    for doc in (readme, install_doc):
        assert "./scripts/init/generate_env.sh" in doc
        assert "docker compose up -d --build" in doc
        assert "docker compose exec backend alembic upgrade head" in doc
        assert "http://localhost:9001" not in doc, "La console MinIO ne doit plus être documentée comme exposée publiquement"

    nginx_conf = (REPO_ROOT / "infrastructure/nginx/nginx.conf").read_text(encoding="utf-8")
    assert "server_tokens off;" in nginx_conf
    assert "/nginx-health" in nginx_conf
    assert "proxy_request_buffering off;" in nginx_conf
