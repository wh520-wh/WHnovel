import json

from app import models, schemas
from app.api import chat_options, chat_stream
from app.api import chat_router as chat_api
from app.api.chat_locks import _get_or_create_lock
from app.database import SessionLocal
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _first_story_id() -> int:
    resp = client.get("/api/stories")
    resp.raise_for_status()
    return resp.json()[0]["id"]


def _ensure_model_config() -> int:
    db = SessionLocal()
    try:
        model = models.ModelConfig(
            name="stage3-stream-model",
            model_id="stage3-stream-model",
            api_base_url="https://example.com/v1",
            api_key="x",
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


def _create_archive(story_id: int) -> dict:
    resp = client.post("/api/archives", json={"story_id": story_id, "name": "stage3-test"})
    resp.raise_for_status()
    return resp.json()


DEFAULT_TAIL_PAYLOAD = {
    "reply_text": "",
    "scene": "测试场景",
    "character_state": {"emotion": "平静", "fatigue": 10, "mood": "安定"},
    "story_state": {
        "chapter": "第一章",
        "progress": 12,
        "current_goal": "",
        "current_conflict": "",
    },
    "memory_update": ["你记住了一个关键线索"],
    "plot_label": "",
    "highlight_terms": [],
}


def _build_fake_stream(stream_chunks):
    """Build a fake stream function that yields text chunks."""

    def fake_stream(model_cfg, messages, temperature, usage):
        for chunk in stream_chunks:  # noqa: UP028 — cannot use yield from, usage follows
            yield chunk
        # Set usage from tail
        usage["prompt_tokens"] = 10
        usage["completion_tokens"] = 20

    return fake_stream


def _fake_call_model_once(model_cfg, messages, temperature, **kwargs):
    """Fake _call_model_once that returns a valid tail JSON."""
    tail = json.dumps(DEFAULT_TAIL_PAYLOAD, ensure_ascii=False)
    usage = {"prompt_tokens": 5, "completion_tokens": 10}
    return tail, usage


def test_start_stream_emits_delta_before_tail_and_persists_after_validation(monkeypatch):
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    monkeypatch.setattr(
        chat_api,
        "_stream_model_once",
        _build_fake_stream(
            [
                "这是实时",
                "流式回复",
            ]
        ),
    )
    monkeypatch.setattr(chat_stream, "_call_model_once", _fake_call_model_once)

    resp = client.post(
        "/api/chat/start-stream",
        json={
            "story_id": story_id,
            "archive_id": archive["id"],
            "opening_requirement": "希望以雨夜开场，并出现神秘角色",
        },
    )

    assert resp.status_code == 200
    assert resp.text.index("event: delta") < resp.text.index("event: tail")
    assert resp.text.index("event: tail") < resp.text.index("event: done")
    # 正文收尾后应紧接一个 text_end 事件，用于前端立即释放 streaming 状态（Bug ①+②）
    assert "event: text_end" in resp.text
    assert resp.text.index("event: delta") < resp.text.index("event: text_end")
    assert resp.text.index("event: text_end") < resp.text.index("event: tail")
    assert "这是实时" in resp.text
    assert "流式回复" in resp.text

    messages = client.get(f"/api/chat/messages/{archive['id']}").json()
    assert len(messages) >= 2
    assert messages[0]["role"] == "user"
    assert "雨夜" in messages[0]["content"]
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "这是实时流式回复"

    db = SessionLocal()
    try:
        row = (
            db.query(models.ApiCallLog)
            .filter(
                models.ApiCallLog.archive_id == archive["id"],
                models.ApiCallLog.is_stream == 1,
                models.ApiCallLog.success == 1,
            )
            .order_by(models.ApiCallLog.id.desc())
            .first()
        )
        assert row is not None
        assert int(row.stream_emitted_delta or 0) == 1
        assert int(row.tail_valid or 0) == 1
        assert int(row.ttfb_ms or 0) >= 0
    finally:
        db.close()


def test_stream_midway_failure_returns_error_and_does_persist_draft(monkeypatch):
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    def broken_stream(*args, **kwargs):
        yield "半截回复已经形成完整句子，足以通过首屏缓冲。"
        raise RuntimeError("stream exploded")

    monkeypatch.setattr(chat_api, "_stream_model_once", broken_stream)

    resp = client.post(
        "/api/chat/send-stream", json={"archive_id": archive["id"], "message": "继续推进剧情"}
    )
    assert resp.status_code == 200
    assert "event: error" in resp.text
    assert "stream exploded" in resp.text

    # Draft should be persisted with partial text
    messages = client.get(f"/api/chat/messages/{archive['id']}").json()
    assert len(messages) >= 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["is_draft"] is True


def test_state_generate_creates_message_without_mutating_archive_state(monkeypatch):
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    def fake_call(*args, **kwargs):
        return schemas.StateBroadcastOut(content="此时你呼吸平稳，但警惕仍在上升。")

    monkeypatch.setattr(chat_api, "_call_ai_with_failover", fake_call)

    before = client.get(f"/api/archives/{archive['id']}").json()

    resp = client.post("/api/chat/state-broadcast", json={"archive_id": archive["id"]})
    resp.raise_for_status()
    data = resp.json()

    after = client.get(f"/api/archives/{archive['id']}").json()
    messages = client.get(f"/api/chat/messages/{archive['id']}").json()

    assert data["role"] == "assistant"
    assert data["content"] == "此时你呼吸平稳，但警惕仍在上升。"
    assert before["state_data"] == after["state_data"]
    assert before["story_state"] == after["story_state"]
    assert before["memory_log"] == after["memory_log"]
    assert len(messages) == 1
    assert messages[0]["content"] == data["content"]


def test_options_generation_rejects_concurrent_duplicate_request_logic_contract():
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    lock = _get_or_create_lock(
        chat_options._option_generation_locks,
        chat_options._option_generation_locks_guard,
        archive["id"],
    )
    acquired = lock.acquire(blocking=False)
    assert acquired is True
    try:
        resp = client.post(
            "/api/chat/options/generate", json={"archive_id": archive["id"], "count": 3}
        )
    finally:
        lock.release()

    assert resp.status_code == 409
    assert "正在生成剧情选择项" in resp.text


def test_send_stream_switches_backup_only_before_first_delta(monkeypatch):
    db = SessionLocal()
    try:
        story = db.query(models.Story).order_by(models.Story.id.asc()).first()
        assert story is not None
        archive = models.Archive(
            story_id=story.id,
            name="backup-switch-test",
            state_data={},
            story_state={"chapter": "第一章", "progress": 0},
            memory_log=[],
        )
        db.add(archive)

        primary = models.ModelConfig(
            name="primary-stream-model",
            model_id="primary-stream-model",
            api_base_url="https://example.com/v1",
            api_key="k1",
            enabled=1,
            priority=1,
        )
        backup = models.ModelConfig(
            name="backup-stream-model",
            model_id="backup-stream-model",
            api_base_url="https://example.com/v1",
            api_key="k2",
            enabled=1,
            priority=2,
        )
        db.add_all([primary, backup])
        db.commit()
        db.refresh(archive)
        db.refresh(primary)
        db.refresh(backup)

        settings = db.query(models.UserSettings).first()
        if not settings:
            settings = models.UserSettings()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        settings.primary_model_id = primary.id
        settings.backup_model_ids = [backup.id]
        db.commit()
        archive_id = archive.id
    finally:
        db.close()

    calls: list[str] = []

    def fake_stream(model_cfg, messages, temperature, usage):
        calls.append(model_cfg.model_id)
        if model_cfg.model_id == "primary-stream-model":
            raise RuntimeError("primary failed before delta")
        usage["prompt_tokens"] = 10
        usage["completion_tokens"] = 20
        yield "备用模型接管成功"

    monkeypatch.setattr(chat_api, "_stream_model_once", fake_stream)
    monkeypatch.setattr(chat_stream, "_call_model_once", _fake_call_model_once)

    resp = client.post(
        "/api/chat/send-stream", json={"archive_id": archive_id, "message": "继续推进剧情"}
    )
    assert resp.status_code == 200
    assert "event: delta" in resp.text
    assert "event: tail" in resp.text
    assert "event: done" in resp.text
    assert calls == ["primary-stream-model", "backup-stream-model"]


def test_send_stream_does_not_switch_backup_after_first_delta(monkeypatch):
    """After deltas have been emitted, a failure should NOT try backup — should return error with draft."""
    db = SessionLocal()
    try:
        story = db.query(models.Story).order_by(models.Story.id.asc()).first()
        assert story is not None
        archive = models.Archive(
            story_id=story.id,
            name="no-backup-after-delta-test",
            state_data={},
            story_state={"chapter": "第一章", "progress": 0},
            memory_log=[],
        )
        db.add(archive)

        primary = models.ModelConfig(
            name="primary-stream-model-2",
            model_id="primary-stream-model-2",
            api_base_url="https://example.com/v1",
            api_key="k1",
            enabled=1,
            priority=1,
        )
        backup = models.ModelConfig(
            name="backup-stream-model-2",
            model_id="backup-stream-model-2",
            api_base_url="https://example.com/v1",
            api_key="k2",
            enabled=1,
            priority=2,
        )
        db.add_all([primary, backup])
        db.commit()
        db.refresh(archive)
        db.refresh(primary)
        db.refresh(backup)

        settings = db.query(models.UserSettings).first()
        if not settings:
            settings = models.UserSettings()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        settings.primary_model_id = primary.id
        settings.backup_model_ids = [backup.id]
        db.commit()
        archive_id = archive.id
    finally:
        db.close()

    calls: list[str] = []

    def fake_stream(model_cfg, messages, temperature, usage):
        calls.append(model_cfg.model_id)
        # Emit body text, then fail before second call
        yield "已经输出首段，而且内容足够长，会先被发送给前端。"
        raise RuntimeError("primary exploded after delta")

    monkeypatch.setattr(chat_api, "_stream_model_once", fake_stream)

    resp = client.post("/api/chat/send-stream", json={"archive_id": archive_id, "message": "推进"})
    assert resp.status_code == 200
    assert "event: error" in resp.text
    assert "primary exploded after delta" in resp.text
    assert calls == ["primary-stream-model-2"]

    db = SessionLocal()
    try:
        row = (
            db.query(models.ApiCallLog)
            .filter(
                models.ApiCallLog.archive_id == archive_id,
                models.ApiCallLog.model_name == "primary-stream-model-2",
                models.ApiCallLog.success == 0,
                models.ApiCallLog.is_stream == 1,
            )
            .order_by(models.ApiCallLog.id.desc())
            .first()
        )
        assert row is not None
        assert int(row.stream_emitted_delta or 0) == 1
        assert int(row.fallback_used or 0) == 0
    finally:
        db.close()


def test_stream_second_call_fails_draft_persisted(monkeypatch):
    """First call succeeds with body text, but second call (metadata extraction) fails.
    Should persist draft with body text and return error."""
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    monkeypatch.setattr(
        chat_api,
        "_stream_model_once",
        _build_fake_stream(
            [
                "正文内容已完成",
            ]
        ),
    )

    def failing_tail_call(model_cfg, messages, temperature, **kwargs):
        raise RuntimeError("second call failed: JSON parse error")

    monkeypatch.setattr(chat_stream, "_call_model_once", failing_tail_call)

    resp = client.post(
        "/api/chat/send-stream", json={"archive_id": archive["id"], "message": "推进剧情"}
    )
    assert resp.status_code == 200
    assert "event: error" in resp.text
    assert "second call failed" in resp.text

    messages = client.get(f"/api/chat/messages/{archive['id']}").json()
    assert len(messages) >= 2
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "正文内容已完成"


def test_stream_second_call_returns_invalid_json(monkeypatch):
    """Second call returns text that cannot be parsed as JSON."""
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    monkeypatch.setattr(
        chat_api,
        "_stream_model_once",
        _build_fake_stream(
            [
                "纯文本正文",
            ]
        ),
    )

    def bad_json_call(model_cfg, messages, temperature, **kwargs):
        return "这不是JSON，只是一段纯文字", {"prompt_tokens": 5, "completion_tokens": 10}

    monkeypatch.setattr(chat_stream, "_call_model_once", bad_json_call)

    resp = client.post(
        "/api/chat/send-stream", json={"archive_id": archive["id"], "message": "test"}
    )
    assert resp.status_code == 200
    assert "event: error" in resp.text


def test_stream_body_pollution_before_first_delta_switches_backup(monkeypatch):
    db = SessionLocal()
    try:
        story = db.query(models.Story).order_by(models.Story.id.asc()).first()
        assert story is not None
        archive = models.Archive(
            story_id=story.id,
            name="pollution-backup-test",
            state_data={},
            story_state={"chapter": "第一章", "progress": 0},
            memory_log=[],
        )
        db.add(archive)

        primary = models.ModelConfig(
            name="polluted-primary",
            model_id="polluted-primary",
            api_base_url="https://example.com/v1",
            api_key="k1",
            enabled=1,
            priority=1,
        )
        backup = models.ModelConfig(
            name="clean-backup",
            model_id="clean-backup",
            api_base_url="https://example.com/v1",
            api_key="k2",
            enabled=1,
            priority=2,
        )
        db.add_all([primary, backup])
        db.commit()
        db.refresh(archive)
        db.refresh(primary)
        db.refresh(backup)

        settings = db.query(models.UserSettings).first()
        if not settings:
            settings = models.UserSettings()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        settings.primary_model_id = primary.id
        settings.backup_model_ids = [backup.id]
        db.commit()
        archive_id = archive.id
    finally:
        db.close()

    calls: list[str] = []

    def polluted_stream(model_cfg, messages, temperature, usage):
        calls.append(model_cfg.model_id)
        usage["prompt_tokens"] = 10
        usage["completion_tokens"] = 20
        if model_cfg.model_id == "polluted-primary":
            yield '{"reply_text":"污染正文"}'
            return
        yield "备用模型恢复了正常正文。"

    monkeypatch.setattr(chat_api, "_stream_model_once", polluted_stream)
    monkeypatch.setattr(chat_stream, "_call_model_once", _fake_call_model_once)

    resp = client.post(
        "/api/chat/send-stream", json={"archive_id": archive_id, "message": "继续推进"}
    )
    assert resp.status_code == 200
    assert "备用模型恢复了正常正文。" in resp.text
    assert "event: tail" in resp.text
    assert calls == ["polluted-primary", "clean-backup"]


def test_stream_body_pollution_after_delta_returns_special_error_without_draft(monkeypatch):
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    def polluted_stream(model_cfg, messages, temperature, usage):
        usage["prompt_tokens"] = 10
        usage["completion_tokens"] = 20
        yield "夜色压在屋檐上，你听见门外传来急促脚步。"
        yield '\n```json\n{"reply_text":"bad"}\n```'

    monkeypatch.setattr(chat_api, "_stream_model_once", polluted_stream)

    resp = client.post(
        "/api/chat/send-stream", json={"archive_id": archive["id"], "message": "推进剧情"}
    )
    assert resp.status_code == 200
    assert '"code": "STREAM_BODY_POLLUTED"' in resp.text
    assert '"draft": false' in resp.text.lower()

    messages = client.get(f"/api/chat/messages/{archive['id']}").json()
    assert messages == []
