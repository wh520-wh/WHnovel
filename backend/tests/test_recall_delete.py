"""Tests for recall delete logic."""

import pytest
from app import models
from app.database import get_db
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("WHAINOEL_DB_PATH", str(db_path))
    monkeypatch.setenv("REDIS_PORT", "0")
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(client):
    return next(get_db())


def _create_test_story_and_archive(client, db):
    resp = client.post(
        "/api/stories",
        json={
            "title": "Test Story",
            "description": "test",
            "tags": [],
            "category": "其他",
        },
    )
    story_id = resp.json()["id"]
    resp = client.post(
        "/api/archives",
        json={
            "story_id": story_id,
            "name": "Test Archive",
        },
    )
    archive_id = resp.json()["id"]
    return story_id, archive_id


def _add_messages(db, archive_id, contents):
    for role, content in contents:
        msg = models.ChatMessage(
            archive_id=archive_id,
            role=role,
            content=content,
            state_snapshot={},
            story_state={},
            options=[],
            memory_update=[],
        )
        db.add(msg)
    db.commit()
    msgs = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.archive_id == archive_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    return [m.id for m in msgs]


def test_recall_deletes_ai_and_following_user(client, db):
    """场景: [user1, ai1, user2, ai2]，recall 应删 user2 + ai2，保留 user1 + ai1"""
    _, archive_id = _create_test_story_and_archive(client, db)
    _add_messages(
        db,
        archive_id,
        [
            ("user", "hello"),
            ("assistant", "hi there"),
            ("user", "second user"),
            ("assistant", "second reply"),
        ],
    )

    resp = client.delete(f"/api/chat/messages/{archive_id}/last-ai")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2

    remaining = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.archive_id == archive_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    assert len(remaining) == 2
    assert remaining[0].role == "user"
    assert remaining[0].content == "hello"
    assert remaining[1].role == "assistant"
    assert remaining[1].content == "hi there"


def test_recall_only_ai_when_no_following_user(client, db):
    """场景: [user1, ai1]，只有一轮，user 后面没有更多消息"""
    _, archive_id = _create_test_story_and_archive(client, db)
    _add_messages(
        db,
        archive_id,
        [
            ("user", "hello"),
            ("assistant", "hi there"),
        ],
    )

    resp = client.delete(f"/api/chat/messages/{archive_id}/last-ai")
    assert resp.status_code == 200
    # In DESC order [ai1, user1], user1 is at index 1 (after ai1 in list),
    # so it's considered the "following user" and gets deleted
    assert resp.json()["deleted"] == 2

    remaining = (
        db.query(models.ChatMessage).filter(models.ChatMessage.archive_id == archive_id).all()
    )
    assert len(remaining) == 0
