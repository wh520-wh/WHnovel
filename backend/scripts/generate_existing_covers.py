"""
为所有没有封面图的故事批量生成封面。
用法: cd backend && python scripts/generate_existing_covers.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import models
from app.api.story_generate import generate_story_with_cover
from app.app_settings_service import ensure_app_settings
from app.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    app_settings = ensure_app_settings(db)

    image_model_id = app_settings.default_image_model_id
    if not image_model_id:
        logger.error("未配置默认图片模型")
        db.close()
        return

    image_model = (
        db.query(models.ModelConfig)
        .filter(
            models.ModelConfig.id == image_model_id,
            models.ModelConfig.enabled == 1,
            models.ModelConfig.model_type == "image",
        )
        .first()
    )
    if not image_model:
        logger.error(f"图片模型 #{image_model_id} 不可用")
        db.close()
        return

    text_model = (
        db.query(models.ModelConfig)
        .filter(
            models.ModelConfig.enabled == 1,
            models.ModelConfig.model_type == "chat",
        )
        .order_by(models.ModelConfig.priority.asc())
        .first()
    )
    if not text_model:
        logger.error("没有可用的文字模型")
        db.close()
        return

    stories = (
        db.query(models.Story)
        .filter(
            models.Story.cover_image == "",
        )
        .all()
    )

    logger.info(f"共 {len(stories)} 个故事需要生成封面")

    success = 0
    failed = 0
    for story in stories:
        try:
            result = generate_story_with_cover(
                text_model_cfg=text_model,
                image_model_cfg=image_model,
                category=story.category or "其他",
                title_hint=story.title,
                tags_hint=",".join(story.tags or []),
                enable_image=True,
                image_size=app_settings.image_size or "2K",
                image_watermark=bool(app_settings.image_watermark),
                story_id=story.id,
            )
            if result.cover_url:
                story.cover_image = result.cover_url
                db.commit()
                success += 1
                logger.info(f"[{success+failed}] {story.title}: {result.cover_url}")
            else:
                failed += 1
                logger.warning(f"[{success+failed}] {story.title}: 未生成封面")
        except Exception as e:
            failed += 1
            logger.error(f"[{success+failed}] {story.title} 失败: {e}")

    logger.info(f"完成：成功 {success}，失败 {failed}")
    db.close()


if __name__ == "__main__":
    main()
