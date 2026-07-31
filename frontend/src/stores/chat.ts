import { defineStore } from 'pinia'
import { ref, shallowRef, triggerRef, readonly } from 'vue'
import { debounce } from 'lodash'
import {
  createArchive,
  generateStateBroadcast as apiGenerateStateBroadcast,
  getArchive,
  getArchives,
  getMessages,
  deleteMessages as apiDeleteMessages,
} from '../api'
import type { ChatStreamTailData } from '../types/sse'
import type { StoryNotebook } from '../types/notebook'
import {
  normalizePlotLabel,
  sanitizeAiDisplayText,
  sanitizeAiStringList,
  stripTrailingOptionBlock,
} from '../utils/text'
import { generateId } from '../utils/id'
import { useChatUI } from '../composables/useChatUI'
import { useChatOptions } from '../composables/useChatOptions'
import { useChatArchive } from '../composables/useChatArchive'
import { useChatRecall } from '../composables/useChatRecall'
import { useChatImage } from '../composables/useChatImage'
import { useChatStream } from '../composables/useChatStream'

export interface ChatMsg {
  id: number | string
  archive_id: number
  role: 'user' | 'assistant'
  content: string
  state_snapshot: Record<string, any>
  story_state: Record<string, any>
  options: string[]
  memory_update: string[]
  created_at: string
  plot_label?: string | null
  model_name?: string
  persisted?: boolean
  removing?: boolean
  tailApplied?: boolean
  imageUrl?: string
  imageLoading?: boolean
  imageError?: string
  isStateBroadcast?: boolean
}

export interface Archive {
  id: number
  story_id: number
  name: string
  state_data: Record<string, any>
  story_state: Record<string, any>
  memory_log: string[]
  created_at: string
  updated_at: string
  first_message?: string
  notebook?: Record<string, unknown> | null
}

// Re-export for use by composables
export function normalizeIncomingMessage(message: Record<string, unknown>): ChatMsg {
  const role = (message.role as 'user' | 'assistant') || 'assistant'
  const rawContent = String(message.content || '')
  return {
    ...message,
    role,
    content:
      role === 'assistant'
        ? stripTrailingOptionBlock(sanitizeAiDisplayText(rawContent))
        : rawContent,
    options: sanitizeAiStringList(message.options as string[] | undefined),
    plot_label: normalizePlotLabel(message.plot_label as string | null | undefined),
    imageUrl: (message.imageUrl ?? message.image_url) as string | undefined,
    isStateBroadcast: !!(message.isStateBroadcast ?? message.is_state_broadcast),
    persisted: true,
  } as ChatMsg
}

export const useChatStore = defineStore('chat', () => {
  // --- Core state ---
  const messages = ref<ChatMsg[]>([])
  const currentState = ref<Record<string, any>>({})
  const currentStoryState = ref<Record<string, any>>({})
  const currentMemoryLog = ref<string[]>([])
  const currentNotebook = ref<StoryNotebook | null>(null)

  // --- Composable modules ---
  const optionsModule = useChatOptions()
  const uiModule = useChatUI()
  const archiveModule = useChatArchive()
  const imageModule = useChatImage({
    messages,
    currentArchive: archiveModule.currentArchive as unknown as { value: Archive | null },
  })

  // --- Highlight terms debounce (kept here for applyTailToAssistant) ---
  const highlightedTerms = shallowRef<string[]>([])
  const setHighlightedTermsDebounced = debounce((terms: string[]) => {
    highlightedTerms.value = terms
    triggerRef(highlightedTerms)
  }, 100)

  // --- Internal helpers ---
  function updateMessageById(messageId: string | number, updater: (message: ChatMsg) => void) {
    const target = messages.value.find((message) => message.id === messageId)
    if (!target) return
    updater(target)
  }

  function markMessagesPersisted(messageIds: Array<string | number>) {
    const idSet = new Set(messageIds)
    for (const message of messages.value) {
      if (idSet.has(message.id)) {
        message.persisted = true
      }
    }
  }

  function applyTailToAssistant(messageId: string | number, tail: ChatStreamTailData) {
    // 如果 tail 返回了真实的 message_id，更新消息的 ID（从临时 UUID 变为持久化的 numeric ID）
    const realMessageId = tail.message_id ?? messageId
    updateMessageById(messageId, (message) => {
      message.id = realMessageId
      message.content = stripTrailingOptionBlock(
        sanitizeAiDisplayText(tail.reply_text || message.content),
      )
      message.state_snapshot = tail.character_state || {}
      message.story_state = tail.story_state || {}
      message.options = []
      message.memory_update = tail.memory_update || []
      message.plot_label = normalizePlotLabel(tail.plot_label)
      if (tail.model_name) message.model_name = tail.model_name
      message.tailApplied = true
    })
    setHighlightedTermsDebounced(tail.highlight_terms || [])
    // 更新相邻 user 消息的 ID（user 消息在 assistant 消息之前，紧邻）
    if (tail.user_id) {
      const assistantIdx = messages.value.findIndex(
        (m) => m.id === realMessageId || m.id === messageId,
      )
      if (assistantIdx > 0 && messages.value[assistantIdx - 1].role === 'user') {
        messages.value[assistantIdx - 1].id = tail.user_id
      }
    }
    markMessagesPersisted([realMessageId])
    if (tail.notebook) currentNotebook.value = tail.notebook as unknown as StoryNotebook
  }

  // --- Recall module ---
  const recallModule = useChatRecall({
    messages,
    currentArchive: archiveModule.currentArchive as unknown as { value: Archive | null },
    currentState,
    currentStoryState,
    currentMemoryLog,
    currentNotebook,
    streaming: uiModule.streaming,
    sending: uiModule.sending,
    awaitingTail: uiModule.awaitingTail as unknown as { value: boolean },
    onFinishOptionLock: (s) => optionsModule.finishOptionLock(s),
    onClearOptions: () => optionsModule.dismissCurrentOptions(),
    onClearHighlightTerms: () => {
      highlightedTerms.value = []
      setHighlightedTermsDebounced.cancel()
    },
  })

  // --- Stream module ---
  const streamModule = useChatStream({
    messages,
    currentState,
    currentStoryState,
    currentMemoryLog,
    currentArchive: archiveModule.currentArchive as unknown as { value: Archive | null },
    sending: uiModule.sending,
    streaming: uiModule.streaming,
    awaitingTail: uiModule.awaitingTail as unknown as { value: boolean },
    optionsLocked: optionsModule.optionsLocked,
    autoGenerateOptions: optionsModule.autoGenerateOptions,
    onApplyTail: applyTailToAssistant,
    onAutoGenerateOptions: (archiveId) => optionsModule.autoGenerateOptionsAsync(archiveId),
    onRefreshArchives: (storyId) => fetchArchives(storyId),
    onBeginOptionLock: (option) => optionsModule.beginOptionLock(option),
    onFinishOptionLock: (s) => optionsModule.finishOptionLock(s),
    onClearOptions: () => optionsModule.dismissCurrentOptions(),
  })

  // --- Archive actions ---
  async function fetchArchives(storyId: number) {
    const { data } = await getArchives(storyId)
    archiveModule.archives.value = data
  }

  async function startNewArchive(storyId: number, name: string = '默认会话') {
    try {
      streamModule.abortStream()
    } catch {
      // stream may already be inactive
    }
    imageModule.abortInFlightImageRequest()
    const { data } = await createArchive(storyId, name)
    archiveModule.currentArchive.value = data
    currentState.value = data.state_data || {}
    currentStoryState.value = data.story_state || {}
    currentMemoryLog.value = data.memory_log || []
    currentNotebook.value = (data.notebook ?? null) as StoryNotebook | null
    messages.value = []
    optionsModule.dismissCurrentOptions()
    optionsModule.optionsLocked.value = false
    optionsModule.generatingOptions.value = false
    optionsModule.generatingOptionsFailed.value = false
    optionsModule.awaitingOptions.value = false
    uiModule.sending.value = false
    uiModule.streaming.value = false
    uiModule.awaitingTail.value = false
    uiModule.generatingStateBroadcast.value = false
    uiModule.recallInProgress.value = false
    optionsModule.lastOptionsSnapshot.value = []
    optionsModule.optionsHistory.value = []
    highlightedTerms.value = []
    await fetchArchives(storyId)
    return data
  }

  // Bug #27：请求版本号防快速切档竞态——模式对齐 story.ts requestVersion。
  // 每次 loadArchive 递增；await 后版本不一致即视为过期响应，丢弃不应用。
  let loadArchiveVersion = 0

  async function loadArchive(archiveId: number) {
    const myVersion = ++loadArchiveVersion
    try {
      streamModule.abortStream()
    } catch {
      // stream may already be inactive
    }
    const previousArchiveId = archiveModule.currentArchive.value?.id
    if (previousArchiveId !== undefined && previousArchiveId !== archiveId) {
      imageModule.abortInFlightImageRequest()
    }
    const { data: archive } = await getArchive(archiveId)
    if (myVersion !== loadArchiveVersion) return null // 已有更新的切档请求，丢弃过期响应
    archiveModule.currentArchive.value = archive
    currentState.value = archive.state_data || {}
    currentStoryState.value = archive.story_state || {}
    currentMemoryLog.value = archive.memory_log || []
    currentNotebook.value = (archive.notebook ?? null) as StoryNotebook | null

    const { data: msgs } = await getMessages(archiveId)
    if (myVersion !== loadArchiveVersion) return null // 同上：旧 archive 的消息不得覆盖新 archive
    const normalizedMsgs = (Array.isArray(msgs) ? msgs : []).map((m) =>
      normalizeIncomingMessage(m as Record<string, unknown>),
    )
    messages.value = normalizedMsgs

    const lastAi = [...normalizedMsgs].reverse().find((m: ChatMsg) => m.role === 'assistant')
    optionsModule.dismissCurrentOptions()
    currentStoryState.value = lastAi?.story_state || currentStoryState.value
    highlightedTerms.value = []
    optionsModule.optionsLocked.value = false
    optionsModule.generatingOptions.value = false
    optionsModule.generatingOptionsFailed.value = false
    optionsModule.awaitingOptions.value = false
    uiModule.sending.value = false
    uiModule.streaming.value = false
    uiModule.awaitingTail.value = false
    uiModule.generatingStateBroadcast.value = false
    uiModule.recallInProgress.value = false
    return archive
  }

  // Task 7 审查修复：ensureActiveArchive 的"已有存档"快速路径直接赋值不 fetch，
  // currentNotebook 会残留上一条存档的笔记本。这里在 store 层包装原实现：
  // 非新档路径用 getArchive 重拉并同步（fire-and-forget，与 useChatRecall 的撤回同步同模式）。
  // 不触碰 loadArchive 的 Bug #27 版本号防竞态逻辑，两者互不干扰。
  async function ensureActiveArchive(
    storyId: number,
  ): Promise<{ archiveId: number; isNew: boolean }> {
    const result = await archiveModule.ensureActiveArchive(storyId)
    if (!result.isNew) {
      const archiveId = archiveModule.currentArchive.value?.id
      if (archiveId) {
        getArchive(archiveId).then(({ data }) => {
          currentNotebook.value = (data.notebook ?? null) as StoryNotebook | null
        })
      }
    }
    return result
  }

  // --- Options helpers ---
  function beginOptionLock(option: string) {
    return optionsModule.beginOptionLock(option)
  }

  // --- Manual generate options ---
  async function manualGenerateOptions(count: number = 3, guidance: string = '') {
    if (!archiveModule.currentArchive.value || uiModule.sending.value) return []
    return optionsModule.manualGenerateOptions(
      archiveModule.currentArchive.value.id,
      count,
      guidance,
    )
  }

  async function autoGenerateOptionsAsync() {
    if (!archiveModule.currentArchive.value) return
    await optionsModule.autoGenerateOptionsAsync(archiveModule.currentArchive.value.id)
  }

  // --- State broadcast ---
  async function generateStateBroadcast() {
    if (
      !archiveModule.currentArchive.value ||
      uiModule.sending.value ||
      uiModule.streaming.value ||
      uiModule.generatingStateBroadcast.value
    )
      return
    uiModule.generatingStateBroadcast.value = true
    try {
      const { data } = await apiGenerateStateBroadcast(archiveModule.currentArchive.value.id)
      const content = stripTrailingOptionBlock(sanitizeAiDisplayText(data.content))
      if (!content) {
        throw new Error('状态播报内容已被拦截，请重试')
      }
      const newMsg: ChatMsg = {
        id: generateId(),
        archive_id: archiveModule.currentArchive.value.id,
        role: 'assistant',
        content,
        isStateBroadcast: true,
        state_snapshot: { ...currentState.value },
        story_state: { ...currentStoryState.value },
        options: [],
        memory_update: [],
        created_at: new Date().toISOString(),
        persisted: true,
      }
      messages.value.push(newMsg)
      return content
    } finally {
      uiModule.generatingStateBroadcast.value = false
    }
  }

  // --- Clear chat ---
  function clearChat() {
    try {
      streamModule.abortStream()
    } catch {
      // stream may already be inactive
    }
    imageModule.abortInFlightImageRequest()
    messages.value = []
    archiveModule.currentArchive.value = null
    currentState.value = {}
    currentStoryState.value = {}
    currentMemoryLog.value = []
    currentNotebook.value = null
    optionsModule.dismissCurrentOptions()
    optionsModule.optionsLocked.value = false
    optionsModule.generatingOptions.value = false
    optionsModule.generatingOptionsFailed.value = false
    optionsModule.awaitingOptions.value = false
    uiModule.sending.value = false
    uiModule.streaming.value = false
    uiModule.awaitingTail.value = false
    uiModule.generatingStateBroadcast.value = false
    uiModule.recallInProgress.value = false
    highlightedTerms.value = []
    optionsModule.lastOptionsSnapshot.value = []
    optionsModule.optionsHistory.value = []
    setHighlightedTermsDebounced.cancel()
  }

  // --- Delete messages ---
  async function deleteMessages(messageIds: (number | string)[]) {
    if (!archiveModule.currentArchive.value) return
    // 转换为数字并过滤无效值
    const numericIds = messageIds
      .map((id) => Number(id))
      .filter((id) => Number.isInteger(id) && id > 0)
    if (numericIds.length === 0) return
    // 保存原始消息用于回滚
    const originalMsgMap = new Map<number, ChatMsg>()
    for (const msg of messages.value) {
      if (numericIds.includes(msg.id as number)) {
        originalMsgMap.set(msg.id as number, { ...msg })
      }
    }

    // Mark as removing to trigger animation
    for (const id of numericIds) {
      updateMessageById(id, (msg) => {
        msg.removing = true
      })
    }
    try {
      await apiDeleteMessages(archiveModule.currentArchive.value.id, numericIds)
      // Remove from array after API call succeeds
      messages.value = messages.value.filter((msg) => !numericIds.includes(msg.id as number))
    } catch (error) {
      // Revert removing state AND restore messages
      for (const id of numericIds) {
        const original = originalMsgMap.get(id)
        if (original) {
          const idx = messages.value.findIndex((msg) => msg.id === id)
          if (idx === -1) {
            messages.value.push(original)
          } else {
            messages.value[idx] = original
          }
        }
      }
      throw error
    }
  }

  // --- sendStream：选项锁生命周期已收口进 streamModule.sendStream（Bug #28），直接透出 ---
  return {
    // messages (shared ref)
    messages,
    // archive
    archives: archiveModule.archives,
    currentArchive: archiveModule.currentArchive,
    fetchArchives,
    startNewArchive,
    ensureActiveArchive,
    loadArchive,
    // state
    currentState,
    currentStoryState,
    currentMemoryLog,
    currentNotebook,
    // options
    currentOptions: optionsModule.currentOptions,
    optionsLocked: optionsModule.optionsLocked,
    lockedOption: optionsModule.lockedOption,
    generatingOptions: optionsModule.generatingOptions,
    generatingOptionsFailed: optionsModule.generatingOptionsFailed,
    awaitingOptions: optionsModule.awaitingOptions,
    autoGenerateOptions: optionsModule.autoGenerateOptions,
    setAutoGenerateOptions: optionsModule.setAutoGenerateOptions,
    lastOptionsSnapshot: optionsModule.lastOptionsSnapshot,
    beginOptionLock,
    finishOptionLock: optionsModule.finishOptionLock,
    dismissCurrentOptions: optionsModule.dismissCurrentOptions,
    optionsHistoryDepth: optionsModule.optionsHistoryDepth,
    restorePreviousOptions: optionsModule.restorePreviousOptions,
    manualGenerateOptions,
    autoGenerateOptionsAsync,
    // UI state
    sending: uiModule.sending,
    streaming: uiModule.streaming,
    awaitingTail: readonly(uiModule.awaitingTail),
    loading: uiModule.loading,
    generatingStateBroadcast: uiModule.generatingStateBroadcast,
    recallInProgress: uiModule.recallInProgress,
    streamingFollow: readonly(uiModule.streamingFollow),
    setStreamingFollow: uiModule.setStreamingFollow,
    // recall
    recallLastRound: recallModule.recallLastRound,
    confirmRecall: recallModule.confirmRecall,
    canRecallLastRound: readonly(recallModule.canRecallLastRound),
    // image
    isGeneratingImage: imageModule.isGeneratingImage,
    generatingImageMsgId: imageModule.generatingImageMsgId,
    generateImage: imageModule.generateImage,
    // stream
    startStory: streamModule.startStory,
    sendStream: streamModule.sendStream,
    abortStream: streamModule.abortStream,
    generateStateBroadcast,
    // highlight
    highlightedTerms: readonly(highlightedTerms),
    // clear
    clearChat,
    // delete
    deleteMessages,
  }
})
