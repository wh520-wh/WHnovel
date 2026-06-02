"""
Redis client wrapper with graceful degradation.
When Redis is unavailable, all operations become no-ops (do not block the app).
"""
import os
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed; caching disabled")


class RedisClient:
    _instance: Optional['RedisClient'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self._client: Optional[redis.Redis] = None
        self._available = False
        self._host = os.environ.get("REDIS_HOST", "localhost")
        self._port = int(os.environ.get("REDIS_PORT", "6379"))
        self._db = int(os.environ.get("REDIS_DB", "0"))
        self._password = os.environ.get("REDIS_PASSWORD", None)
        self._connect()

    def _connect(self):
        if not REDIS_AVAILABLE:
            return
        try:
            self._client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=3,
            )
            self._client.ping()
            self._available = True
            logger.info(f"Redis connected: {self._host}:{self._port}")
        except Exception as e:
            self._available = False
            self._client = None
            logger.warning(f"Redis unavailable, caching disabled: {e}")

    def is_available(self) -> bool:
        return self._available

    def get(self, key: str) -> Optional[str]:
        if not self._available:
            return None
        try:
            return self._client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET failed: {e}")
            return None

    def set(self, key: str, value: str, ttl: int = 300) -> bool:
        if not self._available:
            return False
        try:
            self._client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.warning(f"Redis SET failed: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self._available:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis DELETE failed: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern. Returns count of deleted keys."""
        if not self._available:
            return 0
        try:
            keys = list(self._client.scan_iter(match=pattern))
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Redis DELETE_PATTERN failed: {e}")
            return 0

    # --- Distributed lock ---
    def lock_acquire(self, key: str, ttl: int = 30) -> bool | None:
        """Acquire a distributed lock (SETNX with TTL).
        Returns True if acquired, False if already held by another process, None if Redis error.
        """
        if not self._available:
            return None  # Redis unavailable
        try:
            return bool(self._client.set(key, "1", nx=True, ex=ttl))
        except Exception as e:
            logger.error(f"Redis lock_acquire failed: {e}")
            self._available = False  # Mark Redis as unavailable
            return None  # Redis error, caller should fall back

    def lock_release(self, key: str) -> bool:
        """Release a distributed lock."""
        if not self._available:
            logger.warning(f"Redis lock_release: Redis unavailable, lock may linger until TTL expires")
            return False
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis lock_release failed: {e}")
            return False


# Singleton accessor
def get_redis() -> RedisClient:
    return RedisClient()
