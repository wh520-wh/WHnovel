from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from . import config as backup_store
from . import models
from .app_settings_service import ensure_app_settings


def _get_or_create_user_settings(db: Session) -> models.UserSettings:
    settings = db.query(models.UserSettings).first()
    if not settings:
        settings = models.UserSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def build_backup_payload(db: Session) -> dict[str, Any]:
    models_payload = []
    rows = (
        db.query(models.ModelConfig)
        .order_by(models.ModelConfig.priority.asc(), models.ModelConfig.id.asc())
        .all()
    )
    for item in rows:
        models_payload.append(
            {
                "id": item.id,
                "name": item.name,
                "model_id": item.model_id,
                "api_base_url": item.api_base_url or "",
                "api_key": item.api_key or "",
                "enabled": item.enabled,
                "priority": item.priority,
                "price_input_per_1k": float(item.price_input_per_1k or 0.0),
                "price_output_per_1k": float(item.price_output_per_1k or 0.0),
                "pricing_unit": item.pricing_unit or "per_1k",
                "model_type": item.model_type or "chat",
                "image_api_base": item.image_api_base or "",
                "image_api_key": item.image_api_key or "",
                "ssl_verify": bool(item.ssl_verify),
            }
        )

    app_settings = ensure_app_settings(db)
    user_settings = _get_or_create_user_settings(db)

    return {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "source": "database",
        "migration_version": 2,
        "models": models_payload,
        "app_settings": {
            "default_system_prompt": app_settings.default_system_prompt or "",
            "state_broadcast_prompt": app_settings.state_broadcast_prompt or "",
            "enable_image_generation": bool(app_settings.enable_image_generation),
            "default_image_model_id": app_settings.default_image_model_id,
            "image_size": app_settings.image_size or "2K",
            "image_watermark": bool(app_settings.image_watermark),
            "default_image_style": app_settings.default_image_style or "",
        },
        "user_settings": {
            "model_name": user_settings.model_name or "",
            "api_base_url": user_settings.api_base_url or "",
            "context_length": user_settings.context_length or 10,
            "reply_style": user_settings.reply_style or "detailed",
            "primary_model_id": user_settings.primary_model_id,
            "backup_model_ids": user_settings.backup_model_ids or [],
            "auto_generate_options": bool(user_settings.auto_generate_options),
            "theme": user_settings.theme or "dark",
            "options_prompt": user_settings.options_prompt or "",
            "copy_image_format": user_settings.copy_image_format or "url",
            "disable_chat_bubble_elastic": bool(user_settings.disable_chat_bubble_elastic),
        },
    }


def export_backup_file(db: Session) -> tuple[Path, dict[str, Any]]:
    payload = build_backup_payload(db)
    backup_store.save_config(payload)
    backup_store.clear_cache()
    return backup_store._CONFIG_FILE, payload


def load_backup_payload() -> dict[str, Any]:
    backup_store.clear_cache()
    payload = backup_store.load_config()
    if not isinstance(payload, dict) or not payload:
        raise ValueError("未找到可导入的 JSON 备份文件")
    models_payload = payload.get("models")
    if not isinstance(models_payload, list):
        raise ValueError("备份文件缺少合法的 models 列表")
    return payload


def _require_positive_int(value: Any, *, field_name: str, index: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"models[{index}].{field_name} 必须是正整数")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"models[{index}].{field_name} 必须是正整数") from exc
    if parsed <= 0:
        raise ValueError(f"models[{index}].{field_name} 必须是正整数")
    return parsed


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_model_payload(item: dict[str, Any], index: int) -> dict[str, Any]:
    model_pk = _require_positive_int(item.get("id"), field_name="id", index=index)
    name = str(item.get("name") or "").strip()
    model_id = str(item.get("model_id") or "").strip()
    api_base_url = str(item.get("api_base_url") or "").strip()
    if not name:
        raise ValueError(f"models[{index}].name 不能为空")
    if not model_id:
        raise ValueError(f"models[{index}].model_id 不能为空")
    if not api_base_url:
        raise ValueError(f"models[{index}].api_base_url 不能为空")

    return {
        "id": model_pk,
        "name": name,
        "model_id": model_id,
        "api_base_url": api_base_url,
        "api_key": str(item.get("api_key") or ""),
        "enabled": _coerce_int(item.get("enabled"), 1),
        "priority": _coerce_int(item.get("priority"), 100),
        "price_input_per_1k": _coerce_float(item.get("price_input_per_1k"), 0.0),
        "price_output_per_1k": _coerce_float(item.get("price_output_per_1k"), 0.0),
        "pricing_unit": str(item.get("pricing_unit") or "per_1k"),
        "model_type": str(item.get("model_type") or "chat"),
        "image_api_base": str(item.get("image_api_base") or ""),
        "image_api_key": str(item.get("image_api_key") or ""),
        "ssl_verify": bool(item.get("ssl_verify", True)),
    }


def import_backup_file(db: Session) -> dict[str, Any]:
    payload = load_backup_payload()
    raw_models = payload.get("models") or []

    normalized_models: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, item in enumerate(raw_models):
        if not isinstance(item, dict):
            raise ValueError(f"models[{index}] 必须是对象")
        normalized = _normalize_model_payload(item, index)
        model_pk = normalized["id"]
        if model_pk in seen_ids:
            raise ValueError(f"models[{index}].id 重复: {model_pk}")
        seen_ids.add(model_pk)
        normalized_models.append(normalized)

    current_models = {item.id: item for item in db.query(models.ModelConfig).all()}
    restored_ids = {item["id"] for item in normalized_models}
    removed_ids = [model_id for model_id in current_models.keys() if model_id not in restored_ids]

    for item in normalized_models:
        model_data = dict(item)
        model_pk = model_data.pop("id")
        existing = current_models.get(model_pk)
        if existing is None:
            db.add(models.ModelConfig(id=model_pk, **model_data))
            continue
        for field, value in model_data.items():
            setattr(existing, field, value)

    app_settings = ensure_app_settings(db)
    user_settings = _get_or_create_user_settings(db)

    enabled_chat_model_ids = {
        item["id"]
        for item in normalized_models
        if item["enabled"] == 1 and item["model_type"] == "chat"
    }
    enabled_image_model_ids = {
        item["id"]
        for item in normalized_models
        if item["enabled"] == 1 and item["model_type"] == "image"
    }

    user_payload = payload.get("user_settings")
    if isinstance(user_payload, dict):
        primary_model_id = user_payload.get("primary_model_id")
        if primary_model_id is not None:
            primary_model_id = _coerce_int(primary_model_id, 0) or None
        if primary_model_id not in enabled_chat_model_ids:
            primary_model_id = None

        backup_model_ids: list[int] = []
        for raw_id in user_payload.get("backup_model_ids") or []:
            raw_id = _coerce_int(raw_id, 0)
            if raw_id <= 0:
                continue
            if raw_id == primary_model_id:
                continue
            if raw_id not in enabled_chat_model_ids:
                continue
            if raw_id in backup_model_ids:
                continue
            backup_model_ids.append(raw_id)

        user_settings.model_name = str(
            user_payload.get("model_name") or user_settings.model_name or ""
        )
        user_settings.api_base_url = str(
            user_payload.get("api_base_url") or user_settings.api_base_url or ""
        )
        user_settings.context_length = _coerce_int(
            user_payload.get("context_length"), user_settings.context_length or 10
        )
        user_settings.reply_style = str(
            user_payload.get("reply_style") or user_settings.reply_style or "detailed"
        )
        user_settings.primary_model_id = primary_model_id
        user_settings.backup_model_ids = backup_model_ids
        user_settings.auto_generate_options = (
            1 if bool(user_payload.get("auto_generate_options", True)) else 0
        )
        user_settings.theme = str(user_payload.get("theme") or user_settings.theme or "dark")
        user_settings.options_prompt = str(user_payload.get("options_prompt") or "")
        user_settings.copy_image_format = str(
            user_payload.get("copy_image_format") or user_settings.copy_image_format or "url"
        )
        user_settings.disable_chat_bubble_elastic = (
            1 if bool(user_payload.get("disable_chat_bubble_elastic", False)) else 0
        )

    app_payload = payload.get("app_settings")
    if isinstance(app_payload, dict):
        default_image_model_id = app_payload.get("default_image_model_id")
        if default_image_model_id is not None:
            default_image_model_id = _coerce_int(default_image_model_id, 0) or None
        if default_image_model_id not in enabled_image_model_ids:
            default_image_model_id = None

        app_settings.default_system_prompt = str(
            app_payload.get("default_system_prompt") or app_settings.default_system_prompt or ""
        )
        app_settings.state_broadcast_prompt = str(
            app_payload.get("state_broadcast_prompt") or app_settings.state_broadcast_prompt or ""
        )
        app_settings.enable_image_generation = (
            1 if bool(app_payload.get("enable_image_generation", False)) else 0
        )
        app_settings.default_image_model_id = default_image_model_id
        app_settings.image_size = str(
            app_payload.get("image_size") or app_settings.image_size or "2K"
        )
        app_settings.image_watermark = 1 if bool(app_payload.get("image_watermark", False)) else 0
        app_settings.default_image_style = str(
            app_payload.get("default_image_style") or app_settings.default_image_style or ""
        )

    if removed_ids:
        if user_settings.primary_model_id in removed_ids:
            user_settings.primary_model_id = None
        user_settings.backup_model_ids = [
            model_id
            for model_id in (user_settings.backup_model_ids or [])
            if model_id not in removed_ids
        ]
        if app_settings.default_image_model_id in removed_ids:
            app_settings.default_image_model_id = None
        for model_id in removed_ids:
            db.delete(current_models[model_id])

    db.commit()
    backup_store.clear_cache()

    return {
        "path": str(backup_store._CONFIG_FILE),
        "exported_at": payload.get("exported_at"),
        "restored_models": len(normalized_models),
        "removed_models": len(removed_ids),
        "restored_app_settings": isinstance(app_payload, dict),
        "restored_user_settings": isinstance(user_payload, dict),
    }
