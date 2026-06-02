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
})
