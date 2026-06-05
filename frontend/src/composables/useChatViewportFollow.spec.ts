import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useChatViewportFollow } from './useChatViewportFollow'

type RafCallback = (time: number) => void

describe('useChatViewportFollow', () => {
  const rafQueue = new Map<number, RafCallback>()
  let rafId = 0
  let now = 1000

  beforeEach(() => {
    rafQueue.clear()
    rafId = 0
    now = 1000

    vi.spyOn(performance, 'now').mockImplementation(() => now)

    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn((cb: RafCallback) => {
        rafId += 1
        rafQueue.set(rafId, cb)
        return rafId
      }),
    )

    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn((id: number) => {
        rafQueue.delete(id)
      }),
    )

    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({
        matches: query.includes('(max-width: 767px)'),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('progressively scrolls toward scrollHeight instead of instant snapping', async () => {
    const storyPlay = document.createElement('section')
    const chatArea = document.createElement('div')
    const inputArea = document.createElement('div')
    const quickOptions = document.createElement('div')
    const textarea = document.createElement('textarea')

    let scrollHeight = 400
    let scrollTop = 380
    Object.defineProperty(chatArea, 'scrollHeight', { configurable: true, get: () => scrollHeight })
    Object.defineProperty(chatArea, 'scrollTop', {
      configurable: true,
      get: () => scrollTop,
      set: (v: number) => {
        scrollTop = v
      },
    })
    Object.defineProperty(chatArea, 'clientHeight', { configurable: true, value: 400 })
    ;(chatArea as any).scrollTo = vi.fn(({ top }: { top: number }) => {
      scrollTop = top
    })

    Object.defineProperty(window, 'visualViewport', {
      configurable: true,
      value: { height: 700, offsetTop: 0, addEventListener: vi.fn(), removeEventListener: vi.fn() },
    })

    const storyPlayRef = ref<HTMLElement | null>(storyPlay)
    const chatAreaRef = ref<HTMLElement | null>(chatArea)
    const inputAreaRef = ref<HTMLElement | null>(inputArea)
    const quickOptionsRef = ref<HTMLElement | null>(quickOptions)
    const textareaRef = ref<HTMLTextAreaElement | null>(textarea)
    const assistantMessageCount = ref(1)
    const streaming = ref(false)
    const streamingFollow = ref(true)

    const Harness = defineComponent({
      setup(_, { expose }) {
        const api = useChatViewportFollow({
          storyPlayRef,
          chatAreaRef,
          inputAreaRef,
          quickOptionsRef,
          textareaRef,
          assistantMessageCount,
          streaming,
          streamingFollow,
        })
        expose(api)
        return () => null
      },
    })

    const wrapper = mount(Harness)

    const pumpOneFrame = () => {
      const callbacks = [...rafQueue.values()]
      rafQueue.clear()
      for (const cb of callbacks) cb(now)
    }

    streaming.value = true
    await wrapper.vm.$nextTick()
    pumpOneFrame()
    // Initial lerp from 380 toward 400 (not an instant snap)
    expect(scrollTop).toBeGreaterThan(380)
    expect(scrollTop).toBeLessThan(400)

    // Content grows 100px — first frame should NOT jump all the way
    scrollHeight = 500
    now += 80
    pumpOneFrame()
    // Should move, but less than the full 100px growth (lerp factor ~0.45)
    expect(scrollTop).toBeGreaterThan(380)
    expect(scrollTop).toBeLessThan(500)

    // After several more frames, should converge near target
    for (let i = 0; i < 10; i += 1) {
      now += 20
      pumpOneFrame()
    }
    // Should be very close to target (within snap threshold)
    expect(scrollTop).toBeGreaterThanOrEqual(498)

    streaming.value = false
    await wrapper.vm.$nextTick()
    pumpOneFrame()

    wrapper.unmount()
  })

  it('updates target progressively when content grows multiple times', async () => {
    const storyPlay = document.createElement('section')
    const chatArea = document.createElement('div')
    const inputArea = document.createElement('div')
    const quickOptions = document.createElement('div')
    const textarea = document.createElement('textarea')

    let scrollHeight = 400
    let scrollTop = 390
    Object.defineProperty(chatArea, 'scrollHeight', { configurable: true, get: () => scrollHeight })
    Object.defineProperty(chatArea, 'scrollTop', {
      configurable: true,
      get: () => scrollTop,
      set: (v: number) => {
        scrollTop = v
      },
    })
    Object.defineProperty(chatArea, 'clientHeight', { configurable: true, value: 400 })
    ;(chatArea as any).scrollTo = vi.fn(({ top }: { top: number }) => {
      scrollTop = top
    })

    Object.defineProperty(window, 'visualViewport', {
      configurable: true,
      value: { height: 700, offsetTop: 0, addEventListener: vi.fn(), removeEventListener: vi.fn() },
    })

    const storyPlayRef = ref<HTMLElement | null>(storyPlay)
    const chatAreaRef = ref<HTMLElement | null>(chatArea)
    const inputAreaRef = ref<HTMLElement | null>(inputArea)
    const quickOptionsRef = ref<HTMLElement | null>(quickOptions)
    const textareaRef = ref<HTMLTextAreaElement | null>(textarea)
    const assistantMessageCount = ref(1)
    const streaming = ref(true)
    const streamingFollow = ref(true)

    const Harness = defineComponent({
      setup(_, { expose }) {
        const api = useChatViewportFollow({
          storyPlayRef,
          chatAreaRef,
          inputAreaRef,
          quickOptionsRef,
          textareaRef,
          assistantMessageCount,
          streaming,
          streamingFollow,
        })
        expose(api)
        return () => null
      },
    })

    const wrapper = mount(Harness)

    const pumpOneFrame = () => {
      const callbacks = [...rafQueue.values()]
      rafQueue.clear()
      for (const cb of callbacks) cb(now)
    }

    await wrapper.vm.$nextTick()
    pumpOneFrame()

    // First growth: 400 → 450
    scrollHeight = 450
    now += 80
    pumpOneFrame()
    const afterFirst = scrollTop
    expect(afterFirst).toBeGreaterThan(390)
    expect(afterFirst).toBeLessThan(450)

    // Second growth arrives before first target reached: 450 → 520
    // Target updates, lerp continues from current position toward new target
    scrollHeight = 520
    now += 80
    pumpOneFrame()
    const afterSecond = scrollTop
    expect(afterSecond).toBeGreaterThan(afterFirst)
    expect(afterSecond).toBeLessThan(520)

    // Converge
    for (let i = 0; i < 12; i += 1) {
      now += 20
      pumpOneFrame()
    }
    expect(scrollTop).toBeGreaterThanOrEqual(518)

    wrapper.unmount()
  })

  it('snaps instantly when prefers-reduced-motion is set', async () => {
    // Override matchMedia to simulate reduced motion preference
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    )

    const storyPlay = document.createElement('section')
    const chatArea = document.createElement('div')
    const inputArea = document.createElement('div')
    const quickOptions = document.createElement('div')
    const textarea = document.createElement('textarea')

    let scrollHeight = 400
    let scrollTop = 380
    Object.defineProperty(chatArea, 'scrollHeight', { configurable: true, get: () => scrollHeight })
    Object.defineProperty(chatArea, 'scrollTop', {
      configurable: true,
      get: () => scrollTop,
      set: (v: number) => {
        scrollTop = v
      },
    })
    Object.defineProperty(chatArea, 'clientHeight', { configurable: true, value: 400 })
    ;(chatArea as any).scrollTo = vi.fn(({ top }: { top: number }) => {
      scrollTop = top
    })

    Object.defineProperty(window, 'visualViewport', {
      configurable: true,
      value: { height: 700, offsetTop: 0, addEventListener: vi.fn(), removeEventListener: vi.fn() },
    })

    const storyPlayRef = ref<HTMLElement | null>(storyPlay)
    const chatAreaRef = ref<HTMLElement | null>(chatArea)
    const inputAreaRef = ref<HTMLElement | null>(inputArea)
    const quickOptionsRef = ref<HTMLElement | null>(quickOptions)
    const textareaRef = ref<HTMLTextAreaElement | null>(textarea)
    const assistantMessageCount = ref(1)
    const streaming = ref(false)
    const streamingFollow = ref(true)

    const Harness = defineComponent({
      setup(_, { expose }) {
        const api = useChatViewportFollow({
          storyPlayRef,
          chatAreaRef,
          inputAreaRef,
          quickOptionsRef,
          textareaRef,
          assistantMessageCount,
          streaming,
          streamingFollow,
        })
        expose(api)
        return () => null
      },
    })

    const wrapper = mount(Harness)

    const pumpOneFrame = () => {
      const callbacks = [...rafQueue.values()]
      rafQueue.clear()
      for (const cb of callbacks) cb(now)
    }

    streaming.value = true
    await wrapper.vm.$nextTick()
    pumpOneFrame()

    // With reduced motion, should jump instantly (old behavior)
    scrollHeight = 600
    now += 80
    pumpOneFrame()
    expect(scrollTop).toBe(600)

    streaming.value = false
    await wrapper.vm.$nextTick()
    pumpOneFrame()

    wrapper.unmount()
  })

  it('queueBottomFollow scrolls to bottom', async () => {
    const storyPlay = document.createElement('section')
    const chatArea = document.createElement('div')
    const inputArea = document.createElement('div')
    const quickOptions = document.createElement('div')
    const textarea = document.createElement('textarea')

    let scrollTop = 460
    Object.defineProperty(chatArea, 'scrollTop', {
      configurable: true,
      get: () => scrollTop,
      set: (v: number) => {
        scrollTop = v
      },
    })
    Object.defineProperty(chatArea, 'scrollHeight', { configurable: true, value: 1000 })
    Object.defineProperty(chatArea, 'clientHeight', { configurable: true, value: 500 })
    ;(chatArea as any).scrollTo = vi.fn(({ top }: { top: number }) => {
      scrollTop = top
    })

    const storyPlayRef = ref<HTMLElement | null>(storyPlay)
    const chatAreaRef = ref<HTMLElement | null>(chatArea)
    const inputAreaRef = ref<HTMLElement | null>(inputArea)
    const quickOptionsRef = ref<HTMLElement | null>(quickOptions)
    const textareaRef = ref<HTMLTextAreaElement | null>(textarea)
    const assistantMessageCount = ref(0)
    const streaming = ref(false)
    const streamingFollow = ref(true)

    const Harness = defineComponent({
      setup(_, { expose }) {
        const api = useChatViewportFollow({
          storyPlayRef,
          chatAreaRef,
          inputAreaRef,
          quickOptionsRef,
          textareaRef,
          assistantMessageCount,
          streaming,
          streamingFollow,
        })
        expose(api)
        return () => null
      },
    })

    const wrapper = mount(Harness)
    const api = wrapper.vm as any

    // queueBottomFollow should trigger a scroll to bottom
    api.queueBottomFollow({ behavior: 'auto', frames: 2 })

    const flushAllRaf = (maxRounds = 10) => {
      for (let i = 0; i < maxRounds && rafQueue.size > 0; i += 1) {
        const callbacks = [...rafQueue.values()]
        rafQueue.clear()
        for (const cb of callbacks) cb(now)
      }
    }
    flushAllRaf()

    // chatArea.scrollTo should have been called to scroll to bottom
    expect((chatArea as any).scrollTo).toHaveBeenCalled()

    wrapper.unmount()
  })

  it('pauses stream-follow frames while user is away from bottom and restarts near bottom', async () => {
    const storyPlay = document.createElement('section')
    const chatArea = document.createElement('div')
    const inputArea = document.createElement('div')
    const quickOptions = document.createElement('div')
    const textarea = document.createElement('textarea')

    let scrollHeight = 1200
    let scrollTop = 100
    Object.defineProperty(chatArea, 'scrollHeight', { configurable: true, get: () => scrollHeight })
    Object.defineProperty(chatArea, 'scrollTop', {
      configurable: true,
      get: () => scrollTop,
      set: (v: number) => {
        scrollTop = v
      },
    })
    Object.defineProperty(chatArea, 'clientHeight', { configurable: true, value: 400 })
    ;(chatArea as any).scrollTo = vi.fn(({ top }: { top: number }) => {
      scrollTop = top
    })

    const storyPlayRef = ref<HTMLElement | null>(storyPlay)
    const chatAreaRef = ref<HTMLElement | null>(chatArea)
    const inputAreaRef = ref<HTMLElement | null>(inputArea)
    const quickOptionsRef = ref<HTMLElement | null>(quickOptions)
    const textareaRef = ref<HTMLTextAreaElement | null>(textarea)
    const assistantMessageCount = ref(1)
    const streaming = ref(true)
    const streamingFollow = ref(true)

    const Harness = defineComponent({
      setup(_, { expose }) {
        const api = useChatViewportFollow({
          storyPlayRef,
          chatAreaRef,
          inputAreaRef,
          quickOptionsRef,
          textareaRef,
          assistantMessageCount,
          streaming,
          streamingFollow,
        })
        expose(api)
        return () => null
      },
    })

    const wrapper = mount(Harness)
    const api = wrapper.vm as any
    api.autoFollow = false

    const pumpOneFrame = () => {
      const callbacks = [...rafQueue.values()]
      rafQueue.clear()
      for (const cb of callbacks) cb(now)
    }

    await wrapper.vm.$nextTick()
    pumpOneFrame()

    expect(rafQueue.size).toBe(0)

    scrollTop = 790
    chatArea.dispatchEvent(new Event('scroll'))
    now += 20
    await wrapper.vm.$nextTick()
    pumpOneFrame()

    scrollHeight = 1400
    now += 80
    pumpOneFrame()

    // Should lerp toward 1400, not snap instantly
    expect(scrollTop).toBeGreaterThan(790)
    expect(scrollTop).toBeLessThan(1400)

    // Converge over subsequent frames
    for (let i = 0; i < 12; i += 1) {
      now += 20
      pumpOneFrame()
    }
    expect(scrollTop).toBeGreaterThanOrEqual(1398)

    wrapper.unmount()
  })
})
