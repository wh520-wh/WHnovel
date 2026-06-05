from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..app_settings_service import ensure_app_settings
from ..config_backup import export_backup_file, import_backup_file
from ..crypto import decrypt, encrypt
from ..database import get_db
from ..prompts.defaults import infer_prompt_source
from ..redis_client import get_redis

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)
METRICS_RESET_CONFIRM_TEXT = "RESET_METRICS"

APPSETTINGS_CACHE_KEY = "cache:settings:app"
MODEL_CACHE_KEY = "cache:models:enabled"
USERSETTINGS_CACHE_KEY = "cache:settings:user"
APPSETTINGS_CACHE_TTL = 600  # 10 minutes
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_SHUTDOWN_DELAY_MS = 900
FRONTEND_SHUTDOWN_DELAY_MS = 2600


def _schedule_system_shutdown() -> None:
    worker = str(PROJECT_ROOT / "backend" / "app" / "shutdown_worker.py")
    creationflags = 0
    for flag_name in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS", "CREATE_NO_WINDOW"):
        creationflags |= int(getattr(subprocess, flag_name, 0))

    subprocess.Popen(
        [
            sys.executable,
            worker,
            str(PROJECT_ROOT),
            str(BACKEND_SHUTDOWN_DELAY_MS),
            str(FRONTEND_SHUTDOWN_DELAY_MS),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )


# ---- Model configuration ----
def _to_model_out(m: models.ModelConfig) -> schemas.ModelConfigOut:
    return schemas.ModelConfigOut(
        id=m.id,
        name=m.name,
        model_id=m.model_id,
        api_base_url=m.api_base_url,
        enabled=m.enabled,
        priority=m.priority,
        price_input_per_1k=float(m.price_input_per_1k or 0.0),
        price_output_per_1k=float(m.price_output_per_1k or 0.0),
        pricing_unit=m.pricing_unit or "per_1k",
        temperature=m.temperature,
        max_tokens=m.max_tokens,
        has_api_key=bool(m.api_key),
        model_type=m.model_type or "chat",
        image_api_base=m.image_api_base or "",
        api_mode=m.api_mode or "openai_chat_completions",
        image_api_mode=m.image_api_mode or "openai_images",
        image_workflow_template=m.image_workflow_template or "",
        response_format_mode=m.response_format_mode or "json_schema",
    )


@router.get("/models", response_model=list[schemas.ModelConfigOut])
def list_models(db: Session = Depends(get_db)):
    rows = (
        db.query(models.ModelConfig)
        .order_by(models.ModelConfig.priority.asc(), models.ModelConfig.id.asc())
        .all()
    )
    return [_to_model_out(m) for m in rows]


@router.post("/models", response_model=schemas.ModelConfigOut)
def create_model(payload: schemas.ModelConfigIn, db: Session = Depends(get_db)):
    if not payload.name:
        raise HTTPException(400, "名称不能为空")
    if not payload.model_id:
        raise HTTPException(400, "模型 ID 不能为空")
    if not payload.api_base_url and not (payload.model_type == "image" and payload.image_api_base):
        raise HTTPException(400, "API 地址不能为空")
    data = payload.model_dump()
    data["pricing_unit"] = data.get("pricing_unit") or "per_1k"
    if data.get("api_key"):
        data["api_key"] = encrypt(data["api_key"])
    # image_api_key 也需要加密
    if data.get("image_api_key"):
        data["image_api_key"] = encrypt(data["image_api_key"])
    m = models.ModelConfig(**data)
    db.add(m)
    db.commit()
    db.refresh(m)
    redis = get_redis()
    if redis.is_available():
        redis.delete(MODEL_CACHE_KEY)
    return _to_model_out(m)


@router.put("/models/{model_id}", response_model=schemas.ModelConfigOut)
def update_model(model_id: int, payload: schemas.ModelConfigIn, db: Session = Depends(get_db)):
    m = db.query(models.ModelConfig).filter(models.ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    data = payload.model_dump(exclude_unset=True)
    data["pricing_unit"] = data.get("pricing_unit") or "per_1k"
    # Keep existing API key when update payload sends empty string.
    if not data.get("api_key"):
        data.pop("api_key", None)
    else:
        data["api_key"] = encrypt(data["api_key"])

    # image_api_key 也需要加密，保留旧值当为空
    if not data.get("image_api_key"):
        data.pop("image_api_key", None)
    else:
        data["image_api_key"] = encrypt(data["image_api_key"])

    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    redis = get_redis()
    if redis.is_available():
        redis.delete(MODEL_CACHE_KEY)
    return _to_model_out(m)


@router.delete("/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    m = db.query(models.ModelConfig).filter(models.ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")

    settings = db.query(models.UserSettings).all()
    for s in settings:
        if s.primary_model_id == model_id:
            s.primary_model_id = None
        s.backup_model_ids = [mid for mid in (s.backup_model_ids or []) if mid != model_id]

    app_settings = db.query(models.AppSettings).first()
    if app_settings and app_settings.default_image_model_id == model_id:
        app_settings.default_image_model_id = None

    db.delete(m)
    db.commit()
    redis = get_redis()
    if redis.is_available():
        redis.delete(MODEL_CACHE_KEY)
        redis.delete(APPSETTINGS_CACHE_KEY)
        redis.delete(USERSETTINGS_CACHE_KEY)
    return {"ok": True}


@router.post("/models/test")
def test_model(model_id: int, db: Session = Depends(get_db)):
    """Test a model configuration with a 10-second timeout, respecting api_mode."""
    m = db.query(models.ModelConfig).filter(models.ModelConfig.id == model_id).first()
    if not m:
        raise HTTPException(404, "模型不存在")

    import time

    if m.model_type == "image":
        return _test_image_model(m)

    from .chat_api_adapter import get_adapter

    mode = m.api_mode or "openai_chat_completions"
    ad = get_adapter(mode)

    url = ad["url"](m.api_base_url or "", m.model_id, False)
    body = ad["body"](
        m.model_id,
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.1,
        stream=False,
        max_tokens=16,
    )
    raw_key = m.api_key or ""
    api_key = decrypt(raw_key) if raw_key else ""
    headers = ad["headers"](api_key)

    start = time.monotonic()
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=body, headers=headers)
    except httpx.TimeoutException:
        return {"success": False, "error": "网络超时，请检查地址是否可访问"}
    except httpx.ConnectError:
        return {"success": False, "error": "网络超时，请检查地址是否可访问"}
    duration_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code == 401:
        return {"success": False, "error": "API Key 错误"}
    if resp.status_code == 403:
        return {"success": False, "error": "无访问权限"}
    if resp.status_code == 404:
        return {"success": False, "error": "API 地址无效"}
    if resp.status_code == 429:
        return {"success": False, "error": "请求过于频繁，请稍后重试"}
    if resp.status_code >= 500:
        return {"success": False, "error": f"服务端错误（{resp.status_code}）"}

    if resp.status_code >= 400:
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:240]}"}

    return {"success": True, "duration_ms": duration_ms}


def _test_image_model(m: models.ModelConfig) -> dict:
    """Test image model connectivity and auth without generating an actual image.
    Sends an empty POST body — the API will reject it with 400 (invalid params)
    but that confirms the endpoint is reachable and auth is correct."""
    import time

    from .chat_api_adapter import get_adapter

    mode = m.image_api_mode or "openai_images"
    ad = get_adapter(mode)
    base_url = m.image_api_base or m.api_base_url or ""

    if mode == "comfyui":
        url = f"{base_url.rstrip('/')}/prompt"
    else:
        url = ad["url"](base_url, m.model_id, False)

    key = decrypt(m.image_api_key) if m.image_api_key else decrypt(m.api_key) if m.api_key else ""
    headers = ad["headers"](key) if ad.get("headers") else {"Content-Type": "application/json"}

    start = time.monotonic()
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json={}, headers=headers)
    except httpx.TimeoutException:
        return {"success": False, "error": "网络超时，请检查地址是否可访问"}
    except httpx.ConnectError:
        return {"success": False, "error": "网络超时，请检查地址是否可访问"}
    duration_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code == 401:
        return {"success": False, "error": "API Key 错误"}
    if resp.status_code == 403:
        return {"success": False, "error": "无访问权限"}
    if resp.status_code == 404:
        return {"success": False, "error": "API 地址无效"}
    # 400 (bad request) or 200 means connectivity + auth OK
    return {"success": True, "duration_ms": duration_ms}


@router.post("/config-backup/export")
def export_config_backup(db: Session = Depends(get_db)):
    path, payload = export_backup_file(db)
    return {
        "ok": True,
        "path": str(path),
        "exported_at": payload["exported_at"],
        "models_count": len(payload["models"]),
        "includes_app_settings": "app_settings" in payload,
        "includes_user_settings": "user_settings" in payload,
    }


@router.post("/config-backup/import")
def import_config_backup(db: Session = Depends(get_db)):
    try:
        result = import_backup_file(db)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    redis = get_redis()
    if redis.is_available():
        redis.delete(MODEL_CACHE_KEY)
        redis.delete(APPSETTINGS_CACHE_KEY)
        redis.delete(USERSETTINGS_CACHE_KEY)

    return {
        "ok": True,
        **result,
    }


@router.post("/system/shutdown", response_model=schemas.SystemShutdownOut)
def shutdown_system():
    try:
        _schedule_system_shutdown()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to schedule system shutdown")
        raise HTTPException(500, f"关停任务启动失败: {str(exc)[:120]}") from exc

    return schemas.SystemShutdownOut(
        ok=True,
        message="关停任务已启动：即将先关闭后端，再关闭前端。",
        scheduled_at=datetime.now(),
        backend_delay_ms=BACKEND_SHUTDOWN_DELAY_MS,
        frontend_delay_ms=FRONTEND_SHUTDOWN_DELAY_MS,
    )


def _to_app_settings_out(s: models.AppSettings) -> schemas.AppSettingsOut:
    return schemas.AppSettingsOut(
        id=s.id,
        default_system_prompt=s.default_system_prompt or "",
        default_system_prompt_source=infer_prompt_source(s.default_system_prompt or ""),
        state_broadcast_prompt=s.state_broadcast_prompt or "",
        enable_image_generation=bool(s.enable_image_generation),
        default_image_model_id=s.default_image_model_id,
        image_size=s.image_size or "2K",
        image_watermark=bool(s.image_watermark),
        default_image_style=s.default_image_style or "唯美、氛围感强，适合作为小说封面",
        style_skill_enabled=s.style_skill_enabled or 0,
        style_skill_content=s.style_skill_content or "",
    )


@router.get("/app-settings", response_model=schemas.AppSettingsOut)
def get_app_settings(db: Session = Depends(get_db)):
    redis = get_redis()
    if redis.is_available():
        cached = redis.get(APPSETTINGS_CACHE_KEY)
        if cached:
            try:
                data = json.loads(cached)
                return schemas.AppSettingsOut.model_validate(data)
            except Exception:
                pass

    s = ensure_app_settings(db)
    result = _to_app_settings_out(s)

    if redis.is_available():
        cache_data = {
            "id": s.id,
            "default_system_prompt": s.default_system_prompt or "",
            "default_system_prompt_source": infer_prompt_source(s.default_system_prompt or ""),
            "state_broadcast_prompt": s.state_broadcast_prompt or "",
            "enable_image_generation": bool(s.enable_image_generation),
            "default_image_model_id": s.default_image_model_id,
            "image_size": s.image_size or "2K",
            "image_watermark": bool(s.image_watermark),
            "default_image_style": s.default_image_style or "唯美、氛围感强，适合作为小说封面",
            "style_skill_enabled": s.style_skill_enabled or 0,
            "style_skill_content": s.style_skill_content or "",
        }
        redis.set(
            APPSETTINGS_CACHE_KEY,
            json.dumps(cache_data, ensure_ascii=False),
            ttl=APPSETTINGS_CACHE_TTL,
        )

    return result


@router.put("/app-settings", response_model=schemas.AppSettingsOut)
def update_app_settings(payload: schemas.AppSettingsUpdate, db: Session = Depends(get_db)):
    s = ensure_app_settings(db)
    data = payload.model_dump(exclude_unset=True)

    # 验证 default_image_model_id 必须是一个启用中的图片模型
    if "default_image_model_id" in data:
        img_id = data["default_image_model_id"]
        if img_id is not None:
            img_model = (
                db.query(models.ModelConfig)
                .filter(
                    models.ModelConfig.id == img_id,
                    models.ModelConfig.enabled == 1,
                    models.ModelConfig.model_type == "image",
                )
                .first()
            )
            if not img_model:
                raise HTTPException(400, "默认图片模型未启用或不存在")

    # Validate style skill content
    skill_enabled = data.get("style_skill_enabled", s.style_skill_enabled)
    skill_content = data.get("style_skill_content", s.style_skill_content)
    if skill_enabled:
        skill_content = (skill_content or "").strip()
        if skill_content:
            if len(skill_content) < 200:
                raise HTTPException(400, "Skill内容至少需要200字")
            if len(skill_content) > 1500:
                raise HTTPException(400, "Skill内容不能超过1500字")
            if (
                "----- SKILL START -----" not in skill_content
                or "----- SKILL END -----" not in skill_content
            ):
                raise HTTPException(400, "Skill内容必须包含边界符标记")

    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    s = ensure_app_settings(db)
    redis = get_redis()
    redis.delete(APPSETTINGS_CACHE_KEY)
    return _to_app_settings_out(s)


def _resolve_time_window(start: str | None, end: str | None):
    if start:
        start_dt = datetime.fromisoformat(start)
    else:
        start_dt = datetime.now() - timedelta(days=7)
    if end:
        end_dt = datetime.fromisoformat(end)
    else:
        end_dt = datetime.now()
    return start_dt, end_dt


def _current_hour_str() -> str:
    return datetime.now().replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:00")


@router.get("/metrics/summary", response_model=schemas.MetricsSummaryOut)
def metrics_summary(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    start_dt, end_dt = _resolve_time_window(start, end)
    current_hour = _current_hour_str()

    # Build time window strings for hourly lookup
    start_hour_str = start_dt.strftime("%Y-%m-%d %H:00") if start_dt else None
    end_hour_str = end_dt.strftime("%Y-%m-%d %H:00") if end_dt else None

    # Determine if we need to fall back to api_call_logs (current hour not yet aggregated)
    end_hour_dt = end_dt.replace(minute=0, second=0, microsecond=0)
    include_current_hour = end_hour_dt.strftime("%Y-%m-%d %H:00") == current_hour

    total_calls = 0
    success_calls = 0
    total_latency_ms = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_cost = 0.0
    plot_label_calls = 0
    plot_label_cost = 0.0

    # Past complete hours: use metrics_hourly
    past_end = end_hour_str
    if include_current_hour:
        # Truncate to previous hour
        prev_dt = end_dt.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        past_end = prev_dt.strftime("%Y-%m-%d %H:00")

    hourly_query = db.query(
        func.sum(models.MetricsHourly.total_calls).label("total_calls"),
        func.sum(models.MetricsHourly.success_calls).label("success_calls"),
        func.sum(models.MetricsHourly.total_latency_ms).label("total_latency_ms"),
        func.sum(models.MetricsHourly.total_tokens).label("total_tokens"),
        func.sum(models.MetricsHourly.total_cost).label("total_cost"),
        func.sum(models.MetricsHourly.plot_label_calls).label("plot_label_calls"),
        func.sum(models.MetricsHourly.plot_label_cost).label("plot_label_cost"),
    )
    if start_hour_str:
        hourly_query = hourly_query.filter(models.MetricsHourly.hour >= start_hour_str)
    hourly_query = hourly_query.filter(models.MetricsHourly.hour <= past_end)

    h = hourly_query.first()
    if h:
        total_calls += int(h.total_calls or 0)
        success_calls += int(h.success_calls or 0)
        total_latency_ms += int(h.total_latency_ms or 0)
        total_tokens += int(h.total_tokens or 0)
        total_cost += float(h.total_cost or 0.0)
        plot_label_calls = int(h.plot_label_calls or 0)
        plot_label_cost = float(h.plot_label_cost or 0.0)

    # Fall back to api_call_logs for current hour (not yet aggregated)
    if include_current_hour:
        current_q = db.query(models.ApiCallLog).filter(
            models.ApiCallLog.created_at >= end_hour_dt,
            models.ApiCallLog.created_at <= end_dt,
        )
        total_calls += current_q.count()
        success_calls += current_q.filter(models.ApiCallLog.success == 1).count()
        total_latency_ms += int(
            current_q.with_entities(func.sum(models.ApiCallLog.latency_ms)).scalar() or 0
        )
        total_prompt_tokens += int(
            current_q.with_entities(func.sum(models.ApiCallLog.prompt_tokens)).scalar() or 0
        )
        total_completion_tokens += int(
            current_q.with_entities(func.sum(models.ApiCallLog.completion_tokens)).scalar() or 0
        )
        total_tokens += int(
            current_q.with_entities(func.sum(models.ApiCallLog.total_tokens)).scalar() or 0
        )
        total_cost += float(
            current_q.with_entities(func.sum(models.ApiCallLog.cost_estimate)).scalar() or 0
        )
        plot_label_calls += int(
            current_q.with_entities(func.sum(models.ApiCallLog.plot_label_generated)).scalar() or 0
        )
        plot_label_cost += float(
            current_q.with_entities(
                func.sum(
                    case(
                        (
                            models.ApiCallLog.plot_label_generated == 1,
                            models.ApiCallLog.cost_estimate,
                        ),
                        else_=0.0,
                    )
                )
            ).scalar()
            or 0
        )
    else:
        # Full range from api_call_logs (for avg latency calculation)
        q = db.query(models.ApiCallLog).filter(
            models.ApiCallLog.created_at >= start_dt,
            models.ApiCallLog.created_at <= end_dt,
        )
        total_prompt_tokens = int(
            q.with_entities(func.sum(models.ApiCallLog.prompt_tokens)).scalar() or 0
        )
        total_completion_tokens = int(
            q.with_entities(func.sum(models.ApiCallLog.completion_tokens)).scalar() or 0
        )

    avg_latency = float(total_latency_ms / total_calls) if total_calls > 0 else 0.0

    return schemas.MetricsSummaryOut(
        total_calls=total_calls,
        success_calls=success_calls,
        success_rate=(success_calls / total_calls * 100.0) if total_calls else 0.0,
        avg_latency_ms=avg_latency,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        total_cost=float(total_cost),
        plot_label_calls=plot_label_calls,
        plot_label_cost=plot_label_cost,
    )


@router.get("/metrics/by-model", response_model=list[schemas.MetricsByModelItem])
def metrics_by_model(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    start_dt, end_dt = _resolve_time_window(start, end)
    current_hour = _current_hour_str()
    end_hour_dt = end_dt.replace(minute=0, second=0, microsecond=0)
    include_current_hour = end_hour_dt.strftime("%Y-%m-%d %H:00") == current_hour

    start_hour_str = start_dt.strftime("%Y-%m-%d %H:00") if start_dt else None
    past_end_hour = end_hour_dt.strftime("%Y-%m-%d %H:00")
    if include_current_hour:
        prev_dt = end_dt.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        past_end_hour = prev_dt.strftime("%Y-%m-%d %H:00")

    # Aggregate from metrics_hourly (past complete hours)
    hourly_q = db.query(
        models.MetricsHourly.model_config_id.label("model_config_id"),
        func.sum(models.MetricsHourly.total_calls).label("total_calls"),
        func.sum(models.MetricsHourly.success_calls).label("success_calls"),
        func.sum(models.MetricsHourly.total_latency_ms).label("total_latency_ms"),
        func.sum(models.MetricsHourly.total_tokens).label("total_tokens"),
        func.sum(models.MetricsHourly.total_cost).label("total_cost"),
        func.sum(models.MetricsHourly.plot_label_calls).label("plot_label_calls"),
        func.sum(models.MetricsHourly.plot_label_cost).label("plot_label_cost"),
    )
    if start_hour_str:
        hourly_q = hourly_q.filter(models.MetricsHourly.hour >= start_hour_str)
    hourly_q = hourly_q.filter(models.MetricsHourly.hour <= past_end_hour)
    hourly_rows = hourly_q.group_by(models.MetricsHourly.model_config_id).all()

    # Build a map from model_config_id to aggregated data
    model_data: dict[int, dict] = {}
    for r in hourly_rows:
        cid = r.model_config_id
        total = int(r.total_calls or 0)
        success = int(r.success_calls or 0)
        latency = int(r.total_latency_ms or 0)
        model_data[cid] = {
            "total_calls": total,
            "success_calls": success,
            "avg_latency_ms": latency / total if total > 0 else 0.0,
            "total_tokens": int(r.total_tokens or 0),
            "total_cost": float(r.total_cost or 0.0),
            "plot_label_calls": int(r.plot_label_calls or 0),
            "plot_label_cost": float(r.plot_label_cost or 0.0),
        }

    # Supplement with api_call_logs for current hour
    if include_current_hour:
        live_q = (
            db.query(
                models.ApiCallLog.model_config_id.label("model_config_id"),
                func.count(models.ApiCallLog.id).label("total_calls"),
                func.sum(models.ApiCallLog.success).label("success_calls"),
                func.avg(models.ApiCallLog.latency_ms).label("avg_latency_ms"),
                func.sum(models.ApiCallLog.total_tokens).label("total_tokens"),
                func.sum(models.ApiCallLog.cost_estimate).label("total_cost"),
                func.sum(models.ApiCallLog.plot_label_generated).label("plot_label_calls"),
                func.sum(
                    case(
                        (
                            models.ApiCallLog.plot_label_generated == 1,
                            models.ApiCallLog.cost_estimate,
                        ),
                        else_=0.0,
                    )
                ).label("plot_label_cost"),
            )
            .filter(
                models.ApiCallLog.created_at >= end_hour_dt,
                models.ApiCallLog.created_at <= end_dt,
            )
            .group_by(models.ApiCallLog.model_config_id)
        )

        for r in live_q.all():
            cid = r.model_config_id
            total = int(r.total_calls or 0)
            success = int(r.success_calls or 0)
            if cid in model_data:
                d = model_data[cid]
                d["total_calls"] += total
                d["success_calls"] += success
                d["total_tokens"] += int(r.total_tokens or 0)
                d["total_cost"] += float(r.total_cost or 0.0)
                d["plot_label_calls"] += int(r.plot_label_calls or 0)
                d["plot_label_cost"] += float(r.plot_label_cost or 0.0)
                # Recalculate avg latency
                old_total = d["total_calls"] - total
                old_latency = d["avg_latency_ms"] * old_total if old_total > 0 else 0
                new_latency = float(r.avg_latency_ms or 0) * total
                d["avg_latency_ms"] = (
                    (old_latency + new_latency) / d["total_calls"] if d["total_calls"] > 0 else 0
                )
            else:
                model_data[cid] = {
                    "total_calls": total,
                    "success_calls": success,
                    "avg_latency_ms": float(r.avg_latency_ms or 0.0),
                    "total_tokens": int(r.total_tokens or 0),
                    "total_cost": float(r.total_cost or 0.0),
                    "plot_label_calls": int(r.plot_label_calls or 0),
                    "plot_label_cost": float(r.plot_label_cost or 0.0),
                }

    # Look up model names
    model_names: dict[int, str] = {}
    if model_data:
        model_ids = list(model_data.keys())
        configs = db.query(models.ModelConfig).filter(models.ModelConfig.id.in_(model_ids)).all()
        model_names = {c.id: c.name for c in configs}

    result: list[schemas.MetricsByModelItem] = []
    for cid, d in sorted(model_data.items(), key=lambda x: x[1]["total_calls"], reverse=True):
        total = d["total_calls"]
        success = d["success_calls"]
        result.append(
            schemas.MetricsByModelItem(
                model_config_id=cid,
                model_name=model_names.get(cid, "未知模型"),
                total_calls=total,
                success_calls=success,
                success_rate=(success / total * 100.0) if total else 0.0,
                avg_latency_ms=d["avg_latency_ms"],
                total_tokens=d["total_tokens"],
                total_cost=d["total_cost"],
            )
        )
    return result


@router.get("/metrics/timeseries", response_model=list[schemas.MetricsTimeseriesItem])
def metrics_timeseries(
    start: str | None = None, end: str | None = None, db: Session = Depends(get_db)
):
    start_dt, end_dt = _resolve_time_window(start, end)
    current_hour = _current_hour_str()
    end_hour_dt = end_dt.replace(minute=0, second=0, microsecond=0)
    include_current_hour = end_hour_dt.strftime("%Y-%m-%d %H:00") == current_hour

    start_hour_str = start_dt.strftime("%Y-%m-%d %H:00") if start_dt else None
    past_end_hour = end_hour_dt.strftime("%Y-%m-%d %H:00")
    if include_current_hour:
        prev_dt = end_dt.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        past_end_hour = prev_dt.strftime("%Y-%m-%d %H:00")

    # Aggregate from metrics_hourly by day (past complete hours)
    daily_data: dict[str, dict] = {}
    hourly_q = db.query(
        models.MetricsHourly.hour.label("hour"),
        func.sum(models.MetricsHourly.total_calls).label("total_calls"),
        func.sum(models.MetricsHourly.success_calls).label("success_calls"),
        func.sum(models.MetricsHourly.total_tokens).label("total_tokens"),
        func.sum(models.MetricsHourly.total_cost).label("total_cost"),
    )
    if start_hour_str:
        hourly_q = hourly_q.filter(models.MetricsHourly.hour >= start_hour_str)
    hourly_q = hourly_q.filter(models.MetricsHourly.hour <= past_end_hour)

    for r in hourly_q.group_by(models.MetricsHourly.hour).all():
        day_str = r.hour[:10]  # 'YYYY-MM-DD'
        if day_str not in daily_data:
            daily_data[day_str] = {
                "total_calls": 0,
                "success_calls": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
            }
        d = daily_data[day_str]
        d["total_calls"] += int(r.total_calls or 0)
        d["success_calls"] += int(r.success_calls or 0)
        d["total_tokens"] += int(r.total_tokens or 0)
        d["total_cost"] += float(r.total_cost or 0.0)

    # Supplement with api_call_logs for current hour
    if include_current_hour:
        live_q = (
            db.query(
                func.date(models.ApiCallLog.created_at).label("day"),
                func.count(models.ApiCallLog.id).label("total_calls"),
                func.sum(models.ApiCallLog.success).label("success_calls"),
                func.sum(models.ApiCallLog.total_tokens).label("total_tokens"),
                func.sum(models.ApiCallLog.cost_estimate).label("total_cost"),
            )
            .filter(
                models.ApiCallLog.created_at >= end_hour_dt,
                models.ApiCallLog.created_at <= end_dt,
            )
            .group_by(func.date(models.ApiCallLog.created_at))
        )

        for r in live_q.all():
            day_str = str(r.day)
            if day_str not in daily_data:
                daily_data[day_str] = {
                    "total_calls": 0,
                    "success_calls": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                }
            d = daily_data[day_str]
            d["total_calls"] += int(r.total_calls or 0)
            d["success_calls"] += int(r.success_calls or 0)
            d["total_tokens"] += int(r.total_tokens or 0)
            d["total_cost"] += float(r.total_cost or 0.0)

    result: list[schemas.MetricsTimeseriesItem] = []
    for day_str in sorted(daily_data.keys()):
        d = daily_data[day_str]
        total = d["total_calls"]
        success = d["success_calls"]
        result.append(
            schemas.MetricsTimeseriesItem(
                day=day_str,
                total_calls=total,
                success_calls=success,
                success_rate=(success / total * 100.0) if total else 0.0,
                total_tokens=d["total_tokens"],
                total_cost=d["total_cost"],
            )
        )
    return result


@router.get("/metrics/stream-requests", response_model=list[schemas.StreamRequestLogItem])
def metrics_stream_requests(
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    start_dt, end_dt = _resolve_time_window(start, end)
    safe_limit = min(max(int(limit or 100), 1), 500)
    rows = (
        db.query(models.ApiCallLog)
        .filter(
            models.ApiCallLog.created_at >= start_dt,
            models.ApiCallLog.created_at <= end_dt,
            models.ApiCallLog.is_stream == 1,
        )
        .order_by(models.ApiCallLog.created_at.desc(), models.ApiCallLog.id.desc())
        .limit(safe_limit)
        .all()
    )

    return [
        schemas.StreamRequestLogItem(
            id=r.id,
            request_id=r.request_id,
            created_at=r.created_at,
            archive_id=r.archive_id,
            story_id=r.story_id,
            model_name=r.model_name or "",
            success=bool(r.success),
            error_code=r.error_code or "",
            error_stage=r.error_stage or "",
            stream_emitted_delta=bool(r.stream_emitted_delta),
            ttfb_ms=int(r.ttfb_ms or 0),
            fallback_used=bool(r.fallback_used),
            tail_valid=bool(r.tail_valid),
            latency_ms=int(r.latency_ms or 0),
        )
        for r in rows
    ]


@router.post("/metrics/reset")
def metrics_reset(payload: schemas.MetricsResetIn, db: Session = Depends(get_db)):
    if payload.confirm_text != METRICS_RESET_CONFIRM_TEXT:
        raise HTTPException(400, f"确认文本错误，请输入 {METRICS_RESET_CONFIRM_TEXT}")
    db.query(models.ApiCallLog).delete()
    db.query(models.MetricsHourly).delete()
    db.commit()
    return {"ok": True}
