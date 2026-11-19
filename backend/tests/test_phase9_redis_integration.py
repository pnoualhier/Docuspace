"""
DocuSpace Phase 9 — Real Redis Integration Test
Uses REDIS_URL when provided (CI service container) or spawns a local redis-server instance with requirepass.
"""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
import redis

from backend.tests.pg_harness import find_free_port


def test_phase9_redis_real_auth_and_rate_limit_ttl():
    ci_redis_url = os.getenv("REDIS_URL", "").strip()
    if ci_redis_url and os.getenv("GITHUB_ACTIONS") == "true":
        client = redis.from_url(ci_redis_url, decode_responses=True)
        assert client.ping() is True
        key = "docuspace:ci:ratelimit:test"
        client.setex(key, 30, "5")
        assert client.get(key) == "5"
        assert client.ttl(key) > 0
        client.delete(key)
        return

    redis_bin = shutil.which("redis-server")
    if not redis_bin:
        pytest.skip("redis-server non installé")

    port = find_free_port()
    password = "phase9_redis_test_password_32chars"
    tmpdir = tempfile.mkdtemp(prefix="docuspace_redis_")
    proc = subprocess.Popen(
        [
            redis_bin,
            "--port", str(port),
            "--bind", "127.0.0.1",
            "--requirepass", password,
            "--dir", tmpdir,
            "--save", "",
            "--appendonly", "no",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        client = redis.Redis(host="127.0.0.1", port=port, password=password, decode_responses=True)
        for _ in range(30):
            try:
                if client.ping():
                    break
            except Exception:
                time.sleep(0.1)
        assert client.ping() is True

        # Wrong password must be rejected
        unauth_client = redis.Redis(host="127.0.0.1", port=port, password="wrong", decode_responses=True)
        with pytest.raises(redis.AuthenticationError):
            unauth_client.ping()

        # Verify rate-limit counter & expiration behavior
        rl_key = "ratelimit:share:127.0.0.1"
        assert client.incr(rl_key) == 1
        assert client.expire(rl_key, 900) is True
        assert client.incr(rl_key) == 2
        assert 0 < client.ttl(rl_key) <= 900
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(tmpdir, ignore_errors=True)
