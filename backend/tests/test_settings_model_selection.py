from app import models
from app.api.chat_models import _get_enabled_models
from app.database import SessionLocal
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_settings_backup_models_are_normalized():
    db = SessionLocal()
    try:
        m1 = models.ModelConfig(
            name="m1",
            model_id="m1",
            api_base_url="https://example.com/v1",
            api_key="k1",
            enabled=1,
            priority=1,
        )
        m2 = models.ModelConfig(
            name="m2",
            model_id="m2",
            api_base_url="https://example.com/v1",
            api_key="k2",
            enabled=1,
            priority=2,
        )
        db.add_all([m1, m2])
        db.commit()
        db.refresh(m1)
        db.refresh(m2)
    finally:
        db.close()

    # 故意传入：包含主模型、重复项
    resp = client.put(
        "/api/settings",
        json={
            "primary_model_id": m1.id,
            "backup_model_ids": [m1.id, m2.id, m2.id, m1.id],
        },
    )
    resp.raise_for_status()
    data = resp.json()

    assert data["primary_model_id"] == m1.id
    assert data["backup_model_ids"] == [m2.id]


def test_settings_roundtrip_persistence():
    db = SessionLocal()
    try:
        m = models.ModelConfig(
            name="persist-model",
            model_id="persist-model",
            api_base_url="https://example.com/v1",
            api_key="persist-key",
            enabled=1,
            priority=3,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
    finally:
        db.close()

    payload = {
        "primary_model_id": m.id,
        "backup_model_ids": [],
        "context_length": 18,
        "reply_style": "creative",
        "theme": "dark",
        "copy_image_format": "binary",
        "disable_chat_bubble_elastic": True,
    }
    save_resp = client.put("/api/settings", json=payload)
    save_resp.raise_for_status()

    get_resp = client.get("/api/settings")
    get_resp.raise_for_status()
    data = get_resp.json()
    assert data["primary_model_id"] == payload["primary_model_id"]
    assert data["backup_model_ids"] == payload["backup_model_ids"]
    assert data["context_length"] == payload["context_length"]
    assert data["reply_style"] == payload["reply_style"]
    assert data["theme"] == payload["theme"]
    assert data["copy_image_format"] == payload["copy_image_format"]
    assert data["disable_chat_bubble_elastic"] is payload["disable_chat_bubble_elastic"]


def test_update_unrelated_setting_should_not_be_blocked_by_stale_disabled_primary():
    db = SessionLocal()
    try:
        m = models.ModelConfig(
            name="stale-primary-model",
            model_id="stale-primary-model",
            api_base_url="https://example.com/v1",
            api_key="stale-key",
            enabled=1,
            priority=9,
        )
        db.add(m)
        db.commit()
        db.refresh(m)

        s = db.query(models.UserSettings).first()
        if not s:
            s = models.UserSettings()
            db.add(s)
            db.commit()
            db.refresh(s)
        s.primary_model_id = m.id
        s.backup_model_ids = [m.id]
        db.commit()

        # Disable model afterwards to simulate stale settings.
        m.enabled = 0
        db.commit()
    finally:
        db.close()

    resp = client.put("/api/settings", json={"auto_generate_options": False})
    resp.raise_for_status()
    data = resp.json()
    assert data["auto_generate_options"] is False
    assert data["primary_model_id"] is None
    assert data["backup_model_ids"] == []


def test_settings_reject_image_model_as_primary_model():
    db = SessionLocal()
    try:
        image_model = models.ModelConfig(
            name="image-only-model",
            model_id="image-only-model",
            api_base_url="https://example.com/v1",
            api_key="image-key",
            enabled=1,
            priority=1,
            model_type="image",
        )
        db.add(image_model)
        db.commit()
        db.refresh(image_model)
    finally:
        db.close()

    resp = client.put(
        "/api/settings",
        json={"primary_model_id": image_model.id},
    )
    assert resp.status_code == 400
    assert "主模型未启用或不存在" in resp.text


def test_chat_enabled_models_exclude_image_models():
    db = SessionLocal()
    try:
        chat_model = models.ModelConfig(
            name="chat-model",
            model_id="chat-model",
            api_base_url="https://example.com/v1",
            api_key="chat-key",
            enabled=1,
            priority=1,
            model_type="chat",
        )
        image_model = models.ModelConfig(
            name="image-model",
            model_id="image-model",
            api_base_url="https://example.com/v1",
            api_key="image-key",
            enabled=1,
            priority=2,
            model_type="image",
        )
        db.add_all([chat_model, image_model])
        db.commit()
        db.refresh(chat_model)
        db.refresh(image_model)

        enabled = _get_enabled_models(db)
        assert [item.id for item in enabled] == [chat_model.id]
    finally:
        db.close()
