from app import models
from app.api import chat_router as chat_api
from app.api import chat_stream
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
            name="option-pollution-model",
            model_id="option-pollution-model",
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
    resp = client.post(
        "/api/archives", json={"story_id": story_id, "name": "option-pollution-test"}
    )
    resp.raise_for_status()
    return resp.json()


def test_detect_body_pollution_flags_trailing_option_block():
    polluted = (
        "你将册子迅速塞入怀中，耳边的金属靴声已经逼近大厅入口。\n"
        "空气里泛起刺痛般的静默波纹，你必须立刻行动。\n\n"
        "低声回应无名之声，索取更多关于册子内容的意象碎片以快速理解\n"
        "尝试用阿勒夫之力扭曲局部现实，制造短暂的幻影分身迷惑追击者\n"
        "迅速搜索大厅边缘书架，寻找可能的隐藏通道或防御性古老载体"
    )

    assert chat_stream._detect_body_pollution(polluted, pre_delta=False) == "option_block"


def test_stream_body_pollution_option_block_after_delta_returns_special_error(monkeypatch):
    _ensure_model_config()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    def polluted_stream(model_cfg, messages, temperature, usage):
        usage["prompt_tokens"] = 10
        usage["completion_tokens"] = 20
        yield "你将册子迅速塞入怀中，耳边的金属靴声已经逼近大厅入口。\n空气里泛起刺痛般的静默波纹，你必须立刻行动。\n\n"
        yield "低声回应无名之声，索取更多关于册子内容的意象碎片以快速理解"
        yield "\n尝试用阿勒夫之力扭曲局部现实，制造短暂的幻影分身迷惑追击者"
        yield "\n迅速搜索大厅边缘书架，寻找可能的隐藏通道或防御性古老载体"

    monkeypatch.setattr(chat_api, "_stream_model_once", polluted_stream)

    resp = client.post(
        "/api/chat/send-stream", json={"archive_id": archive["id"], "message": "继续推进剧情"}
    )
    assert resp.status_code == 200
    assert '"code": "STREAM_BODY_POLLUTED"' in resp.text
    assert '"draft": false' in resp.text.lower()

    messages = client.get(f"/api/chat/messages/{archive['id']}").json()
    assert messages == []


def test_stream_chat_response_filters_non_dialogue_history(monkeypatch):
    """流式 history 不含 draft/broadcast/图片，首条非 system 为 user。"""
    from datetime import datetime, timedelta

    from app import models
    from app.api import chat_router, chat_stream
    from app.database import SessionLocal

    _ensure_model_config()
    db = SessionLocal()
    story = models.Story(title="stream filter test")
    archive = models.Archive(story=story, name="sf archive")
    db.add(archive)
    db.commit()
    db.refresh(archive)

    base = datetime(2026, 1, 1, 12, 0, 0)
    db.add_all(
        [
            models.ChatMessage(archive_id=archive.id, role="user", content="q1", created_at=base),
            models.ChatMessage(
                archive_id=archive.id,
                role="assistant",
                content="a1",
                created_at=base + timedelta(seconds=1),
                is_draft=0,
            ),
            models.ChatMessage(
                archive_id=archive.id,
                role="assistant",
                content="状态播报文本",
                created_at=base + timedelta(seconds=2),
                is_state_broadcast=1,
            ),
        ]
    )
    db.commit()

    captured = {}

    def fake_stream(model_cfg, messages, temperature, usage):
        captured["messages"] = messages
        usage["prompt_tokens"] = 1
        yield ""

    monkeypatch.setattr(chat_router, "_stream_model_once", fake_stream)

    settings = chat_router._get_or_create_settings(db)
    gen = chat_stream._stream_chat_response(
        db,
        story=story,
        archive=archive,
        settings=settings,
        user_content="q2",
        persist_user_content="q2",
        include_history=True,
        first_opening=False,
        stream_fn=fake_stream,
    )
    # 消耗生成器
    list(gen)

    msgs = captured["messages"]
    # 首条应为 system，第二条应为 user
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    bodies = [m["content"] for m in msgs]
    assert "状态播报文本" not in bodies
    assert "q1" in bodies and "a1" in bodies
