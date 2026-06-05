"""通用 per-archive 并发锁（Redis + threading fallback）."""

from __future__ import annotations

import threading
from contextlib import contextmanager

from ..redis_client import get_redis


def _get_or_create_lock(
    locks_dict: dict[int, threading.Lock],
    guard: threading.Lock,
    archive_id: int,
) -> threading.Lock:
    with guard:
        lock = locks_dict.get(archive_id)
        if lock is None:
            lock = threading.Lock()
            locks_dict[archive_id] = lock
        return lock


@contextmanager
def _acquire_per_archive_lock(
    archive_id: int,
    *,
    redis_key: str,
    ttl: int,
    busy_message: str,
    locks_dict: dict[int, threading.Lock],
    locks_guard: threading.Lock,
):
    """通用 per-archive 锁：Redis → threading fallback → HTTP 409."""
    from fastapi import HTTPException

    redis = get_redis()
    used_redis = False
    lock: threading.Lock | None = None

    if redis.is_available():
        acquired = redis.lock_acquire(redis_key, ttl=ttl)
        if acquired is None:
            pass  # Redis error, fall through to threading
        elif acquired is False:
            raise HTTPException(409, busy_message)
        else:
            used_redis = True

    if not used_redis:
        lock = _get_or_create_lock(locks_dict, locks_guard, archive_id)
        if not lock.acquire(blocking=False):
            raise HTTPException(409, busy_message)

    try:
        yield
    finally:
        if used_redis:
            redis.lock_release(redis_key)
        elif lock is not None:
            lock.release()
