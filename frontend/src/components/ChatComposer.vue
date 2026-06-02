<template>
  <div class="input-area" ref="rootEl">
    <div v-if="thinking || awaitingTail" class="ai-thinking-hint">{{ thinkingHint }}</div>
    <div v-if="generatingOptions" class="options-generating-hint">剧情选项生成中...</div>
    <div v-if="generatingOptionsFailed" class="options-failed-hint" @click="$emit('retryOptions')">选项生成失败，点此重试</div>
    <div class="bottom-bar">
      <button
        class="plus-btn"
        :class="{ active: menuActive }"
        type="button"
        title="菜单"
        ref="plusButtonEl"
        @click="$emit('toggle-menu')"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>
      <div class="input-shell">
        <textarea
          class="bottom-input"
          v-model="inputValue"
          placeholder="请输入..."
          enterkeyhint="send"
          :disabled="disabled"
          rows="1"
          ref="textareaEl"
          @keydown.enter.exact.prevent="emitSend"
          @input="handleTextareaInput"
          @focus="handleFocus"
          @blur="handleBlur"
        ></textarea>
        <div class="char-count" :class="{ warn: modelValue.length > 1800 }">
          {{ modelValue.length }}/2000
        </div>
      </div>
      <button class="send-btn" :class="{ ready: canSend }" type="button" :disabled="!canSend" @click="emitSend">
        <span v-if="showSpinner" class="loading-spinner"></span>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { debounce } from 'lodash'
import { useDraft } from '../composables/useDraft'

const storyIdRef = computed(() => props.storyId ?? null)
const archiveIdRef = computed(() => props.archiveId ?? null)

const draftModule = useDraft({
  currentStoryId: storyIdRef,
  currentArchiveId: archiveIdRef,
})

const debouncedSaveDraft = debounce((text: string) => {
  if (text.trim()) {
    draftModule.saveDraft(text)
  } else {
    draftModule.clearDraft()
  }
}, 500)

const props = defineProps<{
  modelValue: string
  disabled: boolean
  sendBusy?: boolean
  thinking: boolean
  awaitingTail?: boolean
  menuActive: boolean
  showSpinner: boolean
  generatingOptions?: boolean
  generatingOptionsFailed?: boolean
  storyId?: number | null
  archiveId?: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: [value: string]
  'toggle-menu': []
  focus: []
  blur: []
  resized: [{ previousHeight: number; nextHeight: number }]
  retryOptions: []
}>()

const rootEl = ref<HTMLDivElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const plusButtonEl = ref<HTMLButtonElement | null>(null)

const inputValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
})

const canSend = computed(() => !props.disabled && !props.sendBusy && props.modelValue.trim().length > 0)

const thinkingHint = computed(() => {
  if (props.awaitingTail) return '正在整理状态和选项...'
  return 'AI 正在回复...'
})

function emitResize(previousHeight: number) {
  const nextHeight = rootEl.value?.offsetHeight ?? previousHeight
  if (Math.abs(nextHeight - previousHeight) < 1) return
  emit('resized', { previousHeight, nextHeight })
}

function resizeTextarea() {
  const el = textareaEl.value
  if (!el) return
  const previousHeight = rootEl.value?.offsetHeight ?? 0
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  emitResize(previousHeight)
}

function focusTextarea() {
  textareaEl.value?.focus()
}

function loadDraft(): string | null {
  return draftModule.loadDraft()
}

function clearDraft(): void {
  debouncedSaveDraft.cancel()
  draftModule.clearDraft()
}

function emitSend() {
  const trimmed = props.modelValue.trim()
  if (!trimmed || props.disabled || props.sendBusy) return
  emit('send', trimmed)
  // 立即清空输入框（乐观更新），无需等父组件响应
  emit('update:modelValue', '')
}

function handleTextareaInput() {
  debouncedResize()
}

const debouncedResize = debounce(resizeTextarea, 100)

function handleFocus() {
  emit('focus')
}

function handleBlur() {
  debouncedSaveDraft.flush()
  emit('blur')
}

watch(
  () => props.modelValue,
  (text) => {
    debouncedSaveDraft(text)
    nextTick(resizeTextarea)
  },
)

onMounted(() => {
  resizeTextarea()
})

defineExpose({
  rootEl,
  textareaEl,
  plusButtonEl,
  resizeTextarea,
  focusTextarea,
  loadDraft,
  clearDraft,
})
</script>

<style scoped>
.input-area {
  position: sticky;
  bottom: 0;
  padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
  background: var(--input-area-bg, var(--bg-card));
  transition:
    opacity var(--duration-slow) var(--ease-smooth),
    transform var(--duration-slow) var(--ease-smooth);
}

[data-theme="light"] .input-area {
  background: var(--bg-card);
}

.ai-thinking-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  padding: 4px 0 6px;
  animation: fade-in 200ms var(--ease-smooth) both;
  transition: opacity 220ms ease-out;
}

.options-generating-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  padding: 4px 0 6px;
  animation: fade-in 200ms var(--ease-smooth) both;
  transition: opacity 220ms ease-out;
}

.options-failed-hint {
  text-align: center;
  font-size: 12px;
  color: #e6a23c;
  padding: 4px 0 6px;
  animation: fade-in 200ms var(--ease-smooth) both;
  cursor: pointer;
}

.bottom-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
}

.input-shell {
  position: relative;
  flex: 1;
  min-width: 0;
}

.plus-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-smooth), box-shadow var(--duration-fast) var(--ease-smooth), background-color var(--duration-fast) var(--ease-smooth), border-color var(--duration-fast) var(--ease-smooth), color var(--duration-fast) var(--ease-smooth);
}

.plus-btn:hover {
  transform: scale(1.1);
  border-color: var(--accent-color);
}

.plus-btn:active {
  transform: scale(0.9);
  transition-duration: 80ms;
}

.plus-btn.active {
  background: color-mix(in srgb, var(--accent-color) 20%, var(--bg-card));
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.bottom-input {
  width: 100%;
  min-height: 44px;
  max-height: 200px;
  padding: 10px 68px 16px 16px;
  border-radius: 22px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  resize: none;
  overflow-y: auto;
  transition: transform var(--duration-base) var(--ease-spring), box-shadow var(--duration-base) var(--ease-spring), background-color var(--duration-base) var(--ease-spring), border-color var(--duration-base) var(--ease-spring), color var(--duration-base) var(--ease-spring);
  min-width: 0;
  box-shadow: var(--shadow-sm);
  transform: scale(1);
}

.bottom-input::placeholder {
  color: var(--text-muted);
}

.bottom-input:hover {
  border-color: color-mix(in srgb, var(--accent-color) 50%, var(--border-color));
}

.bottom-input:focus {
  border-color: var(--accent-color);
  box-shadow: var(--shadow-sm), 0 0 0 3px color-mix(in srgb, var(--accent-color) 20%, transparent);
}

.bottom-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.char-count {
  position: absolute;
  bottom: 5px;
  right: 14px;
  font-size: 10px;
  color: var(--text-muted);
  pointer-events: none;
  transition: color var(--duration-fast) var(--ease-smooth);
}

.char-count.warn {
  color: #e6a23c;
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: var(--user-bubble);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-smooth), box-shadow var(--duration-fast) var(--ease-smooth), background-color var(--duration-fast) var(--ease-smooth), border-color var(--duration-fast) var(--ease-smooth), color var(--duration-fast) var(--ease-smooth);
  box-shadow: var(--shadow-md);
}

.send-btn.ready:not(:disabled) {
  box-shadow: var(--shadow-lg), 0 0 0 2px color-mix(in srgb, var(--accent-color) 18%, transparent);
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.1);
  box-shadow: var(--shadow-lg), var(--shadow-glow);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.9);
  transition-duration: 80ms;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.loading-spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spinner-spin 600ms linear infinite;
}

@media (max-width: 767px) {
  .input-area {
    position: sticky;
    bottom: var(--keyboard-offset, 0px);
    left: 0;
    right: 0;
    background: var(--bg-primary);
    padding: 8px 12px calc(8px + env(safe-area-inset-bottom));
    z-index: 100;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.15);
    transition: transform 220ms var(--ease-smooth), opacity 220ms var(--ease-smooth);
  }

  .ai-thinking-hint {
    font-size: 13px;
  }
}

@media (min-width: 768px) and (max-width: 1199px) {
  .input-area {
    padding: 10px 16px calc(12px + env(safe-area-inset-bottom));
  }
}

@media (min-width: 1200px) {
  .input-area {
    padding: 10px 20px 12px;
  }
}
</style>
