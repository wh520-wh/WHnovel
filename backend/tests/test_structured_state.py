import json

from app import models, schemas
from app.api import chat_router as chat_api
from app.api import story_generate as story_generate_api
from app.database import SessionLocal
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _first_story_id() -> int:
    resp = client.get("/api/stories")
    resp.raise_for_status()
    return resp.json()[0]["id"]


def _ensure_story_with_world_setting() -> int:
    """确保存在一个带 world_setting 的 story，并返回其 id。供需要 world_setting 的接口使用。"""
    db = SessionLocal()
    try:
        existing = (
            db.query(models.Story)
            .filter(models.Story.world_setting.isnot(None), models.Story.world_setting != "")
            .order_by(models.Story.id.asc())
            .first()
        )
        if existing:
            return existing.id
        story = models.Story(
            title="测试用故事",
            category="测试",
            tags="[]",
            description="",
            world_setting="测试世界观：旧港口、雾、深夜",
            image_style="电影感厚涂",
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        return story.id
    finally:
        db.close()


def _ensure_chat_model() -> int:
    db = SessionLocal()
    try:
        model = models.ModelConfig(
            name="ai-governance-model",
            model_id="ai-governance-model",
            api_base_url="https://example.com/v1",
            api_key="k",
            enabled=1,
            priority=1,
            model_type="chat",
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

        app_settings = db.query(models.AppSettings).first()
        if app_settings:
            app_settings.enable_image_generation = 0

        db.commit()
        return model.id
    finally:
        db.close()


def test_preset_openings_route_returns_wrapped_openings(monkeypatch):
    _ensure_chat_model()
    story_id = _ensure_story_with_world_setting()

    def fake_call(*args, **kwargs):
        return schemas.PresetOpeningsResponse(
            openings=[
                schemas.PresetOpeningItem(
                    id=1, label="转学生", value="你在雨夜拖着行李走进陌生校园。"
                ),
                schemas.PresetOpeningItem(
                    id=2, label="失忆者", value="你从病房醒来，只记得一个模糊名字。"
                ),
                schemas.PresetOpeningItem(
                    id=3, label="追捕者", value="你刚踏入城门，就被通缉令上的画像惊到。"
                ),
                schemas.PresetOpeningItem(
                    id=4, label="见习生", value="你第一次值夜班，就听见停尸房传来敲门声。"
                ),
                schemas.PresetOpeningItem(
                    id=5, label="归乡人", value="你回到故乡时，整条街的人都在躲着你。"
                ),
            ]
        )

    monkeypatch.setattr(chat_api, "_call_ai_with_failover", fake_call)

    resp = client.post("/api/chat/preset-openings", json={"story_id": story_id})
    resp.raise_for_status()
    data = resp.json()

    assert "openings" in data
    assert len(data["openings"]) == 5
    assert data["openings"][0]["id"] == 1
    assert data["openings"][0]["label"] == "转学生"


def test_story_generate_route_rejects_extra_fields_from_model(monkeypatch):
    _ensure_chat_model()

    def fake_call_model_once(model_cfg, messages, temperature, **kwargs):
        payload = {
            "title": "雾港异闻",
            "category": "悬疑",
            "tags": ["调查", "港口"],
            "cover_url": "",
            "description": "简介",
            "world_setting": "世界观",
            "image_style": "电影感厚涂",
            "extra_field": "not allowed",
        }
        return json.dumps(payload, ensure_ascii=False), {}

    monkeypatch.setattr(story_generate_api, "_call_model_once", fake_call_model_once)

    resp = client.post(
        "/api/stories/ai-generate",
        json={"category": "悬疑", "title_hint": "雾港", "tags_hint": "调查"},
    )
    assert resp.status_code == 500
    assert "生成失败" in resp.text


def test_story_generate_route_overrides_category_and_cover_url(monkeypatch):
    _ensure_chat_model()

    def fake_call_model_once(model_cfg, messages, temperature, **kwargs):
        payload = {
            "title": "雾港异闻",
            "category": "错误分类",
            "tags": ["调查", "港口", "迷雾"],
            "cover_url": "https://bad.example/cover.png",
            "description": "暴雨停靠的雾港里，失踪案与古老钟楼同时苏醒。",
            "world_setting": "港口城市每到午夜都会响起不属于现实的钟声。",
            "image_style": "冷色电影感插画",
        }
        return json.dumps(payload, ensure_ascii=False), {}

    monkeypatch.setattr(story_generate_api, "_call_model_once", fake_call_model_once)

    resp = client.post(
        "/api/stories/ai-generate",
        json={"category": "悬疑", "title_hint": "雾港", "tags_hint": "调查"},
    )
    resp.raise_for_status()
    data = resp.json()

    assert data["category"] == "悬疑"
    assert data["cover_url"] == ""
    assert data["title"] == "雾港异闻"
