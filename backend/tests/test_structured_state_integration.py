import pytest
from app import models, schemas
from app.api import chat_router as chat_api
from app.database import SessionLocal
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient

client = TestClient(app)


def _get_first_story_id() -> int:
    resp = client.get("/api/stories")
    resp.raise_for_status()
    data = resp.json()
    assert len(data) > 0
    return data[0]["id"]


def _create_archive() -> dict:
    story_id = _get_first_story_id()
    resp = client.post("/api/archives", json={"story_id": story_id, "name": "测试存档"})
    resp.raise_for_status()
    return resp.json()


def _ensure_chat_model() -> int:
    db = SessionLocal()
    try:
        model = models.ModelConfig(
            name="state-test-model",
            model_id="state-test-model",
            api_base_url="https://example.com/v1",
            api_key="state-test-key",
            enabled=1,
            priority=1,
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        settings = db.query(models.UserSettings).first()
        if not settings:
            settings = models.UserSettings()
            db.add(settings)
            db.commit()
            db.refresh(settings)

        settings.primary_model_id = model.id
        settings.backup_model_ids = []
        db.commit()
        return model.id
    finally:
        db.close()


@pytest.fixture(autouse=True)
def mock_ai_call(monkeypatch):
    def _fake_call_ai_with_failover(*args, **kwargs):
        return schemas.ChatResponse(
            reply_text="测试回复",
            scene="测试场景",
            character_state={"scene": "测试场景", "好感度": 66},
            story_state={"chapter": "第一章", "progress": 42},
            options=["继续", "离开"],
            memory_update=["测试记忆"],
        )

    monkeypatch.setattr(chat_api, "_call_ai_with_failover", _fake_call_ai_with_failover)


def test_create_archive_initializes_story_state_and_memory_log():
    archive = _create_archive()
    assert "story_state" in archive
    assert "memory_log" in archive
    assert archive["story_state"] == {"chapter": "第一章", "progress": 0}
    assert archive["memory_log"] == []


def test_chat_response_schema_complete():
    _ensure_chat_model()
    archive = _create_archive()
    resp = client.post("/api/chat/send", json={"archive_id": archive["id"], "message": "继续调查"})
    resp.raise_for_status()
    data = resp.json()

    for key in ["reply_text", "scene", "character_state", "story_state", "memory_update"]:
        assert key in data
    assert isinstance(data["character_state"], dict)
    assert isinstance(data["story_state"], dict)
    assert isinstance(data["memory_update"], list)


def test_send_message_persists_archive_structured_state():
    _ensure_chat_model()
    archive = _create_archive()
    chat = client.post("/api/chat/send", json={"archive_id": archive["id"], "message": "记录线索"})
    chat.raise_for_status()
    reply = chat.json()

    archive_resp = client.get(f"/api/archives/{archive['id']}")
    archive_resp.raise_for_status()
    saved = archive_resp.json()

    assert saved["state_data"] == reply["character_state"]
    assert saved["story_state"] == reply["story_state"]
    assert len(saved["memory_log"]) >= len(reply["memory_update"])
    assert saved["memory_log"][-len(reply["memory_update"]) :] == reply["memory_update"]


def test_get_messages_returns_structured_fields():
    _ensure_chat_model()
    archive = _create_archive()
    send_resp = client.post(
        "/api/chat/send", json={"archive_id": archive["id"], "message": "观察细节"}
    )
    send_resp.raise_for_status()

    msg_resp = client.get(f"/api/chat/messages/{archive['id']}")
    msg_resp.raise_for_status()
    messages = msg_resp.json()
    assert len(messages) >= 2

    for msg in messages:
        assert "story_state" in msg
        assert "memory_update" in msg
        assert isinstance(msg["story_state"], dict)
        assert isinstance(msg["memory_update"], list)


def test_send_failure_should_not_persist_user_message(monkeypatch):
    _ensure_chat_model()

    def _raise_fail(*args, **kwargs):
        from fastapi import HTTPException

        raise HTTPException(503, "all failed")

    monkeypatch.setattr(chat_api, "_call_ai_with_failover", _raise_fail)

    archive = _create_archive()
    resp = client.post(
        "/api/chat/send", json={"archive_id": archive["id"], "message": "这条会失败"}
    )
    assert resp.status_code == 503

    msg_resp = client.get(f"/api/chat/messages/{archive['id']}")
    msg_resp.raise_for_status()
    assert msg_resp.json() == []
