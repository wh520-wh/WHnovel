import json
from datetime import datetime, timedelta

from app import config as backup_config
from app import metrics_service, models
from app.api.chat_models import _get_enabled_models
from app.app_settings_service import ensure_app_settings
from app.database import SessionLocal
from app.main import app
from app.prompts.defaults import DEFAULT_STATE_BROADCAST_PROMPT, DEFAULT_SYSTEM_PROMPT_TEXT
from fastapi.testclient import TestClient

client = TestClient(app)


def test_app_settings_can_read_and_update():
    resp = client.get("/api/admin/app-settings")
    resp.raise_for_status()
    data = resp.json()
    assert "default_system_prompt" in data
    assert "default_system_prompt_source" in data

    updated = client.put(
        "/api/admin/app-settings", json={"default_system_prompt": "测试默认提示词"}
    )
    updated.raise_for_status()
    assert updated.json()["default_system_prompt"] == "测试默认提示词"


def test_metrics_endpoints_and_reset():
    db = SessionLocal()
    try:
        db.add(
            models.ApiCallLog(
                request_id="r1",
                archive_id=None,
                story_id=None,
                model_config_id=None,
                model_name="test-model",
                success=1,
                latency_ms=500,
                prompt_tokens=100,
                completion_tokens=200,
                total_tokens=300,
                cost_estimate=0.12,
            )
        )
        db.add(
            models.ApiCallLog(
                request_id="r2",
                archive_id=None,
                story_id=None,
                model_config_id=None,
                model_name="test-model",
                success=0,
                error_code="X",
                error_message="fail",
                latency_ms=900,
                prompt_tokens=50,
                completion_tokens=50,
                total_tokens=100,
                cost_estimate=0.03,
            )
        )
        db.commit()
    finally:
        db.close()

    summary = client.get("/api/admin/metrics/summary")
    summary.raise_for_status()
    assert summary.json()["total_calls"] >= 2

    by_model = client.get("/api/admin/metrics/by-model")
    by_model.raise_for_status()
    assert isinstance(by_model.json(), list)

    trend = client.get("/api/admin/metrics/timeseries")
    trend.raise_for_status()
    assert isinstance(trend.json(), list)

    stream_rows = client.get("/api/admin/metrics/stream-requests")
    stream_rows.raise_for_status()
    assert isinstance(stream_rows.json(), list)

    bad_reset = client.post("/api/admin/metrics/reset", json={"confirm_text": "NO"})
    assert bad_reset.status_code == 400

    ok_reset = client.post("/api/admin/metrics/reset", json={"confirm_text": "RESET_METRICS"})
    ok_reset.raise_for_status()
    assert ok_reset.json()["ok"] is True


def test_model_api_key_is_preserved_when_update_key_is_empty():
    created = client.post(
        "/api/admin/models",
        json={
            "name": "safe-key-model",
            "model_id": "safe-key-model",
            "api_base_url": "https://example.com/v1",
            "api_key": "secret-key-123",
            "enabled": 1,
            "priority": 5,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
        },
    )
    created.raise_for_status()
    model_id = created.json()["id"]

    updated = client.put(
        f"/api/admin/models/{model_id}",
        json={
            "name": "safe-key-model-updated",
            "model_id": "safe-key-model",
            "api_base_url": "https://example.com/v1",
            "api_key": "",
            "enabled": 1,
            "priority": 6,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
        },
    )
    updated.raise_for_status()
    assert updated.json()["has_api_key"] is True


def test_update_app_settings_should_not_be_blocked_by_stale_disabled_model():
    created = client.post(
        "/api/admin/models",
        json={
            "name": "first-model-stale",
            "model_id": "first-model-stale",
            "api_base_url": "https://example.com/v1",
            "api_key": "k",
            "enabled": 1,
            "priority": 11,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
        },
    )
    created.raise_for_status()
    model_id = created.json()["id"]

    # Toggle the model off, then verify updating app-settings still succeeds.
    toggle = client.put(
        f"/api/admin/models/{model_id}",
        json={
            "name": "first-model-stale",
            "model_id": "first-model-stale",
            "api_base_url": "https://example.com/v1",
            "api_key": "",
            "enabled": 0,
            "priority": 11,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
        },
    )
    toggle.raise_for_status()

    resp = client.put(
        "/api/admin/app-settings",
        json={"default_system_prompt": "prompt-v2"},
    )
    resp.raise_for_status()
    data = resp.json()
    assert data["default_system_prompt"] == "prompt-v2"


def test_app_settings_returns_saved_default_image_style():
    updated = client.put(
        "/api/admin/app-settings",
        json={"default_image_style": "水彩插画，朦胧暖光"},
    )
    updated.raise_for_status()
    assert updated.json()["default_image_style"] == "水彩插画，朦胧暖光"

    fetched = client.get("/api/admin/app-settings")
    fetched.raise_for_status()
    assert fetched.json()["default_image_style"] == "水彩插画，朦胧暖光"


def test_empty_default_system_prompt_is_backfilled_from_example_txt():
    reset = client.put(
        "/api/admin/app-settings",
        json={"default_system_prompt": ""},
    )
    reset.raise_for_status()

    got = client.get("/api/admin/app-settings")
    got.raise_for_status()
    data = got.json()
    assert data["default_system_prompt"] == DEFAULT_SYSTEM_PROMPT_TEXT
    assert data["default_system_prompt_source"] == "example_default"


def test_stream_request_metrics_endpoint_returns_stream_fields():
    db = SessionLocal()
    try:
        db.add(
            models.ApiCallLog(
                request_id="stream-row-1",
                archive_id=123,
                story_id=456,
                model_name="stream-model-a",
                success=0,
                error_code="STREAM_MODEL_FAILED",
                error_message="boom",
                latency_ms=900,
                is_stream=1,
                stream_emitted_delta=1,
                ttfb_ms=180,
                fallback_used=0,
                tail_valid=0,
                error_stage="post_delta",
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/admin/metrics/stream-requests", params={"limit": 10})
    resp.raise_for_status()
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    hit = next((x for x in data if x["request_id"] == "stream-row-1"), None)
    assert hit is not None
    assert hit["stream_emitted_delta"] is True
    assert hit["tail_valid"] is False
    assert hit["error_stage"] == "post_delta"


def test_stream_request_metrics_endpoint_filters_order_and_limit():
    now = datetime(2042, 1, 1, 12, 0, 0)
    db = SessionLocal()
    try:
        db.add(
            models.ApiCallLog(
                request_id="non-stream-ignore",
                model_name="normal-model",
                success=1,
                latency_ms=120,
                is_stream=0,
                created_at=now - timedelta(seconds=5),
            )
        )
        db.add(
            models.ApiCallLog(
                request_id="stream-old",
                model_name="stream-model-old",
                success=1,
                latency_ms=220,
                is_stream=1,
                stream_emitted_delta=1,
                tail_valid=1,
                created_at=now - timedelta(seconds=2),
            )
        )
        db.add(
            models.ApiCallLog(
                request_id="stream-new",
                model_name="stream-model-new",
                success=0,
                error_code="STREAM_MODEL_FAILED",
                error_stage="upstream",
                latency_ms=330,
                is_stream=1,
                stream_emitted_delta=0,
                tail_valid=0,
                created_at=now - timedelta(seconds=1),
            )
        )
        db.commit()
    finally:
        db.close()

    window_start = (now - timedelta(seconds=10)).isoformat()
    window_end = (now + timedelta(seconds=10)).isoformat()

    resp_limit_1 = client.get(
        "/api/admin/metrics/stream-requests",
        params={"start": window_start, "end": window_end, "limit": 1},
    )
    resp_limit_1.raise_for_status()
    top_rows = resp_limit_1.json()
    assert len(top_rows) == 1
    assert top_rows[0]["request_id"] == "stream-new"

    resp_all = client.get(
        "/api/admin/metrics/stream-requests",
        params={"start": window_start, "end": window_end, "limit": 50},
    )
    resp_all.raise_for_status()
    rows = resp_all.json()
    request_ids = [x["request_id"] for x in rows]
    assert "stream-new" in request_ids
    assert "stream-old" in request_ids
    assert "non-stream-ignore" not in request_ids


def test_run_aggregation_cycle_uses_session_and_closes_it(monkeypatch):
    events: list[object] = []

    class DummySession:
        closed = False

        def close(self):
            self.closed = True
            events.append("closed")

    session = DummySession()

    monkeypatch.setattr(metrics_service, "SessionLocal", lambda: session)

    def fake_aggregate(db, hour=None):
        events.append(("aggregate", db, hour))
        return 1

    monkeypatch.setattr(metrics_service, "aggregate_hourly_metrics", fake_aggregate)

    metrics_service._run_aggregation_cycle()

    assert events[0] == ("aggregate", session, None)
    assert events[1] == "closed"
    assert session.closed is True


def test_scheduler_run_and_reschedule_executes_cycle_then_reschedules(monkeypatch):
    scheduler = metrics_service.BackgroundScheduler()
    events: list[str] = []

    monkeypatch.setattr(metrics_service, "_run_aggregation_cycle", lambda: events.append("cycle"))
    monkeypatch.setattr(scheduler, "_schedule_next", lambda: events.append("schedule"))

    scheduler._run_and_reschedule()

    assert events == ["cycle", "schedule"]


def test_runtime_does_not_restore_models_from_json_backup():
    backup_config.save_config(
        {
            "models": [
                {
                    "id": 999,
                    "name": "json-only-model",
                    "model_id": "json-only-model",
                    "api_base_url": "https://example.com/v1",
                    "enabled": 1,
                    "priority": 1,
                }
            ]
        }
    )

    db = SessionLocal()
    try:
        assert db.query(models.ModelConfig).count() == 0
        assert _get_enabled_models(db) == []
        assert db.query(models.ModelConfig).count() == 0
    finally:
        db.close()


def test_runtime_does_not_restore_app_settings_from_json_backup():
    backup_config.save_config(
        {
            "app_settings": {
                "default_system_prompt": "json-backup-prompt",
                "state_broadcast_prompt": "json-backup-state",
                "enable_image_generation": False,
            }
        }
    )

    db = SessionLocal()
    try:
        db.query(models.AppSettings).delete()
        db.commit()

        settings = ensure_app_settings(db)

        assert settings.default_system_prompt == DEFAULT_SYSTEM_PROMPT_TEXT
        assert settings.state_broadcast_prompt == DEFAULT_STATE_BROADCAST_PROMPT
    finally:
        db.close()


def test_model_changes_do_not_auto_write_json_backup():
    if backup_config._CONFIG_FILE.exists():
        backup_config._CONFIG_FILE.unlink()
    backup_config.clear_cache()

    created = client.post(
        "/api/admin/models",
        json={
            "name": "db-only-model",
            "model_id": "db-only-model",
            "api_base_url": "https://example.com/v1",
            "api_key": "secret-key",
            "enabled": 1,
            "priority": 9,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
        },
    )
    created.raise_for_status()

    updated = client.put(
        "/api/admin/app-settings",
        json={"default_system_prompt": "db-only-prompt"},
    )
    updated.raise_for_status()

    assert not backup_config._CONFIG_FILE.exists()


def test_export_config_backup_writes_current_db_snapshot():
    if backup_config._CONFIG_FILE.exists():
        backup_config._CONFIG_FILE.unlink()
    backup_config.clear_cache()

    created = client.post(
        "/api/admin/models",
        json={
            "name": "backup-export-model",
            "model_id": "backup-export-model",
            "api_base_url": "https://example.com/v1",
            "api_key": "export-key",
            "enabled": 1,
            "priority": 1,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
        },
    )
    created.raise_for_status()

    app_settings_resp = client.put(
        "/api/admin/app-settings",
        json={
            "default_system_prompt": "exported-prompt",
            "default_image_style": "胶片感悬疑封面",
        },
    )
    app_settings_resp.raise_for_status()

    export_resp = client.post("/api/admin/config-backup/export")
    export_resp.raise_for_status()
    data = export_resp.json()

    assert data["ok"] is True
    assert data["models_count"] >= 1
    assert backup_config._CONFIG_FILE.exists()

    payload = json.loads(backup_config._CONFIG_FILE.read_text(encoding="utf-8"))
    assert payload["source"] == "database"
    assert payload["app_settings"]["default_system_prompt"] == "exported-prompt"
    assert payload["app_settings"]["default_image_style"] == "胶片感悬疑封面"
    exported_model = next(
        item for item in payload["models"] if item["name"] == "backup-export-model"
    )
    assert exported_model["ssl_verify"] is True
    assert any(item["name"] == "backup-export-model" for item in payload["models"])


def test_delete_model_clears_default_image_model_id():
    created = client.post(
        "/api/admin/models",
        json={
            "name": "image-model-delete",
            "model_id": "image-model-delete",
            "api_base_url": "https://example.com/v1",
            "api_key": "image-secret",
            "enabled": 1,
            "priority": 3,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
            "model_type": "image",
            "image_api_base": "https://example.com/images",
            "image_api_key": "image-secret",
        },
    )
    created.raise_for_status()
    model_id = created.json()["id"]

    updated = client.put(
        "/api/admin/app-settings",
        json={"default_image_model_id": model_id},
    )
    updated.raise_for_status()
    assert updated.json()["default_image_model_id"] == model_id

    deleted = client.delete(f"/api/admin/models/{model_id}")
    deleted.raise_for_status()

    fetched = client.get("/api/admin/app-settings")
    fetched.raise_for_status()
    assert fetched.json()["default_image_model_id"] is None


def test_import_config_backup_restores_db_snapshot_from_json_backup():
    existing = client.post(
        "/api/admin/models",
        json={
            "name": "stale-before-import",
            "model_id": "stale-before-import",
            "api_base_url": "https://example.com/v1",
            "api_key": "stale-key",
            "enabled": 1,
            "priority": 1,
            "price_input_per_1k": 0,
            "price_output_per_1k": 0,
            "pricing_unit": "per_1k",
        },
    )
    existing.raise_for_status()

    backup_config.save_config(
        {
            "exported_at": "2026-04-14T23:40:00",
            "source": "database",
            "migration_version": 2,
            "models": [
                {
                    "id": 501,
                    "name": "restored-chat",
                    "model_id": "restored-chat",
                    "api_base_url": "https://restore.example.com/v1",
                    "api_key": "encrypted-chat-key",
                    "enabled": 1,
                    "priority": 1,
                    "price_input_per_1k": 0.12,
                    "price_output_per_1k": 0.34,
                    "pricing_unit": "per_1k",
                    "model_type": "chat",
                    "image_api_base": "",
                    "image_api_key": "",
                    "ssl_verify": True,
                },
                {
                    "id": 502,
                    "name": "restored-image",
                    "model_id": "restored-image",
                    "api_base_url": "https://restore.example.com/v1",
                    "api_key": "encrypted-image-key",
                    "enabled": 1,
                    "priority": 2,
                    "price_input_per_1k": 0,
                    "price_output_per_1k": 0,
                    "pricing_unit": "per_1k",
                    "model_type": "image",
                    "image_api_base": "https://restore.example.com/images",
                    "image_api_key": "encrypted-image-key",
                    "ssl_verify": False,
                },
            ],
            "app_settings": {
                "default_system_prompt": "restored-system-prompt",
                "state_broadcast_prompt": "restored-state-prompt",
                "enable_image_generation": True,
                "default_image_model_id": 502,
                "image_size": "2K",
                "image_watermark": True,
                "default_image_style": "赛博水彩封面",
            },
            "user_settings": {
                "model_name": "restored-chat",
                "api_base_url": "https://restore.example.com/v1",
                "context_length": 18,
                "reply_style": "creative",
                "primary_model_id": 501,
                "backup_model_ids": [501, 999],
                "auto_generate_options": False,
                "theme": "light",
                "options_prompt": "restored-options-prompt",
                "copy_image_format": "binary",
                "disable_chat_bubble_elastic": True,
            },
        }
    )
    backup_config.clear_cache()

    imported = client.post("/api/admin/config-backup/import")
    imported.raise_for_status()
    data = imported.json()
    assert data["ok"] is True
    assert data["restored_models"] == 2
    assert data["removed_models"] >= 1

    db = SessionLocal()
    try:
        restored_models = db.query(models.ModelConfig).order_by(models.ModelConfig.id.asc()).all()
        assert [item.id for item in restored_models] == [501, 502]
        assert restored_models[0].name == "restored-chat"
        assert restored_models[1].ssl_verify is False

        app_settings = ensure_app_settings(db)
        assert app_settings.default_system_prompt == "restored-system-prompt"
        assert app_settings.default_image_model_id == 502
        assert app_settings.default_image_style == "赛博水彩封面"

        user_settings = db.query(models.UserSettings).first()
        assert user_settings is not None
        assert user_settings.primary_model_id == 501
        assert user_settings.backup_model_ids == []
        assert user_settings.auto_generate_options == 0
        assert user_settings.theme == "light"
        assert user_settings.copy_image_format == "binary"
        assert user_settings.disable_chat_bubble_elastic == 1
    finally:
        db.close()
