"""Chat API routes."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..prompts import PLOT_PROGRESS_RULE_PROMPT, PRESET_OPENINGS_PROMPT
from .ai_contracts import (
    TASK_OPTIONS_GENERATE,
    TASK_PRESET_OPENINGS,
    TASK_STATE_BROADCAST,
    get_contract_output_rule,
)
from .chat_cache import get_or_generate
from .chat_models import (
    _call_ai_with_failover,
    _call_text_model_once,
    _get_enabled_models,
    _get_normal_model_candidates,
    _get_temperature,
    _order_model_chain,
    _stream_model_once,
)
from .chat_options import _acquire_option_generation_lock
from .chat_options_validator import validate_options_list
from .chat_storage import (
    _build_messages,
    _ensure_archive_for_story,
    _get_or_create_app_settings,
    _get_or_create_settings,
    _get_story_characters,
    _persist_exchange,
    bulk_delete_messages,
)
from .chat_stream import (
    _acquire_image_generation_lock,
    _acquire_stream_generation_lock,
    _generate_chat_response,
    _stream_chat_response,
)
from .image_generation import generate_chat_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _locked_streaming_response(
    archive_id: int, stream_factory: Callable[[], Iterable[str]]
) -> StreamingResponse:
    lock_context = _acquire_stream_generation_lock(archive_id)
    lock_context.__enter__()

    def locked_stream():
        try:
            yield from stream_factory()
        finally:
            lock_context.__exit__(None, None, None)

    return StreamingResponse(
        locked_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


DEFAULT_CHAPTER = "第一章"


@router.post("/start-stream")
def start_chat_stream(payload: schemas.ChatStartInput, db: Session = Depends(get_db)):
    story = db.query(models.Story).filter(models.Story.id == payload.story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")

    settings = _get_or_create_settings(db)
    archive = _ensure_archive_for_story(db, story, payload.archive_id)

    existing_ai_msg = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.archive_id == archive.id, models.ChatMessage.role == "assistant")
        .first()
    )
    if existing_ai_msg:
        raise HTTPException(400, "当前会话已开始，请直接继续对话")

    opening_requirement = payload.opening_requirement.strip()
    if not opening_requirement:
        raise HTTPException(400, "开场要求不能为空")

    user_content = (
        "请根据下面的用户开场要求，结合世界观生成一个自然的故事开场。\n"
        "只需要输出小说正文，不要输出 JSON、代码块或任何中转说明。\n"
        f"用户开场要求：{opening_requirement}"
    )

    return _locked_streaming_response(
        archive.id,
        lambda: _stream_chat_response(
            db,
            story=story,
            archive=archive,
            settings=settings,
            user_content=user_content,
            persist_user_content=opening_requirement,
            include_history=False,
            first_opening=False,
            first_message=opening_requirement,
            stream_fn=_stream_model_once,
        ),
    )


@router.post("/preset-openings", response_model=schemas.PresetOpeningsResponse)
def get_preset_openings(
    payload: schemas.PresetOpeningsRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    story = db.query(models.Story).filter(models.Story.id == payload.story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")

    if not story.world_setting:
        raise HTTPException(400, "该故事没有世界观设定，无法生成预设开场")

    world_setting = story.world_setting.strip()
    if_none_match = request.headers.get("If-None-Match")

    def generate_openings():
        settings = _get_or_create_settings(db)
        enabled = _get_enabled_models(db)
        if not enabled:
            raise HTTPException(503, "没有可用模型，请先在管理后台启用模型")

        ordered = _order_model_chain(enabled, settings.primary_model_id, settings.backup_model_ids)
        if not ordered:
            raise HTTPException(503, "模型未配置或未启用")

        prompt = PRESET_OPENINGS_PROMPT.format(world_setting=world_setting)
        messages = [{"role": "user", "content": prompt}]

        validated = _call_ai_with_failover(
            db,
            candidates=ordered,
            story=story,
            archive=None,
            messages=messages,
            temperature=0.7,
            contract_task=TASK_PRESET_OPENINGS,
        )
        return [item.model_dump() for item in validated.openings]

    openings, etag, was_cached = get_or_generate(story.id, generate_openings)

    if was_cached and if_none_match and if_none_match == etag:
        response.status_code = 304
        return Response(status_code=304)

    response.headers["ETag"] = etag
    return schemas.PresetOpeningsResponse(openings=openings)


@router.post("/send-stream")
def send_message_stream(payload: schemas.ChatInput, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == payload.archive_id).first()
    if not archive:
        raise HTTPException(404, "会话不存在")

    settings = _get_or_create_settings(db)
    story = archive.story

    user_content = payload.message.strip()
    if not user_content:
        raise HTTPException(400, "消息不能为空")

    return _locked_streaming_response(
        archive.id,
        lambda: _stream_chat_response(
            db,
            story=story,
            archive=archive,
            settings=settings,
            user_content=user_content,
            persist_user_content=user_content,
            include_history=True,
            first_opening=False,
            stream_fn=_stream_model_once,
        ),
    )


@router.post("/send", response_model=schemas.ChatResponse)
def send_message(payload: schemas.ChatInput, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == payload.archive_id).first()
    if not archive:
        raise HTTPException(404, "会话不存在")

    settings = _get_or_create_settings(db)
    story = archive.story

    user_content = payload.message.strip()
    if not user_content:
        raise HTTPException(400, "消息不能为空")

    with _acquire_stream_generation_lock(archive.id):
        validated = _generate_chat_response(
            db,
            story=story,
            archive=archive,
            settings=settings,
            user_content=user_content,
            include_history=True,
            first_opening=False,
            extra_sections=["【剧情推进与选项差异化约束】\n" + PLOT_PROGRESS_RULE_PROMPT],
            call_ai_fn=_call_ai_with_failover,
        )
        _persist_exchange(
            db,
            archive=archive,
            user_content=user_content,
            validated=validated,
            first_message=user_content if not archive.first_message else "",
        )
        return validated


@router.post("/options/generate", response_model=schemas.OptionsGenerateOut)
def generate_options(payload: schemas.OptionsGenerateIn, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == payload.archive_id).first()
    if not archive:
        raise HTTPException(404, "会话不存在")

    with _acquire_option_generation_lock(archive.id):
        settings = _get_or_create_settings(db)
        story = archive.story

        count = min(max(int(payload.count or 3), 1), 6)
        guidance = payload.guidance.strip()
        type_constraint = "三个选项必须分别属于行动/对话/探索三种不同类型，彼此差异明显。"
        RETRY_HINT = "\n\n【重试提示】上一次生成的选项不够差异化，请确保三个选项分别属于行动/对话/探索三种不同类型，字数10-27字，禁止模糊词。"
        if settings.options_prompt:
            user_content = settings.options_prompt.strip()
            if guidance:
                user_content += f"\n额外要求：{guidance}"
            user_content += f"\n\n{type_constraint}"
            if "{count}" in user_content:
                user_content = user_content.replace("{count}", str(count))
        else:
            user_content = (
                f"请仅根据当前剧情生成 {count} 个后续可选行动。\n"
                "要求：简洁明确、彼此差异明显、可直接点击。"
            )
            if guidance:
                user_content += f"\n额外要求：{guidance}"

        messages = _build_messages(
            story,
            archive,
            user_content,
            settings,
            db,
            include_history=True,
            output_rule_prompt=get_contract_output_rule(TASK_OPTIONS_GENERATE),
            extra_sections=["【剧情推进与选项差异化约束】\n" + PLOT_PROGRESS_RULE_PROMPT],
            characters=_get_story_characters(db, story.id),
            context_length=8,
        )
        candidates = _get_normal_model_candidates(db, settings)
        temperature = _get_temperature(candidates[0] if candidates else None)

        validated = _call_ai_with_failover(
            db,
            candidates=candidates,
            story=story,
            archive=archive,
            messages=messages,
            temperature=temperature,
            contract_task=TASK_OPTIONS_GENERATE,
        )

        ok, err_msg = validate_options_list(validated.options or [])
        if not ok:
            retry_messages = [msg.copy() if isinstance(msg, dict) else msg for msg in messages]
            for i in range(len(retry_messages) - 1, -1, -1):
                if isinstance(retry_messages[i], dict) and retry_messages[i].get("role") == "user":
                    retry_messages[i] = {
                        **retry_messages[i],
                        "content": retry_messages[i]["content"] + RETRY_HINT,
                    }
                    break
            validated_retry = _call_ai_with_failover(
                db,
                candidates=candidates,
                story=story,
                archive=archive,
                messages=retry_messages,
                temperature=temperature,
                contract_task=TASK_OPTIONS_GENERATE,
            )
            ok2, err_msg2 = validate_options_list(validated_retry.options or [])
            if not ok2:
                raise HTTPException(400, f"选项生成失败：{err_msg2 or err_msg}")
            return schemas.OptionsGenerateOut(options=(validated_retry.options or [])[:count])

        return schemas.OptionsGenerateOut(options=(validated.options or [])[:count])


@router.post("/generate-image", response_model=schemas.GenerateImageOut)
def generate_chat_image_endpoint(
    payload: schemas.GenerateImageIn,
    db: Session = Depends(get_db),
):
    archive = db.query(models.Archive).filter(models.Archive.id == payload.archive_id).first()
    if not archive:
        raise HTTPException(404, "会话不存在")

    with _acquire_image_generation_lock(archive.id):
        idempotency_key = payload.idempotency_key or None
        if idempotency_key:
            existing = (
                db.query(models.ChatMessage)
                .filter(
                    models.ChatMessage.archive_id == archive.id,
                    models.ChatMessage.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing:
                return schemas.GenerateImageOut(
                    image_url=existing.image_url or "",
                    message_id=existing.id,
                    model_name=existing.model_name or "",
                )

        app_settings = _get_or_create_app_settings(db)
        story = archive.story

        image_model_cfg = None
        if app_settings.default_image_model_id:
            image_model_cfg = (
                db.query(models.ModelConfig)
                .filter(models.ModelConfig.id == app_settings.default_image_model_id)
                .first()
            )
        if not image_model_cfg:
            raise HTTPException(400, "未配置默认图片模型，请前往管理后台设置")
        if not image_model_cfg.enabled:
            raise HTTPException(400, "默认图片模型已禁用，请前往管理后台更换")
        if image_model_cfg.model_type != "image":
            raise HTTPException(400, "配置的模型不是图片模型，请前往管理后台更换")

        recent_msgs = (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.archive_id == payload.archive_id)
            .order_by(models.ChatMessage.created_at.desc())
            .limit(10)
            .all()
        )
        recent_msgs = list(reversed(recent_msgs))

        context_parts = []
        if story.world_setting:
            context_parts.append(f"世界观设定：{story.world_setting[:300]}")
        for msg in recent_msgs[-6:]:
            role_label = "用户" if msg.role == "user" else "AI"
            content = msg.content[:200] if msg.content else ""
            if content:
                context_parts.append(f"{role_label}：{content}")

        scene_context = "\n".join(context_parts)

        image_style = ""
        if story.image_style:
            image_style = story.image_style.strip()
        if not image_style and app_settings.default_image_style:
            image_style = app_settings.default_image_style.strip()
        if image_style:
            scene_context = f"{scene_context}\n\n画风要求：{image_style}"

        image_prompt_req = (
            "Based on the following story scene, describe in English what this scene looks like "
            "for image generation. Focus on visual details: setting, characters, mood, lighting, colors. "
            f"Keep it to 1-2 sentences, vivid and cinematic.\n\n{scene_context}"
        )

        settings = _get_or_create_settings(db)
        candidates = _get_normal_model_candidates(db, settings)
        if not candidates:
            raise HTTPException(400, "无可用对话模型")

        build_msgs = _build_messages(
            story,
            archive,
            image_prompt_req,
            settings,
            db,
            include_history=False,
            output_rule_prompt=None,
            extra_sections=[],
            characters=[],
        )
        temperature = _get_temperature(candidates[0] if candidates else None)
        image_prompt = ""
        try:
            image_prompt, _ = _call_text_model_once(candidates[0], build_msgs, temperature)
        except Exception:
            logger.warning("文本模型翻译图片 prompt 失败，使用原始场景描述作为回退")

        image_prompt = (image_prompt or "").strip()
        image_prompt = re.sub(r"<[^>]+>", "", image_prompt).strip()
        if not image_prompt:
            image_prompt = scene_context[:200]

        try:
            image_url = generate_chat_image(
                image_model_cfg=image_model_cfg,
                prompt=image_prompt,
                archive_id=archive.id,
                size=payload.size or "2K",
                watermark=payload.watermark,
                style="",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"图片生成失败: {exc}")
            raise HTTPException(500, "图片生成失败，请稍后重试") from exc

        ai_msg = models.ChatMessage(
            archive_id=archive.id,
            role="assistant",
            content="",
            state_snapshot=archive.state_data or {},
            story_state=archive.story_state or {"chapter": DEFAULT_CHAPTER, "progress": 0},
            options=[],
            memory_update=[],
            image_url=image_url,
            is_draft=0,
            idempotency_key=idempotency_key,
            model_name=image_model_cfg.model_id,
        )
        try:
            db.add(ai_msg)
            archive.updated_at = datetime.now()
            db.commit()
            db.refresh(ai_msg)
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(models.ChatMessage)
                .filter(
                    models.ChatMessage.archive_id == archive.id,
                    models.ChatMessage.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing:
                return schemas.GenerateImageOut(
                    image_url=existing.image_url or "",
                    message_id=existing.id,
                    model_name=existing.model_name or "",
                )
            raise

        return schemas.GenerateImageOut(
            image_url=image_url, message_id=ai_msg.id, model_name=image_model_cfg.model_id
        )


@router.get("/messages/{archive_id}", response_model=list[schemas.ChatMessageOut])
def get_messages(
    archive_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.archive_id == archive_id)
        .order_by(models.ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )


@router.get("/nodes/{archive_id}", response_model=list[schemas.StoryNodeOut])
def get_story_nodes(archive_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.StoryNode)
        .filter(models.StoryNode.archive_id == archive_id)
        .order_by(models.StoryNode.created_at.asc())
        .all()
    )


@router.delete("/messages/{archive_id}/last-ai")
def delete_last_ai_message(archive_id: int, db: Session = Depends(get_db)):
    archive = (
        db.query(models.Archive).filter(models.Archive.id == archive_id).with_for_update().first()
    )
    if not archive:
        raise HTTPException(404, "会话不存在")

    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.archive_id == archive_id)
        .order_by(models.ChatMessage.created_at.desc())
        .all()
    )
    if not messages:
        raise HTTPException(404, "没有可删除的消息")

    last_ai = None
    last_ai_idx = -1
    for index, msg in enumerate(messages):
        if msg.role == "assistant":
            last_ai = msg
            last_ai_idx = index
            break

    if not last_ai:
        raise HTTPException(400, "没有找到 AI 消息")

    deleted_count = 0
    if last_ai.story_node:
        db.delete(last_ai.story_node)

    db.delete(last_ai)
    deleted_count += 1

    if last_ai_idx + 1 < len(messages) and messages[last_ai_idx + 1].role == "user":
        db.delete(messages[last_ai_idx + 1])
        deleted_count += 1

    # Bug #7: 撤回时回滚 archive 三字段到 last_ai 写入前的旧值（last_ai.pre_* 快照）。
    # last_ai 无 pre_* 时（fix 部署前的老数据），回退到更老的 assistant 输出快照；都没有则用初始默认。
    last_remaining_ai = None
    for msg in messages[last_ai_idx + 1 :]:
        if msg.role == "assistant":
            last_remaining_ai = msg
            break

    pre_state = last_ai.pre_state_data
    pre_story = last_ai.pre_story_state
    pre_memory = last_ai.pre_memory_log
    if pre_state is None and last_remaining_ai is not None:
        pre_state = last_remaining_ai.state_snapshot
    if pre_story is None and last_remaining_ai is not None:
        pre_story = last_remaining_ai.story_state
    if pre_memory is None and last_remaining_ai is not None:
        pre_memory = last_remaining_ai.memory_update

    archive.state_data = pre_state if pre_state is not None else {}
    archive.story_state = pre_story if pre_story is not None else {}
    archive.memory_log = list(pre_memory) if pre_memory is not None else []

    db.commit()
    return {"deleted": deleted_count}


@router.delete("/messages/{archive_id}/bulk", response_model=schemas.BulkDeleteResponse)
def bulk_delete_messages_endpoint(
    archive_id: int, body: schemas.BulkDeleteRequest, db: Session = Depends(get_db)
):
    archive = db.query(models.Archive).filter(models.Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(404, "会话不存在")

    if not body.message_ids:
        return schemas.BulkDeleteResponse(deleted=0)

    deleted = bulk_delete_messages(db, archive_id, body.message_ids)
    return schemas.BulkDeleteResponse(deleted=deleted)


@router.post("/state-broadcast", response_model=schemas.StateBroadcastOut)
def generate_state_broadcast(payload: schemas.StateBroadcastIn, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == payload.archive_id).first()
    if not archive:
        raise HTTPException(404, "会话不存在")

    app_settings = _get_or_create_app_settings(db)
    state_broadcast_prompt = (app_settings.state_broadcast_prompt or "").strip()
    if not state_broadcast_prompt:
        raise HTTPException(400, "未配置状态播报提示词，请前往管理后台设置")

    settings = _get_or_create_settings(db)
    story = archive.story

    state_info = f"""当前角色状态：{archive.state_data or {}}
当前剧情状态：{archive.story_state or {}}
记忆日志：{archive.memory_log or []}"""

    user_content = f"""请根据以下状态信息，生成角色/剧情状态的键值对列表：

{state_info}

要求：
- 根据当前小说世界观和上下文自行判断应展示哪些属性，不要使用固定字段列表
- 至少生成 5-8 个属性（不少于 5 个），尽量丰富
- 属性类别参考（不限于这些）：角色状态（生命值/精神值/体力等）、场景环境、章节进度、当前目标、装备物品、同伴关系、时间天气、特殊效果等
- 每行一个属性，格式为：属性名 | 属性值
- 空值显示"无"，不省略
- 输出必须放在 JSON 对象的 content 字段内，格式为 {{"content": "键值对内容"}}"""

    messages = _build_messages(
        story,
        archive,
        user_content,
        settings,
        db,
        include_history=False,
        output_rule_prompt=get_contract_output_rule(TASK_STATE_BROADCAST),
        extra_sections=["【状态播报规则】\n" + state_broadcast_prompt],
        characters=_get_story_characters(db, story.id),
    )
    candidates = _get_normal_model_candidates(db, settings)
    temperature = _get_temperature(candidates[0] if candidates else None)

    validated = _call_ai_with_failover(
        db,
        candidates=candidates,
        story=story,
        archive=archive,
        messages=messages,
        temperature=temperature,
        contract_task=TASK_STATE_BROADCAST,
    )

    content = validated.content or ""

    ai_msg = models.ChatMessage(
        archive_id=archive.id,
        role="assistant",
        content=content,
        state_snapshot=archive.state_data or {},
        story_state=archive.story_state or {"chapter": DEFAULT_CHAPTER, "progress": 0},
        options=[],
        memory_update=[],
        is_state_broadcast=1,
    )
    db.add(ai_msg)
    archive.updated_at = datetime.now()
    db.commit()

    return schemas.StateBroadcastOut(content=content)
