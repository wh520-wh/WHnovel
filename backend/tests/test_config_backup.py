"""Bug #6 回归：config_backup 导出/导入必须保留 v17+ 新增字段，版本号对齐 SCHEMA_VERSION。

根因：导出/导入字段清单手工维护，与 models.py 漂移——ComfyUI workflow、
自定义 api_mode、response_format_mode 等配置在"导出→重装→导入"主路径下静默丢失。
"""

import pytest
from app import config as backup_config
from app import models
from app.app_settings_service import ensure_app_settings
from app.config_backup import build_backup_payload, import_backup_file
from app.database import SessionLocal
from app.migrations import SCHEMA_VERSION


def _make_model(db, **overrides):
    payload = {
        "name": "cfg-backup-model",
        "model_id": "cfg-backup-model",
        "api_base_url": "https://example.com/v1",
        "api_key": "k",
        "enabled": 1,
        "priority": 1,
        "model_type": "chat",
    }
    payload.update(overrides)
    item = models.ModelConfig(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_export_includes_v17_plus_fields_and_current_schema_version():
    db = SessionLocal()
    try:
        _make_model(
            db,
            api_mode="claude_messages",
            temperature=0.7,
            max_tokens=4096,
            response_format_mode="json_object",
        )
        _make_model(
            db,
            name="cfg-backup-image",
            model_id="cfg-backup-image",
            model_type="image",
            image_api_mode="comfyui",
            image_workflow_template='{"nodes":[]}',
        )
        payload = build_backup_payload(db)
    finally:
        db.close()

    by_name = {item["name"]: item for item in payload["models"]}
    chat = by_name["cfg-backup-model"]
    assert chat["api_mode"] == "claude_messages"
    assert chat["temperature"] == 0.7
    assert chat["max_tokens"] == 4096
    assert chat["response_format_mode"] == "json_object"

    image = by_name["cfg-backup-image"]
    assert image["image_api_mode"] == "comfyui"
    assert image["image_workflow_template"] == '{"nodes":[]}'

    # 版本号不得再硬编码旧值，必须与 migrations.SCHEMA_VERSION 对齐
    assert payload["migration_version"] == SCHEMA_VERSION


def test_import_restores_v17_plus_fields_on_fresh_db():
    """核心场景：ComfyUI/自定义模式配置经 导出→空库→导入 后不得丢失。"""
    backup_config.save_config(
        {
            "exported_at": "2026-07-21T00:00:00",
            "source": "database",
            "migration_version": SCHEMA_VERSION,
            "models": [
                {
                    "id": 601,
                    "name": "restored-comfy",
                    "model_id": "restored-comfy",
                    "api_base_url": "https://restore.example.com/v1",
                    "api_key": "k",
                    "enabled": 1,
                    "priority": 1,
                    "price_input_per_1k": 0,
                    "price_output_per_1k": 0,
                    "pricing_unit": "per_1k",
                    "model_type": "image",
                    "image_api_base": "https://restore.example.com/images",
                    "image_api_key": "ik",
                    "ssl_verify": True,
                    "api_mode": "openai_chat_completions",
                    "image_api_mode": "comfyui",
                    "image_workflow_template": '{"1":{"class_type":"KSampler"}}',
                    "temperature": 0.9,
                    "max_tokens": 2048,
                    "response_format_mode": "json_object",
                }
            ],
        }
    )
    backup_config.clear_cache()

    db = SessionLocal()
    try:
        import_backup_file(db)
        item = db.query(models.ModelConfig).filter_by(id=601).one()
        assert item.image_api_mode == "comfyui"
        assert item.image_workflow_template == '{"1":{"class_type":"KSampler"}}'
        assert item.temperature == 0.9
        assert item.max_tokens == 2048
        assert item.response_format_mode == "json_object"
    finally:
        db.close()


def test_import_old_backup_without_new_fields_preserves_existing_values():
    """旧版备份（缺新字段键）导入：更新路径保留现值，新建路径取 DB 默认值。"""
    db = SessionLocal()
    try:
        _make_model(db, id=602, api_mode="claude_messages", response_format_mode="json_object")
    finally:
        db.close()

    old_shape_model = {
        "id": 602,
        "name": "cfg-backup-model",
        "model_id": "cfg-backup-model",
        "api_base_url": "https://example.com/v1",
        "api_key": "k",
        "enabled": 1,
        "priority": 1,
        "price_input_per_1k": 0,
        "price_output_per_1k": 0,
        "pricing_unit": "per_1k",
        "model_type": "chat",
        "image_api_base": "",
        "image_api_key": "",
        "ssl_verify": True,
        # 无 api_mode / response_format_mode 等 v17+ 键
    }
    backup_config.save_config(
        {
            "exported_at": "2026-04-14T23:40:00",
            "source": "database",
            "migration_version": 2,
            "models": [old_shape_model, {**old_shape_model, "id": 603, "name": "old-new"}],
        }
    )
    backup_config.clear_cache()

    db = SessionLocal()
    try:
        import_backup_file(db)
        updated = db.query(models.ModelConfig).filter_by(id=602).one()
        assert updated.api_mode == "claude_messages"
        assert updated.response_format_mode == "json_object"

        created = db.query(models.ModelConfig).filter_by(id=603).one()
        assert created.api_mode == "openai_chat_completions"
        assert created.response_format_mode == "json_schema"
    finally:
        db.close()


def test_import_rejects_backup_from_newer_version():
    backup_config.save_config(
        {
            "exported_at": "2026-07-21T00:00:00",
            "source": "database",
            "migration_version": SCHEMA_VERSION + 1,
            "models": [],
        }
    )
    backup_config.clear_cache()

    db = SessionLocal()
    try:
        with pytest.raises(ValueError, match="版本"):
            import_backup_file(db)
    finally:
        db.close()


def test_import_sanitizes_invalid_image_size():
    """与 Bug #18 同一事实源：备份里的非法 image_size 导入时兜底 "2K"。"""
    db = SessionLocal()
    try:
        original = ensure_app_settings(db).image_size
    finally:
        db.close()

    backup_config.save_config(
        {
            "exported_at": "2026-07-21T00:00:00",
            "source": "database",
            "migration_version": SCHEMA_VERSION,
            "models": [],
            "app_settings": {"image_size": "banana-size"},
        }
    )
    backup_config.clear_cache()

    db = SessionLocal()
    try:
        import_backup_file(db)
        assert ensure_app_settings(db).image_size == "2K"
        ensure_app_settings(db).image_size = original
        db.commit()
    finally:
        db.close()
