"""Tests for chat_router image generation error handling."""

from unittest.mock import MagicMock, patch

import pytest
from app import schemas
from app.api import chat_router
from fastapi import HTTPException


def test_generate_chat_image_generic_error_on_failure():
    """generate_chat_image 抛异常时，返回给客户端的消息不应包含原始异常详情。

    策略：直接 patch endpoint 内部依赖的函数，跳过 db.query 链路，
    只测 error-handling 路径（generate_chat_image → except → HTTPException）。
    """
    payload = schemas.GenerateImageIn(archive_id=1, size="2K", watermark=False)

    with (
        patch.object(chat_router, "_get_or_create_app_settings") as mock_app,
        patch.object(chat_router, "_get_or_create_settings") as mock_settings,
        patch.object(chat_router, "_get_normal_model_candidates") as mock_candidates,
        patch.object(chat_router, "_build_messages", return_value=[]),
        patch.object(chat_router, "_call_text_model_once", return_value=("prompt", "")),
        patch.object(
            chat_router, "generate_chat_image", side_effect=RuntimeError("secret_internal_detail")
        ),
    ):
        mock_app.return_value.enable_image_generation = True
        mock_app.return_value.default_image_model_id = 1
        mock_app.return_value.default_image_style = ""

        image_model_cfg = MagicMock()
        image_model_cfg.enabled = True
        image_model_cfg.model_type = "image"

        db = MagicMock()
        archive_mock = MagicMock()
        archive_mock.story = MagicMock()
        archive_mock.story.world_setting = ""
        archive_mock.story.image_style = ""

        db.query.return_value.filter.return_value.first.side_effect = [
            archive_mock,
            image_model_cfg,
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        mock_settings.return_value.reply_style = "concise"
        mock_candidates.return_value = [MagicMock()]

        with pytest.raises(HTTPException) as exc_info:
            chat_router.generate_chat_image_endpoint(payload, db)

    assert exc_info.value.status_code == 500
    assert "secret_internal_detail" not in str(exc_info.value.detail)
    assert "请稍后重试" in str(exc_info.value.detail)
