"""Tests for chat_locks — per-archive lock factory."""

import threading
from unittest.mock import patch

import pytest


class FakeRedis:
    """Simulate Redis client for lock testing."""

    def __init__(self, available=True, lock_acquire_returns=True):
        self.available = available
        self._lock_returns = lock_acquire_returns
        self._held_keys: set[str] = set()
        self._released_keys: set[str] = set()

    def is_available(self):
        return self.available

    def lock_acquire(self, key, ttl=None):
        if self._lock_returns is True:
            self._held_keys.add(key)
            return True
        if self._lock_returns is False:
            return False
        return None  # Redis error

    def lock_release(self, key):
        self._released_keys.add(key)


def test_lock_factory_acquires_and_releases_threading_lock():
    """When Redis unavailable, falls back to threading.Lock."""
    from app.api.chat_locks import _acquire_per_archive_lock

    locks_dict: dict[int, threading.Lock] = {}
    guard = threading.Lock()

    with patch("app.api.chat_locks.get_redis", return_value=FakeRedis(available=False)):
        with _acquire_per_archive_lock(
            1,
            redis_key="test:archive:1",
            ttl=60,
            busy_message="busy",
            locks_dict=locks_dict,
            locks_guard=guard,
        ):
            pass  # lock held and released

    assert 1 in locks_dict


def test_lock_factory_raises_409_when_locked():
    """Raises HTTPException(409) when threading lock is already held."""
    from app.api.chat_locks import _acquire_per_archive_lock

    locks_dict: dict[int, threading.Lock] = {}
    guard = threading.Lock()
    acquired = threading.Event()
    release_now = threading.Event()

    def holder():
        with patch("app.api.chat_locks.get_redis", return_value=FakeRedis(available=False)):
            with _acquire_per_archive_lock(
                1,
                redis_key="test:archive:1",
                ttl=60,
                busy_message="busy",
                locks_dict=locks_dict,
                locks_guard=guard,
            ):
                acquired.set()
                release_now.wait()

    t = threading.Thread(target=holder, daemon=True)
    t.start()
    acquired.wait(timeout=2)

    from fastapi import HTTPException

    with patch("app.api.chat_locks.get_redis", return_value=FakeRedis(available=False)):
        with pytest.raises(HTTPException) as exc:
            with _acquire_per_archive_lock(
                1,
                redis_key="test:archive:1",
                ttl=60,
                busy_message="busy",
                locks_dict=locks_dict,
                locks_guard=guard,
            ):
                pass

    assert exc.value.status_code == 409
    release_now.set()
    t.join(timeout=2)


def test_lock_factory_uses_redis_when_available():
    """When Redis is available, uses Redis lock instead of threading."""
    from app.api.chat_locks import _acquire_per_archive_lock

    locks_dict: dict[int, threading.Lock] = {}
    guard = threading.Lock()
    fake_redis = FakeRedis(available=True, lock_acquire_returns=True)

    with patch("app.api.chat_locks.get_redis", return_value=fake_redis):
        with _acquire_per_archive_lock(
            1,
            redis_key="test:archive:1",
            ttl=60,
            busy_message="busy",
            locks_dict=locks_dict,
            locks_guard=guard,
        ):
            pass

    assert "test:archive:1" in fake_redis._held_keys
    assert "test:archive:1" in fake_redis._released_keys
