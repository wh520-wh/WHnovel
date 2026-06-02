"""Default system prompts and prompt source helpers."""
from __future__ import annotations

from pathlib import Path


def _read_text_or_default(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return default


DEFAULT_SYSTEM_PROMPT_TEXT = "你是互动小说AI，请严格遵循结构化输出规则生成内容。"

DEFAULT_STATE_BROADCAST_PROMPT = """请根据当前小说世界观和上下文，生成角色/剧情状态的键值对列表。

要求：
- 根据小说设定和当前剧情上下文自行判断应展示哪些属性，不要使用固定字段列表
- 至少生成 5-8 个属性（不少于 5 个），尽量丰富
- 属性类别参考（不限于这些）：角色状态（生命值/精神值/体力等）、场景环境、章节进度、当前目标、装备物品、同伴关系、时间天气、特殊效果等
- 每行一个属性，格式为：属性名 | 属性值
- 空值显示"无"，不省略
- 只输出键值对，不要任何解释或描述

示例（仅供参考，实际字段由AI根据上下文自行判断）：
地点 | 废弃神社后院
时间 | 子夜
情绪 | 警觉中带着不安

仅输出键值对，不要任何解释或描写。"""


def infer_prompt_source(default_system_prompt: str) -> str:
    prompt = (default_system_prompt or "").strip()
    if not prompt:
        return "empty"
    if prompt == DEFAULT_SYSTEM_PROMPT_TEXT:
        return "example_default"
    return "custom"
