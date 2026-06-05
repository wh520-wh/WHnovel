"""选项生成锁机制"""

from __future__ import annotations

import threading
from contextlib import contextmanager

from .chat_locks import _acquire_per_archive_lock

_option_generation_locks: dict[int, threading.Lock] = {}
_option_generation_locks_guard = threading.Lock()


def _lock_key(archive_id: int) -> str:
    return f"lock:archive:{archive_id}"


@contextmanager
def _acquire_option_generation_lock(archive_id: int):
    """Acquire an exclusive lock for generating chat options for the given archive."""
    with _acquire_per_archive_lock(
        archive_id,
        redis_key=_lock_key(archive_id),
        ttl=30,
        busy_message="该会话正在生成剧情选择项，请稍后重试",
        locks_dict=_option_generation_locks,
        locks_guard=_option_generation_locks_guard,
    ):
        yield
