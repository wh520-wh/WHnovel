import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => {
  const mocks = {
    createArchive: vi.fn(),
    deleteLastAiMessage: vi.fn(),
    deleteMessages: vi.fn(),
    generateChatImage: vi.fn(),
    generateStoryOptions: vi.fn(),
    generateStateBroadcast: vi.fn(),
    getArchive: vi.fn(),
    getArchives: vi.fn(),
    getMessages: vi.fn(),
    sendMessageStream: vi.fn(),
    startChatStream: vi.fn(),
  }

  return {
    ...mocks,
    __mocks: mocks,
  }
})

import { normalizeIncomingMessage, useChatStore } from './chat'

const { __mocks: apiMocks } = (await import('../api')) as any

describe('chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiMocks.getArchive.mockReset()
    apiMocks.getMessages.mockReset()
    apiMocks.getArchives.mockReset()
    apiMocks.sendMessageStream.mockReset()
  })

  it('clears highlightedTerms when loading an archive', async () => {
    apiMocks.getArchive.mockResolvedValue({
      data: {
        id: 2,
        story_id: 1,
        name: 'A2',
        state_data: {},
        story_state: {},
        memory_log: [],
        created_at: '2026-04-16T00:00:00Z',
        updated_at: '2026-04-16T00:00:00Z',
      },
    })
    apiMocks.getMessages.mockResolvedValue({
      data: [
        {
          id: 101,
          archive_id: 2,
          role: 'assistant',
          content: 'hello',
          state_snapshot: {},
          story_state: {},
          options: [],
          memory_update: [],
          created_at: '2026-04-16T00:00:00Z',
        },
      ],
    })

    const store = useChatStore()
    ;(store as any).$state.highlightedTerms = ['旧高亮']

    await store.loadArchive(2)

    expect((store as any).highlightedTerms).toEqual([])
  })

  it('clears locked option state when loading an archive', async () => {
    apiMocks.getArchive.mockResolvedValue({
      data: {
        id: 2,
        story_id: 1,
        name: 'A2',
        state_data: {},
        story_state: {},
        memory_log: [],
        created_at: '2026-04-16T00:00:00Z',
        updated_at: '2026-04-16T00:00:00Z',
      },
    })
    apiMocks.getMessages.mockResolvedValue({ data: [] })

    const store = useChatStore()
    store.currentOptions = ['观察四周', '直接追问']

    const locked = store.beginOptionLock('直接追问')
    expect(locked).toBe(true)
    expect(store.lockedOption).toBe('直接追问')

    await store.loadArchive(2)

    expect(store.lockedOption).toBe('')
    expect(store.currentOptions).toEqual([])
    expect(store.lastOptionsSnapshot).toEqual([])
    expect(store.optionsLocked).toBe(false)
  })

  it('clears current options immediately when sending free text', async () => {
    apiMocks.getArchives.mockResolvedValue({ data: [] })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any
    store.currentOptions = ['观察四周', '直接追问']

    apiMocks.sendMessageStream.mockImplementation(
      async (_archiveId: number, _text: string, onEvent: any) => {
        expect(store.currentOptions).toEqual([])
        expect(store.optionsLocked).toBe(false)

        onEvent({
          event: 'tail',
          data: {
            archive_id: 1,
            reply_text: 'AI 回复',
            character_state: {},
            story_state: {},
            memory_update: [],
            plot_label: null,
            highlight_terms: [],
          },
        })
      },
    )

    apiMocks.generateStoryOptions.mockResolvedValue({ data: { options: ['后续动作'] } })

    await store.sendStream('我自己决定行动')

    expect(store.currentOptions).toEqual(['后续动作'])
  })

  it('rewinds option snapshot when stream aborts after text_end', async () => {
    // Simulates the 180s AbortController timeout: delta + text_end arrive,
    // then fetch is aborted before any `error` event gets to onEvent.
    // Options must be restored from snapshot so the user can retry.
    apiMocks.getArchives.mockResolvedValue({ data: [] })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any
    store.currentOptions = ['观察四周', '直接追问', '低声回应']

    apiMocks.sendMessageStream.mockImplementation(
      async (_archiveId: number, _text: string, onEvent: any) => {
        onEvent({ event: 'delta', data: { text: '你看到' } })
        onEvent({ event: 'delta', data: { text: '一束光从门缝透出……' } })
        onEvent({ event: 'text_end', data: { reply_text: '你看到一束光从门缝透出……' } })
        // No tail / no error event — simulate upstream hang + 180s abort
        throw new Error('请求超时（180s），请检查模型配置或网络')
      },
    )

    let caught: unknown = null
    try {
      await store.sendStream('观察四周', { fromOption: true })
    } catch (e) {
      caught = e
    }

    expect(store.optionsLocked).toBe(false)
    expect(store.currentOptions).toEqual(['观察四周', '直接追问', '低声回应'])
    expect(store.lastOptionsSnapshot).toEqual(['观察四周', '直接追问', '低声回应'])
    expect((caught as { partial?: boolean })?.partial).toBe(true)
  })

  it('keeps option-lock flow when sending an AI option', async () => {
    apiMocks.getArchives.mockResolvedValue({ data: [] })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any
    store.currentOptions = ['观察四周', '直接追问']

    apiMocks.sendMessageStream.mockImplementation(
      async (_archiveId: number, _text: string, onEvent: any) => {
        expect(store.optionsLocked).toBe(true)
        expect(store.currentOptions).toEqual([])
        expect(store.lastOptionsSnapshot).toEqual(['观察四周', '直接追问'])

        onEvent({
          event: 'tail',
          data: {
            archive_id: 1,
            reply_text: 'AI 回复',
            character_state: {},
            story_state: {},
            memory_update: [],
            plot_label: null,
            highlight_terms: [],
          },
        })
      },
    )

    apiMocks.generateStoryOptions.mockResolvedValue({ data: { options: ['继续追问'] } })

    await store.sendStream('观察四周', { fromOption: true })

    expect(store.optionsLocked).toBe(false)
    expect(store.currentOptions).toEqual(['继续追问'])
  })

  it('deleteMessages reverts messages on API failure', async () => {
    const store = useChatStore()
    // 模拟 API 抛错
    apiMocks.deleteMessages.mockRejectedValue(new Error('network error'))

    store.messages = [
      {
        id: 1,
        role: 'user',
        content: 'a',
        archive_id: 1,
        state_snapshot: {},
        story_state: {},
        options: [],
        memory_update: [],
        created_at: '',
        persisted: true,
        removing: false,
      } as any,
      {
        id: 2,
        role: 'assistant',
        content: 'b',
        archive_id: 1,
        state_snapshot: {},
        story_state: {},
        options: [],
        memory_update: [],
        created_at: '',
        persisted: true,
        removing: false,
      } as any,
    ]
    store.currentArchive = {
      id: 1,
      story_id: 1,
      name: '',
      state_data: {},
      story_state: {},
      memory_log: [],
      created_at: '',
      updated_at: '',
    } as any

    try {
      await store.deleteMessages([1, 2])
    } catch {
      // Expected to throw after rollback
    }

    // 验证 messages 数组仍然完整
    expect(store.messages.length).toBe(2)
    expect(store.messages[0].removing).toBe(false)
    expect(store.messages[1].removing).toBe(false)
  })

  it('generateStateBroadcast sets isStateBroadcast flag on new message', async () => {
    apiMocks.getArchives.mockResolvedValue({ data: [] })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any

    apiMocks.generateStateBroadcast.mockResolvedValue({
      data: { content: 'State broadcast message' },
    })

    await store.generateStateBroadcast()

    expect(Array.isArray(store.messages)).toBe(true)
    expect(store.messages.length).toBeGreaterThan(0)
    const lastMessage = store.messages[store.messages.length - 1]
    expect(lastMessage.role).toBe('assistant')
    expect(lastMessage.content).toBe('State broadcast message')
    expect(lastMessage.isStateBroadcast).toBe(true)
  })
})

describe('normalizeIncomingMessage', () => {
  it('accepts array of unknown objects from API', () => {
    const raw = [
      {
        id: 1,
        archive_id: 2,
        role: 'assistant',
        content: 'hello',
        state_snapshot: {},
        story_state: {},
        options: [],
        memory_update: [],
        created_at: '2026-01-01T00:00:00Z',
      },
    ]
    // simulate what loadArchive does after removing `as any[]`
    const result = (Array.isArray(raw) ? raw : []).map((m) =>
      normalizeIncomingMessage(m as Record<string, unknown>),
    )
    expect(result[0].content).toBe('hello')
    expect(result[0].role).toBe('assistant')
  })
})
