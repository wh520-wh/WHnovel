"""
为所有没有 image_style 的故事批量生成图片风格描述。
用法: cd backend && python scripts/batch_generate_image_styles.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import models
from app.api.story_generate import generate_story_content
from app.app_settings_service import ensure_app_settings
from app.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    ensure_app_settings(db)  # side effect: ensure settings row exists

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

    # 查找所有 image_style 为空的故事
    stories = (
        db.query(models.Story)
        .filter(
            models.Story.image_style == "",
        )
        .all()
    )

    logger.info(f"共 {len(stories)} 个故事需要生成图片风格")

    success = 0
    failed = 0
    for story in stories:
        try:
            result = generate_story_content(
                model_cfg=text_model,
                category=story.category or "其他",
                title_hint=story.title,
                tags_hint=",".join(story.tags or []),
                user_image_style="",  # 空字符串，AI 完全自主生成
            )
            image_style = result.image_style.strip() if result.image_style else ""
            if image_style:
                story.image_style = image_style
                db.commit()
                success += 1
                logger.info(f"[{success+failed}] {story.title}: {image_style}")
            else:
                failed += 1
                logger.warning(f"[{success+failed}] {story.title}: AI 未产出风格描述")
        except Exception as e:
            failed += 1
            logger.error(f"[{success+failed}] {story.title} 失败: {e}")

    logger.info(f"完成：成功 {success}，失败 {failed}")
    db.close()


if __name__ == "__main__":
    main()
