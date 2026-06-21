"""图片生成模块测试"""

from unittest.mock import MagicMock, patch

import pytest
from app.api.image_generation import _call_image_api, _download_and_save_image
from app.prompts.image_gen import _build_cover_prompt


class TestBuildCoverPrompt:
    def test_includes_title_and_world_setting(self):
        prompt = _build_cover_prompt("这是一个赛博朋克世界", "未来都市")
        assert "未来都市" in prompt
        assert "赛博朋克" in prompt

    def test_truncates_long_world_setting(self):
        long_ws = "世界设定。" * 300
        prompt = _build_cover_prompt(long_ws, "标题")
        assert len(prompt) < len(long_ws) * 2


class TestCallImageApi:
    @patch("app.api.image_generation.certifi.where", return_value=True)
    @patch("app.api.chat_api_adapter.get_adapter")
    @patch("app.api.image_generation.httpx.Client")
    def test_returns_url_from_data(self, mock_client_cls, mock_get_adapter, mock_certifi):
        mock_get_adapter.return_value = {
            "url": MagicMock(return_value="https://fake.api/v1/images/generations"),
            "headers": MagicMock(return_value={"Authorization": "Bearer test-key"}),
            "image_body": MagicMock(
                return_value={"model": "m", "prompt": "p", "size": "2k", "watermark": True}
            ),
            "image_parser": MagicMock(return_value="https://example.com/img.png"),
        }

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value.status_code = 200
        mock_instance.post.return_value.json.return_value = {
            "data": [{"url": "https://example.com/img.png"}]
        }
        mock_client_cls.return_value = mock_instance

        result = _call_image_api(
            api_key="test-key",
            api_base="https://ark.cn-beijing.volces.com",
            model="doubao-seedream-5-0-260128",
            prompt="test prompt",
        )
        assert result == "https://example.com/img.png"

    @patch("app.api.image_generation.certifi.where", return_value=True)
    @patch("app.api.chat_api_adapter.get_adapter")
    @patch("app.api.image_generation.httpx.Client")
    def test_raises_on_http_error(self, mock_client_cls, mock_get_adapter, mock_certifi):
        mock_get_adapter.return_value = {
            "url": MagicMock(return_value="https://fake.api/v1/images/generations"),
            "headers": MagicMock(return_value={"Authorization": "Bearer test-key"}),
            "image_body": MagicMock(
                return_value={"model": "m", "prompt": "p", "size": "2k", "watermark": True}
            ),
            "image_parser": MagicMock(),
        }

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value.status_code = 400
        mock_instance.post.return_value.text = "Bad Request"
        mock_client_cls.return_value = mock_instance

        with pytest.raises(RuntimeError, match="HTTP 400"):
            _call_image_api(api_key="key", api_base="https://base", model="model", prompt="prompt")

    @patch("app.api.image_generation.certifi.where", return_value=True)
    @patch("app.api.chat_api_adapter.get_adapter")
    @patch("app.api.image_generation.httpx.Client")
    def test_raises_on_missing_data(self, mock_client_cls, mock_get_adapter, mock_certifi):
        mock_get_adapter.return_value = {
            "url": MagicMock(return_value="https://fake.api/v1/images/generations"),
            "headers": MagicMock(return_value={"Authorization": "Bearer test-key"}),
            "image_body": MagicMock(
                return_value={"model": "m", "prompt": "p", "size": "2k", "watermark": True}
            ),
            "image_parser": MagicMock(side_effect=KeyError("url")),
        }

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value.status_code = 200
        mock_instance.post.return_value.json.return_value = {}
        mock_client_cls.return_value = mock_instance

        with pytest.raises(RuntimeError, match="response parse error"):
            _call_image_api(api_key="key", api_base="https://base", model="model", prompt="prompt")

    @patch("app.api.image_generation.certifi.where", return_value=True)
    @patch("app.api.chat_api_adapter.get_adapter")
    @patch("app.api.image_generation.httpx.Client")
    def test_raises_on_invalid_size(self, mock_client_cls, mock_get_adapter, mock_certifi):
        with pytest.raises(ValueError, match="Invalid image_size"):
            _call_image_api(
                api_key="key",
                api_base="https://base",
                model="model",
                prompt="prompt",
                size="4K",
            )

    @patch("app.api.image_generation.certifi.where", return_value=True)
    @patch("app.api.chat_api_adapter.get_adapter")
    @patch("app.api.image_generation.httpx.Client")
    def test_raises_on_missing_api_key(self, mock_client_cls, mock_get_adapter, mock_certifi):
        mock_get_adapter.return_value = {
            "url": MagicMock(return_value="https://fake.api/v1/images/generations"),
            "headers": MagicMock(return_value={"Authorization": "Bearer "}),
            "image_body": MagicMock(
                return_value={"model": "m", "prompt": "p", "size": "2k", "watermark": True}
            ),
            "image_parser": MagicMock(),
        }

        with pytest.raises(RuntimeError, match="未配置 API Key"):
            _call_image_api(api_key="", api_base="https://base", model="model", prompt="prompt")

    @patch("app.api.image_generation.certifi.where", return_value=True)
    @patch("app.api.chat_api_adapter.get_adapter")
    @patch("app.api.image_generation.httpx.Client")
    def test_drift_key_triggers_401_not_unconfigured(
        self, mock_client_cls, mock_get_adapter, mock_certifi
    ):
        """漂移修复后：非空（密文）key 不触发'未配置'短路，发请求得真 401。"""
        mock_get_adapter.return_value = {
            "url": MagicMock(return_value="https://fake.api/v1/images/generations"),
            "headers": MagicMock(return_value={"Authorization": "Bearer blob"}),
            "image_body": MagicMock(return_value={"model": "m", "prompt": "p", "size": "2k", "watermark": True}),
        }
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value.status_code = 401
        mock_instance.post.return_value.text = "unauthorized"
        mock_client_cls.return_value = mock_instance

        with pytest.raises(RuntimeError, match="Image API HTTP 401"):
            _call_image_api(
                api_key="non-empty-ciphertext-blob",
                api_base="https://fake.api",
                model="m",
                prompt="p",
            )

    @patch("app.api.image_generation.certifi.where", return_value=True)
    @patch("app.api.chat_api_adapter.get_adapter")
    @patch("app.api.image_generation.httpx.Client")
    def test_missing_api_key_still_reports_unconfigured(
        self, mock_client_cls, mock_get_adapter, mock_certifi
    ):
        """api_key='' 仍命中'未配置'短路（回归保护）。"""
        mock_get_adapter.return_value = {
            "url": MagicMock(return_value="https://fake.api/v1/images/generations"),
            "headers": MagicMock(return_value={}),
            "image_body": MagicMock(return_value={"model": "m", "prompt": "p", "size": "2k", "watermark": True}),
        }
        with pytest.raises(RuntimeError, match="未配置 API Key"):
            _call_image_api(api_key="", api_base="https://fake.api", model="m", prompt="p")


class TestSaveImageLocally:
    @patch("app.api.image_generation.httpx.Client")
    @patch("app.api.image_generation.STATIC_IMAGES_DIR")
    def test_returns_local_path(self, mock_static_dir, mock_client_cls):
        mock_static_dir.mkdir = MagicMock()
        mock_save_path = MagicMock()
        mock_save_path.write_bytes = MagicMock()
        mock_static_dir.__truediv__ = MagicMock(return_value=mock_save_path)

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.content = b"fake_image_bytes"
        mock_client_cls.return_value = mock_instance

        result = _download_and_save_image(
            "https://example.com/img.png", "story_42_cover_1234567890.png"
        )
        assert result.endswith("/api/images/story_42_cover_1234567890.png")


class TestBuildBackgroundPrompt:
    def test_includes_key_elements(self):
        from app.prompts.image_gen import _build_background_prompt

        result = _build_background_prompt(
            world_setting="一座古老的城堡矗立在悬崖之上",
            title="星辰与剑",
            style="水墨风格",
        )
        assert "背景" in result
        assert "无主体文字" in result
        assert "氛围感" in result
        assert "星辰与剑" in result

    def test_no_style(self):
        from app.prompts.image_gen import _build_background_prompt

        result = _build_background_prompt(
            world_setting="未来都市",
            title="机械之心",
        )
        assert "背景" in result
        assert "机械之心" in result
