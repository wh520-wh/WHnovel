import { startChatStream, sendMessageStream, getArchive, getArchives } from '../api'
import type { ChatStreamEvent, ChatStreamTailData } from '../types/sse'
import type { ChatMsg, Archive } from '../stores/chat'
import { sanitizeAiDisplayText, stripTrailingOptionBlock } from '../utils/text'
import { generateId } from '../utils/id'

function makeTempMsg(archiveId: number, role: 'user' | 'assistant', content: string): ChatMsg {
  return {
    id: generateId(),
    archive_id: archiveId,
    role,
    content,
    state_snapshot: {},
    story_state: {},
    options: [],
    memory_update: [],
    created_at: new Date().toISOString(),
    persisted: false,
  }
}

let streamAbortController: AbortController | null = null

export function useChatStream(params: {
  messages: { value: ChatMsg[] }
  currentState: { value: Record<string, any> }
  currentStoryState: { value: Record<string, any> }
  currentMemoryLog: { value: string[] }
  currentArchive: { value: Archive | null }
  sending: { value: boolean }
  streaming: { value: boolean }
  awaitingTail: { value: boolean }
  optionsLocked: { value: boolean }
  autoGenerateOptions: { value: boolean }
  onApplyTail: (messageId: string | number, tail: ChatStreamTailData) => void
  onAutoGenerateOptions: (archiveId: number) => void
  onFinishOptionLock: (success: boolean) => void
  onClearOptions: () => void
}) {
  const {
    messages, currentState, currentStoryState, currentMemoryLog, currentArchive,
    sending, streaming, awaitingTail, optionsLocked, autoGenerateOptions,
    onApplyTail, onAutoGenerateOptions, onFinishOptionLock, onClearOptions,
  } = params

  function abortStream() {
    streamAbortController?.abort()
    streamAbortController = null
  }

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

  // Shared helper: applies tail data to store state (character_state, story_state, memory_log, archive refresh)
  async function applyTailToStoreState(tail: ChatStreamTailData, archiveId: number) {
    currentState.value = tail.character_state || {}
    currentStoryState.value = tail.story_state || {}
    currentMemoryLog.value = [...currentMemoryLog.value, ...(tail.memory_update || [])].slice(-100)

    const finalArchiveId = tail.archive_id || archiveId
    try {
      if (finalArchiveId !== archiveId) {
        const { data: archive } = await getArchive(finalArchiveId)
        currentArchive.value = archive
      }
      if (currentArchive.value) {
        await getArchives(currentArchive.value.story_id)
      }
    } catch {
      // archive refresh failed; state was already updated above, non-fatal
    }
  }

  // Shared helper: wraps caught error with partial/commit semantics
  function wrapStreamError(
    e: unknown,
    opts: { committed: boolean; draftPersisted: boolean; textEnded: boolean; prefix: string },
  ): never {
    const { committed, draftPersisted, textEnded, prefix } = opts
    const isPartial = (e as { partial?: boolean } | null)?.partial === true
    if (committed && !isPartial) {
      let message: string
      if (draftPersisted) {
        message = `${prefix}正文已保留，结构化数据生成失败，可继续输入或手动生成选项`
      } else if (textEnded) {
        message = `${prefix}正文已显示但后端响应未按时结束，可继续输入或稍后刷新`
      } else {
        message = `${prefix}已显示但后端响应未按时结束，可继续输入或稍后刷新`
      }
      const wrapped = new Error(message) as Error & { partial?: boolean; cause?: unknown }
      wrapped.partial = true
      wrapped.cause = e
      throw wrapped
    }
    throw e
  }

  // Shared SSE event handler for both startStory and sendStream
  function _handleStreamEvents(params: {
    tempAssistantId: string | number
    optimisticUserId: string | number
    tailRef: { get value(): ChatStreamTailData | null; set value(v: ChatStreamTailData | null) }
    streamErrorRef: { get value(): string; set value(v: string) }
    draftPersistedRef: { get value(): boolean; set value(v: boolean) }
    textEndedRef: { get value(): boolean; set value(v: boolean) }
    fallbackMessage: string
  }) {
    const {
      tempAssistantId, optimisticUserId,
      tailRef, streamErrorRef, draftPersistedRef, textEndedRef, fallbackMessage,
    } = params
    return (evt: ChatStreamEvent) => {
      if (evt.event === 'delta') {
        updateMessageById(tempAssistantId, (message) => {
          if (message.tailApplied) return
          message.content += evt.data?.text || ''
        })
        return
      }
      if (evt.event === 'text_end') {
        streaming.value = false
        awaitingTail.value = true
        textEndedRef.value = true
        return
      }
      if (evt.event === 'tail') {
        tailRef.value = evt.data
        try {
          onApplyTail(tempAssistantId, tailRef.value)
        } finally {
          markMessagesPersisted([optimisticUserId, tempAssistantId])
        }
        streaming.value = false
        awaitingTail.value = false
        return
      }
      if (evt.event === 'error') {
        if (tailRef.value) return
        if (evt.data?.draft) {
          // 更新 user 消息 ID
          if (evt.data?.user_id) {
            updateMessageById(optimisticUserId, (message) => {
              message.id = evt.data.user_id!
            })
          }
          // 更新 assistant 消息 ID
          if (evt.data?.message_id) {
            updateMessageById(tempAssistantId, (message) => {
              message.id = evt.data.message_id!
            })
          }
          markMessagesPersisted([optimisticUserId, tempAssistantId])
          draftPersistedRef.value = true
          return
        }
        streamErrorRef.value = handleStreamError(tempAssistantId, evt, fallbackMessage)
      }
    }
  }

  function handleStreamError(
    tempAssistantId: string | number,
    evt: Extract<ChatStreamEvent, { event: 'error' }>,
    fallbackMessage: string,
  ): string {
    const code = evt.data?.code
    const message = evt.data?.message || fallbackMessage
    if (code === 'STREAM_BODY_POLLUTED') {
      const idSet = new Set([tempAssistantId])
      messages.value = messages.value.filter((message) => !idSet.has(message.id))
      return '检测到结构化内容混入正文，已拦截本轮回复，请重试'
    }
    return message
  }

  async function startStory(storyId: number, openingRequirement: string) {
    if (!currentArchive.value || sending.value) return
    sending.value = true
    streaming.value = true

    streamAbortController = new AbortController()
    const signal = streamAbortController.signal

    const archiveId = currentArchive.value.id
    const optimisticUser = makeTempMsg(archiveId, 'user', openingRequirement)
    const tempAssistant = makeTempMsg(archiveId, 'assistant', '')
    const tempAssistantId = tempAssistant.id
    messages.value.push(optimisticUser)
    messages.value.push(tempAssistant)

    let tail: ChatStreamTailData | null = null
    let streamError = ''
    let draftPersisted = false
    let textEnded = false
    try {
      await startChatStream(storyId, openingRequirement, archiveId, _handleStreamEvents({
        tempAssistantId,
        optimisticUserId: optimisticUser.id,
        tailRef: { get value() { return tail }, set value(v) { tail = v } },
        streamErrorRef: { get value() { return streamError }, set value(v) { streamError = v } },
        draftPersistedRef: { get value() { return draftPersisted }, set value(v) { draftPersisted = v } },
        textEndedRef: { get value() { return textEnded }, set value(v) { textEnded = v } },
        fallbackMessage: '开场生成失败',
      }), signal)

      if (streamError) throw new Error(streamError)
      if (!tail) {
        if (draftPersisted) {
          const partialErr = new Error('开场正文已保留，结构化数据生成失败，可继续输入或重试') as Error & { partial?: boolean }
          partialErr.partial = true
          throw partialErr
        }
        throw new Error('开场生成失败：未收到结构化尾包')
      }

      await applyTailToStoreState(tail, archiveId)

      // 流完全结束后自动生成选项（避免与 tail 竞态）
      if (autoGenerateOptions.value && !optionsLocked.value) {
        onAutoGenerateOptions(archiveId)
      }
    } catch (e) {
      throw wrapStreamError(e, {
        committed: !!(tail || textEnded || draftPersisted),
        draftPersisted,
        textEnded,
        prefix: '开场',
      })
    } finally {
      streamAbortController = null
      streaming.value = false
      awaitingTail.value = false
      sending.value = false
    }
  }

  async function sendStream(text: string, options: { fromOption?: boolean } = {}) {
    if (!currentArchive.value || sending.value) return

    if (!options.fromOption) {
      onClearOptions()
    }

    sending.value = true
    streaming.value = true

    streamAbortController = new AbortController()
    const signal = streamAbortController.signal

    const archiveId = currentArchive.value.id
    const optimisticUser = makeTempMsg(archiveId, 'user', text)
    const tempAssistant = makeTempMsg(archiveId, 'assistant', '')
    messages.value.push(optimisticUser)
    messages.value.push(tempAssistant)
    const tempAssistantId = tempAssistant.id

    let tail: ChatStreamTailData | null = null
    let streamError = ''
    let draftPersisted = false
    let textEnded = false
    let succeeded = false
    try {
      await sendMessageStream(archiveId, text, _handleStreamEvents({
        tempAssistantId,
        optimisticUserId: optimisticUser.id,
        tailRef: { get value() { return tail }, set value(v) { tail = v } },
        streamErrorRef: { get value() { return streamError }, set value(v) { streamError = v } },
        draftPersistedRef: { get value() { return draftPersisted }, set value(v) { draftPersisted = v } },
        textEndedRef: { get value() { return textEnded }, set value(v) { textEnded = v } },
        fallbackMessage: '消息生成失败',
      }), signal)

      if (streamError) throw new Error(streamError)
      if (!tail) {
        if (draftPersisted) {
          const partialErr = new Error('本轮正文已保留，结构化数据生成失败，可继续输入或手动生成选项') as Error & { partial?: boolean }
          partialErr.partial = true
          throw partialErr
        }
        throw new Error('消息生成失败：未收到结构化尾包')
      }

      await applyTailToStoreState(tail, archiveId)
      onFinishOptionLock(true)

      // 流完全结束后、选项锁已释放，自动生成选项
      if (autoGenerateOptions.value && !optionsLocked.value) {
        onAutoGenerateOptions(archiveId)
      }

      succeeded = true
    } catch (e) {
      throw wrapStreamError(e, {
        committed: !!(tail || textEnded || draftPersisted),
        draftPersisted,
        textEnded,
        prefix: '本轮',
      })
    } finally {
      streamAbortController = null
      streaming.value = false
      awaitingTail.value = false
      sending.value = false
      if (!succeeded) {
        onFinishOptionLock(false)
      }
    }
  }

  async function generateStateBroadcast(apiGenerateStateBroadcast: (archiveId: number) => Promise<{ data: { content: string } }>) {
    if (!currentArchive.value) return
    const content = stripTrailingOptionBlock(sanitizeAiDisplayText((await apiGenerateStateBroadcast(currentArchive.value.id)).data.content))
    if (!content) {
      throw new Error('状态播报内容已被拦截，请重试')
    }
    const newMsg: ChatMsg = {
      id: generateId(),
      archive_id: currentArchive.value.id,
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
  }

  return {
    startStory,
    sendStream,
    abortStream,
    generateStateBroadcast,
  }
}
