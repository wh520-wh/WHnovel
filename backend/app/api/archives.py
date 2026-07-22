from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .chat_storage import _init_state_from_story

router = APIRouter(prefix="/api/archives", tags=["archives"])


@router.get("/by_story/{story_id}", response_model=list[schemas.ArchiveOut])
def list_archives(story_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Archive)
        .filter(models.Archive.story_id == story_id)
        .order_by(models.Archive.updated_at.desc())
        .all()
    )


@router.post("", response_model=schemas.ArchiveOut)
def create_archive(payload: schemas.ArchiveCreate, db: Session = Depends(get_db)):
    story = db.query(models.Story).filter(models.Story.id == payload.story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在")

    # 初始化状态：如果没有传入 state_data，用 story.state_config 的默认值
    state_data = payload.state_data
    if not state_data:
        state_data = _init_state_from_story(story)

    story_state = payload.story_state or {"chapter": "第一章", "progress": 0}
    memory_log = payload.memory_log or []

    archive = models.Archive(
        story_id=payload.story_id,
        name=payload.name,
        state_data=state_data,
        story_state=story_state,
        memory_log=memory_log,
    )
    db.add(archive)
    db.commit()
    db.refresh(archive)
    return archive


@router.get("/{archive_id}", response_model=schemas.ArchiveOut)
def get_archive(archive_id: int, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(404, "存档不存在")
    return archive


@router.delete("/{archive_id}")
def delete_archive(archive_id: int, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(404, "存档不存在")
    db.delete(archive)
    db.commit()
    return {"ok": True}


@router.put("/{archive_id}/rename")
def rename_archive(archive_id: int, name: str, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(404, "存档不存在")
    archive.name = name
    db.commit()
    return {"ok": True}


@router.get("/{archive_id}/export")
def export_archive(
    archive_id: int,
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    archive = db.query(models.Archive).filter(models.Archive.id == archive_id).first()
    if not archive:
        raise HTTPException(404, "存档不存在")

    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.archive_id == archive_id)
        .order_by(models.ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return {
        "archive": {
            "id": archive.id,
            "story_id": archive.story_id,
            "name": archive.name,
            "state_data": archive.state_data,
            "story_state": archive.story_state,
            "memory_log": archive.memory_log,
            "first_message": archive.first_message,
            "created_at": archive.created_at.isoformat() if archive.created_at else "",
            "updated_at": archive.updated_at.isoformat() if archive.updated_at else "",
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in messages
        ],
    }


@router.post("/import")
def import_archive(payload: dict, db: Session = Depends(get_db)):
    archive_data = payload.get("archive")
    messages_data = payload.get("messages", [])
    # Bug #49：导入 payload 原为裸 dict 无校验，messages 非 list / 项非 dict / story_id 非整数
    # 时直接 500。加类型校验返 400 明确提示，合法导入行为不变。
    if not isinstance(archive_data, dict):
        raise HTTPException(400, "缺少 archive 字段或格式错误")
    if not isinstance(messages_data, list):
        raise HTTPException(400, "messages 字段必须为列表")
    story_id = archive_data.get("story_id")
    if not isinstance(story_id, int):
        raise HTTPException(400, "archive.story_id 必须为整数")
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(404, "故事不存在，无法导入存档")

    archive = models.Archive(
        story_id=story_id,
        name=archive_data.get("name", "导入存档"),
        state_data=archive_data.get("state_data", {}),
        story_state=archive_data.get("story_state", {"chapter": "第一章", "progress": 0}),
        memory_log=archive_data.get("memory_log", []),
        first_message=archive_data.get("first_message", ""),
    )
    db.add(archive)
    db.flush()

    for msg_data in messages_data:
        if not isinstance(msg_data, dict):
            raise HTTPException(400, "messages 中存在非对象项")
        msg = models.ChatMessage(
            archive_id=archive.id,
            role=msg_data.get("role", "user"),
            content=msg_data.get("content", ""),
            state_snapshot=archive_data.get("state_data", {}),
            story_state=archive_data.get("story_state", {}),
            options=[],
            memory_update=[],
        )
        db.add(msg)

    db.commit()
    return {"id": archive.id}
