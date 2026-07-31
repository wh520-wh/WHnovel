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

  it('removes empty assistant bubble on pure stream failure (Bug #48)', async () => {
    apiMocks.getArchives.mockResolvedValue({ data: [] })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any

    apiMocks.sendMessageStream.mockImplementation(
      async (_archiveId: number, _text: string, onEvent: any) => {
        // 纯失败：仅 error 事件，无 delta/tail/draft（如未配置模型 Bug #46 触发）
        onEvent({
          event: 'error',
          data: { code: 'HTTP_503', message: '没有可用模型', task: 'chat_stream', draft: false },
        })
      },
    )

    let caught: unknown = null
    try {
      await store.sendStream('测试消息')
    } catch (e) {
      caught = e
    }

    // 空的临时 AI 气泡应被移除，不残留空白气泡；仅保留乐观用户消息
    expect(store.messages.filter((m: any) => m.role === 'assistant')).toEqual([])
    expect(store.messages.length).toBe(1)
    expect(store.messages[0].role).toBe('user')
    expect(caught).toBeTruthy()
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

  it('writes refreshed archive list into store after stream tail (Bug #25)', async () => {
    apiMocks.getArchives.mockResolvedValue({
      data: [
        {
          id: 1,
          story_id: 1,
          name: '会话A',
          state_data: {},
          story_state: {},
          memory_log: [],
          created_at: '2026-04-16T00:00:00Z',
          updated_at: '2026-04-16T01:00:00Z',
        },
      ],
    })
    apiMocks.generateStoryOptions.mockResolvedValue({ data: { options: [] } })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any

    apiMocks.sendMessageStream.mockImplementation(
      async (_archiveId: number, _text: string, onEvent: any) => {
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

    await store.sendStream('你好')

    expect(apiMocks.getArchives).toHaveBeenCalledWith(1)
    expect((store as any).archives).toHaveLength(1)
    expect((store as any).archives[0].name).toBe('会话A')
  })

  it('does not overwrite currentArchive when user switches archive during tail refresh (Bug #26)', async () => {
    apiMocks.getArchives.mockResolvedValue({ data: [] })
    apiMocks.generateStoryOptions.mockResolvedValue({ data: { options: [] } })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any

    let resolveArchive: (value: unknown) => void = () => {}
    apiMocks.getArchive.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveArchive = resolve
        }),
    )
    apiMocks.sendMessageStream.mockImplementation(
      async (_archiveId: number, _text: string, onEvent: any) => {
        onEvent({
          event: 'tail',
          data: {
            // 后端换档：tail 携带的 archive_id 与发起流的存档不同
            archive_id: 2,
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

    const sendPromise = store.sendStream('你好')
    // 等 tail 处理进入 getArchive(2) 的等待窗口
    await vi.waitFor(() => expect(apiMocks.getArchive).toHaveBeenCalledWith(2))
    // 用户在此窗口内切到存档 3
    store.currentArchive = { id: 3, story_id: 1 } as any
    resolveArchive({ data: { id: 2, story_id: 1, name: '新分支' } })
    await sendPromise

    // 迟到的 tail 存档响应不得覆盖用户已切换的存档
    expect(store.currentArchive?.id).toBe(3)
  })

  it('ensureActiveArchive guarantees currentArchive on existing archives even after clearChat', async () => {
    // 开场发送无反应根因：init 流程 clearChat 把 currentArchive 清成 null 后，
    // ensureActiveArchive 的"已有存档"分支不重设 → startStory guard 静默 return
    apiMocks.getArchives.mockResolvedValue({
      data: [
        {
          id: 2,
          story_id: 1,
          name: 'A2',
          state_data: {},
          story_state: {},
          memory_log: [],
          created_at: '2026-04-16T00:00:00Z',
          updated_at: '2026-04-16T00:00:00Z',
        },
      ],
    })
    // store 层包装会 fire-and-forget 重拉存档以同步 currentNotebook
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

    const store = useChatStore()
    store.clearChat()

    const result = await store.ensureActiveArchive(1)

    expect(result.isNew).toBe(false)
    expect(result.archiveId).toBe(2)
    expect(store.currentArchive?.id).toBe(2)
  })

  it('clearChat resets currentNotebook to null', () => {
    const store = useChatStore()
    store.currentNotebook = {
      world_line: [{ text: '残留', status: 'active' }],
      character_line: [],
      relationship_line: [],
    } as any

    store.clearChat()

    expect(store.currentNotebook).toBeNull()
  })

  it('ensureActiveArchive fast path syncs currentNotebook from getArchive', async () => {
    // 已有存档快速路径只赋值不 fetch，notebook 会残留上一条存档的值；
    // store 层包装应重拉 getArchive 同步 currentNotebook
    apiMocks.getArchives.mockResolvedValue({
      data: [
        {
          id: 2,
          story_id: 1,
          name: 'A2',
          state_data: {},
          story_state: {},
          memory_log: [],
          created_at: '2026-04-16T00:00:00Z',
          updated_at: '2026-04-16T00:00:00Z',
        },
      ],
    })
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
        notebook: {
          world_line: [{ text: '世界线记录', status: 'active' }],
          character_line: [],
          relationship_line: [],
        },
      },
    })

    const store = useChatStore()
    store.clearChat()
    // 残留上一条存档的笔记本
    store.currentNotebook = {
      world_line: [{ text: '上一条存档的残留', status: 'closed' }],
      character_line: [],
      relationship_line: [],
    } as any

    const result = await store.ensureActiveArchive(1)

    expect(result.isNew).toBe(false)
    expect(result.archiveId).toBe(2)
    // fire-and-forget 拉取完成后同步
    await vi.waitFor(() => {
      expect(store.currentNotebook).toEqual({
        world_line: [{ text: '世界线记录', status: 'active' }],
        character_line: [],
        relationship_line: [],
      })
    })
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

  it('does not take option lock when option send early-returns while already sending (Bug #28)', async () => {
    apiMocks.getArchives.mockResolvedValue({ data: [] })

    const store = useChatStore()
    store.currentArchive = { id: 1, story_id: 1 } as any
    store.currentOptions = ['观察四周', '直接追问']
    ;(store as any).sending = true // 模拟另一路流式正在进行，sendStream 将 early return

    await store.sendStream('直接追问', { fromOption: true })

    // 治本案：guard 命中时锁根本不会被取，选项区不可能锁死
    expect(store.optionsLocked).toBe(false)
    expect(store.lockedOption).toBe('')
    expect(store.currentOptions).toEqual(['观察四周', '直接追问'])
  })

  it('ignores stale loadArchive responses when switching archives quickly (Bug #27)', async () => {
    const archiveA = {
      id: 1,
      story_id: 1,
      name: 'A',
      state_data: {},
      story_state: {},
      memory_log: [],
      created_at: '2026-04-16T00:00:00Z',
      updated_at: '2026-04-16T00:00:00Z',
    }
    const archiveB = { ...archiveA, id: 2, name: 'B' }
    const msgA = {
      id: 101,
      archive_id: 1,
      role: 'assistant',
      content: 'A 的消息',
      state_snapshot: {},
      story_state: {},
      options: [],
      memory_update: [],
      created_at: '2026-04-16T00:00:00Z',
    }
    const msgB = { ...msgA, id: 201, archive_id: 2, content: 'B 的消息' }

    // getMessages(A) 故意晚于 getMessages(B) 返回，模拟快速切档时的响应乱序
    let resolveA: (v: any) => void = () => {}
    apiMocks.getArchive.mockImplementation(async (id: number) => ({
      data: id === 1 ? archiveA : archiveB,
    }))
    apiMocks.getMessages.mockImplementation(
      (id: number) =>
        new Promise((resolve) => {
          if (id === 1) resolveA = resolve
          else resolve({ data: [msgB] })
        }),
    )

    const store = useChatStore()
    const p1 = store.loadArchive(1)
    const p2 = store.loadArchive(2)
    await p2 // B 先完整落地
    resolveA({ data: [msgA] }) // A 的迟到响应
    await p1

    expect(store.currentArchive?.id).toBe(2)
    expect(store.messages.map((m) => m.content)).toEqual(['B 的消息'])
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

import type { StoryNotebook } from '../types/notebook'

describe('notebook types', () => {
  it('accepts valid story notebook shape', () => {
    const nb: StoryNotebook = {
      world_line: [{ text: '魔教攻入皇城', status: 'active' }],
      character_line: [],
      relationship_line: [{ text: '师徒反目', status: 'closed' }],
    }
    expect(nb.world_line[0].status).toBe('active')
  })
})
