import axios from 'axios'
import type { ChatStreamEvent } from '../types/sse'

// 使用相对路径，自动适配当前页面的 host
const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
})

function extractErrorDetail(data: unknown): string {
  if (!data) return ''
  if (typeof data === 'string') return data.trim()

  const obj = data as Record<string, unknown> | undefined
  const detail = obj?.detail
  if (typeof detail === 'string') return detail.trim()
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item?.msg) return String(item.msg)
        return JSON.stringify(item)
      })
      .filter(Boolean)
      .join('; ')
      .trim()
  }
  if (detail && typeof detail === 'object') {
    return JSON.stringify(detail)
  }
  return ''
}

// 浏览器网络错误码 → 友好提示
const NETWORK_ERROR_MAP: Record<string, string> = {
  'net::ERR_INCOMPLETE_CHUNKED_ENCODING': '服务器连接中断，请稍后重试',
  'net::ERR_CONNECTION_RESET': '连接被重置，请稍后重试',
  'net::ERR_CONNECTION_REFUSED': '服务器拒绝连接，请检查后端服务是否运行',
  'net::ERR_NAME_NOT_RESOLVED': '无法解析服务器地址，请检查网络',
  'net::ERR_TIMED_OUT': '连接超时，请稍后重试',
  'network error': '网络连接失败，请检查网络后重试',
  'Failed to fetch': '网络请求失败，请检查网络连接',
}

function friendlyMessage(msg: string): string {
  const lower = msg.toLowerCase()
  // 精确匹配
  if (NETWORK_ERROR_MAP[msg]) return NETWORK_ERROR_MAP[msg]
  // 模糊匹配关键词
  if (lower.includes('err_incomplete') || lower.includes('chunked'))
    return NETWORK_ERROR_MAP['net::ERR_INCOMPLETE_CHUNKED_ENCODING']
  if (lower.includes('connection reset')) return NETWORK_ERROR_MAP['net::ERR_CONNECTION_RESET']
  if (lower.includes('connection refused')) return NETWORK_ERROR_MAP['net::ERR_CONNECTION_REFUSED']
  if (lower.includes('name not resolved') || lower.includes('getaddrinfo'))
    return NETWORK_ERROR_MAP['net::ERR_NAME_NOT_RESOLVED']
  if (lower.includes('timed out') || lower === 'timeout')
    return NETWORK_ERROR_MAP['net::ERR_TIMED_OUT']
  if (lower === 'network error' || lower.includes('failed to fetch'))
    return NETWORK_ERROR_MAP['Failed to fetch']
  return msg
}

export function getErrorMessage(error: unknown, fallback: string = '请求失败') {
  if (axios.isAxiosError(error)) {
    const detail = extractErrorDetail(error.response?.data)
    if (detail) return detail
    if (error.message) return friendlyMessage(error.message)
  }
  if (error instanceof Error && error.message) return friendlyMessage(error.message)
  if (typeof error === 'string' && error.trim()) return friendlyMessage(error.trim())
  return fallback
}

// ChatStreamEvent 从 ../types/sse 导入

// payload 类型（TODO: 精确类型依赖后端 ChatStartInput / ChatInput）
interface PostSSEPayload {
  story_id?: number
  opening_requirement?: string
  archive_id?: number | null
  message?: string
  [key: string]: unknown
}

const VALID_SSE_EVENTS = ['delta', 'text_end', 'tail', 'error', 'done'] as const

export async function postSSE(
  path: string,
  payload: PostSSEPayload,
  onEvent: (evt: ChatStreamEvent) => void,
  externalSignal?: AbortSignal,
) {
  const MAX_RETRIES = 3
  const RETRY_DELAYS = [1000, 2000, 4000]
  let receivedAnyEvent = false

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 180000)

    // Link external signal to internal controller
    if (externalSignal?.aborted) {
      controller.abort()
    }
    const onExternalAbort = () => controller.abort()
    externalSignal?.addEventListener('abort', onExternalAbort)

    try {
      const resp = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!resp.ok) {
        let detail = ''
        try {
          const text = await resp.text()
          try {
            const json = JSON.parse(text)
            detail = json.detail || json.message || json.error || text
          } catch {
            detail = text || `HTTP ${resp.status}`
          }
        } catch {
          detail = `HTTP ${resp.status}`
        }
        throw new Error(detail)
      }

      if (!resp.body) {
        throw new Error('流式响应不可用')
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          while (true) {
            const m = buffer.match(/\r?\n\r?\n/)
            if (!m) break

            const idx = m.index!
            const block = buffer.slice(0, idx).replace(/\r/g, '').trim()
            buffer = buffer.slice(idx + m[0].length)
            if (!block) continue

            let eventName = ''
            const dataParts: string[] = []
            for (const line of block.split('\n')) {
              const trimmed = line.trim()
              // 跳过 SSE 注释行（以 : 开头，如 : keepalive）
              if (trimmed.startsWith(':')) continue
              if (trimmed.startsWith('event:')) eventName = trimmed.slice(6).trim()
              else if (trimmed.startsWith('data:')) dataParts.push(trimmed.slice(5))
            }
            const dataStr = dataParts.join('\n').trim()

            // 跳过既无 event: 也无 data: 的块（纯注释块）
            if (!eventName && !dataStr) continue

            if (!VALID_SSE_EVENTS.includes(eventName as (typeof VALID_SSE_EVENTS)[number])) {
              throw new Error(`SSE格式错误: 未知事件类型 "${eventName}"`)
            }

            let data: unknown
            if (!dataStr) {
              data = {}
            } else {
              try {
                data = JSON.parse(dataStr)
              } catch {
                throw new Error(`SSE格式错误: event="${eventName}" 的 data 无法解析为 JSON`)
              }
              // 基本结构校验
              if (eventName === 'delta' && typeof (data as any)?.text !== 'string') {
                throw new Error(`SSE格式错误: delta 事件的 data.text 应为 string`)
              }
              if (eventName === 'tail' && typeof (data as any)?.reply_text !== 'string') {
                throw new Error(`SSE格式错误: tail 事件的 data.reply_text 应为 string`)
              }
            }

            const evt = { event: eventName, data } as ChatStreamEvent
            receivedAnyEvent = true
            onEvent(evt)
            if (eventName === 'done') return
            if (eventName === 'error') {
              // 立即抛出，让 chat.ts 不用等到 stream 结束就能弹窗处理
              const msg = (evt as any).data?.message || 'SSE错误'
              throw new Error(msg)
            }
          }
        }
      } finally {
        reader.releaseLock()
        clearTimeout(timer)
      }
      return
    } catch (e: any) {
      clearTimeout(timer)
      console.debug('[SSE] catch:', e?.name, e?.message)
      // External abort (user-initiated) should not be retried or translated to timeout message
      if (e?.name === 'AbortError' && externalSignal?.aborted) throw e
      if (e?.name === 'AbortError')
        throw new Error('请求超时（180s），请检查模型配置或网络', { cause: e })
      // 已经收到过 SSE 事件（delta 等）后不再重试，避免内容重复追加
      if (receivedAnyEvent) throw e
      if (attempt < MAX_RETRIES - 1) {
        await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]))
        continue
      }
      throw e
    } finally {
      clearTimeout(timer)
      externalSignal?.removeEventListener('abort', onExternalAbort)
    }
  }
}

// ---- Type-safe API inputs ----
export interface StoryCreateInput {
  title: string
  cover_image?: string
  background_image?: string
  description?: string
  tags?: string[]
  category?: string
  world_setting?: string
  system_prompt?: string
  state_config?: Record<string, unknown>[]
  opening_requirement?: string
  image_style?: string
}

export interface StoryUpdateInput {
  title?: string
  cover_image?: string
  background_image?: string
  description?: string
  tags?: string[]
  category?: string
  world_setting?: string
  system_prompt?: string
  state_config?: Record<string, unknown>[]
  opening_requirement?: string
  image_style?: string
}

export interface CharacterCreateInput {
  name: string
  personality?: string
  background?: string
  avatar?: string
  story_id?: number
}

export interface CharacterUpdateInput {
  name?: string
  personality?: string
  background?: string
  avatar?: string
}

// ---- Stories ----
export const getStories = () => api.get('/stories')
export const getStory = (id: number) => api.get(`/stories/${id}`)
export const createStory = (data: StoryCreateInput) => api.post('/stories', data)
export const updateStory = (id: number, data: StoryUpdateInput) => api.put(`/stories/${id}`, data)
export const deleteStory = (id: number) => api.delete(`/stories/${id}`)
export const aiGenerateStory = (data: {
  category: string
  title_hint: string
  tags_hint: string
  model_id?: number
  image_model_id?: number
  image_style?: string
  preference?: string
  skip_cover?: boolean
  generate_cover?: boolean
  cover_image_model_id?: number
  generate_background?: boolean
  background_image_model_id?: number
}) => api.post('/stories/ai-generate', data)
export const aiGenerateCover = (data: {
  world_setting: string
  title: string
  image_style: string
  image_model_id?: number
}) => api.post('/stories/ai-generate-cover', data)
export const regenerateStoryCover = (storyId: number) =>
  api.post(`/stories/${storyId}/regenerate-cover`)
export const standaloneGenerateCover = (storyId: number, imageModelId: number) =>
  api.post(`/stories/${storyId}/generate-cover`, { image_model_id: imageModelId })
export const standaloneGenerateBackground = (storyId: number, imageModelId: number) =>
  api.post(`/stories/${storyId}/generate-background`, { image_model_id: imageModelId })
export const uploadStoryImage = (storyId: number, file: File, purpose: 'cover' | 'background') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('purpose', purpose)
  return api.post(`/stories/${storyId}/upload-image`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ---- Characters ----
export const getCharacters = (storyId: number) => api.get(`/stories/${storyId}/characters`)
export const createCharacter = (storyId: number, data: CharacterCreateInput) =>
  api.post(`/stories/${storyId}/characters`, data)
export const updateCharacter = (id: number, data: CharacterUpdateInput) =>
  api.put(`/stories/characters/${id}`, data)
export const deleteCharacter = (id: number) => api.delete(`/stories/characters/${id}`)

// ---- Chat ----
export const getMessages = (archiveId: number) => api.get(`/chat/messages/${archiveId}`)

export const startChatStream = (
  storyId: number,
  openingRequirement: string,
  archiveId: number | null,
  onEvent: (evt: ChatStreamEvent) => void,
  signal?: AbortSignal,
) =>
  postSSE(
    '/chat/start-stream',
    {
      story_id: storyId,
      opening_requirement: openingRequirement,
      archive_id: archiveId,
    },
    onEvent,
    signal,
  )

export const sendMessageStream = (
  archiveId: number,
  message: string,
  onEvent: (evt: ChatStreamEvent) => void,
  signal?: AbortSignal,
) =>
  postSSE(
    '/chat/send-stream',
    {
      archive_id: archiveId,
      message,
    },
    onEvent,
    signal,
  )

export const generateStoryOptions = (archiveId: number, count: number = 3, guidance: string = '') =>
  api.post('/chat/options/generate', {
    archive_id: archiveId,
    count,
    guidance,
  })

export const generateStateBroadcast = (archiveId: number) =>
  api.post('/chat/state-broadcast', {
    archive_id: archiveId,
  })

export interface GenerateChatImageResponse {
  image_url: string
  message_id: number
  model_name?: string
}

export const generateChatImage = (
  archiveId: number,
  size: string = '2K',
  watermark: boolean = false,
  signal?: AbortSignal,
  idempotencyKey?: string,
) =>
  api.post<GenerateChatImageResponse>(
    '/chat/generate-image',
    { archive_id: archiveId, size, watermark, idempotency_key: idempotencyKey },
    { signal },
  )

export interface PresetOpening {
  id: number
  label: string
  value: string
}

interface PresetOpeningsCache {
  openings: PresetOpening[]
  etag: string
}

function _presetOpeningsCacheKey(storyId: number): string {
  return `preset_openings:${storyId}`
}

function _getCached(storyId: number): PresetOpeningsCache | null {
  try {
    const raw = localStorage.getItem(_presetOpeningsCacheKey(storyId))
    if (!raw) return null
    return JSON.parse(raw) as PresetOpeningsCache
  } catch (e) {
    console.warn('[PresetOpenings] localStorage cache read failed:', e)
    return null
  }
}

function _setCached(storyId: number, openings: PresetOpening[], etag: string): void {
  try {
    localStorage.setItem(_presetOpeningsCacheKey(storyId), JSON.stringify({ openings, etag }))
  } catch (e) {
    console.warn('[PresetOpenings] localStorage cache write failed:', e)
  }
}

export const generatePresetOpenings = async (storyId: number): Promise<PresetOpening[]> => {
  const cached = _getCached(storyId)

  const headers: Record<string, string> = {}
  if (cached) {
    headers['If-None-Match'] = cached.etag
  }

  const res = await api.post<{ openings: PresetOpening[] }>(
    '/chat/preset-openings',
    { story_id: storyId },
    { headers },
  )

  if (res.status === 304 && cached) {
    return cached.openings
  }

  const etag = (res.headers as Record<string, string | null>).etag || ''
  if (etag && res.data?.openings) {
    _setCached(storyId, res.data.openings, etag)
  }

  return res.data?.openings ?? []
}

export const deleteLastAiMessage = async (archiveId: number): Promise<{ deleted: number }> => {
  const res = await api.delete(`/chat/messages/${archiveId}/last-ai`)
  if (res.status !== 200) {
    throw new Error(`删除失败 (${res.status})`)
  }
  return res.data
}

export const deleteMessages = (
  archiveId: number,
  messageIds: number[],
): Promise<{ deleted: number }> =>
  api
    .delete(`/chat/messages/${archiveId}/bulk`, { data: { message_ids: messageIds } })
    .then((res) => res.data)

// ---- Archives ----
export const getArchives = (storyId: number) => api.get(`/archives/by_story/${storyId}`)
export const createArchive = (storyId: number, name: string = '默认会话') =>
  api.post('/archives', { story_id: storyId, name })
export const getArchive = (id: number) => api.get(`/archives/${id}`)
export const deleteArchive = (id: number) => api.delete(`/archives/${id}`)
export const renameArchive = (id: number, name: string) =>
  api.put(`/archives/${id}/rename?name=${encodeURIComponent(name)}`)

export interface ExportedArchive {
  archive: {
    id: number
    story_id: number
    name: string
    state_data: Record<string, any>
    story_state: Record<string, any>
    memory_log: string[]
    first_message: string
    created_at: string
    updated_at: string
  }
  messages: Array<{
    id: number
    role: string
    content: string
    created_at: string
  }>
}

export const exportArchive = (id: number): Promise<ExportedArchive> =>
  api.get(`/archives/${id}/export`).then((res) => res.data)

export const importArchive = (data: ExportedArchive): Promise<{ id: number }> =>
  api.post('/archives/import', data).then((res) => res.data)

// ---- Settings ----
export const getSettings = () => api.get('/settings')
export const updateSettings = (data: any) => api.put('/settings', data)

// ---- Admin: model configs ----
export const getModels = () => api.get('/admin/models')
export const createModel = (data: any) => api.post('/admin/models', data)
export const updateModel = (id: number, data: any) => api.put(`/admin/models/${id}`, data)
export const deleteModel = (id: number) => api.delete(`/admin/models/${id}`)
export const testModelConnection = (modelId: number) =>
  api.post<{ success: boolean; duration_ms?: number; error?: string }>(`/admin/models/test`, null, {
    params: { model_id: modelId },
  })

// ---- Admin: app settings ----
export const getAppSettings = () => api.get('/admin/app-settings')
export const updateAppSettings = (data: any) => api.put('/admin/app-settings', data)

export interface SystemShutdownResponse {
  ok: boolean
  message: string
  scheduled_at: string
  backend_delay_ms: number
  frontend_delay_ms: number
}

export const shutdownSystem = () => api.post<SystemShutdownResponse>('/admin/system/shutdown')

// ---- Admin: metrics ----
export const getMetricsSummary = (params?: any) => api.get('/admin/metrics/summary', { params })
export const getMetricsByModel = (params?: any) => api.get('/admin/metrics/by-model', { params })
export const getMetricsTimeseries = (params?: any) =>
  api.get('/admin/metrics/timeseries', { params })
export const getMetricsStreamRequests = (params?: any) =>
  api.get('/admin/metrics/stream-requests', { params })
export const resetMetrics = (confirmText: string) =>
  api.post('/admin/metrics/reset', { confirm_text: confirmText })

export default api
