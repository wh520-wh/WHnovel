from fastapi.testclient import TestClient

from app.api import admin as admin_api
from app.main import app


client = TestClient(app)


def test_admin_shutdown_endpoint_schedules_worker(monkeypatch):
    called = {"value": False}

    def fake_schedule() -> None:
        called["value"] = True

    monkeypatch.setattr(admin_api, "_schedule_system_shutdown", fake_schedule)

    resp = client.post("/api/admin/system/shutdown")
    resp.raise_for_status()
    data = resp.json()

    assert data["ok"] is True
    assert data["backend_delay_ms"] > 0
    assert data["frontend_delay_ms"] >= data["backend_delay_ms"]
    assert "scheduled_at" in data
    assert called["value"] is True
