"""Bug #9 回归测试：预设开场缓存并发安全。

- single-flight：同故事并发请求只产生一次 generate_fn（真实计费 LLM）调用；
- TTL 过期并发删除不再 KeyError（del 改 pop）。
"""

import threading
import time

from app.api import chat_cache


def setup_function():
    chat_cache._cache.clear()


def test_concurrent_get_or_generate_single_flight():
    calls = []
    barrier = threading.Barrier(4)

    def generate_fn():
        calls.append(1)
        time.sleep(0.1)  # 模拟真实 LLM 调用耗时，放大竞态窗口
        return [{"title": "开场A", "content": "..."}]

    results = []

    def worker():
        barrier.wait()  # 同时起跑，最大化并发
        results.append(chat_cache.get_or_generate(42, generate_fn))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(calls) == 1  # 重复计费调用被 single-flight 消除
    assert len(results) == 4
    for openings, etag, _was_cached in results:
        assert openings == [{"title": "开场A", "content": "..."}]
        assert etag is not None
    # 恰有一个线程真正生成，其余命中缓存
    assert sorted(r[2] for r in results) == [False, True, True, True]


def test_expired_entry_concurrent_delete_no_keyerror(monkeypatch):
    chat_cache._set_cached(7, [{"title": "旧", "content": "x"}], "etag-old")
    # 强制条目过期
    chat_cache._cache[7]["ts"] = time.monotonic() - chat_cache._TTL_SECONDS - 1

    errors = []

    def worker():
        try:
            chat_cache._get_cached(7)
        except KeyError as e:  # del 并发下的旧缺陷
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert 7 not in chat_cache._cache
