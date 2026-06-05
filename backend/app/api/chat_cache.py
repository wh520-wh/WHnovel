"""预设开场缓存"""

from __future__ import annotations

import hashlib
import time
from typing import Any

_TTL_SECONDS = 3600  # 1 hour

_cache: dict[int, dict[str, Any]] = {}


def _make_etag(openings: list[dict]) -> str:
    content = str(openings)
    return hashlib.md5(content.encode()).hexdigest()


def _get_cached(story_id: int) -> dict[str, Any] | None:
    entry = _cache.get(story_id)
    if entry is None:
        return None
    if time.monotonic() - entry["ts"] > _TTL_SECONDS:
        del _cache[story_id]
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

    openings = generate_fn()
    etag = _make_etag(openings)
    _set_cached(story_id, openings, etag)
    return openings, etag, False
