"""SSE streaming response logic."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..prompts import (
    HUMANIZED_WRITING_RULES,
    MAX_ROUNDS_WITHOUT_PLOT_LABEL,
    PLOT_LABEL_FORCED_PROMPT,
    STREAM_ERROR_STAGE_POST_DELTA,
    STREAM_ERROR_STAGE_PRE_DELTA,
    STREAM_ERROR_STAGE_TAIL_JSON,
    STREAM_ERROR_STAGE_TAIL_SCHEMA,
    STREAM_ERROR_STAGE_UPSTREAM,
    _restore_tail_escape,
)
from ..prompts.guard import (
    BodyPollutedError,
    _detect_body_pollution,
    _has_sentence_boundary,
    _is_trailing_bracket_line,
    _strip_trailing_bracket_line,
)
from ..prompts.narrative import (
    _STREAM_BODY_NARRATIVE_PROMPT,
    _build_length_prompt,
    _length_spec_for_style,
)
from .ai_contracts import (
    TASK_CHAT_RESPONSE,
    build_contract_response_format,
    get_contract_output_rule,
)
from .chat_locks import _acquire_per_archive_lock
from .chat_metrics import _log_call
from .chat_models import (
    _calc_cost,
    _call_model_once,
    _get_normal_model_candidates,
    _get_temperature,
    _stream_model_once,
    _validate_contract_from_text,
)
from .chat_sse import _sse_event, _sse_keepalive
from .chat_storage import (
    ANTI_INJECTION_CLAUSE,
    _build_memory_section,
    _build_messages,
    _build_tail_messages,
    _count_rounds_without_plot_label,
    _expand_character_references,
    _get_or_create_app_settings,
    _get_or_create_settings,
    _get_story_characters,
    _persist_draft_exchange,
    _persist_exchange,
    _query_dialogue_history,
    _resolve_memory_inject_count,
)

# Concurrency lock for stream generation (per-archive)
_stream_generation_locks: dict[int, threading.Lock] = {}
_stream_generation_locks_guard = threading.Lock()


def _stream_lock_key(archive_id: int) -> str:
    return f"stream:archive:{archive_id}"


def _image_lock_key(archive_id: int) -> str:
    return f"image:archive:{archive_id}"


@contextmanager
def _acquire_image_generation_lock(archive_id: int):
    """Acquire an exclusive lock for generating an image for the given archive."""
    with _acquire_per_archive_lock(
        archive_id,
        redis_key=_image_lock_key(archive_id),
        ttl=120,
        busy_message="该会话正在生成图片，请稍后重试",
        locks_dict=_stream_generation_locks,
        locks_guard=_stream_generation_locks_guard,
    ):
        yield


@contextmanager
def _acquire_stream_generation_lock(archive_id: int):
    """Acquire an exclusive lock for streaming a chat response for the given archive."""
    with _acquire_per_archive_lock(
        archive_id,
        redis_key=_stream_lock_key(archive_id),
        ttl=60,
        busy_message="该会话正在生成回复，请稍后重试",
        locks_dict=_stream_generation_locks,
        locks_guard=_stream_generation_locks_guard,
    ):
        yield


logger = logging.getLogger(__name__)

DEFAULT_CHAPTER = "第一章"

_STREAM_GUARD_MIN_CHARS = 80
_STREAM_GUARD_MAX_CHARS = 140

_STREAM_KEEPALIVE_INTERVAL = 15  # 每 N 个 delta 发送一次 keepalive


def _build_stream_prompt_sections(
    story: models.Story,
    db: Session,
    *,
    forced_plot_label: bool = False,
    characters: list[dict] | None = None,
    reply_style: str | None = None,
    memory_section: str | None = None,
) -> list[str]:
    app_settings = _get_or_create_app_settings(db)
    global_default_system_prompt = (app_settings.default_system_prompt or "").strip()

    world_text = (story.world_setting or "").strip()
    if world_text and characters:
        world_text = _expand_character_references(world_text, characters)

    sections: list[str] = []
    if global_default_system_prompt:
        sections.append("【全局默认系统提示词】\n" + global_default_system_prompt)
    if (story.system_prompt or "").strip():
        sections.append("【故事专属系统提示词】\n" + story.system_prompt.strip())
    if world_text:
        sections.append("【故事世界观提示词】\n" + world_text)
    if memory_section:
        sections.append(memory_section)
    # Inject writing style skill if enabled
    if app_settings.style_skill_enabled and (app_settings.style_skill_content or "").strip():
        sections.append(
            "【文笔风格约束 - 仅影响正文叙事】\n" + app_settings.style_skill_content.strip()
        )
    sections.append(_STREAM_BODY_NARRATIVE_PROMPT)
    sections.append(HUMANIZED_WRITING_RULES)
    sections.append(_build_length_prompt(_length_spec_for_style(reply_style)))
    if forced_plot_label:
        sections.append(PLOT_LABEL_FORCED_PROMPT)
    sections.append(
        "【输出规则 - 仅正文】\n"
        "你只需要输出小说正文，不要生成 JSON，不要生成字段名，不要生成代码块，不要生成任何系统说明。\n"
        "直接开始正文，不要使用“好的”“以下是输出”“根据设定”等开场。\n"
        "使用第二人称“你”，保持叙事连贯，并自然推进剧情。"
    )
    sections.append(ANTI_INJECTION_CLAUSE)
    return sections


def _stream_chat_response(
    db: Session,
    *,
    story: models.Story,
    archive: models.Archive,
    settings: models.UserSettings,
    user_content: str,
    persist_user_content: str,
    include_history: bool,
    first_opening: bool,
    first_message: str = "",
    stream_fn=None,
) -> Generator[str, None, None]:
    # 准备阶段（构建 prompt、解析候选模型）发生在首个 yield 之前。
    # 此处若直接 raise（典型：未配置模型时 _get_normal_model_candidates 抛 503），
    # 响应已以 200 开始流式输出，异常只会掐断连接，前端收到空 Body，
    # 只能报"未收到结构化尾包"而非真实原因。统一转成 SSE error 事件让前端正确提示。
    try:
        rounds_without_label = _count_rounds_without_plot_label(db, archive.id)
        forced_plot_label = rounds_without_label >= MAX_ROUNDS_WITHOUT_PLOT_LABEL

        characters = _get_story_characters(db, story.id)
        inject_count = _resolve_memory_inject_count(settings.memory_inject_count)
        memory_section = _build_memory_section(
            archive.memory_log, inject_count, archive_id=archive.id, escape=False
        )
        stream_sections = _build_stream_prompt_sections(
            story,
            db,
            forced_plot_label=forced_plot_label,
            characters=characters,
            reply_style=settings.reply_style,
            memory_section=memory_section,
        )
        messages: list[dict] = [{"role": "system", "content": "\n\n".join(stream_sections)}]
        if include_history:
            current_settings = _get_or_create_settings(db)
            context_length = current_settings.context_length or 10
            history = _query_dialogue_history(db, archive.id, context_length)
            for item in history:
                messages.append(
                    {
                        "role": "assistant" if item.role == "assistant" else "user",
                        "content": item.content,
                    }
                )
        messages.append({"role": "user", "content": _restore_tail_escape(user_content)})

        candidates = _get_normal_model_candidates(db, settings)
    except HTTPException as exc:
        yield _sse_event(
            "error",
            {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail)[:200],
                "task": "chat_stream",
                "draft": False,
            },
        )
        yield _sse_event("done", {"ok": False})
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("流式聊天准备阶段失败")
        yield _sse_event(
            "error",
            {
                "code": "STREAM_PREPARATION_FAILED",
                "message": f"聊天准备失败：{exc}"[:200],
                "task": "chat_stream",
                "draft": False,
            },
        )
        yield _sse_event("done", {"ok": False})
        return
    temperature = _get_temperature(candidates[0] if candidates else None)
    _stream = stream_fn or _stream_model_once

    request_id = uuid.uuid4().hex
    last_error = "模型调用失败"
    last_error_code = "STREAM_ALL_MODELS_FAILED"

    for idx, model_cfg in enumerate(candidates):
        started_at = time.perf_counter()
        usage: dict = {}
        visible_chunks: list[str] = []
        pending_chunks: list[str] = []
        emitted_delta = False
        ttfb_ms = 0
        delta_count = 0
        reply_text = ""
        recent_window = ""
        tail_buffer = ""

        try:
            for chunk in _stream(model_cfg, messages, temperature, usage):
                if not chunk:
                    continue

                if not ttfb_ms:
                    ttfb_ms = int((time.perf_counter() - started_at) * 1000)

                if not emitted_delta:
                    pending_chunks.append(chunk)
                    buffered = "".join(pending_chunks)
                    pollution_reason = _detect_body_pollution(buffered, pre_delta=True)
                    if pollution_reason:
                        raise BodyPollutedError(pollution_reason, pre_delta=True)
                    if (
                        len(buffered) < _STREAM_GUARD_MIN_CHARS
                        and len(buffered) < _STREAM_GUARD_MAX_CHARS
                        and not _has_sentence_boundary(buffered)
                    ):
                        continue
                    for buffered_chunk in pending_chunks:
                        visible_chunks.append(buffered_chunk)
                        emitted_delta = True
                        yield _sse_event("delta", {"text": buffered_chunk})
                        delta_count += 1
                        if delta_count % _STREAM_KEEPALIVE_INTERVAL == 0:
                            yield _sse_keepalive()
                    recent_window = buffered[-400:]
                    pending_chunks = []
                    continue

                pollution_reason = _detect_body_pollution(
                    (recent_window + chunk)[-400:], pre_delta=False
                )
                if pollution_reason:
                    raise BodyPollutedError(pollution_reason, pre_delta=False)

                if "\n" in chunk:
                    # Flush old tail_buffer; it is no longer the last line
                    if tail_buffer:
                        visible_chunks.append(tail_buffer)
                        recent_window = (recent_window + tail_buffer)[-400:]
                        yield _sse_event("delta", {"text": tail_buffer})
                        delta_count += 1
                        if delta_count % _STREAM_KEEPALIVE_INTERVAL == 0:
                            yield _sse_keepalive()
                        tail_buffer = ""
                    # Split chunk: everything up to (but not including) the last newline
                    # goes directly; content after the last newline goes into tail_buffer
                    last_nl = chunk.rfind("\n")
                    before_nl = chunk[: last_nl + 1]
                    after_nl = chunk[last_nl + 1 :]
                    if before_nl:
                        visible_chunks.append(before_nl)
                        recent_window = (recent_window + before_nl)[-400:]
                        yield _sse_event("delta", {"text": before_nl})
                        delta_count += 1
                        if delta_count % _STREAM_KEEPALIVE_INTERVAL == 0:
                            yield _sse_keepalive()
                    tail_buffer = after_nl
                else:
                    tail_buffer += chunk
                    recent_window = (recent_window + chunk)[-400:]

            if pending_chunks:
                buffered = "".join(pending_chunks)
                pollution_reason = _detect_body_pollution(buffered, pre_delta=True)
                if pollution_reason:
                    raise BodyPollutedError(pollution_reason, pre_delta=True)
                for buffered_chunk in pending_chunks:
                    visible_chunks.append(buffered_chunk)
                    emitted_delta = True
                    yield _sse_event("delta", {"text": buffered_chunk})
                    delta_count += 1
                    if delta_count % _STREAM_KEEPALIVE_INTERVAL == 0:
                        yield _sse_keepalive()

            # Flush tail_buffer: if it's a trailing bracket line, discard it; otherwise send it
            if tail_buffer:
                if _is_trailing_bracket_line(tail_buffer):
                    tail_buffer = ""  # discard
                else:
                    visible_chunks.append(tail_buffer)
                    yield _sse_event("delta", {"text": tail_buffer})
                    delta_count += 1
                    if delta_count % _STREAM_KEEPALIVE_INTERVAL == 0:
                        yield _sse_keepalive()
                    tail_buffer = ""

            reply_text = _strip_trailing_bracket_line("".join(visible_chunks))
            if not reply_text:
                raise ValueError("模型未返回任何正文内容")
            # 正文已完整流完：立即通知前端释放 streaming 状态（解除输入框禁用、停止"三点"动效）。
            # 后续 tail 仍会带来结构化数据（选项、状态、记忆），但那不应阻塞用户继续输入。
            yield _sse_event("text_end", {"reply_text": reply_text})

            try:
                tail_messages = _build_tail_messages(
                    body_text=reply_text,
                    prev_character_state=archive.state_data or {},
                    prev_story_state=archive.story_state
                    or {"chapter": DEFAULT_CHAPTER, "progress": 0},
                    recent_memory=archive.memory_log or [],
                )

                tail_content, tail_usage = _call_model_once(
                    model_cfg,
                    tail_messages,
                    0.3,
                    response_format=build_contract_response_format(TASK_CHAT_RESPONSE),
                    timeout=60.0,
                )
                validated = _validate_contract_from_text(
                    TASK_CHAT_RESPONSE,
                    tail_content,
                    allow_legacy_text_fallback=False,
                )
                validated = validated.model_copy(
                    update={
                        "reply_text": reply_text,
                    }
                )

                user_id, ai_id = _persist_exchange(
                    db,
                    archive=archive,
                    user_content=persist_user_content,
                    validated=validated,
                    model_name=model_cfg.model_id,
                    first_message=first_message,
                )

                latency_ms = int((time.perf_counter() - started_at) * 1000)
                prompt_tokens = int(usage.get("prompt_tokens") or 0) + int(
                    tail_usage.get("prompt_tokens") or 0
                )
                completion_tokens = int(usage.get("completion_tokens") or 0) + int(
                    tail_usage.get("completion_tokens") or 0
                )
                total_tokens = int(usage.get("total_tokens") or 0) + int(
                    tail_usage.get("total_tokens")
                    or (
                        int(tail_usage.get("prompt_tokens") or 0)
                        + int(tail_usage.get("completion_tokens") or 0)
                    )
                )
                cost = _calc_cost(model_cfg, prompt_tokens, completion_tokens)

                _log_call(
                    db,
                    request_id=request_id,
                    archive_id=archive.id,
                    story_id=story.id,
                    model_cfg=model_cfg,
                    success=True,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_estimate=cost,
                    is_stream=True,
                    stream_emitted_delta=emitted_delta,
                    ttfb_ms=ttfb_ms,
                    fallback_used=idx > 0,
                    tail_valid=True,
                    plot_label_generated=bool(validated.plot_label),
                )

                tail = validated.model_dump()
                tail["archive_id"] = archive.id
                tail["message_id"] = ai_id
                tail["user_id"] = user_id
                tail["model_name"] = model_cfg.model_id
                yield _sse_event("tail", tail)
                yield _sse_event("done", {"ok": True})
                return

            except Exception as exc:  # noqa: BLE001
                # tail 阶段异常：先 yield error 和 done，再用 return 退出 generator（不要 raise）。
                # raise 会触发 GeneratorExit，FastAPI 会强制关闭响应体，客户端读不到 done，得等 180 秒超时。
                # return 让 SSE 流正常结束，客户端拿到 done 后自己清理。
                last_error = str(exc)
                last_error_code = "STREAM_MODEL_FAILED"
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                lower_error = last_error.lower()
                if isinstance(exc, ValidationError):
                    error_stage = STREAM_ERROR_STAGE_TAIL_SCHEMA
                elif "json" in lower_error or "schema" in lower_error or "校验" in lower_error:
                    error_stage = STREAM_ERROR_STAGE_TAIL_JSON
                else:
                    error_stage = (
                        STREAM_ERROR_STAGE_UPSTREAM
                        if last_error.strip().startswith("HTTP")
                        else STREAM_ERROR_STAGE_POST_DELTA
                    )

                user_id, ai_id = _persist_draft_exchange(
                    db,
                    archive=archive,
                    user_content=persist_user_content,
                    draft_reply_text=reply_text,
                    model_name=model_cfg.model_id,
                    first_message=first_message,
                )
                _log_call(
                    db,
                    request_id=request_id,
                    archive_id=archive.id,
                    story_id=story.id,
                    model_cfg=model_cfg,
                    success=False,
                    error_code=last_error_code,
                    error_message=last_error,
                    latency_ms=latency_ms,
                    is_stream=True,
                    stream_emitted_delta=emitted_delta,
                    ttfb_ms=ttfb_ms,
                    fallback_used=idx > 0,
                    tail_valid=False,
                    error_stage=error_stage,
                    plot_label_generated=False,
                )
                yield _sse_event(
                    "error",
                    {
                        "code": last_error_code,
                        "message": last_error[:200],
                        "task": "chat_tail",
                        "draft": True,
                        "user_id": user_id,
                        "message_id": ai_id,
                    },
                )
                yield _sse_event("done", {"ok": False})
                return

        except GeneratorExit:
            return

        except BodyPollutedError as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            last_error = str(exc)
            last_error_code = "STREAM_BODY_POLLUTED"
            error_stage = (
                STREAM_ERROR_STAGE_PRE_DELTA if exc.pre_delta else STREAM_ERROR_STAGE_POST_DELTA
            )

            _log_call(
                db,
                request_id=request_id,
                archive_id=archive.id,
                story_id=story.id,
                model_cfg=model_cfg,
                success=False,
                error_code="STREAM_BODY_POLLUTED",
                error_message=last_error,
                latency_ms=latency_ms,
                is_stream=True,
                stream_emitted_delta=emitted_delta,
                ttfb_ms=ttfb_ms,
                fallback_used=idx > 0,
                tail_valid=False,
                error_stage=error_stage,
                plot_label_generated=False,
            )

            if exc.pre_delta:
                continue

            yield _sse_event(
                "error",
                {
                    "code": "STREAM_BODY_POLLUTED",
                    "message": "检测到结构化内容混入正文，已拦截本轮输出",
                    "task": "chat_body",
                    "draft": False,
                },
            )
            yield _sse_event("done", {"ok": False})
            return

        except (ValidationError, ValueError) as exc:
            if tail_buffer:
                if _is_trailing_bracket_line(tail_buffer):
                    tail_buffer = ""  # discard
                else:
                    visible_chunks.append(tail_buffer)
                    tail_buffer = ""
            reply_text = _strip_trailing_bracket_line("".join(visible_chunks))
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            last_error = str(exc)
            last_error_code = "STREAM_SCHEMA_INVALID"
            lower_error = last_error.lower()

            if isinstance(exc, ValidationError):
                error_stage = STREAM_ERROR_STAGE_TAIL_SCHEMA
            elif "json" in lower_error:
                error_stage = STREAM_ERROR_STAGE_TAIL_JSON
            elif "schema" in lower_error or "校验" in lower_error:
                error_stage = STREAM_ERROR_STAGE_TAIL_SCHEMA
            elif emitted_delta:
                error_stage = STREAM_ERROR_STAGE_POST_DELTA
            else:
                error_stage = STREAM_ERROR_STAGE_PRE_DELTA

            _log_call(
                db,
                request_id=request_id,
                archive_id=archive.id,
                story_id=story.id,
                model_cfg=model_cfg,
                success=False,
                error_code="STREAM_SCHEMA_INVALID",
                error_message=last_error,
                latency_ms=latency_ms,
                is_stream=True,
                stream_emitted_delta=emitted_delta,
                ttfb_ms=ttfb_ms,
                fallback_used=idx > 0,
                tail_valid=False,
                error_stage=error_stage,
                plot_label_generated=False,
            )

            if emitted_delta:
                user_id, ai_id = _persist_draft_exchange(
                    db,
                    archive=archive,
                    user_content=persist_user_content,
                    draft_reply_text=reply_text,
                    model_name=model_cfg.model_id,
                    first_message=first_message,
                )
                yield _sse_event(
                    "error",
                    {
                        "code": "STREAM_SCHEMA_INVALID",
                        "message": last_error[:200],
                        "task": "chat_tail",
                        "draft": True,
                        "user_id": user_id,
                        "message_id": ai_id,
                    },
                )
                yield _sse_event("done", {"ok": False})
                return

        except Exception as exc:  # noqa: BLE001
            if tail_buffer:
                if _is_trailing_bracket_line(tail_buffer):
                    tail_buffer = ""  # discard
                else:
                    visible_chunks.append(tail_buffer)
                    tail_buffer = ""
            reply_text = _strip_trailing_bracket_line("".join(visible_chunks))
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            last_error = str(exc)
            last_error_code = "STREAM_MODEL_FAILED"
            error_stage = (
                STREAM_ERROR_STAGE_UPSTREAM
                if last_error.strip().startswith("HTTP")
                else STREAM_ERROR_STAGE_PRE_DELTA
            )

            _log_call(
                db,
                request_id=request_id,
                archive_id=archive.id,
                story_id=story.id,
                model_cfg=model_cfg,
                success=False,
                error_code="STREAM_MODEL_FAILED",
                error_message=last_error,
                latency_ms=latency_ms,
                is_stream=True,
                stream_emitted_delta=emitted_delta,
                ttfb_ms=ttfb_ms,
                fallback_used=idx > 0,
                tail_valid=False,
                error_stage=error_stage,
                plot_label_generated=False,
            )

            if emitted_delta:
                user_id, ai_id = _persist_draft_exchange(
                    db,
                    archive=archive,
                    user_content=persist_user_content,
                    draft_reply_text=reply_text,
                    model_name=model_cfg.model_id,
                    first_message=first_message,
                )
                yield _sse_event(
                    "error",
                    {
                        "code": "STREAM_MODEL_FAILED",
                        "message": last_error[:200],
                        "task": "chat_stream",
                        "draft": True,
                        "user_id": user_id,
                        "message_id": ai_id,
                    },
                )
                yield _sse_event("done", {"ok": False})
                return

    yield _sse_event(
        "error",
        {
            "code": last_error_code,
            "message": last_error[:200],
            "task": "chat_stream",
            "draft": False,
        },
    )
    yield _sse_event("done", {"ok": False})


def _generate_chat_response(
    db: Session,
    *,
    story: models.Story,
    archive: models.Archive,
    settings: models.UserSettings,
    user_content: str,
    include_history: bool,
    first_opening: bool,
    extra_sections: list[str] | None = None,
    call_ai_fn=None,
) -> schemas.ChatResponse:
    rounds_without_label = _count_rounds_without_plot_label(db, archive.id)
    forced_plot_label = rounds_without_label >= MAX_ROUNDS_WITHOUT_PLOT_LABEL

    inject_count = _resolve_memory_inject_count(settings.memory_inject_count)
    memory_section = _build_memory_section(
        archive.memory_log, inject_count, archive_id=archive.id, escape=True
    )
    messages = _build_messages(
        story,
        archive,
        user_content,
        settings,
        db,
        include_history=include_history,
        output_rule_prompt=get_contract_output_rule(TASK_CHAT_RESPONSE),
        extra_sections=extra_sections,
        forced_plot_label=forced_plot_label,
        characters=_get_story_characters(db, story.id),
        memory_section=memory_section,
    )
    candidates = _get_normal_model_candidates(db, settings)
    temperature = _get_temperature(candidates[0] if candidates else None)

    if call_ai_fn is None:
        from .chat_models import _call_ai_with_failover as _call_ai
    else:
        _call_ai = call_ai_fn

    validated = _call_ai(
        db,
        candidates=candidates,
        story=story,
        archive=archive,
        messages=messages,
        temperature=temperature,
    )
    return validated
