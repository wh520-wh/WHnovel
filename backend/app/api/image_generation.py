"""图片生成 — 封面图、背景图、对话图片"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import certifi
import httpx

from ..crypto import decrypt
from ..prompts.image_gen import _build_background_prompt, _build_cover_prompt
from ..schemas import VALID_IMAGE_SIZES

STATIC_IMAGES_DIR = Path(__file__).parent.parent / "static" / "images"
_IMAGE_SIZES = VALID_IMAGE_SIZES


def resolve_image_size(value: str | None) -> str:
    """读取侧兜底：存量脏数据（空串/非法值/None）回退 "2K"，不再让下游 500。"""
    return value if value in VALID_IMAGE_SIZES else "2K"


def _call_image_api(
    api_key: str,
    api_base: str,
    model: str,
    prompt: str,
    size: str = "2K",
    watermark: bool = True,
    ssl_verify: bool = True,
    image_api_mode: str = "openai_images",
    image_workflow_template: str | None = None,
) -> str:
    """
    Call image generation API.
    - openai_images: POST {base}/v1/images/generations
    - custom_image: POST {base} (caller provides full URL)
    - comfyui: POST {base}/prompt with workflow template
    """
    if size not in _IMAGE_SIZES:
        raise ValueError(f"Invalid image_size: {size}. Must be one of {_IMAGE_SIZES}")

    if image_api_mode == "comfyui":
        if not image_workflow_template:
            raise RuntimeError("ComfyUI 模型未配置 workflow 模板，请前往管理后台设置")
        from .comfyui_adapter import _call_comfyui_api

        return _call_comfyui_api(
            api_base=api_base,
            workflow_template=image_workflow_template,
            prompt=prompt,
            ssl_verify=ssl_verify,
        )

    from .chat_api_adapter import _body_openai_images, _parse_openai_image, get_adapter

    ad = get_adapter(image_api_mode)
    url = ad["url"](api_base, model, False)

    image_body = ad.get("image_body", _body_openai_images)
    body = image_body(model, prompt, size, watermark)
    if not api_key:
        raise RuntimeError("图片模型未配置 API Key，请前往管理后台设置")
    headers = ad["headers"](api_key)
    verify = certifi.where() if ssl_verify else False
    with httpx.Client(timeout=120.0, verify=verify) as client:
        resp = client.post(url, json=body, headers=headers)
    if resp.status_code >= 400:
        raise RuntimeError(f"Image API HTTP {resp.status_code}: {resp.text[:240]}")
    data = resp.json()
    try:
        image_parser = ad.get("image_parser", _parse_openai_image)
        return image_parser(data)
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Image API response parse error: {e}, body: {resp.text[:300]}") from e


def _download_and_save_image(image_url: str, filename: str) -> str:
    """
    下载图片并保存到 backend/static/images/。
    filename 应包含完整文件名（含扩展名）。
    如果 image_url 已经是本地 /api/images/ 路径则直接返回。
    """
    if image_url.startswith("/api/images/"):
        return image_url
    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    save_path = STATIC_IMAGES_DIR / filename
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(image_url)
    if resp.status_code >= 400:
        raise RuntimeError(f"Failed to download image: HTTP {resp.status_code}")
    save_path.write_bytes(resp.content)
    return f"/api/images/{filename}"


def generate_cover_image(
    image_model_cfg,  # ModelConfig instance
    world_setting: str,
    title: str,
    story_id: int,
    size: str = "2K",
    watermark: bool = True,
    style: str = "",  # 图片风格描述
) -> str:
    """
    完整流程：构建 prompt → 调用 API → 下载保存 → 返回本地路径。
    失败时抛出异常，由调用方决定如何处理。
    """
    prompt = _build_cover_prompt(world_setting, title, style)
    api_key = (
        decrypt(image_model_cfg.image_api_key or image_model_cfg.api_key)
        if (image_model_cfg.image_api_key or image_model_cfg.api_key)
        else ""
    )
    image_url = _call_image_api(
        api_key=api_key,
        api_base=image_model_cfg.image_api_base or image_model_cfg.api_base_url or "",
        model=image_model_cfg.model_id,
        prompt=prompt,
        size=size,
        watermark=watermark,
        ssl_verify=image_model_cfg.ssl_verify,
        image_api_mode=image_model_cfg.image_api_mode or "openai_images",
        image_workflow_template=image_model_cfg.image_workflow_template,
    )
    local_path = _download_and_save_image(
        image_url, f"story_{story_id}_cover_{int(time.time())}.png"
    )
    return local_path


def generate_background_image(
    image_model_cfg,  # ModelConfig instance
    world_setting: str,
    title: str,
    story_id: int,
    size: str = "2K",
    watermark: bool = True,
    style: str = "",
) -> str:
    """
    完整流程：构建背景图 prompt → 调用 API → 下载保存 → 返回本地路径。
    背景图强调宽幅、无文字、氛围感为主。
    失败时抛出异常，由调用方决定如何处理。
    """
    prompt = _build_background_prompt(world_setting, title, style)
    api_key = (
        decrypt(image_model_cfg.image_api_key or image_model_cfg.api_key)
        if (image_model_cfg.image_api_key or image_model_cfg.api_key)
        else ""
    )
    image_url = _call_image_api(
        api_key=api_key,
        api_base=image_model_cfg.image_api_base or image_model_cfg.api_base_url or "",
        model=image_model_cfg.model_id,
        prompt=prompt,
        size=size,
        watermark=watermark,
        ssl_verify=image_model_cfg.ssl_verify,
        image_api_mode=image_model_cfg.image_api_mode or "openai_images",
        image_workflow_template=image_model_cfg.image_workflow_template,
    )
    local_path = _download_and_save_image(
        image_url, f"story_{story_id}_background_{int(time.time())}.png"
    )
    return local_path


def generate_chat_image(
    image_model_cfg,  # ModelConfig instance
    prompt: str,
    archive_id: int,
    size: str = "2K",
    watermark: bool = False,
    style: str = "",  # 图片风格描述
) -> str:
    """
    完整流程：调用图片 API → 下载保存 → 返回本地路径。
    用于对话内图片生成。
    失败时抛出异常，由调用方决定如何处理。
    """
    # 将风格描述追加到 prompt 末尾
    import logging

    _img_logger = logging.getLogger(__name__)
    if style:
        prompt = f"{prompt.strip()}\n\n图片风格要求：{style}"
    _stored = image_model_cfg.image_api_key or image_model_cfg.api_key
    api_key = decrypt(_stored) if _stored else ""
    _img_logger.info(
        f"图片生成: model_id={image_model_cfg.model_id}, has_key={bool(_stored)}, api_base={image_model_cfg.image_api_base or image_model_cfg.api_base_url}"
    )
    image_url = _call_image_api(
        api_key=api_key,
        api_base=image_model_cfg.image_api_base or image_model_cfg.api_base_url or "",
        model=image_model_cfg.model_id,
        prompt=prompt,
        size=size,
        watermark=watermark,
        ssl_verify=image_model_cfg.ssl_verify,
        image_api_mode=image_model_cfg.image_api_mode or "openai_images",
        image_workflow_template=image_model_cfg.image_workflow_template,
    )
    local_path = _download_and_save_image(image_url, f"chat_{archive_id}_{uuid.uuid4().hex}.png")
    return local_path
