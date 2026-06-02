"""Re-export shim — body pollution detection moved to app.prompts.guard."""
from ..prompts.guard import (  # noqa: F401
    BodyPollutedError,
    _OPTION_BLOCK_CUE_RE,
    _OPTION_LINE_RE,
    _detect_body_pollution,
    _has_sentence_boundary,
    _is_likely_option_line,
    _is_trailing_bracket_line,
    _looks_like_trailing_option_block,
    _strip_trailing_bracket_line,
    detect_body_pollution,
)
