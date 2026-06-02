"""Image generation prompt builders."""
from __future__ import annotations

_MAX_WORLD_SETTING_CHARS = 800


def _build_cover_prompt(world_setting: str, title: str, style: str = "") -> str:
    """
    从世界观、标题和风格描述构建封面图 prompt。
    参考豆包 seed 模型风格，输出中文场景描述。
    """
    style_section = f"画风要求：{style}" if style else "画风要求：唯美、氛围感强，适合作为小说封面"
    return (
        f"请为以下故事生成一张封面图。\n"
        f"标题：{title}\n"
        f"世界观：\n{world_setting[:_MAX_WORLD_SETTING_CHARS]}\n\n"
        f"{style_section}。\n"
        f"请直接描述画面，不要包含文字。"
    )


_BG_PROMPT_SUFFIX = (
    "\n重要要求：这是一张宽幅聊天背景图，无主体文字，"
    "不要包含任何文字、书名或标题，"
    "以氛围感和环境为主，适合作为阅读界面的背景。"
)


def _build_background_prompt(world_setting: str, title: str, style: str = "") -> str:
    base = _build_cover_prompt(world_setting, title, style)
    return base + _BG_PROMPT_SUFFIX
