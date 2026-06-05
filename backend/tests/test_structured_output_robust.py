import copy
import inspect
from unittest.mock import MagicMock, patch

import pytest
from app.api import chat_models
from app.api.ai_contracts import (
    TASK_CHAT_RESPONSE,
    TASK_OPTIONS_GENERATE,
    TASK_PRESET_OPENINGS,
    TASK_STATE_BROADCAST,
    TASK_STORY_GENERATE,
    build_contract_response_format,
    validate_and_convert_contract,
    validate_contract_payload,
)
from app.api.chat_fallback import _fallback_parse_options
from app.models import ModelConfig
from pydantic import ValidationError


def test_response_format_sent_for_all_openai_models():
    source = inspect.getsource(chat_models._call_model_once)
    assert "if _is_deepseek_model" not in source
    assert "response_format" in source
    assert "response_format_chain" not in source


def test_is_deepseek_model_removed():
    assert not hasattr(chat_models, "_is_deepseek_model")


def _fake_config():
    return ModelConfig(
        id=999,
        name="test-model",
        model_id="test-model-id",
        api_base_url="https://example.com/v1",
        api_key="fake-encrypted-key",
        enabled=1,
        priority=1,
        ssl_verify=True,
        response_format_mode="json_schema",
    )


def test_default_call_uses_json_object_response_format():
    fake_config = _fake_config()
    captured_body = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [{"message": {"content": '{"test":"ok"}'}}],
                "usage": {},
            }

    def mock_post(self, url, json=None, headers=None):
        captured_body["body"] = json
        return FakeResponse()

    with (
        patch("app.api.chat_models.decrypt", return_value="fake-decrypted-key"),
        patch("httpx.Client.post", mock_post),
    ):
        chat_models._call_model_once(fake_config, [{"role": "user", "content": "test"}], 0.7)

    assert captured_body["body"]["response_format"] == {"type": "json_object"}


def test_contract_call_uses_strict_json_schema_response_format():
    fake_config = _fake_config()
    captured_body = {}
    response_format = build_contract_response_format(TASK_OPTIONS_GENERATE)

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {"message": {"content": '{"options":["继续调查","后退观察","尝试交流"]}'}}
                ],
                "usage": {},
            }

    def mock_post(self, url, json=None, headers=None):
        captured_body["body"] = json
        return FakeResponse()

    with (
        patch("app.api.chat_models.decrypt", return_value="fake-decrypted-key"),
        patch("httpx.Client.post", mock_post),
    ):
        chat_models._call_model_once(
            fake_config,
            [{"role": "user", "content": "test"}],
            0.7,
            response_format=response_format,
        )

    sent_format = captured_body["body"]["response_format"]
    assert sent_format["type"] == "json_schema"
    assert sent_format["json_schema"]["strict"] is True
    assert sent_format["json_schema"]["name"] == "options_generate"


def test_call_model_once_retries_same_format_on_400():
    fake_config = _fake_config()
    captured_bodies = []
    call_count = {"n": 0}
    response_format = build_contract_response_format(TASK_CHAT_RESPONSE)

    def mock_post(self, url, json=None, headers=None):
        call_count["n"] += 1
        captured_bodies.append(copy.deepcopy(json))

        if call_count["n"] < 2:
            resp = MagicMock()
            resp.status_code = 400
            resp.text = '{"error": {"type": "invalid_request_error", "message": "bad format"}}'
            return resp

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"reply_text":"ok","scene":"","character_state":{},"story_state":{},"memory_update":[],"plot_label":"","highlight_terms":[]}'
                    }
                }
            ],
            "usage": {},
        }
        return resp

    with (
        patch("app.api.chat_models.decrypt", return_value="fake-decrypted-key"),
        patch("httpx.Client.post", mock_post),
    ):
        chat_models._call_model_once(
            fake_config,
            [{"role": "user", "content": "test"}],
            0.7,
            response_format=response_format,
        )

    assert call_count["n"] == 2
    assert captured_bodies[0]["response_format"]["type"] == "json_schema"
    assert captured_bodies[1]["response_format"]["type"] == "json_schema"


def test_call_model_once_no_cross_format_fallback():
    fake_config = _fake_config()
    call_count = {"n": 0}
    response_format = build_contract_response_format(TASK_CHAT_RESPONSE)

    def mock_post(self, url, json=None, headers=None):
        call_count["n"] += 1
        resp = MagicMock()
        resp.status_code = 400
        resp.text = '{"error": {"type": "invalid_request_error", "message": "bad format"}}'
        return resp

    with (
        patch("app.api.chat_models.decrypt", return_value="fake-decrypted-key"),
        patch("httpx.Client.post", mock_post),
        pytest.raises(RuntimeError, match="HTTP 400"),
    ):
        chat_models._call_model_once(
            fake_config,
            [{"role": "user", "content": "test"}],
            0.7,
            response_format=response_format,
        )

    assert call_count["n"] == 2


def test_call_model_once_json_object_mode_uses_json_object():
    fake_config = _fake_config()
    fake_config.response_format_mode = "json_object"
    captured_body = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [{"message": {"content": '{"test":"ok"}'}}],
                "usage": {},
            }

    def mock_post(self, url, json=None, headers=None):
        captured_body["body"] = json
        return FakeResponse()

    with (
        patch("app.api.chat_models.decrypt", return_value="fake-decrypted-key"),
        patch("httpx.Client.post", mock_post),
    ):
        chat_models._call_model_once(
            fake_config,
            [{"role": "user", "content": "test"}],
            0.7,
            response_format=build_contract_response_format(TASK_CHAT_RESPONSE),
        )

    assert captured_body["body"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1. 打开抽屉\n2. 走向门口\n3. 检查墙面", ["打开抽屉", "走向门口", "检查墙面"]),
        ("1.  开门\n  2. 关门 \n 3.  等待", ["开门", "关门", "等待"]),
        ("纯文本无编号", []),
        ("你走进房间\n1. 开门\n2. 关门\n一些描述", ["开门", "关门"]),
        ("", []),
    ],
)
def test_fallback_parse_options(text, expected):
    assert _fallback_parse_options(text) == expected


def test_extract_json_payload_fallback_to_numbered_list():
    result = chat_models._extract_json_payload(
        "你走进大厅\n1. 观察四周\n2. 往前走\n3. 回头看看",
        fallback_options=True,
    )
    assert result == {"options": ["观察四周", "往前走", "回头看看"]}


def test_extract_json_payload_fallback_disabled_raises():
    with pytest.raises(ValueError, match="未找到可解析的 JSON 对象"):
        chat_models._extract_json_payload(
            "你走进大厅\n1. 观察四周\n2. 往前走\n3. 回头看看",
            fallback_options=False,
        )


def test_extract_json_payload_fallback_empty_raises():
    with pytest.raises(ValueError, match="未找到可解析的 JSON 对象"):
        chat_models._extract_json_payload("纯文本无编号内容", fallback_options=True)


def test_options_contract_allows_legacy_numbered_list_text():
    validated = chat_models._validate_contract_from_text(
        TASK_OPTIONS_GENERATE,
        "1. 继续调查\n2. 暂时后退\n3. 尝试交涉",
    )
    assert validated.options == ["继续调查", "暂时后退", "尝试交涉"]


def test_chat_contract_invalid_plot_label_is_dropped_and_highlight_terms_default_empty():
    validated = validate_and_convert_contract(
        TASK_CHAT_RESPONSE,
        {
            "reply_text": "测试回复",
            "scene": "测试场景",
            "character_state": {"emotion": "平静", "fatigue": 10, "mood": "稳"},
            "story_state": {
                "chapter": "第一章",
                "progress": 10,
                "current_goal": "",
                "current_conflict": "",
            },
            "memory_update": [],
            "plot_label": '{"bad": true}',
        },
    )
    assert validated.plot_label is None
    assert validated.highlight_terms == []


def test_story_generate_contract_forbids_extra_fields():
    with pytest.raises(ValidationError):
        validate_contract_payload(
            TASK_STORY_GENERATE,
            {
                "title": "标题",
                "category": "悬疑",
                "tags": ["调查"],
                "cover_url": "",
                "description": "简介",
                "world_setting": "世界观",
                "image_style": "厚涂",
                "extra_field": "not allowed",
            },
        )


def test_preset_openings_contract_requires_exactly_five_items():
    with pytest.raises(ValidationError):
        validate_contract_payload(
            TASK_PRESET_OPENINGS,
            {
                "openings": [
                    {"label": "开场1", "value": "描述1"},
                    {"label": "开场2", "value": "描述2"},
                    {"label": "开场3", "value": "描述3"},
                    {"label": "开场4", "value": "描述4"},
                ]
            },
        )


# ---------------------------------------------------------------------------
# _coerce_flat_kv_to_content tests
# ---------------------------------------------------------------------------


def test_coerce_flat_kv_to_content_converts_flat_dict():
    result = chat_models._coerce_flat_kv_to_content({"姓名": "林逸", "地点": "教学楼"})
    assert result == {"content": "姓名 | 林逸\n地点 | 教学楼"}


def test_coerce_flat_kv_to_content_passes_through_content_key():
    payload = {"content": "already wrapped"}
    result = chat_models._coerce_flat_kv_to_content(payload)
    assert result is payload


def test_coerce_flat_kv_to_content_skips_nested_dict():
    payload = {"items": ["a", "b"]}
    result = chat_models._coerce_flat_kv_to_content(payload)
    assert result == {"items": ["a", "b"]}


def test_coerce_flat_kv_to_content_empty_dict():
    result = chat_models._coerce_flat_kv_to_content({})
    assert result == {}


def test_state_broadcast_coercion_integrated():
    """Flat KV dict that would fail StateBroadcastContract gets auto-coerced."""
    validated = chat_models._validate_contract_from_text(
        TASK_STATE_BROADCAST,
        '{"姓名": "林逸", "状态": "受伤"}',
    )
    assert validated.content == "姓名 | 林逸\n状态 | 受伤"


def test_state_broadcast_well_formed_passes_through():
    """Well-formed {"content": "..."} should work without modification."""
    validated = chat_models._validate_contract_from_text(
        TASK_STATE_BROADCAST,
        '{"content": "姓名 | 林逸\\n状态 | 受伤"}',
    )
    assert "林逸" in validated.content
