import { describe, it, expect, vi } from 'vitest'
import { postSSE } from './index'

describe('postSSE', () => {
  it('releases reader lock when SSE parse throws', async () => {
    const releaseLock = vi.fn()
    const encoder = new TextEncoder()
    // 先发一个合法 delta 让 receivedAnyEvent=true，再发未知事件触发解析抛错，
    // 使 catch 直接 rethrow（不重试），快速 reject
    const deltaChunk = encoder.encode('event: delta\ndata: {"text":"hi"}\n\n')
    const badChunk = encoder.encode('event: bogus\ndata: {}\n\n')

    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: deltaChunk })
        .mockResolvedValueOnce({ done: false, value: badChunk }),
      releaseLock,
    }

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => reader },
    } as any)

    const onEvent = vi.fn()

    await expect(postSSE('/test', {}, onEvent)).rejects.toThrow()
    expect(releaseLock).toHaveBeenCalled()
  })

  it('delivers error event via onEvent and resolves without throwing (Bug #31)', async () => {
    const encoder = new TextEncoder()
    const errorChunk = encoder.encode('event: error\ndata: {"message":"backend raw error"}\n\n')

    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: errorChunk })
        .mockResolvedValue({ done: true, value: undefined }),
      releaseLock: vi.fn(),
    }

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => reader },
    } as any)

    const onEvent = vi.fn()
    // 不再用原始 data.message 抛错，错误文案交由 useChatStream 统一处理
    await expect(postSSE('/test', {}, onEvent)).resolves.toBeUndefined()
    expect(onEvent).toHaveBeenCalledTimes(1)
    expect(onEvent.mock.calls[0][0].event).toBe('error')
    expect(onEvent.mock.calls[0][0].data.message).toBe('backend raw error')
  })

  it('flushes residual buffer when stream ends without trailing blank line (Bug #30)', async () => {
    const encoder = new TextEncoder()
    // tail 事件没有以空行结尾，随后流直接关闭
    const tailChunk = encoder.encode('event: tail\ndata: {"reply_text":"结局正文"}')

    const reader = {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: tailChunk })
        .mockResolvedValue({ done: true, value: undefined }),
      releaseLock: vi.fn(),
    }

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => reader },
    } as any)

    const onEvent = vi.fn()
    await postSSE('/test', {}, onEvent)

    expect(onEvent).toHaveBeenCalledTimes(1)
    expect(onEvent.mock.calls[0][0].event).toBe('tail')
    expect(onEvent.mock.calls[0][0].data.reply_text).toBe('结局正文')
  })
})
