"""
Real PostgreSQL 15+/16 Harness for Phase 9 Integration & RLS Tests.
Uses TEST_DATABASE_URL in CI, or spawns an ephemeral local PostgreSQL 15 instance.
"""
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PG_BIN = Path("/usr/lib/postgresql/15/bin")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class PostgresHarness:
    def __init__(self, db_name: str = "docuspace_p9"):
        self.external_url = os.getenv("TEST_DATABASE_URL", "").strip()
        self.tmpdir = None
        self.port = 5432
        self.pg_bin = PG_BIN
        self.super_sync_url = ""
        self.app_async_url = ""
        self.super_async_url = ""
        self.db_name = db_name

    def start(self):
        if self.external_url:
            self.super_async_url = self.external_url
            self.super_sync_url = self.external_url.replace("+asyncpg", "")
            self.app_async_url = os.getenv("TEST_APP_DATABASE_URL", self.external_url)
            self._ensure_extensions_and_app_role()
            return

        if not (self.pg_bin / "initdb").exists():
            pytest.skip("PostgreSQL binaire introuvable et TEST_DATABASE_URL non défini")

        self.port = find_free_port()
        self.tmpdir = tempfile.mkdtemp(prefix="docuspace_pg_")
        os.chmod(self.tmpdir, 0o777)
        data_dir = Path(self.tmpdir) / "data"
        log_file = Path(self.tmpdir) / "pg.log"
        data_dir.mkdir()
        subprocess.run(["chown", "-R", "nobody:nogroup", self.tmpdir], check=True)

        init_bin = str(self.pg_bin / "initdb")
        pg_ctl_bin = str(self.pg_bin / "pg_ctl")
        cmd = (
            f"{init_bin} -D {data_dir} -U pgadmin --auth=trust -E UTF8 >/dev/null && "
            f"{pg_ctl_bin} -D {data_dir} -o '-k {self.tmpdir} -p {self.port} -h 127.0.0.1' -l {log_file} start"
        )
        subprocess.run(["su", "-s", "/bin/sh", "nobody", "-c", cmd], check=True)

        self.super_sync_url = f"postgresql://pgadmin@127.0.0.1:{self.port}/{self.db_name}"
        self.super_async_url = f"postgresql+asyncpg://pgadmin@127.0.0.1:{self.port}/{self.db_name}"
        self.app_async_url = f"postgresql+asyncpg://docuspace_app:AppTestPass99!@127.0.0.1:{self.port}/{self.db_name}"

        subprocess.run(
            [str(self.pg_bin / "psql"), "-h", "127.0.0.1", "-p", str(self.port), "-U", "pgadmin", "-d", "postgres", "-c", f"CREATE DATABASE {self.db_name};"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        self._ensure_extensions_and_app_role()

    def run_psql(self, sql: str, db: str | None = None):
        target_db = db or self.db_name
        if self.external_url:
            subprocess.run(["psql", self.super_sync_url, "-c", sql], check=True, stdout=subprocess.DEVNULL)
        else:
            subprocess.run(
                [str(self.pg_bin / "psql"), "-h", "127.0.0.1", "-p", str(self.port), "-U", "pgadmin", "-d", target_db, "-c", sql],
                check=True,
                stdout=subprocess.DEVNULL,
            )

    def _ensure_extensions_and_app_role(self):
        ext_sql = (REPO_ROOT / "scripts/init/01_extensions.sql").read_text(encoding="utf-8")
        self.run_psql(ext_sql)
        self.run_psql(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'docuspace_app') THEN "
            "CREATE ROLE docuspace_app LOGIN PASSWORD 'AppTestPass99!' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; "
            "END IF; END $$;"
        )

    def run_alembic_and_grant(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["DATABASE_URL"] = self.super_async_url
        subprocess.run(
            ["alembic", "-c", str(REPO_ROOT / "backend/alembic.ini"), "upgrade", "head"],
            cwd=str(REPO_ROOT),
            env=env,
            check=True,
        )
        perms_sql = (
            "GRANT USAGE ON SCHEMA public TO docuspace_app; "
            "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO docuspace_app; "
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO docuspace_app;"
        )
        self.run_psql(perms_sql)

    def stop(self):
        if self.tmpdir and Path(self.tmpdir).exists():
            data_dir = Path(self.tmpdir) / "data"
            pg_ctl_bin = str(self.pg_bin / "pg_ctl")
            subprocess.run(
                ["su", "-s", "/bin/sh", "nobody", "-c", f"{pg_ctl_bin} -D {data_dir} stop -m immediate >/dev/null 2>&1 || true"],
                check=False,
            )
            shutil.rmtree(self.tmpdir, ignore_errors=True)
