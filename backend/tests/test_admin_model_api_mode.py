from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_create_chat_model_with_api_mode():
    payload = {
        "name": "claude-test",
        "model_id": "claude-3-5-sonnet-20241022",
        "api_base_url": "https://api.anthropic.com",
        "api_key": "test-key",
        "api_mode": "claude_messages",
        "model_type": "chat",
        "priority": 1,
    }
    resp = client.post("/api/admin/models", json=payload)
    resp.raise_for_status()
    data = resp.json()
    assert data["api_mode"] == "claude_messages"
    assert data["image_api_mode"] == "openai_images"


def test_create_image_model_with_image_api_mode():
    payload = {
        "name": "openai-img",
        "model_id": "dall-e-3",
        "api_base_url": "https://api.openai.com",
        "api_key": "test-key",
        "api_mode": "openai_chat_completions",
        "image_api_mode": "openai_images",
        "model_type": "image",
        "image_api_base": "https://api.openai.com",
        "image_model_id": "dall-e-3",
        "priority": 2,
    }
    resp = client.post("/api/admin/models", json=payload)
    resp.raise_for_status()
    data = resp.json()
    assert data["image_api_mode"] == "openai_images"


def test_create_image_model_with_custom_api_mode():
    payload = {
        "name": "custom-img",
        "model_id": "custom-img-model",
        "api_base_url": "https://example.com",
        "api_key": "test-key",
        "api_mode": "openai_chat_completions",
        "image_api_mode": "custom_image",
        "model_type": "image",
        "image_api_base": "https://custom.example.com/v1/images/generations",
        "image_model_id": "custom-img-model",
        "priority": 5,
    }
    resp = client.post("/api/admin/models", json=payload)
    resp.raise_for_status()
    data = resp.json()
    assert data["image_api_mode"] == "custom_image"
    assert data["image_api_base"] == "https://custom.example.com/v1/images/generations"


def test_list_models_includes_api_mode():
    resp = client.get("/api/admin/models")
    resp.raise_for_status()
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "api_mode" in data[0]
        assert "image_api_mode" in data[0]


def test_update_model_api_mode():
    # create first
    create_resp = client.post(
        "/api/admin/models",
        json={
            "name": "update-test",
            "model_id": "gpt-4",
            "api_base_url": "https://api.openai.com/v1",
            "api_key": "k",
            "api_mode": "openai_chat_completions",
            "model_type": "chat",
            "priority": 3,
        },
    )
    create_resp.raise_for_status()
    model_id = create_resp.json()["id"]

    # update api_mode
    update_resp = client.put(
        f"/api/admin/models/{model_id}",
        json={
            "name": "update-test",
            "model_id": "gpt-4",
            "api_base_url": "https://api.openai.com/v1",
            "api_key": "",
            "api_mode": "openai_responses",
            "model_type": "chat",
            "priority": 3,
        },
    )
    update_resp.raise_for_status()
    assert update_resp.json()["api_mode"] == "openai_responses"


def test_test_endpoint_with_claude_mode():
    create_resp = client.post(
        "/api/admin/models",
        json={
            "name": "claude-test-endpoint",
            "model_id": "claude-3-5-sonnet-20241022",
            "api_base_url": "https://api.anthropic.com",
            "api_key": "fake-key",
            "api_mode": "claude_messages",
            "model_type": "chat",
            "priority": 10,
        },
    )
    create_resp.raise_for_status()
    model_id = create_resp.json()["id"]

    resp = client.post("/api/admin/models/test", params={"model_id": model_id})
    data = resp.json()
    assert "success" in data


def test_test_endpoint_with_image_model():
    create_resp = client.post(
        "/api/admin/models",
        json={
            "name": "img-test-endpoint",
            "model_id": "dall-e-3",
            "api_base_url": "https://api.openai.com",
            "api_key": "fake-key",
            "image_api_mode": "openai_images",
            "model_type": "image",
            "image_api_base": "https://api.openai.com",
            "image_model_id": "dall-e-3",
            "priority": 11,
        },
    )
    create_resp.raise_for_status()
    model_id = create_resp.json()["id"]

    resp = client.post("/api/admin/models/test", params={"model_id": model_id})
    data = resp.json()
    assert "success" in data


def test_test_model_reports_drift_on_401_with_drift_key(monkeypatch):
    """漂移 key + 401 → is_drift=True，文案含'密钥漂移'。"""
    from app.api import admin
    from app import models
    from app.database import SessionLocal

    import base64
    drift_blob = base64.b64encode(b"this-is-at-least-13-bytes-long!!").decode("ascii")

    monkeypatch.setattr(admin, "decrypt_safe", lambda c: (c, True) if c == drift_blob else (c, False))

    s = SessionLocal()
    try:
        m = models.ModelConfig(
            name="drift-model", model_id="m", api_base_url="https://fake.api",
            api_key=drift_blob, api_mode="openai_chat_completions", model_type="chat",
            enabled=1, priority=1,
        )
        s.add(m)
        s.commit()
        s.refresh(m)

        class FakeResp:
            status_code = 401
            text = "unauthorized"
        class FakeClient:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, *a, **k): return FakeResp()
        monkeypatch.setattr(admin.httpx, "Client", FakeClient)

        result = admin.test_model(m.id, s)
        assert result["is_drift"] is True
        assert "密钥漂移" in result["error"]
    finally:
        s.close()


def test_test_model_reports_apikey_error_on_401_with_plaintext_key(monkeypatch):
    """明文错 key + 401 → is_drift=False，文案='API Key 错误'。"""
    from app.api import admin
    from app import models
    from app.database import SessionLocal

    monkeypatch.setattr(admin, "decrypt_safe", lambda c: (c, False))

    s = SessionLocal()
    try:
        m = models.ModelConfig(
            name="plain-model", model_id="m", api_base_url="https://fake.api",
            api_key="wrong-plaintext-key", api_mode="openai_chat_completions",
            model_type="chat", enabled=1, priority=1,
        )
        s.add(m)
        s.commit()
        s.refresh(m)

        class FakeResp:
            status_code = 401
            text = "unauthorized"
        class FakeClient:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, *a, **k): return FakeResp()
        monkeypatch.setattr(admin.httpx, "Client", FakeClient)

        result = admin.test_model(m.id, s)
        assert result["is_drift"] is False
        assert result["error"] == "API Key 错误"
    finally:
        s.close()
