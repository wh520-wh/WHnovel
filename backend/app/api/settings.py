import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..redis_client import get_redis

router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTINGS_CACHE_KEY = "cache:settings:user"
SETTINGS_CACHE_TTL = 600  # 10 minutes


def _invalidate_settings_cache():
    redis = get_redis()
    redis.delete(SETTINGS_CACHE_KEY)


def _get_or_create(db: Session) -> models.UserSettings:
    s = db.query(models.UserSettings).first()
    if not s:
        s = models.UserSettings()
        db.add(s)
        db.commit()
        db.refresh(s)

    if s.backup_model_ids is None:
        s.backup_model_ids = []
    if s.auto_generate_options is None:
        s.auto_generate_options = 1
    if s.copy_image_format is None:
        s.copy_image_format = "url"
    if s.disable_chat_bubble_elastic is None:
        s.disable_chat_bubble_elastic = 0
    if s.show_background_image is None:
        s.show_background_image = 1
    if s.memory_inject_count is None:
        s.memory_inject_count = 50
    db.commit()
    db.refresh(s)
    return s


def _normalize_backup_model_ids(ids: list[int] | None, primary_model_id: int | None) -> list[int]:
    if not ids:
        return []
    seen = set()
    result: list[int] = []
    for mid in ids:
        if mid == primary_model_id:
            continue
        if mid in seen:
            continue
        seen.add(mid)
        result.append(mid)
    return result


@router.get("", response_model=schemas.UserSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    redis = get_redis()
    if redis.is_available():
        cached = redis.get(SETTINGS_CACHE_KEY)
        if cached:
            try:
                data = json.loads(cached)
                return schemas.UserSettingsOut.model_validate(data)
            except Exception:
                pass

    s = _get_or_create(db)

    if redis.is_available():
        cache_data = {
            "id": s.id,
            "model_name": s.model_name,
            "api_base_url": s.api_base_url,
            "context_length": s.context_length,
            "reply_style": s.reply_style,
            "primary_model_id": s.primary_model_id,
            "backup_model_ids": s.backup_model_ids or [],
            "auto_generate_options": bool(s.auto_generate_options),
            "theme": s.theme,
            "options_prompt": s.options_prompt,
            "copy_image_format": s.copy_image_format,
            "disable_chat_bubble_elastic": bool(s.disable_chat_bubble_elastic),
            "show_background_image": bool(s.show_background_image),
            "memory_inject_count": s.memory_inject_count,
        }
        redis.set(
            SETTINGS_CACHE_KEY, json.dumps(cache_data, ensure_ascii=False), ttl=SETTINGS_CACHE_TTL
        )

    return s


@router.put("", response_model=schemas.UserSettingsOut)
def update_settings(payload: schemas.UserSettingsUpdate, db: Session = Depends(get_db)):
    s = _get_or_create(db)
    data = payload.model_dump(exclude_unset=True)

    enabled_model_ids = {
        m.id
        for m in db.query(models.ModelConfig)
        .filter(models.ModelConfig.enabled == 1, models.ModelConfig.model_type == "chat")
        .all()
    }
    explicit_primary = "primary_model_id" in data
    explicit_backups = "backup_model_ids" in data

    primary_model_id = data.get("primary_model_id", s.primary_model_id)
    backup_model_ids = data.get("backup_model_ids", s.backup_model_ids or [])

    if primary_model_id is not None and primary_model_id not in enabled_model_ids:
        if explicit_primary:
            raise HTTPException(400, "主模型未启用或不存在")
        primary_model_id = None

    normalized_backup_ids = _normalize_backup_model_ids(backup_model_ids, primary_model_id)
    filtered_backup_ids: list[int] = []
    for mid in normalized_backup_ids:
        if mid not in enabled_model_ids:
            if explicit_backups:
                raise HTTPException(400, "备用模型未启用或不存在")
            continue
        filtered_backup_ids.append(mid)

    data["primary_model_id"] = primary_model_id
    data["backup_model_ids"] = filtered_backup_ids

    if "auto_generate_options" in data:
        data["auto_generate_options"] = 1 if data["auto_generate_options"] else 0
    if "disable_chat_bubble_elastic" in data:
        data["disable_chat_bubble_elastic"] = 1 if data["disable_chat_bubble_elastic"] else 0
    if "show_background_image" in data:
        data["show_background_image"] = 1 if data["show_background_image"] else 0
    if "memory_inject_count" in data:
        data["memory_inject_count"] = max(0, min(100, int(data["memory_inject_count"])))
    if "context_length" in data and data["context_length"] is not None:
        data["context_length"] = max(1, min(200, int(data["context_length"])))

    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    _invalidate_settings_cache()
    return s
