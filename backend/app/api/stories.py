from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
import json

from ..database import get_db
from .. import models, schemas
from ..redis_client import get_redis
from .story_generate import generate_story_content, generate_story_with_cover
from .image_generation import generate_cover_image, generate_background_image
from ..crypto import decrypt

router = APIRouter(prefix="/api/stories", tags=["stories"])

STORIES_CACHE_KEY = "cache:stories:all"
STORIES_CACHE_TTL = 300  # 5 minutes
CHAR_CACHE_KEY = "cache:characters:{story_id}"


def _invalidate_stories_cache():
    redis = get_redis()
    redis.delete(STORIES_CACHE_KEY)


def _invalidate_char_cache(story_id: int):
    redis = get_redis()
    if redis.is_available():
        redis.delete(CHAR_CACHE_KEY.format(story_id=story_id))


@router.get("", response_model=List[schemas.StoryOut])
def list_stories(db: Session = Depends(get_db)):
    redis = get_redis()
    if redis.is_available():
        cached = redis.get(STORIES_CACHE_KEY)
        if cached:
            data = json.loads(cached)
            return data  # 直接返回缓存的 dict 列表，由 Pydantic 做验证转换

    stories = db.query(models.Story).order_by(models.Story.created_at.desc()).all()
    if redis.is_available() and stories:
        # Cache only lightweight fields needed for listing
        cache_data = [
            {
                "id": s.id,
                "title": s.title,
                "cover_image": s.cover_image,
                "background_image": s.background_image,
                "description": s.description,
                "tags": s.tags,
                "category": s.category,
                "world_setting": s.world_setting,
                "system_prompt": s.system_prompt,
                "state_config": s.state_config,
                "opening_requirement": s.opening_requirement,
                "image_style": s.image_style,
                "created_at": s.created_at.isoformat() if s.created_at else "",
            }
            for s in stories
        ]
        redis.set(STORIES_CACHE_KEY, json.dumps(cache_data, ensure_ascii=False), ttl=STORIES_CACHE_TTL)
    return stories


@router.get("/{story_id}", response_model=schemas.StoryOut)
def get_story(story_id: int, db: Session = Depends(get_db)):
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")
    return story


@router.post("", response_model=schemas.StoryOut)
def create_story(payload: schemas.StoryCreate, db: Session = Depends(get_db)):
    story = models.Story(**payload.model_dump())
    db.add(story)
    db.commit()
    db.refresh(story)
    _invalidate_stories_cache()
    return story


@router.put("/{story_id}", response_model=schemas.StoryOut)
def update_story(story_id: int, payload: schemas.StoryUpdate, db: Session = Depends(get_db)):
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(story, k, v)
    db.commit()
    db.refresh(story)
    _invalidate_stories_cache()
    return story


@router.delete("/{story_id}")
def delete_story(story_id: int, db: Session = Depends(get_db)):
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")
    db.delete(story)
    db.commit()
    _invalidate_stories_cache()
    return {"ok": True}


# ---- Characters ----
@router.get("/{story_id}/characters", response_model=List[schemas.CharacterOut])
def list_characters(story_id: int, db: Session = Depends(get_db)):
    return db.query(models.Character).filter(models.Character.story_id == story_id).all()


@router.post("/{story_id}/characters", response_model=schemas.CharacterOut)
def create_character(story_id: int, payload: schemas.CharacterBase, db: Session = Depends(get_db)):
    character = models.Character(story_id=story_id, **payload.model_dump())
    db.add(character)
    db.commit()
    db.refresh(character)
    _invalidate_char_cache(story_id)
    return character


@router.put("/characters/{character_id}", response_model=schemas.CharacterOut)
def update_character(character_id: int, payload: schemas.CharacterBase, db: Session = Depends(get_db)):
    c = db.query(models.Character).filter(models.Character.id == character_id).first()
    if not c:
        raise HTTPException(404, "角色不存在")
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    _invalidate_char_cache(c.story_id)
    return c


@router.delete("/characters/{character_id}")
def delete_character(character_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Character).filter(models.Character.id == character_id).first()
    if not c:
        raise HTTPException(404, "角色不存在")
    story_id = c.story_id
    db.delete(c)
    db.commit()
    _invalidate_char_cache(story_id)
    return {"ok": True}


@router.post("/ai-generate", response_model=schemas.StoryGenerateOut)
def ai_generate_story(
    payload: schemas.StoryGenerateIn,
    db: Session = Depends(get_db),
):
    # 1. 获取文字模型
    if payload.model_id is not None:
        text_model = db.query(models.ModelConfig).filter(
            models.ModelConfig.id == payload.model_id,
            models.ModelConfig.enabled == 1,
            models.ModelConfig.model_type == "chat",
        ).first()
        if not text_model:
            raise HTTPException(503, "指定的文字模型不可用，请检查模型配置")
    else:
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
            raise HTTPException(503, "没有可用的文字模型配置，请先在设置中添加模型")

    # 2. 获取 AppSettings 图片相关配置（size/watermark/style 仍从全局设置读取）
    app_settings = db.query(models.AppSettings).first()
    image_size = app_settings.image_size if app_settings else "2K"
    image_watermark = bool(app_settings and app_settings.image_watermark)

    # 3. 解析封面图模型
    cover_model_cfg = None
    if payload.generate_cover:
        cover_model_id = payload.cover_image_model_id or payload.image_model_id
        if cover_model_id:
            cover_model_cfg = db.query(models.ModelConfig).filter(
                models.ModelConfig.id == cover_model_id,
                models.ModelConfig.enabled == 1,
                models.ModelConfig.model_type == "image",
            ).first()
            if not cover_model_cfg:
                raise HTTPException(503, "指定的封面图片模型不可用")

    # 4. 解析背景图模型
    bg_model_cfg = None
    if payload.generate_background:
        bg_model_id = payload.background_image_model_id
        if bg_model_id:
            bg_model_cfg = db.query(models.ModelConfig).filter(
                models.ModelConfig.id == bg_model_id,
                models.ModelConfig.enabled == 1,
                models.ModelConfig.model_type == "image",
            ).first()
            if not bg_model_cfg:
                raise HTTPException(503, "指定的背景图片模型不可用")

    # 5. 生成故事内容（story_id=0 表示临时生成）
    try:
        result = generate_story_with_cover(
            text_model_cfg=text_model,
            image_model_cfg=cover_model_cfg,
            category=payload.category,
            title_hint=payload.title_hint,
            tags_hint=payload.tags_hint,
            enable_image=payload.generate_cover and cover_model_cfg is not None,
            image_size=image_size,
            image_watermark=image_watermark,
            story_id=0,
            user_image_style=payload.image_style or "",
            user_preference=payload.preference or "",
        )

        # 6. 生成背景图
        if payload.generate_background and bg_model_cfg is not None:
            try:
                bg_path = generate_background_image(
                    image_model_cfg=bg_model_cfg,
                    world_setting=result.world_setting,
                    title=result.title,
                    story_id=0,
                    size=image_size,
                    watermark=image_watermark,
                    style=result.image_style or "",
                )
                result.background_url = bg_path
            except Exception:  # noqa: BLE001
                result.background_url = ""

        return result
    except Exception as e:
        raise HTTPException(500, f"生成失败：{str(e)[:200]}")


@router.post("/ai-generate-cover", response_model=schemas.GenerateCoverOut)
def ai_generate_cover(
    payload: schemas.GenerateCoverIn,
    db: Session = Depends(get_db),
):
    """独立生成封面图，用于分阶段调用：先调 ai-generate 获取内容，再调此接口生成封面。"""
    app_settings = db.query(models.AppSettings).first()

    image_model_id = payload.image_model_id or (app_settings.default_image_model_id if app_settings else None)
    if not image_model_id:
        raise HTTPException(400, "未配置图片模型")

    image_model_cfg = db.query(models.ModelConfig).filter(
        models.ModelConfig.id == image_model_id,
        models.ModelConfig.enabled == 1,
        models.ModelConfig.model_type == "image",
    ).first()
    if not image_model_cfg:
        raise HTTPException(503, "指定的图片模型不可用")

    try:
        cover_url = generate_cover_image(
            image_model_cfg=image_model_cfg,
            world_setting=payload.world_setting,
            title=payload.title,
            story_id=0,
            size=app_settings.image_size or "2K",
            watermark=bool(app_settings.image_watermark),
            style=payload.image_style or "",
        )
        return schemas.GenerateCoverOut(cover_url=cover_url)
    except Exception as e:
        raise HTTPException(500, f"封面生成失败：{str(e)[:200]}")


@router.post("/{story_id}/regenerate-cover", response_model=schemas.StoryOut)
def regenerate_cover(
    story_id: int,
    db: Session = Depends(get_db),
):
    """
    重新生成故事封面图。
    读取 Story.image_style + world_setting，调用图片模型生成新封面。
    """
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")
    if not story.world_setting:
        raise HTTPException(400, "故事世界观为空，无法生成封面，请先完善故事内容")

    app_settings = db.query(models.AppSettings).first()

    image_model_cfg = None
    if app_settings.default_image_model_id:
        image_model_cfg = db.query(models.ModelConfig).filter(
            models.ModelConfig.id == app_settings.default_image_model_id,
            models.ModelConfig.enabled == 1,
            models.ModelConfig.model_type == "image",
        ).first()
    if not image_model_cfg:
        raise HTTPException(503, "没有可用的图片模型配置")

    try:
        from .image_generation import generate_cover_image
        new_cover_url = generate_cover_image(
            image_model_cfg=image_model_cfg,
            world_setting=story.world_setting,
            title=story.title,
            story_id=story_id,
            size=app_settings.image_size or "2K",
            watermark=bool(app_settings.image_watermark),
            style=story.image_style or "",
        )
        story.cover_image = new_cover_url
        db.commit()
        db.refresh(story)
        _invalidate_stories_cache()
        return story
    except Exception as e:
        raise HTTPException(500, f"封面生成失败：{str(e)[:200]}")


@router.post("/{story_id}/generate-cover")
def generate_cover_for_story(
    story_id: int,
    payload: schemas.GenerateCoverForStoryIn,
    db: Session = Depends(get_db),
):
    """独立封面生成：指定 image_model_id 为已有故事生成封面图。"""
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")

    image_model_cfg = db.query(models.ModelConfig).filter(
        models.ModelConfig.id == payload.image_model_id,
        models.ModelConfig.enabled == 1,
        models.ModelConfig.model_type == "image",
    ).first()
    if not image_model_cfg:
        raise HTTPException(503, "指定的图片模型不可用")

    app_settings = db.query(models.AppSettings).first()
    image_size = app_settings.image_size if app_settings else "2K"
    image_watermark = bool(app_settings and app_settings.image_watermark)
    style = story.image_style or (app_settings.default_image_style if app_settings else "")

    try:
        cover_path = generate_cover_image(
            image_model_cfg=image_model_cfg,
            world_setting=story.world_setting,
            title=story.title,
            story_id=story_id,
            size=image_size,
            watermark=image_watermark,
            style=style,
        )
        story.cover_image = cover_path
        db.commit()
        _invalidate_stories_cache()
        return {"cover_image": cover_path}
    except Exception as e:
        raise HTTPException(500, f"封面生成失败：{str(e)[:200]}")


@router.post("/{story_id}/generate-background")
def generate_background_for_story(
    story_id: int,
    payload: schemas.GenerateBackgroundForStoryIn,
    db: Session = Depends(get_db),
):
    """独立背景生成：指定 image_model_id 为已有故事生成背景图。"""
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")

    image_model_cfg = db.query(models.ModelConfig).filter(
        models.ModelConfig.id == payload.image_model_id,
        models.ModelConfig.enabled == 1,
        models.ModelConfig.model_type == "image",
    ).first()
    if not image_model_cfg:
        raise HTTPException(503, "指定的图片模型不可用")

    app_settings = db.query(models.AppSettings).first()
    image_size = app_settings.image_size if app_settings else "2K"
    image_watermark = bool(app_settings and app_settings.image_watermark)
    style = story.image_style or (app_settings.default_image_style if app_settings else "")

    try:
        bg_path = generate_background_image(
            image_model_cfg=image_model_cfg,
            world_setting=story.world_setting,
            title=story.title,
            story_id=story_id,
            size=image_size,
            watermark=image_watermark,
            style=style,
        )
        story.background_image = bg_path
        db.commit()
        _invalidate_stories_cache()
        return {"background_image": bg_path}
    except Exception as e:
        raise HTTPException(500, f"背景生成失败：{str(e)[:200]}")


@router.post("/{story_id}/upload-image")
def upload_image_for_story(
    story_id: int,
    purpose: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """图片上传：purpose 为 'cover' 或 'background'，保存文件并更新 Story 字段。"""
    if purpose not in ("cover", "background"):
        raise HTTPException(400, "purpose 必须为 'cover' 或 'background'")

    # Security: validate content type
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(400, "只允许上传图片文件")

    # Security: validate file extension
    ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
    ext = (file.filename or "image.png").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的图片格式：.{ext}")

    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")

    from .image_generation import STATIC_IMAGES_DIR
    import time

    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Security: read with size limit (10MB)
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片文件不能超过 10MB")

    filename = f"story_{story_id}_{purpose}_{int(time.time())}.{ext}"
    save_path = STATIC_IMAGES_DIR / filename
    save_path.write_bytes(data)

    field = "cover_image" if purpose == "cover" else "background_image"
    path = f"/api/images/{filename}"
    setattr(story, field, path)
    db.commit()
    _invalidate_stories_cache()
    return {"field": field, "path": path}
