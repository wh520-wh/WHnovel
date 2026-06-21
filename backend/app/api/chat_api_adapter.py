"""API mode adapters: URL, body, headers, response parsing per api_mode."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
UrlBuilder = Callable[[str, str, bool], str]  # (base, model_id, stream) -> url
BodyBuilder = Callable[..., dict]
HeadersBuilder = Callable[[str], dict]
ResponseParser = Callable[[dict], tuple[str, dict]]  # (text, usage)
StreamExtractor = Callable[[dict], str | None]  # delta text or None

Adapter = dict[str, Any]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------


def _url_openai_chat(base: str, model_id: str, stream: bool = False) -> str:
    return f"{base.rstrip('/')}/v1/chat/completions"


def _url_openai_responses(base: str, model_id: str, stream: bool = False) -> str:
    return f"{base.rstrip('/')}/v1/responses"


def _url_claude_messages(base: str, model_id: str, stream: bool = False) -> str:
    return f"{base.rstrip('/')}/v1/messages"


def _url_gemini(base: str, model_id: str, stream: bool = False) -> str:
    b = base.rstrip("/")
    if stream:
        return f"{b}/v1beta/models/{model_id}:streamGenerateContent?alt=sse"
    return f"{b}/v1beta/models/{model_id}:generateContent"


def _url_custom_chat(base: str, model_id: str, stream: bool = False) -> str:
    return base.rstrip("/")


def _url_openai_images(base: str, model_id: str, stream: bool = False) -> str:
    return f"{base.rstrip('/')}/v1/images/generations"


def _url_custom_image(base: str, model_id: str, stream: bool = False) -> str:
    return base.rstrip("/")


# ---------------------------------------------------------------------------
# Body builders — non-streaming
# ---------------------------------------------------------------------------


def _sanitize_dialogue_turns(messages: list[dict]) -> list[dict]:
    """对对话消息做交替兜底，防止 Claude/Gemini 因脏 history 400。

    - 合并连续同角色（content 以 \\n\\n 拼接）
    - 丢弃 strip 后为空的内容并 warning
    - 首条非 system 若为 assistant，前面补占位 user '.'
    - 全空则补占位 user '.'
    - system 合并为单条 leading system
    对干净交替输入幂等 no-op。
    """
    system_parts: list[str] = []
    dialogue: list[dict] = []
    for m in messages:
        if m.get("role") == "system":
            system_parts.append(str(m.get("content", "")))
            continue
        content = str(m.get("content", ""))
        if content.strip() == "":
            logger.warning("sanitize: dropped empty %s turn", m.get("role"))
            continue
        role = m.get("role", "user")
        if role != "assistant":
            role = "user"
        # 合并相邻同角色
        if dialogue and dialogue[-1]["role"] == role:
            dialogue[-1]["content"] = dialogue[-1]["content"] + "\n\n" + content
        else:
            dialogue.append({"role": role, "content": content})

    if not dialogue:
        logger.warning("sanitize: all dialogue empty/dropped; inserted placeholder user")
        dialogue.append({"role": "user", "content": "."})
    elif dialogue[0]["role"] != "user":
        logger.warning("sanitize: first non-system turn is assistant; inserted placeholder user")
        dialogue.insert(0, {"role": "user", "content": "."})

    out: list[dict] = []
    if system_parts:
        out.append({"role": "system", "content": "\n\n".join(system_parts)})
    out.extend(dialogue)
    return out


def _body_openai_chat(
    model_id: str,
    messages: list[dict],
    temperature: float,
    *,
    response_format: dict | None = None,
    stream: bool = False,
    max_tokens: int = 6000,
) -> dict:
    body: dict = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
    }
    if stream:
        body["stream"] = True
        body["max_tokens"] = max_tokens
    if response_format is not None:
        body["response_format"] = response_format
    return body


def _body_openai_responses(
    model_id: str,
    messages: list[dict],
    temperature: float,
    *,
    response_format: dict | None = None,
    stream: bool = False,
    max_tokens: int = 6000,
) -> dict:
    body: dict = {
        "model": model_id,
        "input": _messages_to_responses_input(messages),
        "temperature": temperature,
    }
    if stream:
        body["stream"] = True
        body["max_output_tokens"] = max_tokens
    if response_format is not None:
        body["text"] = {"format": response_format}
    return body


def _messages_to_responses_input(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            out.append({"role": "system", "content": content})
        elif role == "assistant":
            out.append({"role": "assistant", "content": content})
        else:
            out.append({"role": "user", "content": content})
    return out


def _body_claude_messages(
    model_id: str,
    messages: list[dict],
    temperature: float,
    *,
    response_format: dict | None = None,
    stream: bool = False,
    max_tokens: int = 6000,
) -> dict:
    system_parts: list[str] = []
    user_assistant: list[dict] = []
    for m in messages:
        if m.get("role") == "system":
            system_parts.append(str(m.get("content", "")))
        else:
            user_assistant.append(
                {
                    "role": m.get("role", "user"),
                    "content": str(m.get("content", "")),
                }
            )
    body: dict = {
        "model": model_id,
        "messages": user_assistant,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if stream:
        body["stream"] = True
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    return body


def _body_gemini(
    model_id: str,
    messages: list[dict],
    temperature: float,
    *,
    response_format: dict | None = None,
    stream: bool = False,
    max_tokens: int = 6000,
) -> dict:
    system_parts: list[str] = []
    contents: list[dict] = []
    for m in messages:
        if m.get("role") == "system":
            system_parts.append(str(m.get("content", "")))
        else:
            role = "model" if m.get("role") == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": str(m.get("content", ""))}],
                }
            )
    body: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_parts:
        body["systemInstruction"] = {
            "parts": [{"text": "\n\n".join(system_parts)}],
        }
    return body


def _body_custom_chat(
    model_id: str,
    messages: list[dict],
    temperature: float,
    *,
    response_format: dict | None = None,
    stream: bool = False,
    max_tokens: int = 6000,
) -> dict:
    return _body_openai_chat(
        model_id,
        messages,
        temperature,
        response_format=response_format,
        stream=stream,
        max_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# Headers builders
# ---------------------------------------------------------------------------


def _headers_openai(api_key: str) -> dict:
    """Build headers for OpenAI-compatible APIs. api_key must be plaintext (already decrypted)."""
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _headers_claude(api_key: str) -> dict:
    """Build headers for Claude Messages API. api_key must be plaintext (already decrypted)."""
    return {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }


def _headers_gemini(api_key: str) -> dict:
    """Build headers for Gemini API. api_key must be plaintext (already decrypted)."""
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }


# ---------------------------------------------------------------------------
# Response parsers — non-streaming
# ---------------------------------------------------------------------------


def _parse_openai_chat(resp_json: dict) -> tuple[str, dict]:
    message = ((resp_json.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    content = _extract_message_content(message)
    usage = resp_json.get("usage") or {}
    return content, usage


def _parse_openai_responses(resp_json: dict) -> tuple[str, dict]:
    output = resp_json.get("output") or []
    parts: list[str] = []
    for item in output:
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if c.get("type") == "output_text":
                    parts.append(c.get("text", ""))
    usage = resp_json.get("usage") or {}
    return "".join(parts), usage


def _parse_claude_messages(resp_json: dict) -> tuple[str, dict]:
    content_list = resp_json.get("content") or []
    parts: list[str] = []
    for c in content_list:
        if c.get("type") == "text":
            parts.append(c.get("text", ""))
    usage = resp_json.get("usage") or {}
    return "".join(parts), usage


def _parse_gemini(resp_json: dict) -> tuple[str, dict]:
    candidates = resp_json.get("candidates") or []
    parts: list[str] = []
    for cand in candidates:
        content = cand.get("content") or {}
        for p in content.get("parts") or []:
            if "text" in p:
                parts.append(p["text"])
    usage_meta = resp_json.get("usageMetadata") or {}
    usage = {
        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
        "total_tokens": usage_meta.get("totalTokenCount", 0),
    }
    return "".join(parts), usage


# ---------------------------------------------------------------------------
# Stream delta extractors
# ---------------------------------------------------------------------------


def _extract_openai_chat_delta(data: dict) -> str | None:
    choice = (data.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    content = delta.get("content")
    if content is None:
        content = (choice.get("message") or {}).get("content")
    if content is None:
        content = choice.get("text")
    return _extract_message_content(content) or None


def _extract_openai_responses_delta(data: dict) -> str | None:
    t = data.get("type", "")
    if "text.delta" in t or t == "response.output_text.delta":
        d = data.get("delta") or {}
        return d.get("text") or data.get("text")
    return None


def _extract_claude_delta(data: dict) -> str | None:
    t = data.get("type", "")
    if t == "content_block_delta":
        d = data.get("delta") or {}
        if d.get("type") == "text_delta":
            return d.get("text", "")
    return None


def _extract_gemini_delta(data: dict) -> str | None:
    candidates = data.get("candidates") or []
    for cand in candidates:
        content = cand.get("content") or {}
        for p in content.get("parts") or []:
            if "text" in p:
                return p["text"]
    return None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _extract_message_content(message: object) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif "content" in item:
                    parts.append(str(item.get("content") or ""))
        return "".join(parts)
    if isinstance(message, dict):
        if "text" in message:
            return str(message["text"])
        if "content" in message:
            return str(message["content"])
    return ""


# ---------------------------------------------------------------------------
# Image body builders
# ---------------------------------------------------------------------------


def _body_openai_images(model_id: str, prompt: str, size: str, watermark: bool) -> dict:
    return {
        "model": model_id,
        "prompt": prompt,
        "response_format": "url",
        "size": size.lower(),
        "watermark": watermark,
    }


# MiniMax image body (same as OpenAI format)
_body_minimax_images = _body_openai_images


# ---------------------------------------------------------------------------
# Image response parsers
# ---------------------------------------------------------------------------


def _parse_openai_image(data: dict) -> str:
    """OpenAI Images API: { data: [{ url: "..." }] }"""
    return data["data"][0]["url"]


def _parse_minimax_image(data: dict) -> str:
    """MiniMax Image API: { data: { image_urls: ["..."] } }"""
    return data["data"]["image_urls"][0]


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------


def get_adapter(api_mode: str) -> Adapter:
    adapters: dict[str, Adapter] = {
        "openai_chat_completions": {
            "url": _url_openai_chat,
            "body": _body_openai_chat,
            "headers": _headers_openai,
            "parser": _parse_openai_chat,
            "extractor": _extract_openai_chat_delta,
            "supports_response_format": True,
        },
        "openai_responses": {
            "url": _url_openai_responses,
            "body": _body_openai_responses,
            "headers": _headers_openai,
            "parser": _parse_openai_responses,
            "extractor": _extract_openai_responses_delta,
            "supports_response_format": True,
        },
        "claude_messages": {
            "url": _url_claude_messages,
            "body": _body_claude_messages,
            "headers": _headers_claude,
            "parser": _parse_claude_messages,
            "extractor": _extract_claude_delta,
            "supports_response_format": False,
        },
        "gemini_generate_content": {
            "url": _url_gemini,
            "body": _body_gemini,
            "headers": _headers_gemini,
            "parser": _parse_gemini,
            "extractor": _extract_gemini_delta,
            "supports_response_format": False,
        },
        "custom_chat": {
            "url": _url_custom_chat,
            "body": _body_custom_chat,
            "headers": _headers_openai,
            "parser": _parse_openai_chat,
            "extractor": _extract_openai_chat_delta,
            "supports_response_format": False,
        },
        "openai_images": {
            "url": _url_openai_images,
            "body": None,
            "headers": _headers_openai,
            "parser": None,
            "extractor": None,
            "supports_response_format": False,
            "image_body": _body_openai_images,
            "image_parser": _parse_openai_image,
        },
        "custom_image": {
            "url": _url_custom_image,
            "body": None,
            "headers": _headers_openai,
            "parser": None,
            "extractor": None,
            "supports_response_format": False,
            "image_body": _body_openai_images,
            "image_parser": _parse_openai_image,
        },
        "minimax_images": {
            "url": _url_custom_image,
            "body": None,
            "headers": _headers_openai,
            "parser": None,
            "extractor": None,
            "supports_response_format": False,
            "image_body": _body_minimax_images,
            "image_parser": _parse_minimax_image,
        },
        "comfyui": {
            "url": None,
            "body": None,
            "headers": None,
            "parser": None,
            "extractor": None,
            "supports_response_format": False,
            "image_body": None,
            "image_parser": None,
        },
    }
    ad = adapters.get(api_mode)
    if ad is None:
        ad = adapters["openai_chat_completions"]
    return ad
