/**
 * SSE 数据流类型定义
 * 对应后端 ChatResponse (schemas.py) 和 SSE 事件类型
 *
 * 注意：SSE 协议使用 `event` 字段标识事件类型，不是 `type`
 */

/** SSE delta 事件：文本增量 */
export interface ChatStreamDeltaEvent {
  event: 'delta'
  data: {
    text: string
  }
}

/** SSE text_end 事件：正文已完整流完，但结构化 tail 尚在生成中 */
export interface ChatStreamTextEndEvent {
  event: 'text_end'
  data: {
    reply_text: string
  }
}

/** SSE tail 事件：结构化数据，对应后端 ChatResponse */
export interface ChatStreamTailEvent {
  event: 'tail'
  data: {
    reply_text: string
    scene: string
    character_state: Record<string, unknown>
    story_state: Record<string, unknown>
    memory_update: string[]
    plot_label?: string | null
    archive_id?: number
    highlight_terms?: string[]
    message_id?: number
    user_id?: number
    model_name?: string
    notebook?: Record<string, unknown> | null
  }
}

/** SSE done 事件 */
export interface ChatStreamDoneEvent {
  event: 'done'
  data: {
    ok?: boolean
  }
}

/** SSE error 事件 */
export interface ChatStreamErrorEvent {
  event: 'error'
  data: {
    code?: string
    message: string
    task?: string
    draft?: boolean
    user_id?: number
    message_id?: number
  }
}

/**
 * 通用的 SSE 事件联合类型（用于 postSSE 的 onEvent 回调）
 * 与后端 api/index.ts 中 postSSE 生成的 evt 对象结构一致
 */
export type ChatStreamEvent =
  | ChatStreamDeltaEvent
  | ChatStreamTextEndEvent
  | ChatStreamTailEvent
  | ChatStreamDoneEvent
  | ChatStreamErrorEvent

/**
 * Tail 事件的数据结构（不含 event 包装）
 * 用于 applyTailToAssistant 等函数的参数类型
 */
export type ChatStreamTailData = ChatStreamTailEvent['data']
