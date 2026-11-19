import hashlib
import hmac
import os
import secrets
import time
from typing import Dict, Tuple

# Attempt Argon2id import; if absent, fall back to high-iteration PBKDF2-SHA256
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    _ARGON2_HASHER = PasswordHasher(
        time_cost=3,
        memory_cost=65536, # 64 Mo RAM
        parallelism=2,
        hash_len=32,
        salt_len=16
    )
    _USE_ARGON2 = True
except ImportError:
    _ARGON2_HASHER = None
    _USE_ARGON2 = False

PBKDF2_ITERATIONS = 100000

def hash_password(password: str) -> str:
    """
    Hashes a password using Argon2id (if available) or PBKDF2-HMAC-SHA256.
    Returns format: 'argon2id$...' or 'pbkdf2_sha256$iterations$salt$hash'
    """
    if _USE_ARGON2 and _ARGON2_HASHER:
        return f"argon2id${_ARGON2_HASHER.hash(password)}"
    
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """
    Verifies a password against the stored hash in constant time.
    """
    if not hashed:
        return False

    if hashed.startswith("argon2id$") and _USE_ARGON2 and _ARGON2_HASHER:
        raw_hash = hashed.split("argon2id$", 1)[1]
        try:
            return _ARGON2_HASHER.verify(raw_hash, password)
        except Exception:
            return False

    if hashed.startswith("pbkdf2_sha256$"):
        parts = hashed.split("$")
        if len(parts) != 4:
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        return hmac.compare_digest(dk.hex(), expected_hex)

    # Simple sha256 fallback if legacy hash
    return False

def generate_share_token(length: int = 32) -> str:
    """Generates a high-entropy URL-safe share token."""
    return secrets.token_urlsafe(length)

def hash_share_token(token: str) -> str:
    """
    Computes the SHA-256 cryptographic digest of a share token.
    PostgreSQL stores only this digest in `shares.token_hash`, never the raw token.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

from backend.app.core.rate_limit import SlidingRateLimiter


class RateLimiter(SlidingRateLimiter):
    """
    Distributed Redis-backed rate limiter (with resilient offline test fallback)
    to protect public share links against password brute-forcing.
    Locks after 5 consecutive failed attempts for 15 minutes.
    """

    def __init__(self, max_attempts: int = 5, lock_duration_seconds: int = 900, redis_url: str | None = None):
        super().__init__(
            namespace="share",
            max_attempts=max_attempts,
            window_seconds=lock_duration_seconds,
            redis_url=redis_url,
        )
        self.lock_duration = lock_duration_seconds


# Global rate limiter for share password access
share_rate_limiter = RateLimiter(max_attempts=5, lock_duration_seconds=900)
