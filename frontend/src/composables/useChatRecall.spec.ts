import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useChatRecall } from './useChatRecall'
import { deleteLastAiMessage } from '../api'

vi.mock('../api', () => ({
  deleteLastAiMessage: vi.fn(async () => {}),
  getArchive: vi.fn(async () => ({ data: { notebook: null } })),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

function makeMsg(
  overrides: Partial<{
    id: number | string
    role: 'user' | 'assistant'
    state_snapshot: Record<string, any>
    story_state: Record<string, any>
    memory_update: string[]
    persisted: boolean
  }> = {},
) {
  return {
    id: overrides.id ?? 1,
    archive_id: 1,
    role: overrides.role ?? 'assistant',
    content: 'test',
    state_snapshot: overrides.state_snapshot ?? {},
    story_state: overrides.story_state ?? {},
    options: [] as string[],
    memory_update: overrides.memory_update ?? [],
    created_at: new Date().toISOString(),
    persisted: overrides.persisted ?? true,
  }
}

describe('useChatRecall', () => {
  it('confirmRecall restores state from last remaining assistant message', async () => {
    const messages = ref([
      makeMsg({ id: 1, role: 'user', persisted: true }),
      makeMsg({
        id: 'a1',
        role: 'assistant',
        persisted: true,
        state_snapshot: { emotion: 'happy' },
        story_state: { chapter: '第一章' },
      }),
      makeMsg({ id: 3, role: 'user', persisted: true }),
      makeMsg({
        id: 'a2',
        role: 'assistant',
        persisted: true,
        state_snapshot: { emotion: 'sad' },
        story_state: { chapter: '第二章' },
      }),
    ])
    const currentArchive = ref({ id: 1 } as any)
    const currentState = ref<Record<string, any>>({ emotion: 'sad' })
    const currentStoryState = ref<Record<string, any>>({ chapter: '第二章' })
    const currentMemoryLog = ref<string[]>(['mem1', 'mem2'])

    const recall = useChatRecall({
      messages,
      currentArchive,
      currentState,
      currentStoryState,
      currentMemoryLog,
      currentNotebook: ref<Record<string, unknown> | null>(null),
      streaming: ref(false),
      sending: ref(false),
      awaitingTail: ref(false),
      onFinishOptionLock: vi.fn(),
      onClearOptions: vi.fn(),
      onClearHighlightTerms: vi.fn(),
    })

    // Simulate: recall last round (messages 3 and a2), then confirm
    const markedIds = await recall.recallLastRound()
    recall.confirmRecall(markedIds)

    // State should roll back to message a1's snapshot
    expect(currentState.value).toEqual({ emotion: 'happy' })
    expect(currentStoryState.value).toEqual({ chapter: '第一章' })
    expect(messages.value).toHaveLength(2)
  })

  it('confirmRecall clears state when no messages remain', async () => {
    const messages = ref([
      makeMsg({ id: 1, role: 'user', persisted: true }),
      makeMsg({ id: 'a1', role: 'assistant', persisted: true }),
    ])
    const currentArchive = ref({ id: 1 } as any)
    const currentState = ref({ emotion: 'happy' })
    const currentStoryState = ref({ chapter: '第一章' })
    const currentMemoryLog = ref<string[]>(['mem1'])

    const recall = useChatRecall({
      messages,
      currentArchive,
      currentState,
      currentStoryState,
      currentMemoryLog,
      currentNotebook: ref<Record<string, unknown> | null>(null),
      streaming: ref(false),
      sending: ref(false),
      awaitingTail: ref(false),
      onFinishOptionLock: vi.fn(),
      onClearOptions: vi.fn(),
      onClearHighlightTerms: vi.fn(),
    })

    const markedIds = await recall.recallLastRound()
    recall.confirmRecall(markedIds)

    expect(currentState.value).toEqual({})
    expect(currentStoryState.value).toEqual({})
    expect(currentMemoryLog.value).toEqual([])
  })

  it('blocks recall while streaming / sending / awaitingTail (Bug #29)', async () => {
    const messages = ref([
      makeMsg({ id: 1, role: 'user', persisted: true }),
      makeMsg({ id: 'a1', role: 'assistant', persisted: true }),
    ])
    const currentArchive = ref({ id: 1 } as any)
    const streaming = ref(true)
    const sending = ref(false)
    const awaitingTail = ref(false)

    const recall = useChatRecall({
      messages,
      currentArchive,
      currentState: ref({}),
      currentStoryState: ref({}),
      currentMemoryLog: ref([]),
      currentNotebook: ref<Record<string, unknown> | null>(null),
      streaming,
      sending,
      awaitingTail,
      onFinishOptionLock: vi.fn(),
      onClearOptions: vi.fn(),
      onClearHighlightTerms: vi.fn(),
    })

    // 流式进行中：入口与函数双守卫
    expect(recall.canRecallLastRound.value).toBe(false)
    expect(await recall.recallLastRound()).toEqual([])

    // awaitingTail 窗口（text_end 已到、tail 未到）同样禁止
    streaming.value = false
    awaitingTail.value = true
    expect(recall.canRecallLastRound.value).toBe(false)
    expect(await recall.recallLastRound()).toEqual([])

    // sending 窗口同样禁止
    awaitingTail.value = false
    sending.value = true
    expect(recall.canRecallLastRound.value).toBe(false)
    expect(await recall.recallLastRound()).toEqual([])

    // 全部解除后恢复可用
    sending.value = false
    expect(recall.canRecallLastRound.value).toBe(true)

    expect(deleteLastAiMessage).not.toHaveBeenCalled()
  })
})
