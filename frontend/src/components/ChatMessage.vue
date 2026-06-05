<template>
  <div
    class="chat-message"
    :class="[
      msg.role,
      {
        removing: msg.removing,
        'msg-ai': msg.role === 'assistant',
        'msg-user': msg.role === 'user',
        'elastic-disabled': settingsStore.settings.disable_chat_bubble_elastic,
        'select-mode': selectMode,
        selected: selectMode && selected,
      },
    ]"
    @pointerdown="onPointerDown"
    @pointerup="onPointerUp"
    @pointercancel="onPointerCancel"
    @pointermove="onPointerMove"
    @contextmenu.prevent="handleContextMenu"
  >
    <div v-if="selectMode" class="msg-checkbox-wrap">
      <input
        type="checkbox"
        class="msg-checkbox"
        :checked="selected"
        @change="handleSelectChange"
        @click.stop
      />
    </div>
    <div class="msg-body">
      <div
        ref="bubbleRef"
        class="msg-bubble"
        :class="{ 'state-broadcast': msg.isStateBroadcast }"
        @click="handleBubbleClick"
        @animationend="handleBubbleAnimationEnd"
      >
        <!-- 图片加载中 -->
        <div v-if="msg.imageLoading" class="image-loading">
          <div class="image-spinner"></div>
          <span class="image-loading-text">
            正在创作图片{{ imageLoadingElapsed > 0 ? ` (${imageLoadingElapsed}s)` : '...' }}
          </span>
        </div>
        <!-- 图片完成 -->
        <div v-else-if="msg.imageUrl" class="image-done">
          <div class="image-wrap" @click="openImagePreview(msg.imageUrl)">
            <img :src="msg.imageUrl" :alt="msg.imageUrl" class="image-thumb" loading="lazy" />
            <div class="image-overlay">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <polyline points="15 3 21 3 21 9" />
                <polyline points="9 21 3 21 3 15" />
                <line x1="21" y1="3" x2="14" y2="10" />
                <line x1="3" y1="21" x2="10" y2="14" />
              </svg>
            </div>
          </div>
          <div class="image-op-bar">
            <button class="image-op-btn" title="重新生成" @click.stop="handleImageRegenerate">
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              重新生成
            </button>
            <button class="image-op-btn" title="保存" @click.stop="handleImageSave(msg.imageUrl)">
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              保存
            </button>
            <button class="image-op-btn" title="复制" @click.stop="handleImageCopy(msg.imageUrl)">
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              复制
            </button>
          </div>
        </div>
        <!-- 图片错误 -->
        <div v-else-if="msg.imageError" class="image-error">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{{ msg.imageError }}</span>
          <button class="image-retry-btn" @click.stop="handleImageRetry">重试</button>
        </div>
        <!-- 正常文本消息 -->
        <template v-else-if="msg.role === 'assistant'">
          <div ref="contentRef" class="msg-content md-content" v-html="renderedContent"></div>
          <!-- 打字指示器：波浪三点 -->
          <!-- dotsVisible 控制 DOM 显示，dotsDying 触发 CSS opacity 过渡实现淡出 -->
          <div v-show="dotsVisible" class="typing-indicator" :class="{ dying: dotsDying }">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </template>
        <div v-else class="msg-content">{{ msg.content }}</div>
      </div>
      <div class="msg-time">
        <div v-if="msg.role === 'assistant' && msg.model_name" class="model-label">
          {{ msg.model_name }}
        </div>
        {{ formatTime(msg.created_at) }}
      </div>
    </div>
  </div>

  <!-- 全屏图片预览 -->
  <Teleport to="body">
    <div v-if="previewUrl" class="image-preview-overlay" @click.self="closeImagePreview">
      <button class="preview-close" aria-label="关闭" @click="closeImagePreview">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
      <img :src="previewUrl" :alt="previewUrl" class="preview-img" />
      <div class="preview-op-bar">
        <!-- prettier-ignore -->
        <button
          class="preview-op-btn"
          @click="handleImageRegenerate(); closeImagePreview()"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
          重新生成
        </button>
        <button class="preview-op-btn" @click="handleImageSave(previewUrl || '')">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          保存
        </button>
        <button class="preview-op-btn" @click="handleImageCopy(previewUrl || '')">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          复制链接
        </button>
        <button class="preview-op-btn" @click="closeImagePreview">关闭</button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useChatStore } from '../stores/chat'
import type { ChatMsg } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'
import { sanitizeAiDisplayText } from '../utils/aiText'
import { stripTrailingOptionBlock } from '../utils/text'
import { formatTime } from '../utils/time'
import { showToast } from '../utils/toast'

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderStateBroadcastTable(content: string): string {
  const lines = content.split('\n').filter((l) => l.trim())
  const rows = lines
    .map((line) => {
      const idx = line.indexOf('|')
      if (idx === -1) return null
      const key = line.slice(0, idx).trim()
      const value = line.slice(idx + 1).trim()
      if (!key) return null
      return `<tr><td class="sb-key">${escapeHtml(key)}</td><td class="sb-val">${escapeHtml(value)}</td></tr>`
    })
    .filter(Boolean)
    .join('')
  if (!rows) return ''
  return `<table class="state-broadcast-table">${rows}</table>`
}

const props = defineProps<{
  msg: ChatMsg
  streaming?: boolean
  selectMode?: boolean
  selected?: boolean
}>()

// text_end 后三点不立即消失，而是延迟 250ms 淡出，给用户"AI还在处理"的感知过渡
// dying 负责 opacity 过渡（从 1→0），visible 负责 v-show 控制消失时机
const dotsVisible = ref(false)
const dotsDying = ref(false)
let dyingTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.streaming,
  (isStreaming) => {
    if (isStreaming) {
      // 流式恢复：立即取消所有定时，重置状态
      if (dyingTimer !== null) {
        clearTimeout(dyingTimer)
        dyingTimer = null
      }
      dotsDying.value = false
      dotsVisible.value = true
    } else if (dyingTimer === null) {
      // text_end 到达：先标记 dying（opacity 开始过渡），再延迟移除
      dotsDying.value = true
      dyingTimer = setTimeout(() => {
        dotsVisible.value = false
        dotsDying.value = false
        dyingTimer = null
      }, 250)
    }
  },
)

const emit = defineEmits<{
  (event: 'recall-animation-end', messageId: string | number): void
  (event: 'select', messageId: number | string, checked: boolean): void
  (event: 'long-press', messageId: number | string): void
}>()

function handleSelectChange(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  emit('select', props.msg.id, checked)
}

const bubbleRef = ref<HTMLElement | null>(null)
const previewUrl = ref<string | null>(null)
const imageLoadingElapsed = ref(0)
let imageLoadingTimer: ReturnType<typeof setInterval> | null = null

watch(
  () => props.msg.imageLoading,
  (loading) => {
    if (loading) {
      imageLoadingElapsed.value = 0
      imageLoadingTimer = setInterval(() => {
        imageLoadingElapsed.value += 1
      }, 1000)
    } else {
      if (imageLoadingTimer !== null) {
        clearInterval(imageLoadingTimer)
        imageLoadingTimer = null
      }
      imageLoadingElapsed.value = 0
    }
  },
)

const chatStore = useChatStore()
const settingsStore = useSettingsStore()

// 高亮处理
const highlightRegExpCache = new Map<string, RegExp>()

function getHighlightRegExp(term: string): RegExp {
  let regex = highlightRegExpCache.get(term)
  if (!regex) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    regex = new RegExp(escaped, 'g')
    highlightRegExpCache.set(term, regex)
  }
  regex.lastIndex = 0
  return regex
}

function applyHighlights(content: string): string {
  let result = content
  const terms = [...(chatStore.highlightedTerms || [])].sort((a, b) => b.length - a.length)
  for (const term of terms) {
    if (term.length < 2) continue
    result = result.replace(getHighlightRegExp(term), `<span class="hl-item">${term}</span>`)
  }
  return result
}

// ESC 关闭全屏预览
watch(previewUrl, (url) => {
  if (url) {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeImagePreview()
    }
    document.addEventListener('keydown', handler)
    // 清理函数在 watch 回到 null 时执行
    return () => document.removeEventListener('keydown', handler)
  }
})

function handleBubbleClick() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  if (settingsStore.settings.disable_chat_bubble_elastic) return
  const el = bubbleRef.value
  if (!el) return
  el.classList.remove('bubble-pop')
  void el.offsetWidth
  el.classList.add('bubble-pop')
  el.addEventListener('animationend', () => el.classList.remove('bubble-pop'), { once: true })
}

function openImagePreview(url: string) {
  previewUrl.value = url
}

function closeImagePreview() {
  previewUrl.value = null
}

function handleImageRegenerate() {
  chatStore.generateImage()
}

function handleImageSave(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = ''
  a.target = '_blank'
  a.click()
}

function handleImageCopy(url: string) {
  if (settingsStore.settings.copy_image_format === 'binary') {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    fetch(url, { signal: controller.signal })
      .then((res) => res.blob())
      .then((blob) => navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]))
      .then(() => showToast('图片已复制到剪贴板'))
      .catch(() => {
        navigator.clipboard.writeText(url).then(() => showToast('图片链接已复制'))
      })
      .finally(() => clearTimeout(timeout))
  } else {
    navigator.clipboard.writeText(url).then(() => showToast('图片链接已复制'))
  }
}

function handleImageRetry() {
  chatStore.generateImage()
}

let pressTimer: ReturnType<typeof setTimeout> | null = null
let pressStartX = 0
let pressStartY = 0

function emitLongPress() {
  emit('long-press', props.msg.id)
}

function onPointerDown(e: PointerEvent) {
  if (props.selectMode) return
  pressStartX = e.clientX
  pressStartY = e.clientY
  pressTimer = setTimeout(emitLongPress, 500)
  bubbleRef.value?.classList.add('pressing')
}

function onPointerMove(e: PointerEvent) {
  if (!pressTimer) return
  const dx = Math.abs(e.clientX - pressStartX)
  const dy = Math.abs(e.clientY - pressStartY)
  if (dx > 10 || dy > 10) {
    clearTimeout(pressTimer)
    pressTimer = null
  }
}

function onPointerUp() {
  if (pressTimer) {
    clearTimeout(pressTimer)
    pressTimer = null
  }
  bubbleRef.value?.classList.remove('pressing')
}

function onPointerCancel() {
  onPointerUp()
}

function handleContextMenu() {
  if (!props.selectMode) emitLongPress()
}

const contentRef = ref<HTMLElement | null>(null)

watch(
  () => props.streaming,
  (isStreaming) => {
    if (!contentRef.value) return
    const cursor = contentRef.value.querySelector('.streaming-cursor')
    if (isStreaming) {
      if (!cursor) {
        const span = document.createElement('span')
        span.className = 'streaming-cursor'
        span.textContent = '|'
        contentRef.value.appendChild(span)
      }
    } else {
      cursor?.remove()
    }
  },
)

const MAX_CONTENT_CACHE = 100
const markdownCache = new Map<string, string>()
const highlightedContentCache = new Map<string, string>()

function trimCache(cache: Map<string, string>) {
  if (cache.size > MAX_CONTENT_CACHE) {
    const keysToDelete = Array.from(cache.keys()).slice(0, Math.floor(MAX_CONTENT_CACHE / 2))
    keysToDelete.forEach((k) => cache.delete(k))
  }
}

const renderedContent = ref('')
let renderRafId: number | null = null

function computeRendered(): string {
  if (props.msg.role !== 'assistant') return ''
  const content = stripTrailingOptionBlock(sanitizeAiDisplayText(props.msg.content || ''))
  if (!content) return ''
  // 状态播报走独立表格渲染，不走 marked.parse
  if (props.msg.isStateBroadcast) {
    return renderStateBroadcastTable(content)
  }
  if (!markdownCache.has(content)) {
    const raw = marked.parse(content)
    const html = typeof raw === 'string' ? raw : ''
    markdownCache.set(content, DOMPurify.sanitize(html) as string)
    trimCache(markdownCache)
  }

  const highlightKey = (chatStore.highlightedTerms || []).join('\u0001')
  const cacheKey = `${content}::${highlightKey}`
  if (!highlightedContentCache.has(cacheKey)) {
    const sanitized = markdownCache.get(content) ?? ''
    highlightedContentCache.set(cacheKey, applyHighlights(sanitized))
    trimCache(highlightedContentCache)
  }
  return highlightedContentCache.get(cacheKey) ?? ''
}

function scheduleRender() {
  if (renderRafId !== null) return
  renderRafId = requestAnimationFrame(() => {
    renderRafId = null
    renderedContent.value = computeRendered()
  })
}

function renderImmediate() {
  if (renderRafId !== null) {
    cancelAnimationFrame(renderRafId)
    renderRafId = null
  }
  renderedContent.value = computeRendered()
}

// Watch content changes: throttle during streaming, immediate otherwise
watch(
  () => props.msg.content,
  () => {
    if (props.streaming) {
      scheduleRender()
    } else {
      renderImmediate()
    }
  },
  { immediate: true },
)

// Watch streaming end: ensure final content renders without rAF delay
watch(
  () => props.streaming,
  (isStreaming) => {
    if (!isStreaming) {
      renderImmediate()
    }
  },
)

// Watch highlight changes: always render immediately
watch(
  () => chatStore.highlightedTerms,
  () => {
    renderImmediate()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  if (renderRafId !== null) {
    cancelAnimationFrame(renderRafId)
    renderRafId = null
  }
  if (imageLoadingTimer !== null) {
    clearInterval(imageLoadingTimer)
    imageLoadingTimer = null
  }
})

function handleBubbleAnimationEnd(event: AnimationEvent) {
  if (!props.msg.removing) return
  if (event.target !== event.currentTarget) return
  if (!['bubble-breaking', 'bubble-breaking-reduced'].includes(event.animationName)) return
  emit('recall-animation-end', props.msg.id)
}
</script>

<style scoped>
/* ---- 容器 ---- */
.chat-message {
  display: flex;
  margin-bottom: 10px;
  padding: 0 4px;
}

/* ---- 编辑模式复选框 ---- */
.msg-checkbox-wrap {
  display: flex;
  align-items: center;
  padding: 0 6px;
  flex-shrink: 0;
}

.msg-checkbox {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 2px solid rgba(20, 184, 166, 0.4);
  background: transparent;
  accent-color: var(--accent-color);
  cursor: pointer;
  transition: border-color 150ms;
}

.msg-checkbox:hover {
  border-color: var(--accent-color);
}

/* 编辑模式下的消息行布局 */
.chat-message.select-mode {
  align-items: center;
}

.chat-message.selected {
  background: rgba(20, 184, 166, 0.08);
  border-radius: 12px;
}

/* ---- 入场动画：底部弹出 + 弹性缩放 ---- */
.assistant,
.user {
  animation: bubble-pop-in 280ms cubic-bezier(0.25, 0.1, 0.25, 1) both;
}

.assistant.elastic-disabled,
.user.elastic-disabled {
  animation: none;
}
/* bubble-pop-in 已提取到全局 style.css */

/* ---- 撤回动画：time-unwind ----
   实际 keyframes 与 wiring 都在 frontend/src/styles/global.css
   的全局 `.chat-message.removing .msg-bubble` 规则里，四套主题共用。
   这里不再重复声明，避免和全局规则互相覆盖。 */

/* ---- Q弹点击：水波纹扩散 ---- */
.msg-bubble.bubble-pop {
  animation: bubble-ripple 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94) both;
}
.assistant .msg-bubble.bubble-pop {
  transform-origin: left center;
}
.user .msg-bubble.bubble-pop {
  transform-origin: right center;
}

@keyframes bubble-ripple {
  0% {
    transform: scale(1);
  }
  20% {
    transform: scale(1.06);
  }
  45% {
    transform: scale(0.97);
  }
  70% {
    transform: scale(1.025);
  }
  85% {
    transform: scale(0.99);
  }
  100% {
    transform: scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .msg-bubble.bubble-pop {
    animation: none !important;
  }
}

/* ---- 长按视觉反馈 ---- */
.msg-bubble.pressing {
  transform: scale(0.97) !important;
  box-shadow: 0 0 12px color-mix(in srgb, var(--accent-color) 30%, transparent) !important;
  transition:
    transform 80ms ease-out,
    box-shadow 80ms ease-out,
    filter 80ms ease-out;
}

@media (prefers-reduced-motion: reduce) {
  .msg-bubble.pressing {
    transform: none !important;
    box-shadow: none !important;
  }
}

/* ---- 用户气泡按压反馈 ---- */
.user:not(.elastic-disabled) .msg-bubble:active {
  transform: scale(0.96) translateY(0) !important;
  box-shadow: var(--shadow-sm) !important;
  filter: brightness(0.92);
  transition:
    transform 80ms ease-out,
    box-shadow 80ms ease-out,
    filter 80ms ease-out;
}

.msg-body {
  display: flex;
  flex-direction: column;
  max-width: min(70%, 450px);
}

/* 电脑端 (768px+) 缩小气泡宽度 */
@media (min-width: 768px) {
  .msg-body {
    max-width: min(70%, 420px);
  }
}

/* 移动端气泡宽度更宽 */
@media (max-width: 767px) {
  .msg-body {
    max-width: min(88%, 450px);
  }

  .msg-bubble {
    max-width: none;
  }

  .image-retry-btn {
    min-height: 44px;
    padding: 10px 16px;
  }

  .msg-checkbox-wrap {
    min-width: 44px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .preview-op-btn {
    min-height: 44px;
  }

  .image-op-btn {
    min-height: 44px;
    padding: 10px 14px;
  }

  .preview-close {
    width: 44px;
    height: 44px;
  }
}
.user {
  justify-content: flex-end;
}
.user .msg-body {
  align-items: flex-end;
}
.assistant .msg-body {
  align-items: flex-start;
}

/* ---- 气泡主体：统一圆润 ---- */
.msg-bubble {
  padding: 12px 16px;
  word-break: break-word;
  overflow-wrap: break-word;
  max-width: 680px;
  transition:
    transform 200ms var(--ease-spring),
    box-shadow 200ms var(--ease-smooth);
}

/* ---- 用户气泡：四边圆润对称 ---- */
.user .msg-bubble {
  white-space: pre-wrap;
  background: var(--user-bubble);
  color: #ffffff;
  font-size: 14px;
  line-height: 1.75;
  border-radius: var(--radius-bubble) var(--radius-bubble) var(--radius-bubble-tail)
    var(--radius-bubble);
  box-shadow: var(--shadow-md);
}

.user:not(.elastic-disabled) .msg-bubble:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

/* ---- AI 气泡：简洁风格 ---- */
.assistant .msg-bubble {
  background: var(--ai-bubble);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.75;
  border-radius: var(--radius-bubble-tail) var(--radius-bubble) var(--radius-bubble)
    var(--radius-bubble);
  border: 1px solid var(--border-color);
  box-shadow: none;
}

.assistant:not(.elastic-disabled) .msg-bubble:hover {
  transform: translateY(-2px);
  border-color: var(--accent-color);
}

.assistant:not(.elastic-disabled) .msg-bubble:active {
  transform: scale(0.96) translateY(0) !important;
  filter: brightness(0.92);
  transition:
    transform 80ms ease-out,
    box-shadow 80ms ease-out,
    filter 80ms ease-out;
}

/* ---- 状态播报消息降权 ---- */
.assistant .msg-bubble.state-broadcast {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  border-radius: 0 !important;
  padding: 8px 0 !important;
  max-width: 100% !important;
  font-size: calc(12px * var(--font-scale, 1));
  line-height: 1.5;
  color: var(--text-muted);
  transform: none !important;
}
.assistant .msg-bubble.state-broadcast:hover {
  border-color: transparent !important;
  transform: none !important;
}
/* 长按视觉反馈对状态播报也生效 */
.msg-bubble.state-broadcast.pressing {
  transform: scale(0.97) !important;
  box-shadow: 0 0 12px color-mix(in srgb, var(--accent-color) 30%, transparent) !important;
}

/* ---- 打字指示器 ---- */
.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 8px;
  transition: opacity 200ms ease-out;
}

.typing-indicator.dying {
  opacity: 0;
}
.typing-dot {
  width: 6px;
  height: 6px;
  background: var(--accent-color);
  border-radius: 50%;
  animation: typing-wave 600ms ease-in-out infinite;
}
.typing-dot:nth-child(1) {
  animation-delay: 0ms;
}
.typing-dot:nth-child(2) {
  animation-delay: 200ms;
}
.typing-dot:nth-child(3) {
  animation-delay: 400ms;
}
/* typing-wave 已提取到全局 style.css */

/* ---- 时间戳 ---- */
.msg-time {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 4px;
  opacity: 0.35;
  transition: opacity 200ms var(--ease-smooth);
  margin-top: 3px;
  text-align: center;
}
.chat-message:hover .msg-time {
  opacity: 0.6;
}

.model-label {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.5;
  line-height: 1.2;
  user-select: none;
  pointer-events: none;
  text-align: center;
}

/* ---- Markdown 样式 ---- */
.msg-content {
  min-height: 6px;
  font-size: calc(var(--text-base) * var(--font-scale, 1));
  line-height: var(--line-height-prose);
}

/* AI 叙事正文：衬线 + CJK 阅读字距，强化「小说」沉浸感 */
.assistant .msg-content {
  font-family: var(--heading);
  letter-spacing: 0.01em;
}
.md-content :deep(p) {
  margin: 0 0 8px;
}
.md-content :deep(p:last-child) {
  margin-bottom: 0;
}
.md-content :deep(strong) {
  color: var(--accent-color);
  font-weight: 600;
}
.md-content :deep(em) {
  opacity: 0.85;
  font-style: italic;
}
.md-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 10px 0;
}
.md-content :deep(ul),
.md-content :deep(ol) {
  padding-left: 16px;
  margin: 6px 0;
}
.md-content :deep(li) {
  margin-bottom: 3px;
  line-height: var(--line-height-prose);
}
.md-content :deep(code) {
  background: color-mix(in srgb, var(--accent-color) 12%, transparent);
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}
.md-content :deep(pre) {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.md-content :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 12px;
}
.md-content :deep(a) {
  color: var(--accent-color);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.md-content :deep(a:hover) {
  color: var(--accent-hover);
}

/* ---- 流式输出光标 ---- */
.streaming-cursor {
  display: inline-block;
  color: var(--accent-color);
  opacity: 0.5;
  margin-left: 1px;
}

/* ---- 图片加载中 ---- */
.image-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}
.image-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(20, 184, 166, 0.3);
  border-top-color: var(--accent-color);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.image-loading-text {
  font-size: 13px;
  color: var(--text-muted);
}

/* ---- 图片完成 ---- */
.image-done {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.image-wrap {
  position: relative;
  display: inline-block;
  cursor: pointer;
  border-radius: 10px;
  overflow: hidden;
  line-height: 0;
}
.image-thumb {
  border-radius: 10px;
  max-width: 100%;
  display: block;
  transition: filter 0.2s;
}
.image-wrap:hover .image-thumb {
  filter: brightness(0.85);
}
.image-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  opacity: 0;
  transition: opacity 0.2s;
  border-radius: 10px;
  color: #fff;
}
.image-wrap:hover .image-overlay {
  opacity: 1;
}

/* 操作栏 */
.image-op-bar {
  display: flex;
  gap: 4px;
  padding: 6px 2px 2px;
  border-top: 1px solid rgba(20, 184, 166, 0.1);
  margin-top: 4px;
}
.image-op-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 7px;
  border: 1px solid rgba(20, 184, 166, 0.2);
  background: rgba(20, 184, 166, 0.08);
  color: var(--accent-color);
  font-size: 11px;
  cursor: pointer;
  transition:
    transform 0.15s,
    box-shadow 0.15s,
    background-color 0.15s,
    border-color 0.15s,
    color 0.15s;
  font-family: inherit;
  white-space: nowrap;
}
.image-op-btn:hover {
  background: rgba(20, 184, 166, 0.2);
  border-color: rgba(20, 184, 166, 0.45);
  transform: translateY(-1px);
}
.image-op-btn:active {
  transform: translateY(0) scale(0.97);
}

/* ---- 图片错误 ---- */
.image-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  color: #f87171;
  font-size: 13px;
}
.image-retry-btn {
  margin-left: auto;
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  font-size: 11px;
  cursor: pointer;
  transition:
    transform 0.15s,
    box-shadow 0.15s,
    background-color 0.15s,
    border-color 0.15s,
    color 0.15s;
  font-family: inherit;
}
.image-retry-btn:hover {
  background: rgba(248, 113, 113, 0.2);
}

/* ---- 全屏预览 ---- */
.image-preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.93);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  animation: preview-fade-in 0.2s ease-out;
}
@keyframes preview-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
.preview-close {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    transform 0.15s,
    box-shadow 0.15s,
    background-color 0.15s,
    border-color 0.15s,
    color 0.15s;
}
.preview-close:hover {
  background: rgba(248, 113, 113, 0.7);
  border-color: rgba(248, 113, 113, 0.5);
}
.preview-img {
  max-width: 90vw;
  max-height: 80vh;
  max-height: 80dvh;
  border-radius: 12px;
  object-fit: contain;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8);
}
.preview-op-bar {
  display: flex;
  gap: 8px;
}
.preview-op-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition:
    transform 0.15s,
    box-shadow 0.15s,
    background-color 0.15s,
    border-color 0.15s,
    color 0.15s;
  font-family: inherit;
}
.preview-op-btn:hover {
  background: rgba(20, 184, 166, 0.7);
  border-color: rgba(20, 184, 166, 0.5);
}

@media (prefers-reduced-motion: reduce) {
  .image-spinner {
    animation: none !important;
  }
  .image-preview-overlay {
    animation: none !important;
  }
}

/* ---- 状态播报表格 ---- */
:deep(.state-broadcast-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: calc(14px * var(--font-scale, 1));
  line-height: 1.6;
  user-select: none;
  -webkit-user-select: none;
  touch-action: manipulation;
}
:deep(.state-broadcast-table tr) {
  border-bottom: 1px solid var(--border-color);
}
:deep(.state-broadcast-table tr:last-child) {
  border-bottom: none;
}
:deep(.state-broadcast-table .sb-key) {
  color: var(--text-muted);
  padding: 4px 24px 4px 0;
  white-space: nowrap;
  text-align: right;
  vertical-align: top;
}
:deep(.state-broadcast-table .sb-val) {
  color: var(--text-primary);
  padding: 4px 0;
  text-align: left;
  vertical-align: top;
}
</style>
