"""Story generation helpers."""
from __future__ import annotations

from .. import models, schemas
from .ai_contracts import TASK_STORY_GENERATE, build_contract_response_format, get_contract_output_rule
from .chat_models import _call_model_once, _validate_contract_from_text


def _build_story_prompt(category: str, title_hint: str, tags_hint: str, user_image_style: str = "", user_preference: str = "") -> str:
    if category == "其他":
        category_instruction = (
            '注意：分类为"其他"，请生成一个独特、不落俗套的世界观。'
            '避免常见的科幻、玄幻、都市套路，要有自己的世界规则、文化设定或社会结构。'
        )
    else:
        category_instruction = f'故事分类为"{category}"，请围绕该分类的核心特征构建故事。'

    hint_section = ""
    if title_hint:
        hint_section += f"\n用户提供的标题方向：{title_hint}"
    if tags_hint:
        hint_section += f"\n用户提供的标签方向：{tags_hint}"
    if user_preference:
        hint_section += f"\n用户对故事的偏好要求：{user_preference}"

    if user_image_style:
        style_section = (
            f"\n用户指定了图片风格要求：{user_image_style}"
            "\n请保留其核心视觉意图，并生成一段适合作为封面画风说明的 image_style。"
        )
    else:
        style_section = (
            "\n请根据故事氛围自主生成 image_style，作为封面图的视觉风格说明。"
        )

    return (
        "你是一名专业的小说世界观策划。\n"
        "请根据以下信息生成一个完整、可直接用于前端展示的故事方案。\n\n"
        f"{category_instruction}"
        f"{hint_section}"
        f"{style_section}\n\n"
        "内容要求：\n"
        "- title 要有吸引力，不超过 50 字\n"
        "- description 为 100-200 字的简介\n"
        "- world_setting 为完整世界观设定\n"
        "- image_style 为简洁清晰的视觉风格说明\n"
        f"- category 固定与输入分类保持一致：{category}\n\n"
        f"{get_contract_output_rule(TASK_STORY_GENERATE)}"
    )


def generate_story_content(
    model_cfg: models.ModelConfig,
    category: str,
    title_hint: str,
    tags_hint: str,
    user_image_style: str = "",
    user_preference: str = "",
) -> schemas.StoryGenerateOut:
    prompt = _build_story_prompt(category, title_hint, tags_hint, user_image_style, user_preference)
    messages = [{"role": "user", "content": prompt}]
    raw_content, _ = _call_model_once(
        model_cfg,
        messages,
        temperature=0.8,
        response_format=build_contract_response_format(TASK_STORY_GENERATE),
        timeout=60.0,
    )
    validated = _validate_contract_from_text(TASK_STORY_GENERATE, raw_content, allow_legacy_text_fallback=False)
    return validated.model_copy(update={"category": category, "cover_url": ""})


def generate_story_with_cover(
    text_model_cfg: models.ModelConfig,
    image_model_cfg: models.ModelConfig | None,
    category: str,
    title_hint: str,
    tags_hint: str,
    enable_image: bool,
    image_size: str,
    image_watermark: bool,
    story_id: int = 0,
    user_image_style: str = "",
    user_preference: str = "",
) -> schemas.StoryGenerateOut:
    story = generate_story_content(
        model_cfg=text_model_cfg,
        category=category,
        title_hint=title_hint,
        tags_hint=tags_hint,
        user_image_style=user_image_style,
        user_preference=user_preference,
    )

    if enable_image and image_model_cfg is not None:
        try:
            from .image_generation import generate_cover_image

            cover_local_path = generate_cover_image(
                image_model_cfg=image_model_cfg,
                world_setting=story.world_setting,
                title=story.title,
                story_id=story_id,
                size=image_size,
                watermark=image_watermark,
                style=story.image_style or "",
            )
            story.cover_url = cover_local_path
        except Exception:  # noqa: BLE001
            story.cover_url = ""

    return story
