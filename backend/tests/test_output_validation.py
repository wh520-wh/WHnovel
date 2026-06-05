from app import models, schemas
from app.api import chat_router as chat_api
from app.api.ai_contracts import (
    TASK_CHAT_RESPONSE,
    TASK_OPTIONS_GENERATE,
    TASK_STATE_BROADCAST,
    get_contract_output_rule,
)
from app.database import SessionLocal
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _first_story_id() -> int:
    resp = client.get("/api/stories")
    resp.raise_for_status()
    return resp.json()[0]["id"]


def _create_archive(story_id: int) -> dict:
    resp = client.post("/api/archives", json={"story_id": story_id, "name": "prompt-governance"})
    resp.raise_for_status()
    return resp.json()


def _ensure_enabled_model() -> int:
    db = SessionLocal()
    try:
        model = models.ModelConfig(
            name="prompt-governance-model",
            model_id="prompt-governance-model",
            api_base_url="https://example.com/v1",
            api_key="k",
            enabled=1,
            priority=1,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model.id
    finally:
        db.close()


def _stub_chat_response() -> schemas.ChatResponse:
    return schemas.ChatResponse(
        reply_text="测试回复",
        scene="测试场景",
        character_state={"hp": 90},
        story_state={"chapter": "第一章", "progress": 10},
        memory_update=["记忆1"],
    )


def test_send_uses_plot_progress_and_json_rule_prompts(monkeypatch):
    _ensure_enabled_model()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    captured: dict = {}

    def fake_call(*args, **kwargs):
        captured["messages"] = kwargs["messages"]
        return _stub_chat_response()

    monkeypatch.setattr(chat_api, "_call_ai_with_failover", fake_call)

    resp = client.post("/api/chat/send", json={"archive_id": archive["id"], "message": "继续推进"})
    resp.raise_for_status()

    system_content = captured["messages"][0]["content"]
    assert "【剧情推进与选项差异化约束】" in system_content
    assert chat_api.PLOT_PROGRESS_RULE_PROMPT in system_content
    assert "【输出规则】" in system_content
    assert get_contract_output_rule(TASK_CHAT_RESPONSE) in system_content


def test_options_generate_uses_plot_progress_and_json_rule_prompts(monkeypatch):
    _ensure_enabled_model()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    captured: dict = {}

    def fake_call(*args, **kwargs):
        captured["messages"] = kwargs["messages"]
        return schemas.OptionsGenerateOut(
            options=[
                "深入遗迹内部进行全面探索",
                "向同伴仔细询问关键线索详情",
                "冷静分析当前局势的具体情况",
            ]
        )

    monkeypatch.setattr(chat_api, "_call_ai_with_failover", fake_call)

    resp = client.post("/api/chat/options/generate", json={"archive_id": archive["id"], "count": 3})
    resp.raise_for_status()

    system_content = captured["messages"][0]["content"]
    assert "【剧情推进与选项差异化约束】" in system_content
    assert chat_api.PLOT_PROGRESS_RULE_PROMPT in system_content
    assert "【输出规则】" in system_content
    assert get_contract_output_rule(TASK_OPTIONS_GENERATE) in system_content


def test_state_generate_uses_state_broadcast_rule_without_plot_rule(monkeypatch):
    _ensure_enabled_model()
    story_id = _first_story_id()
    archive = _create_archive(story_id)

    captured: dict = {}

    def fake_call(*args, **kwargs):
        captured["messages"] = kwargs["messages"]
        return schemas.StateBroadcastOut(content="状态播报测试")

    monkeypatch.setattr(chat_api, "_call_ai_with_failover", fake_call)

    resp = client.post("/api/chat/state-broadcast", json={"archive_id": archive["id"]})
    resp.raise_for_status()

    system_content = captured["messages"][0]["content"]
    assert "【状态播报规则】" in system_content
    assert "状态播报" in system_content
    assert chat_api.PLOT_PROGRESS_RULE_PROMPT not in system_content
    assert "【输出规则】" in system_content
    assert get_contract_output_rule(TASK_STATE_BROADCAST) in system_content
