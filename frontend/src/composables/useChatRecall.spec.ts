import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useChatRecall } from './useChatRecall'

vi.mock('../api', () => ({
  deleteLastAiMessage: vi.fn(async () => {}),
}))

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
})
