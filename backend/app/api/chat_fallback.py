"""非结构化文本回退解析 —— 第三层防御"""
from __future__ import annotations

import re


def _fallback_parse_options(text: str) -> list[str]:
    """将 '1. xxx\n2. xxx\n3. xxx' 解析为 ['xxx', 'xxx', 'xxx']。

    当模型不支持 response_format 且不遵循 JSON 示例时，
    从纯文本编号列表中提取选项。
    """
    lines = re.findall(r"^\s*\d+\.\s*(.+)$", text, re.MULTILINE)
    return [l.strip() for l in lines if l.strip()]
