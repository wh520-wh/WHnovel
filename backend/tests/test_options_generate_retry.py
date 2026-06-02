"""Test that options generation retry returns the retry result, not the first failed result.

Regression test for the bug where the endpoint returned validated.options
(the failed first attempt) instead of validated_retry.options (the successful retry).
"""
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from app.api import chat_router
from app import schemas


@contextmanager
def _fake_lock(archive_id):
    """Stub lock that always acquires immediately."""
    yield


def test_options_generate_retry_returns_retry_result():
    """When the first AI call produces invalid options but the retry succeeds,
    the endpoint must return the RETRY options, not the first-attempt options."""
    first_options = ["还是先看看再说吧", "随便走走看看吧", "想想再决定吧"]  # invalid: forbidden words
    retry_options = ["深入遗迹内部进行全面探索", "向同伴仔细询问关键线索详情", "冷静分析当前局势的具体情况"]  # valid

    first_result = MagicMock()
    first_result.options = first_options

    retry_result = MagicMock()
    retry_result.options = retry_options

    payload = schemas.OptionsGenerateIn(archive_id=1, count=3, guidance="")

    db = MagicMock()
    archive_mock = MagicMock()
    archive_mock.id = 1
    archive_mock.story = MagicMock()
    archive_mock.story.world_setting = "测试世界观"
    archive_mock.story.image_style = ""

    db.query.return_value.filter.return_value.first.return_value = archive_mock

    with patch.object(chat_router, "_acquire_option_generation_lock", _fake_lock), \
         patch.object(chat_router, "_get_or_create_settings") as mock_settings, \
         patch.object(chat_router, "_build_messages", return_value=[{"role": "user", "content": "test"}]), \
         patch.object(chat_router, "_get_normal_model_candidates", return_value=[MagicMock()]), \
         patch.object(chat_router, "_get_temperature", return_value=0.7), \
         patch.object(chat_router, "_call_ai_with_failover", side_effect=[first_result, retry_result]), \
         patch.object(chat_router, "validate_options_list", side_effect=[(False, "选项含模糊词"), (True, None)]):

        mock_settings.return_value.options_prompt = ""

        result = chat_router.generate_options(payload, db)

    # The endpoint must return retry_options, NOT first_options
    assert result.options == retry_options, (
        f"Expected retry options {retry_options}, got {result.options}"
    )


def test_options_generate_no_retry_when_valid():
    """When the first AI call already produces valid options, no retry happens."""
    valid_options = ["深入遗迹内部进行全面探索", "向同伴仔细询问关键线索详情", "冷静分析当前局势的具体情况"]

    first_result = MagicMock()
    first_result.options = valid_options

    payload = schemas.OptionsGenerateIn(archive_id=1, count=3, guidance="")

    db = MagicMock()
    archive_mock = MagicMock()
    archive_mock.id = 1
    archive_mock.story = MagicMock()
    archive_mock.story.world_setting = "测试世界观"
    archive_mock.story.image_style = ""

    db.query.return_value.filter.return_value.first.return_value = archive_mock

    with patch.object(chat_router, "_acquire_option_generation_lock", _fake_lock), \
         patch.object(chat_router, "_get_or_create_settings") as mock_settings, \
         patch.object(chat_router, "_build_messages", return_value=[{"role": "user", "content": "test"}]), \
         patch.object(chat_router, "_get_normal_model_candidates", return_value=[MagicMock()]), \
         patch.object(chat_router, "_get_temperature", return_value=0.7), \
         patch.object(chat_router, "_call_ai_with_failover", return_value=first_result) as mock_ai, \
         patch.object(chat_router, "validate_options_list", return_value=(True, None)):

        mock_settings.return_value.options_prompt = ""

        result = chat_router.generate_options(payload, db)

    assert result.options == valid_options
    # _call_ai_with_failover should only be called once (no retry)
    assert mock_ai.call_count == 1
