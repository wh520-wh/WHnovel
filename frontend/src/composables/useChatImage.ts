import { ref, readonly } from 'vue'
import { generateChatImage } from '../api'
import type { ChatMsg, Archive } from '../stores/chat'
import { generateId } from '../utils/id'

export function useChatImage(params: {
  messages: { value: ChatMsg[] }
  currentArchive: { value: Archive | null }
}) {
  const { messages, currentArchive } = params
  const isGeneratingImage = ref(false)
  const generatingImageMsgId = ref<string | null>(null)
  const imageRequestVersion = ref(0)
  const imageAbortController = ref<AbortController | null>(null)

  function isAbortedRequest(error: unknown): boolean {
    const err = error as any
    const msg = String(err?.message || '')
    return (
      err?.name === 'AbortError' ||
      err?.code === 'ERR_CANCELED' ||
      /aborted|canceled|cancelled/i.test(msg)
    )
  }

  function abortInFlightImageRequest() {
    if (imageAbortController.value) {
      imageAbortController.value.abort()
      imageAbortController.value = null
    }
    imageRequestVersion.value += 1
    isGeneratingImage.value = false
    generatingImageMsgId.value = null
  }

  async function generateImage(size: string = '2K', watermark: boolean = false) {
    if (!currentArchive.value || isGeneratingImage.value) return

    const archiveId = currentArchive.value.id
    const requestVersion = imageRequestVersion.value + 1
    imageRequestVersion.value = requestVersion

    const controller = new AbortController()
    imageAbortController.value = controller
    isGeneratingImage.value = true

    const isStale = () =>
      imageRequestVersion.value !== requestVersion || currentArchive.value?.id !== archiveId

    const updateLoadingMessage = (msgId: string, updater: (old: ChatMsg) => Partial<ChatMsg>) => {
      if (isStale()) return
      const idx = messages.value.findIndex(
        (m) => m.id === msgId && (m as any).archive_id === archiveId,
      )
      if (idx === -1) return
      const old = messages.value[idx]
      messages.value[idx] = { ...old, ...updater(old) } as ChatMsg
    }

    const applySuccess = (
      msgId: string,
      data: { message_id?: number; image_url: string; model_name?: string },
    ) =>
      updateLoadingMessage(msgId, () => ({
        id: data.message_id ?? msgId,
        imageLoading: false,
        imageUrl: data.image_url,
        imageError: undefined,
        persisted: true,
        model_name: data.model_name,
      }))

    const msgId = generateId()
    generatingImageMsgId.value = msgId
    const loadingMsg: ChatMsg = {
      id: msgId,
      archive_id: archiveId,
      role: 'assistant',
      content: '',
      state_snapshot: {},
      story_state: {},
      options: [],
      memory_update: [],
      created_at: new Date().toISOString(),
      imageLoading: true,
      persisted: false,
    }
    messages.value.push(loadingMsg)

    try {
      const { data } = await generateChatImage(archiveId, size, watermark, controller.signal, msgId)
      applySuccess(msgId, data)
    } catch (err) {
      if (isAbortedRequest(err) || isStale()) return
      try {
        const { data } = await generateChatImage(
          archiveId,
          size,
          watermark,
          controller.signal,
          msgId,
        )
        applySuccess(msgId, data)
      } catch (retryErr) {
        if (isAbortedRequest(retryErr) || isStale()) return
        updateLoadingMessage(msgId, () => ({
          imageLoading: false,
          imageError: '图片生成失败，请稍后重试',
        }))
      }
    } finally {
      if (imageAbortController.value === controller) {
        imageAbortController.value = null
      }
      if (!isStale()) {
        isGeneratingImage.value = false
        generatingImageMsgId.value = null
      }
    }
  }

  return {
    isGeneratingImage: readonly(isGeneratingImage),
    generatingImageMsgId: readonly(generatingImageMsgId),
    imageRequestVersion: readonly(imageRequestVersion),
    generateImage,
    abortInFlightImageRequest,
  }
}
