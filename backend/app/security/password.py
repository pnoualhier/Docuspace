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

class RateLimiter:
    """
    In-memory rate limiter to protect public share links against password brute-forcing.
    Locks after 5 consecutive failed attempts for 15 minutes.
    """

    def __init__(self, max_attempts: int = 5, lock_duration_seconds: int = 900):
        self.max_attempts = max_attempts
        self.lock_duration = lock_duration_seconds
        # key: identifier -> (attempts_count, last_attempt_time)
        self._attempts: Dict[str, Tuple[int, float]] = {}

    def is_rate_limited(self, identifier: str) -> bool:
        """Returns True if the identifier is currently blocked."""
        if identifier not in self._attempts:
            return False
        count, last_time = self._attempts[identifier]
        now = time.time()
        if now - last_time > self.lock_duration:
            # Expired lock window
            del self._attempts[identifier]
            return False
        return count >= self.max_attempts

    def record_failed_attempt(self, identifier: str) -> int:
        """Records a failed password verification attempt."""
        now = time.time()
        if identifier in self._attempts:
            count, last_time = self._attempts[identifier]
            if now - last_time > self.lock_duration:
                count = 0
            new_count = count + 1
            self._attempts[identifier] = (new_count, now)
            return new_count
        else:
            self._attempts[identifier] = (1, now)
            return 1

    def reset_attempts(self, identifier: str):
        """Clears failed attempts upon successful password verification."""
        if identifier in self._attempts:
            del self._attempts[identifier]

# Global rate limiter for share password access
share_rate_limiter = RateLimiter(max_attempts=5, lock_duration_seconds=900)
