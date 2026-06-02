"""SSE 事件格式化工具"""
from __future__ import annotations

import json


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_keepalive() -> str:
    return ": keepalive\n\n"
