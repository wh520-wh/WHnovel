import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const settingsStore = reactive({
  settings: {
    copy_image_format: 'url' as 'url' | 'binary',
    disable_chat_bubble_elastic: false,
  },
})

vi.mock('../stores/chat', async () => {
  const { reactive } = await import('vue')
  const chatStore = reactive({
    highlightedTerms: [] as string[],
    generateImage: vi.fn(),
  })

  return {
    useChatStore: () => chatStore,
    __mockChatStore: chatStore,
  }
})

vi.mock('../stores/settings', () => ({
  useSettingsStore: () => settingsStore,
}))

vi.mock('marked', () => ({
  marked: {
    parse: vi.fn((content: string) => `<p>${content}</p>`),
  },
}))

import { marked } from 'marked'
import ChatMessage from './ChatMessage.vue'

const { __mockChatStore: chatStore } = await import('../stores/chat') as any

describe('ChatMessage', () => {
  beforeEach(() => {
    settingsStore.settings.copy_image_format = 'url'
    settingsStore.settings.disable_chat_bubble_elastic = false
    chatStore.highlightedTerms = []
    chatStore.generateImage.mockReset()
    vi.mocked(marked.parse).mockClear()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    })
  })

  it('re-renders highlights when highlightedTerms changes for the same content', async () => {
    chatStore.highlightedTerms = ['alpha']
    chatStore.generateImage.mockReset()

    const wrapper = mount(ChatMessage, {
      props: {
        msg: {
          id: 1,
          archive_id: 1,
          role: 'assistant',
          content: 'alpha beta',
          state_snapshot: {},
          story_state: {},
          options: [],
          memory_update: [],
          created_at: '2026-04-16T00:00:00Z',
        },
        streaming: false,
      },
      global: {
        stubs: {
          teleport: true,
        },
      },
    })

    expect(wrapper.html()).toContain('<span class="hl-item">alpha</span> beta')

    chatStore.highlightedTerms = ['beta']
    await nextTick()

    expect(wrapper.html()).toContain('alpha <span class="hl-item">beta</span>')
    expect(wrapper.html()).not.toContain('<span class="hl-item">alpha</span> beta')
  })

  it('does not re-parse markdown when only highlightedTerms changes', async () => {
    chatStore.highlightedTerms = ['alpha']

    const wrapper = mount(ChatMessage, {
      props: {
        msg: {
          id: 3,
          archive_id: 1,
          role: 'assistant',
          content: 'alpha beta markdown-cache-target',
          state_snapshot: {},
          story_state: {},
          options: [],
          memory_update: [],
          created_at: '2026-04-16T00:00:00Z',
        },
        streaming: false,
      },
      global: {
        stubs: {
          teleport: true,
        },
      },
    })

    const callsAfterMount = vi.mocked(marked.parse).mock.calls.length
    expect(callsAfterMount).toBeGreaterThan(0)
    expect(wrapper.html()).toContain('<span class="hl-item">alpha</span> beta markdown-cache-target')

    chatStore.highlightedTerms = ['beta']
    await nextTick()

    expect(marked.parse).toHaveBeenCalledTimes(callsAfterMount)
    expect(wrapper.html()).toContain('alpha <span class="hl-item">beta</span> markdown-cache-target')
  })

  it('skips bubble click animation when elasticity is disabled', async () => {
    settingsStore.settings.disable_chat_bubble_elastic = true

    const wrapper = mount(ChatMessage, {
      props: {
        msg: {
          id: 2,
          archive_id: 1,
          role: 'assistant',
          content: 'hello',
          state_snapshot: {},
          story_state: {},
          options: [],
          memory_update: [],
          created_at: '2026-04-16T00:00:00Z',
        },
        streaming: false,
      },
      global: {
        stubs: {
          teleport: true,
        },
      },
    })

    const bubble = wrapper.find('.msg-bubble')
    await bubble.trigger('click')

    expect(wrapper.find('.chat-message').classes()).toContain('elastic-disabled')
    expect(bubble.classes()).not.toContain('bubble-pop')
  })
})
