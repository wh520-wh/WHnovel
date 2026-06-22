"""Tests for memory_inject_count setting (clamping + exposure)."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_memory_inject_count_clamped_on_update():
    for val, expected in [("150", 100), ("-5", 0), ("30", 30)]:
        resp = client.put("/api/settings", json={"memory_inject_count": int(val)})
        resp.raise_for_status()
        assert resp.json()["memory_inject_count"] == expected

    # GET 也含该字段
    resp = client.get("/api/settings")
    resp.raise_for_status()
    assert "memory_inject_count" in resp.json()


def test_memory_inject_count_default_present_on_get():
    """新建/既有 settings 的 GET 响应含 memory_inject_count 字段。"""
    resp = client.get("/api/settings")
    resp.raise_for_status()
    data = resp.json()
    assert "memory_inject_count" in data
    assert isinstance(data["memory_inject_count"], int)
