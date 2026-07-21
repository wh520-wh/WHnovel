"""Model calling helpers."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Iterable

import certifi
import httpx
from sqlalchemy.orm import Session

from .. import models
from ..crypto import decrypt  # kept for test monkeypatch compatibility
from ..redis_client import get_redis
from .ai_contracts import (
    TASK_CHAT_RESPONSE,
    TASK_STATE_BROADCAST,
    ContractTask,
    build_contract_response_format,
    contract_allows_legacy_text_fallback,
    validate_and_convert_contract,
)
from .chat_fallback import _fallback_parse_options

logger = logging.getLogger(__name__)


def _request_model_once(
    model_cfg: models.ModelConfig,
    messages: list[dict],
    temperature: float,
    *,
    response_format: dict | None = None,
    timeout: float = 20.0,
) -> tuple[str, dict]:
    from .chat_api_adapter import get_adapter

    mode = model_cfg.api_mode or "openai_chat_completions"
    ad = get_adapter(mode)

    url = ad["url"](model_cfg.api_base_url or "", model_cfg.model_id, False)
    body = ad["body"](
        model_cfg.model_id,
        messages,
        temperature,
        response_format=response_format if ad["supports_response_format"] else None,
        stream=False,
    )
    raw_key = model_cfg.api_key or model_cfg.image_api_key or ""
    api_key = decrypt(raw_key) if raw_key else ""
    headers = ad["headers"](api_key)

    with httpx.Client(
        timeout=timeout, verify=certifi.where() if model_cfg.ssl_verify else False
    ) as client:
        resp = client.post(url, json=body, headers=headers)

    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:240]}")

    data = resp.json()
    content, usage = ad["parser"](data)
    return content, usage


def _call_text_model_once(
    model_cfg: models.ModelConfig,
    messages: list[dict],
    temperature: float,
    *,
    timeout: float = 20.0,
) -> tuple[str, dict]:
    return _request_model_once(
        model_cfg,
        messages,
        temperature,
        response_format=None,
        timeout=timeout,
    )


def _call_model_once(
    model_cfg: models.ModelConfig,
    messages: list[dict],
    temperature: float,
    *,
    response_format: dict | None = None,
    timeout: float = 20.0,
) -> tuple[str, dict]:
    from .chat_api_adapter import get_adapter

    mode = model_cfg.api_mode or "openai_chat_completions"
    ad = get_adapter(mode)

    if not ad["supports_response_format"]:
        return _request_model_once(
            model_cfg,
            messages,
            temperature,
            response_format=None,
            timeout=timeout,
        )

    # 按模型配置决定 response_format
    rf_mode = getattr(model_cfg, "response_format_mode", None) or "json_schema"
    if rf_mode == "json_object":
        effective_format: dict | None = {"type": "json_object"}
    elif response_format is not None:
        effective_format = response_format
    else:
        effective_format = {"type": "json_object"}

    max_retries = 2
    last_error = ""

    for attempt in range(max_retries):
        try:
            return _request_model_once(
                model_cfg,
                messages,
                temperature,
                response_format=effective_format,
                timeout=timeout,
            )
        except RuntimeError as exc:
            last_error = str(exc)
            if "HTTP 400" in last_error and attempt < max_retries - 1:
                logger.debug(
                    "response_format %s returned 400 for model %s, retrying (attempt %d/%d)",
                    effective_format.get("type") if effective_format else "none",
                    model_cfg.model_id,
                    attempt + 1,
                    max_retries,
                )
                continue
            raise

    raise RuntimeError(last_error or "model call failed")


def _parse_sse_data(data: str, usage_ref: dict, extractor=None) -> Iterable[str]:
    """Parse a complete SSE data block and yield text chunks."""
    if not data or data == "[DONE]":
        return

    if extractor is None:
        from .chat_api_adapter import get_adapter

        extractor = get_adapter("openai_chat_completions")["extractor"]

    for data_str in data.split("\n"):
        data_str = data_str.strip()
        if not data_str or data_str == "[DONE]":
            continue

        try:
            data_obj = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        usage = data_obj.get("usage") or {}
        if usage:
            usage_ref.update(usage)

        text = extractor(data_obj)
        if text:
            yield text


def _collect_stream_usage(obj: dict, usage_ref: dict) -> None:
    """Normalize per-mode streaming usage into standard {prompt_tokens, completion_tokens, total_tokens}."""
    t = obj.get("type", "")

    # Claude: message_start carries input_tokens, message_delta carries output_tokens
    if t == "message_start":
        msg = obj.get("message") or {}
        u = msg.get("usage") or {}
        if "input_tokens" in u:
            usage_ref["prompt_tokens"] = u["input_tokens"]
    elif t == "message_delta":
        u = obj.get("usage") or {}
        if "output_tokens" in u:
            usage_ref["completion_tokens"] = u["output_tokens"]
            usage_ref["total_tokens"] = usage_ref.get("prompt_tokens", 0) + u["output_tokens"]

    # Gemini: usageMetadata appears on the final chunk
    um = obj.get("usageMetadata") or {}
    if um:
        usage_ref["prompt_tokens"] = um.get("promptTokenCount", 0)
        usage_ref["completion_tokens"] = um.get("candidatesTokenCount", 0)
        usage_ref["total_tokens"] = um.get("totalTokenCount", 0)


def _stream_model_once(
    model_cfg: models.ModelConfig,
    messages: list[dict],
    temperature: float,
    usage_ref: dict,
) -> Iterable[str]:
    from .chat_api_adapter import get_adapter

    mode = model_cfg.api_mode or "openai_chat_completions"
    ad = get_adapter(mode)

    url = ad["url"](model_cfg.api_base_url or "", model_cfg.model_id, True)
    body = ad["body"](
        model_cfg.model_id,
        messages,
        temperature,
        stream=True,
    )
    raw_key = model_cfg.api_key or ""
    api_key = decrypt(raw_key) if raw_key else ""
    headers = ad["headers"](api_key)

    with httpx.Client(
        timeout=300.0, verify=certifi.where() if model_cfg.ssl_verify else False
    ) as client:
        with client.stream("POST", url, json=body, headers=headers) as resp:
            if resp.status_code >= 400:
                resp.read()
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:240]}")

            extractor = ad["extractor"]

            # OpenAI SSE: "data: ...\n\n" delimited blocks
            if mode in ("openai_chat_completions", "openai_responses", "custom_chat"):
                data_lines: list[str] = []
                for raw_line in resp.iter_lines():
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if not line:
                        if data_lines:
                            full_data = "\n".join(data_lines)
                            for chunk in _parse_sse_data(full_data, usage_ref, extractor):
                                if chunk:
                                    yield chunk
                            data_lines = []
                        continue
                    if line.startswith("event:"):
                        continue
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            if not data_lines:
                                return
                        else:
                            data_lines.append(data_str)
                if data_lines:
                    full_data = "\n".join(data_lines)
                    for chunk in _parse_sse_data(full_data, usage_ref, extractor):
                        if chunk:
                            yield chunk
            else:
                # Claude / Gemini: each "data:" line is a complete JSON event
                for raw_line in resp.iter_lines():
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if not line:
                        continue
                    if line.startswith("event:"):
                        continue
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        try:
                            obj = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        # Normalize usage to standard {prompt_tokens, completion_tokens, total_tokens}
                        _collect_stream_usage(obj, usage_ref)
                        text = extractor(obj)
                        if text:
                            yield text


def _extract_json_payload(text: str, *, fallback_options: bool = False) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("模型返回为空")

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    search_text = fenced.group(1) if fenced else text
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(search_text):
        start = search_text.find("{", pos)
        if start == -1:
            break
        try:
            obj, _ = decoder.raw_decode(search_text, start)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pos = start + 1
            continue

    start = search_text.find("{")
    end = search_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(search_text[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    if fallback_options:
        options = _fallback_parse_options(text)
        if options:
            return {"options": options}

    raise ValueError("未找到可解析的 JSON 对象")


def _coerce_flat_kv_to_content(payload: dict) -> dict:
    """Convert flat key-value dict to {"content": "key | val\n..."} for state_broadcast."""
    if not payload:
        return payload
    if "content" not in payload and all(
        isinstance(v, str | int | float | bool) for v in payload.values()
    ):
        lines = [f"{k} | {v}" for k, v in payload.items()]
        return {"content": "\n".join(lines)}
    return payload


def _validate_contract_from_text(
    task: ContractTask,
    text: str,
    *,
    allow_legacy_text_fallback: bool | None = None,
):
    use_legacy_fallback = (
        contract_allows_legacy_text_fallback(task)
        if allow_legacy_text_fallback is None
        else allow_legacy_text_fallback
    )
    payload = _extract_json_payload(text, fallback_options=use_legacy_fallback)
    if task == TASK_STATE_BROADCAST:
        payload = _coerce_flat_kv_to_content(payload)
    return validate_and_convert_contract(task, payload)


def _coerce_stream_tail_payload(raw_tail: str, reply_text: str):
    validated = _validate_contract_from_text(
        TASK_CHAT_RESPONSE, raw_tail, allow_legacy_text_fallback=False
    )
    return validated.model_copy(update={"reply_text": reply_text})


def _get_temperature(model_cfg=None) -> float:
    if model_cfg is not None and model_cfg.temperature is not None:
        return float(model_cfg.temperature)
    return 0.7


MODEL_CACHE_KEY = "cache:models:enabled"
MODEL_CACHE_TTL = 300


def _get_enabled_models(
    db: Session, *, model_type: str | None = "chat"
) -> list[models.ModelConfig]:
    redis = get_redis()
    use_cache = model_type == "chat"
    if use_cache and redis.is_available():
        cached = redis.get(MODEL_CACHE_KEY)
        if cached:
            model_ids = json.loads(cached)
            if model_ids:
                return (
                    db.query(models.ModelConfig)
                    .filter(models.ModelConfig.id.in_(model_ids), models.ModelConfig.enabled == 1)
                    .all()
                )
            return []

    query = db.query(models.ModelConfig).filter(models.ModelConfig.enabled == 1)
    if model_type is not None:
        query = query.filter(models.ModelConfig.model_type == model_type)

    models_list = query.order_by(
        models.ModelConfig.priority.asc(),
        models.ModelConfig.id.asc(),
    ).all()

    if use_cache and redis.is_available() and models_list:
        redis.set(MODEL_CACHE_KEY, json.dumps([m.id for m in models_list]), ttl=MODEL_CACHE_TTL)

    return models_list


def _order_model_chain(
    enabled_models: list[models.ModelConfig],
    primary_model_id: int | None,
    backup_model_ids: list[int] | None,
) -> list[models.ModelConfig]:
    enabled_by_id = {m.id: m for m in enabled_models}

    ordered: list[models.ModelConfig] = []
    seen: set[int] = set()

    if primary_model_id and primary_model_id in enabled_by_id:
        ordered.append(enabled_by_id[primary_model_id])
        seen.add(primary_model_id)

    for mid in backup_model_ids or []:
        model = enabled_by_id.get(mid)
        if model and model.id not in seen:
            ordered.append(model)
            seen.add(model.id)

    return ordered


def _get_normal_model_candidates(
    db: Session, settings: models.UserSettings
) -> list[models.ModelConfig]:
    from fastapi import HTTPException

    enabled = _get_enabled_models(db)
    if not enabled:
        raise HTTPException(503, "没有可用模型，请先在管理后台启用模型")

    ordered = _order_model_chain(enabled, settings.primary_model_id, settings.backup_model_ids)
    return ordered or enabled


def _calc_cost(model_cfg: models.ModelConfig, prompt_tokens: int, completion_tokens: int) -> float:
    divisor = 1_000_000.0 if model_cfg.pricing_unit == "per_1m" else 1000.0
    return (prompt_tokens / divisor) * float(model_cfg.price_input_per_1k or 0) + (
        completion_tokens / divisor
    ) * float(model_cfg.price_output_per_1k or 0)


def _call_ai_with_failover(
    db: Session,
    *,
    candidates: list[models.ModelConfig],
    story: models.Story,
    archive: models.Archive | None,
    messages: list[dict],
    temperature: float,
    contract_task: ContractTask = TASK_CHAT_RESPONSE,
    allow_legacy_text_fallback: bool | None = None,
):
    from fastapi import HTTPException
    from pydantic import ValidationError

    from .chat_metrics import _log_call

    request_id = uuid.uuid4().hex
    last_error = ""
    response_format = build_contract_response_format(contract_task)
    task_code = contract_task.upper()
    archive_id = archive.id if archive else None
    story_id = story.id if story else 0

    for model_cfg in candidates:
        t0 = time.perf_counter()
        try:
            content, usage = _call_model_once(
                model_cfg,
                messages,
                temperature,
                response_format=response_format,
            )
            validated = _validate_contract_from_text(
                contract_task,
                content,
                allow_legacy_text_fallback=allow_legacy_text_fallback,
            )

            latency_ms = int((time.perf_counter() - t0) * 1000)
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
            cost = _calc_cost(model_cfg, prompt_tokens, completion_tokens)

            _log_call(
                db,
                request_id=request_id,
                archive_id=archive_id,
                story_id=story_id,
                model_cfg=model_cfg,
                success=True,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_estimate=cost,
                plot_label_generated=bool(getattr(validated, "plot_label", None)),
            )
            return validated

        except (ValidationError, ValueError) as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            last_error = f"结构化校验失败: {exc}"
            _log_call(
                db,
                request_id=request_id,
                archive_id=archive_id,
                story_id=story_id,
                model_cfg=model_cfg,
                success=False,
                error_code=f"{task_code}_SCHEMA_INVALID",
                error_message=last_error,
                latency_ms=latency_ms,
                plot_label_generated=False,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - t0) * 1000)
            last_error = str(exc)
            _log_call(
                db,
                request_id=request_id,
                archive_id=archive_id,
                story_id=story_id,
                model_cfg=model_cfg,
                success=False,
                error_code=f"{task_code}_MODEL_CALL_FAILED",
                error_message=last_error,
                latency_ms=latency_ms,
                plot_label_generated=False,
            )

    raise HTTPException(503, f"模型调用失败：{last_error[:200]}")
