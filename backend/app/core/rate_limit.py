import logging
import time
from typing import Dict, Optional, Tuple

import redis

from backend.app.core.config import is_test_runtime, settings

logger = logging.getLogger("docuspace.ratelimit")


class SlidingRateLimiter:
    """
    Distributed Redis-backed rate limiter with automatic TTL expiration.
    Falls back gracefully to an in-process dictionary only when Redis is
    unconfigured or temporarily unreachable (or in offline unit tests).
    """

    def __init__(
        self,
        namespace: str,
        max_attempts: int = 5,
        window_seconds: int = 900,
        redis_url: Optional[str] = None,
    ):
        self.namespace = namespace
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._explicit_redis_url = redis_url
        self._client: Optional[redis.Redis] = None
        self._client_url: Optional[str] = None
        # Fallback / offline unit-test store: key -> (count, first_or_last_timestamp)
        self._attempts: Dict[str, Tuple[int, float]] = {}

    def _effective_redis_url(self) -> str:
        if self._explicit_redis_url is not None:
            return self._explicit_redis_url.strip()
        return (settings.REDIS_URL or "").strip()

    def _get_redis_client(self) -> Optional[redis.Redis]:
        url = self._effective_redis_url()
        if not url:
            return None
        # In unit test runtime, ignore Docker-internal hostname unless explicitly pointed to a reachable test Redis
        if is_test_runtime() and self._explicit_redis_url is None and "@redis:" in url:
            return None
        if self._client is None or self._client_url != url:
            self._client = redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            self._client_url = url
        return self._client

    def _redis_key(self, identifier: str) -> str:
        return f"docuspace:ratelimit:{self.namespace}:{identifier}"

    def is_rate_limited(self, identifier: str) -> bool:
        client = self._get_redis_client()
        if client is not None:
            try:
                raw = client.get(self._redis_key(identifier))
                return int(raw) >= self.max_attempts if raw is not None else False
            except Exception as exc:
                logger.warning("Redis rate limit read fallback (%s): %s", self.namespace, exc)

        if identifier not in self._attempts:
            return False
        count, last_time = self._attempts[identifier]
        if time.time() - last_time > self.window_seconds:
            del self._attempts[identifier]
            return False
        return count >= self.max_attempts

    def record_failed_attempt(self, identifier: str) -> int:
        client = self._get_redis_client()
        if client is not None:
            key = self._redis_key(identifier)
            try:
                pipe = client.pipeline()
                pipe.incr(key)
                pipe.ttl(key)
                count, ttl = pipe.execute()
                if ttl is None or int(ttl) < 0:
                    client.expire(key, self.window_seconds)
                return int(count)
            except Exception as exc:
                logger.warning("Redis rate limit write fallback (%s): %s", self.namespace, exc)

        now = time.time()
        if identifier in self._attempts:
            count, last_time = self._attempts[identifier]
            if now - last_time > self.window_seconds:
                count = 0
            new_count = count + 1
            self._attempts[identifier] = (new_count, now)
            return new_count
        self._attempts[identifier] = (1, now)
        return 1

    def reset_attempts(self, identifier: str) -> None:
        client = self._get_redis_client()
        if client is not None:
            try:
                client.delete(self._redis_key(identifier))
            except Exception as exc:
                logger.warning("Redis rate limit reset fallback (%s): %s", self.namespace, exc)
        self._attempts.pop(identifier, None)
