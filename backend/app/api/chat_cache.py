"""预设开场缓存"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any

_TTL_SECONDS = 3600  # 1 hour

_cache: dict[int, dict[str, Any]] = {}

# Bug #9：每故事一把锁做 single-flight——同故事的并发请求只会有一个执行
# generate_fn（真实计费 LLM 调用），其余阻塞等待后直接读缓存。
# 模式对齐 chat_options 的 per-key threading.Lock + guard。
_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(story_id: int) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(story_id)
        if lock is None:
            lock = threading.Lock()
            _locks[story_id] = lock
        return lock


def _make_etag(openings: list[dict]) -> str:
    content = str(openings)
    return hashlib.md5(content.encode()).hexdigest()


def _get_cached(story_id: int) -> dict[str, Any] | None:
    entry = _cache.get(story_id)
    if entry is None:
        return None
    if time.monotonic() - entry["ts"] > _TTL_SECONDS:
        _cache.pop(story_id, None)  # 并发下另一个线程可能已删除（原 del 会 KeyError 500）
        return None
    return entry


def _set_cached(story_id: int, openings: list[dict], etag: str) -> None:
    _cache[story_id] = {"openings": openings, "etag": etag, "ts": time.monotonic()}


def get_or_generate(
    story_id: int,
    generate_fn,
) -> tuple[list[dict], str | None, bool]:
    """Get from cache or generate fresh.

    Returns (openings, etag, was_cached).
    If was_cached=True, etag is the cached ETag (not None).
    If was_cached=False, etag is the newly generated ETag.
    """
    cached = _get_cached(story_id)
    if cached is not None:
        return cached["openings"], cached["etag"], True

    with _get_lock(story_id):
        # 拿锁后 double-check：等待期间另一个线程可能已生成完毕
        cached = _get_cached(story_id)
        if cached is not None:
            return cached["openings"], cached["etag"], True

        openings = generate_fn()
        etag = _make_etag(openings)
        _set_cached(story_id, openings, etag)
        return openings, etag, False
