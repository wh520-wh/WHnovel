<template>
  <div class="quick-options">
    <!-- mode="out-in": loading 先淡出，再淡入选项列表 -->
    <transition name="restore-hint">
      <div
        v-if="historyDepth && historyDepth > 0 && options.length > 0 && !loading"
        class="restore-hint"
        @click="emit('restore')"
      >
        ↩ 上一次选项 ({{ historyDepth }})
      </div>
    </transition>

    <Transition name="options-switch" mode="out-in">
      <!-- 加载中状态：仅在生成选项时显示 -->
      <div v-if="loading" key="loading" class="options-loading-bubble">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="loading-text">正在生成剧情选项...</span>
      </div>

      <div
        v-else-if="locked && lockedOption && options.length === 0"
        key="locked"
        class="locked-option-bubble"
        aria-live="polite"
      >
        <span class="locked-label">已选择</span>
        <span class="locked-text">{{ lockedOption }}</span>
        <span class="locked-status">生成中...</span>
      </div>

      <Transition v-else name="options-leave">
        <div v-if="options.length > 0" key="options" class="options-list" role="listbox" aria-label="剧情选项">
          <button
            v-for="(opt, i) in options"
            :key="i"
            class="option-btn"
            :class="{ active: activeIndex === i }"
            :disabled="disabled"
            role="option"
            :aria-selected="activeIndex === i"
            tabindex="0"
            type="button"
            @click="handleSelect(opt, i)"
            @keydown="handleKeydown(i, $event)"
          >
            <span class="option-text">{{ opt }}</span>
            <svg class="option-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      </Transition>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

const props = defineProps<{
  options: string[]
  disabled?: boolean
  loading?: boolean
  locked?: boolean
  lockedOption?: string
  historyDepth?: number
}>()

const emit = defineEmits<{
  select: [option: string]
  restore: []
}>()

const activeIndex = ref(-1)
let activeResetTimer: ReturnType<typeof setTimeout> | null = null

function handleSelect(opt: string, i: number) {
  activeIndex.value = i
  emit('select', opt)
  if (activeResetTimer !== null) {
    clearTimeout(activeResetTimer)
  }
  activeResetTimer = setTimeout(() => {
    activeIndex.value = -1
    activeResetTimer = null
  }, 600)
}

function handleKeydown(i: number, event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    const next = Math.min(i + 1, props.options.length - 1)
    focusOption(next)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    const prev = Math.max(i - 1, 0)
    focusOption(prev)
  } else if (event.key === 'Home') {
    event.preventDefault()
    focusOption(0)
  } else if (event.key === 'End') {
    event.preventDefault()
    focusOption(props.options.length - 1)
  } else if (event.key === 'Escape') {
    activeIndex.value = -1
  }
}

function focusOption(index: number) {
  const btns = document.querySelectorAll<HTMLButtonElement>('.option-btn')
  btns[index]?.focus()
  activeIndex.value = index
}

onBeforeUnmount(() => {
  if (activeResetTimer !== null) {
    clearTimeout(activeResetTimer)
    activeResetTimer = null
  }
})
</script>

<style scoped>
.quick-options {
  min-height: 40px;
}

/* ---- 回退提示行 ---- */
.restore-hint {
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px 0 4px 2px;
  transition: color var(--duration-fast) var(--ease-smooth);
  user-select: none;
  width: fit-content;
}

.restore-hint:hover {
  color: var(--accent-color);
}

.restore-hint-enter-active {
  transition: opacity 200ms ease-out, transform 200ms ease-out;
}

.restore-hint-leave-active {
  transition: opacity 150ms ease-in, transform 150ms ease-in;
}

.restore-hint-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}

.restore-hint-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ---- 选项切换过渡：out-in 模式 ---- */
.options-switch-leave-active.options-loading-bubble {
  transition: opacity 200ms ease-in, transform 200ms ease-in;
}
.options-switch-leave-to.options-loading-bubble {
  opacity: 0;
  transform: translateY(-4px);
}

.options-switch-enter-active.options-list {
  animation: option-bounce-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

/* ---- 加载状态：AI 气泡风格 ---- */
.options-loading-bubble {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px 15px;
  background: var(--ai-bubble);
  border: 1px solid var(--border-color);
  border-radius: 22px;
  box-shadow: var(--shadow-sm);
  width: fit-content;
  animation: options-slide-in 220ms var(--ease-out) both;
}

.options-loading-bubble .dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: var(--accent-color);
  border-radius: 50%;
  transform: translateY(0);
  will-change: transform, opacity;
  animation: typing-wave 600ms ease-in-out infinite;
  flex-shrink: 0;
}

.options-loading-bubble .dot:nth-child(1) { animation-delay: 0ms; }
.options-loading-bubble .dot:nth-child(2) { animation-delay: 200ms; }
.options-loading-bubble .dot:nth-child(3) { animation-delay: 400ms; }

.loading-text {
  font-size: 13px;
  color: var(--text-secondary);
}

/* typing-wave 已提取到 style.css */

.locked-option-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  max-width: min(100%, 520px);
  padding: 11px 15px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 36%, var(--border-color));
  background: color-mix(in srgb, var(--accent-color) 14%, var(--bg-card));
  color: var(--text-primary);
  box-shadow: var(--shadow-sm);
  animation: options-slide-in 180ms var(--ease-out) both;
}

.locked-label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--accent-color);
}

.locked-text {
  min-width: 0;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.locked-status {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-muted);
}

@keyframes options-slide-in {
  from { opacity: 0; transform: translateX(-12px); }
  to { opacity: 1; transform: translateX(0); }
}

/* 选项按钮 - 极轻淡入（去掉逐项错峰，列表整体入场） */
@keyframes option-bounce-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* ---- 选项列表 ---- */
.options-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ---- 选项按钮 ---- */
.option-btn {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  padding: 11px 14px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  text-align: left;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-spring),
    box-shadow var(--duration-fast) var(--ease-smooth);

  /* 入场动画：极轻淡入（去掉逐项错峰） */
  animation: option-bounce-in 160ms ease-out both;
}

/* ---- 选项离开动画 ---- */
.option-btn.v-leave-active {
  transition:
    opacity 180ms ease-in,
    transform 180ms ease-in;
}
.option-btn.v-leave-to {
  opacity: 0;
  transform: translateY(-6px) scaleY(0.95);
}

/* 选项列表整体离开动画 */
.options-leave-leave-active {
  transition: opacity 180ms ease-in, transform 180ms ease-in;
}
.options-leave-leave-to {
  opacity: 0;
  transform: translateY(-4px) scaleY(0.95);
}

.option-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--accent-color);
  transform: translateX(3px);
  box-shadow: var(--shadow-md);
}

.option-btn:active:not(:disabled) {
  transform: scale(0.97) translateX(0);
  box-shadow: none;
}

.option-btn.active {
  background: color-mix(in srgb, var(--accent-color) 12%, transparent);
  border-color: var(--accent-color);
  box-shadow: 0 0 0 1px var(--accent-color), var(--shadow-glow);
}

.option-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.option-text {
  flex: 1;
  padding-right: 8px;
}

.option-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0;
  transform: translateX(-4px);
  transition:
    opacity var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth);
}

.option-btn:hover:not(:disabled) .option-arrow {
  opacity: 1;
  transform: translateX(0);
  color: var(--accent-color);
}

.option-btn:focus-visible:not(:disabled) .option-arrow {
  opacity: 1;
  transform: translateX(0);
  color: var(--accent-color);
}

@media (max-width: 767px) {
  .option-btn {
    min-height: 44px;
  }

  .option-text {
    overflow-wrap: break-word;
  }
}
</style>
