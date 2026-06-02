from __future__ import annotations

from typing import Optional

from ..prompts.contracts import OPTIONS_FORBIDDEN_WORDS, OPTIONS_MIN_LENGTH, OPTIONS_MAX_LENGTH

class OptionsValidationError(Exception):
    pass

def validate_options_list(options: list[str]) -> tuple[bool, Optional[str]]:
    """
    五层校验，返回 (is_valid, error_message)
    """
    # Layer 1: 格式校验
    if not isinstance(options, list):
        return False, "options 必须是数组"
    if len(options) < 1:
        return False, "options 不能为空"

    # Layer 2-4: 合并校验（长度 + 禁止词 + 第一人称）
    forbidden = OPTIONS_FORBIDDEN_WORDS
    for opt in options:
        length = len(opt.strip())
        if length < OPTIONS_MIN_LENGTH or length > OPTIONS_MAX_LENGTH:
            return False, f"选项「{opt}」字数不足8字或超过25字"
        if any(fw in opt for fw in forbidden):
            return False, f"选项「{opt}」含模糊词"
        if opt.strip().startswith("我"):
            return False, f"选项「{opt}」以第一人称开头"

    return True, None