import { describe, it, expect, vi } from 'vitest'
import { postSSE } from './index'

describe('postSSE', () => {
  it('releases reader lock when SSE parse throws', async () => {
    const releaseLock = vi.fn()
    const encoder = new TextEncoder()
    // Use a valid SSE error event so receivedAnyEvent gets set before throw,
    // avoiding retries and ensuring the function rejects quickly
    const errorChunk = encoder.encode('event: error\ndata: {"message":"test error"}\n\n')

    const reader = {
      read: vi.fn().mockResolvedValueOnce({ done: false, value: errorChunk }),
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
