"""Test that concurrent streaming requests for the same archive are serialized."""
import threading
import time
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.chat_stream import (
    _acquire_stream_generation_lock,
    _stream_generation_locks,
)


def test_acquire_lock_blocks_second_request():
    """Second concurrent request for same archive_id should be rejected."""
    archive_id = 99999

    # Ensure no prior lock state
    _stream_generation_locks.pop(archive_id, None)

    lock_acquired_count = 0
    lock_rejected_count = 0

    def try_acquire_lock():
        nonlocal lock_acquired_count, lock_rejected_count
        try:
            with _acquire_stream_generation_lock(archive_id):
                lock_acquired_count += 1
                time.sleep(0.5)  # Hold lock for 500ms
        except Exception:
            lock_rejected_count += 1

    # Start first request
    t1 = threading.Thread(target=try_acquire_lock)
    t1.start()
    time.sleep(0.05)  # Let t1 acquire lock

    # Start second request (should be rejected)
    t2 = threading.Thread(target=try_acquire_lock)
    t2.start()
    t2.join()

    t1.join()

    assert lock_acquired_count == 1, "Only one request should acquire lock"
    assert lock_rejected_count == 1, "One request should be rejected"


def test_different_archive_ids_can_proceed_concurrently():
    """Requests for different archives should not block each other."""
    archive_id_1 = 88881
    archive_id_2 = 88882

    results = []

    def try_acquire_lock(archive_id, results_list):
        try:
            with _acquire_stream_generation_lock(archive_id):
                results_list.append(f"acquired_{archive_id}")
                time.sleep(0.2)
        except Exception:
            results_list.append(f"rejected_{archive_id}")

    t1 = threading.Thread(target=try_acquire_lock, args=(archive_id_1, results))
    t2 = threading.Thread(target=try_acquire_lock, args=(archive_id_2, results))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results == [f"acquired_{archive_id_1}", f"acquired_{archive_id_2}"]


def test_lock_released_on_exception():
    """Lock is released even when context manager body raises."""
    archive_id = 77771
    _stream_generation_locks.pop(archive_id, None)

    raised = False

    def raise_in_body():
        nonlocal raised
        try:
            with _acquire_stream_generation_lock(archive_id):
                raise ValueError("simulated error")
        except ValueError:
            raised = True

    t1 = threading.Thread(target=raise_in_body)
    t1.start()
    t1.join()

    assert raised, "Exception should propagate"
    # Lock should be released, third request can acquire
    third_acquired = False
    try:
        with _acquire_stream_generation_lock(archive_id):
            third_acquired = True
    except Exception:
        pass

    assert third_acquired, "Third request should acquire lock after first raised"


def test_send_endpoint_acquires_stream_lock(monkeypatch):
    """send_message endpoint should acquire the stream generation lock."""
    archive_id = 55551

    mock_db = MagicMock()
    mock_archive = MagicMock()
    mock_archive.id = archive_id
    mock_archive.story = MagicMock()
    mock_archive.first_message = None
    mock_archive.state_data = {}
    mock_archive.story_state = {}
    mock_archive.memory_log = []
    mock_db.query.return_value.filter.return_value.first.return_value = mock_archive

    from app.api import chat_router

    monkeypatch.setattr(chat_router, '_get_or_create_settings', MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(chat_router, '_persist_exchange', MagicMock())
    monkeypatch.setattr(chat_router, '_call_ai_with_failover', MagicMock())

    # Use an event to make _generate_chat_response block while holding the real lock
    generate_block = threading.Event()

    def blocking_generate(*args, **kwargs):
        generate_block.wait()  # block until released
        return MagicMock(options=[], plot_label=None, highlight_terms=[])

    monkeypatch.setattr(chat_router, '_generate_chat_response', blocking_generate)

    results = []
    errors = []

    def send_request():
        try:
            payload = MagicMock()
            payload.archive_id = archive_id
            payload.message = "test"
            chat_router.send_message(payload, mock_db)
            results.append("ok")
        except Exception as e:
            errors.append(type(e).__name__)
            results.append(type(e).__name__)

    t1 = threading.Thread(target=send_request)
    t1.start()
    # Give t1 time to acquire the lock and enter blocking_generate
    time.sleep(0.3)

    t2 = threading.Thread(target=send_request)
    t2.start()
    t2.join(timeout=5)

    assert not t2.is_alive(), "Second request should complete (be rejected), not hang"

    # Second request should have been rejected because the lock is held
    assert any(r != "ok" for r in results), f"Second request should be rejected, got results: {results}, errors: {errors}"

    # Release t1
    generate_block.set()
    t1.join(timeout=5)


def test_stream_endpoint_holds_lock_while_body_iterator_is_active(monkeypatch):
    """Streaming endpoint should keep the archive lock for the response body lifetime."""
    archive_id = 55552
    _stream_generation_locks.pop(archive_id, None)

    mock_db = MagicMock()
    mock_archive = MagicMock()
    mock_archive.id = archive_id
    mock_archive.story = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_archive

    from app.api import chat_router

    monkeypatch.setattr(chat_router, '_get_or_create_settings', MagicMock(return_value=MagicMock()))

    def blocking_stream(*args, **kwargs):
        yield 'event: delta\ndata: {"text":"a"}\n\n'
        time.sleep(0.5)
        yield 'event: done\ndata: {}\n\n'

    monkeypatch.setattr(chat_router, '_stream_chat_response', blocking_stream)

    payload = MagicMock()
    payload.archive_id = archive_id
    payload.message = "test"

    first_response = chat_router.send_message_stream(payload, mock_db)

    consumed_first_chunk = threading.Event()

    def consume_first_chunk():
        async def _consume():
            await first_response.body_iterator.__anext__()
            consumed_first_chunk.set()
            await asyncio.sleep(0.5)

        asyncio.run(_consume())

    t1 = threading.Thread(target=consume_first_chunk)
    t1.start()
    assert consumed_first_chunk.wait(timeout=2), "first stream did not start"

    with pytest.raises(HTTPException) as exc:
        chat_router.send_message_stream(payload, mock_db)
    assert exc.value.status_code == 409

    t1.join(timeout=2)


from app.api.chat_stream import _acquire_image_generation_lock


def test_image_lock_blocks_concurrent_requests():
    """Second concurrent image gen request for same archive should be rejected."""
    archive_id = 77772

    acquired = []
    rejected = []

    def try_acquire():
        try:
            with _acquire_image_generation_lock(archive_id):
                acquired.append(True)
                time.sleep(0.5)
        except Exception:
            rejected.append(True)

    t1 = threading.Thread(target=try_acquire)
    t1.start()
    time.sleep(0.05)

    t2 = threading.Thread(target=try_acquire)
    t2.start()
    t2.join()
    t1.join()

    assert len(acquired) == 1
    assert len(rejected) == 1


def test_image_lock_different_archives_concurrent():
    """Different archives can generate images concurrently."""
    aid1 = 88883
    aid2 = 88884

    results = []

    def try_acquire(aid):
        try:
            with _acquire_image_generation_lock(aid):
                results.append(f"ok_{aid}")
                time.sleep(0.2)
        except Exception:
            results.append(f"blocked_{aid}")

    t1 = threading.Thread(target=try_acquire, args=(aid1,))
    t2 = threading.Thread(target=try_acquire, args=(aid2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results == [f"ok_{aid1}", f"ok_{aid2}"]
