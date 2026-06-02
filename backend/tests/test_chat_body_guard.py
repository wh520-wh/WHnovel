"""Test body pollution detection."""
import pytest
from app.prompts.guard import (
    BodyPollutedError,
    _is_likely_option_line,
    _is_trailing_bracket_line,
    _looks_like_trailing_option_block,
    _strip_trailing_bracket_line,
    detect_body_pollution,
)


def test_detect_body_pollution_code_fence():
    """Code fence is detected as pollution."""
    result = detect_body_pollution("Here is the response: ```json", pre_delta=True)
    assert result == "code_fence"


def test_detect_body_pollution_structured_field():
    """Structured field in text is detected."""
    result = detect_body_pollution('{"reply_text": "hello"}', pre_delta=True)
    assert result == "structured_field"


def test_detect_body_pollution_schema_term():
    """Schema term is detected."""
    result = detect_body_pollution("response_format: json", pre_delta=True)
    assert result == "schema_term"


def test_detect_body_pollution_clean_text():
    """Normal text is not polluted."""
    result = detect_body_pollution("这是一段正常的小说文字。", pre_delta=True)
    assert result is None


def test_detect_body_pollution_pre_vs_post():
    """Pre-delta and post-delta have different patterns."""
    # json_prefix only in pre_delta
    result_pre = detect_body_pollution('{"hello": "world"}', pre_delta=True)
    result_post = detect_body_pollution('{"hello": "world"}', pre_delta=False)
    assert result_pre == "json_prefix"
    # post_delta doesn't have json_prefix pattern


def test_body_polluted_error_pre_delta():
    """BodyPollutedError stores pre_delta flag."""
    err = BodyPollutedError("test", pre_delta=True)
    assert err.pre_delta is True
    assert err.reason == "test"


def test_body_polluted_error_post_delta():
    """BodyPollutedError stores post_delta flag."""
    err = BodyPollutedError("test", pre_delta=False)
    assert err.pre_delta is False


def test_is_likely_option_line_valid():
    """Valid option lines are recognized."""
    assert _is_likely_option_line("1. 拿起武器")
    assert _is_likely_option_line("- 调查现场")
    assert _is_likely_option_line("直接走进房间")


def test_is_likely_option_line_invalid():
    """Invalid option lines are rejected."""
    assert not _is_likely_option_line("")
    assert not _is_likely_option_line("这是一段很长的描述性文字不符合选项格式")
    assert not _is_likely_option_line('{"json": "content"}')


def test_looks_like_trailing_option_block():
    """Trailing option blocks are detected."""
    text = "你必须立刻行动。\n\n1. 向左走\n2. 向右走"
    assert _looks_like_trailing_option_block(text)


def test_is_trailing_bracket_line_chinese_brackets():
    assert _is_trailing_bracket_line("（字数：728）")


def test_is_trailing_bracket_line_english_brackets():
    assert _is_trailing_bracket_line("(728字)")


def test_is_trailing_bracket_line_with_leading_space():
    assert _is_trailing_bracket_line("  （字数：728）")


def test_is_trailing_bracket_line_empty():
    assert not _is_trailing_bracket_line("")


def test_is_trailing_bracket_line_normal_text():
    assert not _is_trailing_bracket_line("她轻声说道。")


def test_is_trailing_bracket_line_inline_bracket():
    assert not _is_trailing_bracket_line("她轻声说道（微笑）。")


def test_strip_trailing_bracket_line_removes_last_line():
    text = "她走进了房间。\n（字数：728）"
    assert _strip_trailing_bracket_line(text) == "她走进了房间。"


def test_strip_trailing_bracket_line_english_brackets():
    text = "他转身离开。\n(728字)"
    assert _strip_trailing_bracket_line(text) == "他转身离开。"


def test_strip_trailing_bracket_line_no_bracket():
    text = "她走进了房间。\n他转身离开。"
    assert _strip_trailing_bracket_line(text) == text


def test_strip_trailing_bracket_line_inline_bracket_preserved():
    text = "她轻声说道（微笑）。"
    assert _strip_trailing_bracket_line(text) == text


def test_strip_trailing_bracket_line_bracket_with_blank_line():
    text = "她走进了房间。\n\n（字数：728）"
    # Regex matches the \n directly before bracket line, leaving one trailing \n
    assert _strip_trailing_bracket_line(text) == "她走进了房间。\n"


def test_strip_trailing_bracket_line_bracket_with_spaces():
    text = "他转身离开。\n  （字数：728）  "
    assert _strip_trailing_bracket_line(text) == "他转身离开。"
