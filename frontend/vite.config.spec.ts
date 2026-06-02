import { describe, expect, it } from 'vitest'
import config from './vite.config'

describe('vite dev server port', () => {
  it('uses the canonical whAInoel frontend port without fallback', () => {
    expect(config.server?.port).toBe(5173)
    expect(config.server?.strictPort).toBe(true)
  })
})
