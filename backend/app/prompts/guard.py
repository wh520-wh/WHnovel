"""Body pollution detection — regex patterns and detection functions."""

from __future__ import annotations

import re

_OPTION_BLOCK_CUE_RE = re.compile(
    r"(?:你必须立刻行动|你必须行动|你需要立刻行动|你需要马上行动|接下来你|接下来该|下一步|请选择|你的选择|你可以选择|该怎么做|如何行动)",
    re.IGNORECASE,
)
_OPTION_LINE_RE = re.compile(
    r"^(?:[-*•]\s*|(?:\d+|[一二三四五六七八九十])[\.\、\)]\s*|(?:立刻|立即|迅速|尝试|低声|直接|先|继续|转身|上前|后退|躲开|躲入|躲到|绕到|冲向|搜索|寻找|调查|检查|观察|回应|追问|询问|触碰|触摸|翻找|读取|拿起|握紧|使用|施展|呼唤|伪装|潜入|靠近|远离|稳定|压低|逃离|扭曲|索取))"
)

_PRE_DELTA_POLLUTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("code_fence", re.compile(r"```", re.IGNORECASE)),
    (
        "structured_field",
        re.compile(
            r'"(?:reply_text|scene|options|character_state|story_state|memory_update|plot_label|highlight_terms|content|openings|title|world_setting)"\s*:',
            re.IGNORECASE,
        ),
    ),
    ("schema_term", re.compile(r"\b(?:response_format|json\s*schema)\b", re.IGNORECASE)),
    ("relay_term", re.compile(r"(系统提示|以下是输出|输出格式|用户输入|根据设定)")),
    ("json_prefix", re.compile(r"^\s*[\[{]\s*(?:\"|$)")),
]

_POST_DELTA_POLLUTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("code_fence", re.compile(r"```", re.IGNORECASE)),
    (
        "structured_field",
        re.compile(
            r'"(?:reply_text|scene|options|character_state|story_state|memory_update|plot_label|highlight_terms|content|openings|title|world_setting)"\s*:',
            re.IGNORECASE,
        ),
    ),
    ("schema_term", re.compile(r"\b(?:response_format|json\s*schema)\b", re.IGNORECASE)),
    ("relay_term", re.compile(r"(系统提示|以下是输出|输出格式|用户输入|根据设定)")),
]


class BodyPollutedError(ValueError):
    def __init__(self, reason: str, *, pre_delta: bool):
        super().__init__(reason)
        self.reason = reason
        self.pre_delta = pre_delta


def _has_sentence_boundary(text: str) -> bool:
    return bool(re.search(r"[。！？!?]\s*$", text)) or "\n" in text


def _is_likely_option_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) < 6 or len(stripped) > 40:
        return False
    if re.search(r"[`{}\[\]\"]", stripped):
        return False
    if re.search(r"[。！？!?；;：:]$", stripped):
        return False
    if stripped.startswith(("（", "(", "“", '"', "「")):
        return False
    return bool(_OPTION_LINE_RE.match(stripped))


def _looks_like_trailing_option_block(text: str) -> bool:
    lines = [line.rstrip() for line in text.splitlines()]
    end = len(lines) - 1
    while end >= 0 and not lines[end].strip():
        end -= 1
    if end < 1:
        return False

    start = end
    while start >= 0 and lines[start].strip():
        start -= 1

    block_lines = [line.strip() for line in lines[start + 1 : end + 1] if line.strip()]
    if len(block_lines) < 2 or len(block_lines) > 5:
        return False
    if not all(_is_likely_option_line(line) for line in block_lines):
        return False

    prev_non_empty = ""
    idx = start
    while idx >= 0:
        if lines[idx].strip():
            prev_non_empty = lines[idx].strip()
            break
        idx -= 1

    has_cue = bool(prev_non_empty and _OPTION_BLOCK_CUE_RE.search(prev_non_empty))
    has_blank_separator = start >= 0 and not lines[start].strip()
    if has_cue:
        return True
    return has_blank_separator and len(block_lines) >= 3


def detect_body_pollution(text: str, *, pre_delta: bool) -> str | None:
    """检测正文是否包含结构化内容污染。返回污染类型名称，或 None 表示干净。"""
    patterns = _PRE_DELTA_POLLUTION_PATTERNS if pre_delta else _POST_DELTA_POLLUTION_PATTERNS
    for name, pattern in patterns:
        if pattern.search(text):
            return name
    if _looks_like_trailing_option_block(text):
        return "option_block"
    return None


def _detect_body_pollution(text: str, *, pre_delta: bool) -> str | None:
    """Internal alias for backwards compatibility."""
    return detect_body_pollution(text, pre_delta=pre_delta)


_TRAILING_BRACKET_LINE_RE = re.compile(r"^[ \t]*[（\(].*[\）\)][ \t]*$")

_TRAILING_BRACKET_STRIP_RE = re.compile(r"\n[ \t]*[（\(].*[\）\)]\s*$")


def _is_trailing_bracket_line(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and bool(_TRAILING_BRACKET_LINE_RE.match(stripped))


def _strip_trailing_bracket_line(text: str) -> str:
    m = _TRAILING_BRACKET_STRIP_RE.search(text)
    if m:
        return text[: m.start()]
    return text
