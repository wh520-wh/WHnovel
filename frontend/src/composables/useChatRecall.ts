import { computed, ref } from 'vue'
import { deleteLastAiMessage } from '../api'
import type { ChatMsg, Archive } from '../stores/chat'

export function useChatRecall(params: {
  messages: { value: ChatMsg[] }
  currentArchive: { value: Archive | null }
  currentState: { value: Record<string, any> }
  currentStoryState: { value: Record<string, any> }
  currentMemoryLog: { value: string[] }
  onFinishOptionLock: (success: boolean) => void
  onClearOptions: () => void
  onClearHighlightTerms: () => void
}) {
  const {
    messages,
    currentArchive,
    currentState,
    currentStoryState,
    currentMemoryLog,
    onFinishOptionLock,
    onClearOptions,
    onClearHighlightTerms,
  } = params
  const recallInProgress = ref(false)

  function isMessagePersisted(message: ChatMsg | undefined): boolean {
    if (!message) return false
    if (typeof message.persisted === 'boolean') return message.persisted
    return typeof message.id === 'number'
  }

  function getLastAssistantIndex(): number {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'assistant') {
        return i
      }
    }
    return -1
  }

  function removeMessagesById(messageIds: (string | number)[]) {
    const idSet = new Set(messageIds)
    messages.value = messages.value.filter((message) => !idSet.has(message.id))
  }

  async function recallLastRound(): Promise<(string | number)[]> {
    if (!currentArchive.value) return []
    if (recallInProgress.value) return []
    recallInProgress.value = true
    let markedIds: (string | number)[] = []
    try {
      const lastAiIdx = getLastAssistantIndex()
      if (lastAiIdx === -1) return []

      const lastAiMsg = messages.value[lastAiIdx]
      if (!isMessagePersisted(lastAiMsg)) {
        console.warn('[recallLastRound] 最后一条消息尚未确认落库，跳过撤回')
        return []
      }
      const userMsgId: string | number | null =
        lastAiIdx > 0 && messages.value[lastAiIdx - 1].role === 'user'
          ? messages.value[lastAiIdx - 1].id
          : null

      await deleteLastAiMessage(currentArchive.value.id)

      markedIds = userMsgId !== null ? [lastAiMsg.id, userMsgId] : [lastAiMsg.id]
      for (const msg of messages.value) {
        if (markedIds.includes(msg.id)) {
          msg.removing = true
        }
      }

      onFinishOptionLock(false)
      onClearOptions()

      return markedIds
    } catch (e) {
      for (const msg of messages.value) {
        if (markedIds.includes(msg.id)) {
          msg.removing = false
        }
      }
      throw e
    } finally {
      recallInProgress.value = false
    }
  }

  function confirmRecall(messageIds: (string | number)[]) {
    removeMessagesById(messageIds)
    onClearHighlightTerms()

    // Restore state from the last remaining assistant message
    const lastAi = [...messages.value].reverse().find((m) => m.role === 'assistant')
    if (lastAi) {
      currentState.value = lastAi.state_snapshot || {}
      currentStoryState.value = lastAi.story_state || {}
    } else {
      currentState.value = {}
      currentStoryState.value = {}
      currentMemoryLog.value = []
    }
  }

  const canRecallLastRound = computed(() => {
    if (!currentArchive.value) return false
    const lastAiIdx = getLastAssistantIndex()
    if (lastAiIdx === -1) return false
    return isMessagePersisted(messages.value[lastAiIdx])
  })

  return {
    recallInProgress,
    recallLastRound,
    confirmRecall,
    canRecallLastRound,
  }
}
