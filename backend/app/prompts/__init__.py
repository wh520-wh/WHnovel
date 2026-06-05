"""AI prompt constants — organized by functional domain.

Version history:
  v1.0  2026-05-10  Initial consolidation from chat_prompts.py, ai_contracts.py,
                     chat_stream.py, chat_storage.py, chat_body_guard.py,
                     image_generation.py, app_settings_service.py, seed_data.py.
"""

from .chat_body import (
    JSON_RULE_PROMPT,
    STREAM_ERROR_STAGE_POST_DELTA,
    STREAM_ERROR_STAGE_PRE_DELTA,
    STREAM_ERROR_STAGE_TAIL_DELIMITER,
    STREAM_ERROR_STAGE_TAIL_JSON,
    STREAM_ERROR_STAGE_TAIL_SCHEMA,
    STREAM_ERROR_STAGE_UPSTREAM,
    STREAM_TAIL_DELIMITER,
    _escape_tail_delimiter,
    _make_tail_delimiter,
    _restore_tail_escape,
    make_stream_rule_prompt,
)
from .chat_tail import (
    _TAIL_META_PROMPT,
    TAIL_SYSTEM_PROMPT,
)
from .contracts import (
    _OPTIONS_RULE_PROMPT,
    _PRESET_OPENINGS_RULE_PROMPT,
    _STATE_BROADCAST_RULE_PROMPT,
    _STORY_GENERATE_RULE_PROMPT,
    OPTIONS_FORBIDDEN_WORDS,
    OPTIONS_MAX_LENGTH,
    OPTIONS_MIN_LENGTH,
)
from .defaults import (
    DEFAULT_STATE_BROADCAST_PROMPT,
    DEFAULT_SYSTEM_PROMPT_TEXT,
    infer_prompt_source,
)
from .guard import (
    _OPTION_BLOCK_CUE_RE,
    _OPTION_LINE_RE,
    BodyPollutedError,
    _detect_body_pollution,
    _has_sentence_boundary,
    _is_likely_option_line,
    _looks_like_trailing_option_block,
    detect_body_pollution,
)
from .image_gen import (
    _build_background_prompt,
    _build_cover_prompt,
)
from .narrative import (
    _STREAM_BODY_NARRATIVE_PROMPT,
    HUMANIZED_WRITING_RULES,
    STYLE_RULE_PROMPT,
    _build_length_prompt,
    _length_spec_for_style,
)
from .plot import (
    MAX_ROUNDS_WITHOUT_PLOT_LABEL,
    PLOT_LABEL_FORCED_PROMPT,
    PLOT_LABEL_RULES,
    PLOT_PROGRESS_RULE_PROMPT,
    PRESET_OPENINGS_PROMPT,
    STORY_STATE_RULES,
)
from .seed import SEED_STORY_SYSTEM_PROMPTS

__all__ = [
    "JSON_RULE_PROMPT",
    "STREAM_ERROR_STAGE_POST_DELTA",
    "STREAM_ERROR_STAGE_PRE_DELTA",
    "STREAM_ERROR_STAGE_TAIL_DELIMITER",
    "STREAM_ERROR_STAGE_TAIL_JSON",
    "STREAM_ERROR_STAGE_TAIL_SCHEMA",
    "STREAM_ERROR_STAGE_UPSTREAM",
    "STREAM_TAIL_DELIMITER",
    "_escape_tail_delimiter",
    "_make_tail_delimiter",
    "_restore_tail_escape",
    "make_stream_rule_prompt",
    "_TAIL_META_PROMPT",
    "TAIL_SYSTEM_PROMPT",
    "_OPTIONS_RULE_PROMPT",
    "_PRESET_OPENINGS_RULE_PROMPT",
    "_STATE_BROADCAST_RULE_PROMPT",
    "_STORY_GENERATE_RULE_PROMPT",
    "OPTIONS_FORBIDDEN_WORDS",
    "OPTIONS_MAX_LENGTH",
    "OPTIONS_MIN_LENGTH",
    "DEFAULT_STATE_BROADCAST_PROMPT",
    "DEFAULT_SYSTEM_PROMPT_TEXT",
    "infer_prompt_source",
    "_OPTION_BLOCK_CUE_RE",
    "_OPTION_LINE_RE",
    "BodyPollutedError",
    "_detect_body_pollution",
    "_has_sentence_boundary",
    "_is_likely_option_line",
    "_looks_like_trailing_option_block",
    "detect_body_pollution",
    "_build_background_prompt",
    "_build_cover_prompt",
    "_STREAM_BODY_NARRATIVE_PROMPT",
    "HUMANIZED_WRITING_RULES",
    "STYLE_RULE_PROMPT",
    "_build_length_prompt",
    "_length_spec_for_style",
    "MAX_ROUNDS_WITHOUT_PLOT_LABEL",
    "PLOT_LABEL_FORCED_PROMPT",
    "PLOT_LABEL_RULES",
    "PLOT_PROGRESS_RULE_PROMPT",
    "PRESET_OPENINGS_PROMPT",
    "STORY_STATE_RULES",
    "SEED_STORY_SYSTEM_PROMPTS",
]
