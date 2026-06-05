"""Test SSE formatting utilities."""

from app.api.chat_sse import _sse_event, _sse_keepalive


def test_sse_event_with_data():
    """SSE event formats data correctly with event prefix."""
    result = _sse_event("delta", {"text": "hello"})
    assert "event: delta\n" in result
    assert '"text": "hello"' in result
    assert result.endswith("\n\n")


def test_sse_event_with_chinese():
    """SSE event handles Chinese characters correctly."""
    result = _sse_event("delta", {"text": "你好世界"})
    assert "event: delta\n" in result
    assert "你好世界" in result


def test_sse_keepalive():
    """Keepalive format is correct."""
    result = _sse_keepalive()
    assert result == ": keepalive\n\n"


def test_sse_event_with_empty_payload():
    """SSE event handles empty payload."""
    result = _sse_event("done", {})
    assert "event: done\n" in result
    assert "data: {}\n\n" in result
