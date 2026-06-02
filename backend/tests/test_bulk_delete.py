"""Tests for bulk message deletion endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import models
from app.database import get_db


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
    """Create a story and archive for testing."""
    resp = client.post("/api/stories", json={
        "title": "Test Story",
        "description": "test",
        "tags": [],
        "category": "其他",
    })
    story_id = resp.json()["id"]
    resp = client.post("/api/archives", json={
        "story_id": story_id,
        "name": "Test Archive",
    })
    archive_id = resp.json()["id"]
    return story_id, archive_id


def _add_messages(db, archive_id, contents):
    """Add test messages directly to DB, return their IDs."""
    ids = []
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
    msgs = db.query(models.ChatMessage).filter(
        models.ChatMessage.archive_id == archive_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    return [m.id for m in msgs]


def test_bulk_delete_removes_messages(client, db):
    """Test that bulk delete removes specified messages."""
    _, archive_id = _create_test_story_and_archive(client, db)
    msg_ids = _add_messages(db, archive_id, [
        ("user", "hello"),
        ("assistant", "hi there"),
        ("user", "second"),
        ("assistant", "second reply"),
    ])

    resp = client.request(
        "DELETE",
        f"/api/chat/messages/{archive_id}/bulk",
        json={"message_ids": [msg_ids[0], msg_ids[1]]},
    )

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2

    remaining = db.query(models.ChatMessage).filter(
        models.ChatMessage.archive_id == archive_id
    ).all()
    assert len(remaining) == 2
    assert [m.content for m in remaining] == ["second", "second reply"]


def test_bulk_delete_empty_list(client, db):
    """Test that empty message_ids returns 0 deleted."""
    _, archive_id = _create_test_story_and_archive(client, db)
    resp = client.request(
        "DELETE",
        f"/api/chat/messages/{archive_id}/bulk",
        json={"message_ids": []},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0


def test_bulk_delete_nonexistent_archive(client):
    """Test 404 for non-existent archive."""
    resp = client.request(
        "DELETE",
        "/api/chat/messages/99999/bulk",
        json={"message_ids": [1]},
    )
    assert resp.status_code == 404


def test_bulk_delete_nonexistent_ids(client, db):
    """Test that non-existent IDs are silently skipped."""
    _, archive_id = _create_test_story_and_archive(client, db)
    resp = client.request(
        "DELETE",
        f"/api/chat/messages/{archive_id}/bulk",
        json={"message_ids": [999, 1000]},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0
