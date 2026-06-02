<template>
  <div class="model-select-wrap" :class="{ 'has-value': !!modelValue, 'is-open': isOpen, 'is-disabled': disabled }">

    <!-- 触发器 -->
    <button
      type="button"
      class="model-select-trigger"
      :class="{ 'has-value': !!modelValue, 'is-open': isOpen, 'is-disabled': disabled }"
      @click="toggleDropdown"
      :title="selectedModel ? formatLabel(selectedModel) : placeholder"
      :aria-expanded="isOpen"
      aria-haspopup="listbox"
    >
      <!-- 左侧选中指示条 -->
      <div class="select-indicator" :class="{ active: !!modelValue }">
        <svg v-if="!!modelValue" width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2 5l2.5 2.5L8 2.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>

      <!-- 文本 -->
      <div class="select-text">
        <span v-if="selectedModel" class="selected-label">{{ selectedModel.name }}</span>
        <span v-else class="placeholder-label">{{ placeholder }}</span>
        <span v-if="selectedModel" class="selected-id">{{ selectedModel.model_id }}</span>
      </div>

      <!-- 右侧箭头 -->
      <div class="select-arrow">
        <svg v-if="loading" width="14" height="14" viewBox="0 0 24 24" fill="none" class="spin">
          <path d="M21 12a9 9 0 1 1-6.219-8.56" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>
    </button>

    <!-- 下拉面板 -->
    <Transition name="dropdown">
      <div v-if="isOpen" class="model-select-dropdown" ref="dropdownRef">
        <div v-if="loading" class="dropdown-loading">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" class="spin">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          加载中...
        </div>
        <div v-else-if="options.length === 0" class="dropdown-empty">
          暂无可用模型
        </div>
        <div v-else class="dropdown-list">
          <div
            v-for="option in options"
            :key="option.id"
            class="dropdown-item"
            :class="{ selected: option.id === modelValue }"
            @click="selectOption(option)"
          >
            <div class="item-left">
              <div class="item-name">{{ option.name }}</div>
              <div class="item-id">{{ option.model_id }}</div>
            </div>
            <div class="item-right">

              <svg v-if="option.id === modelValue" width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

export interface ModelOption {
  id: number
  name: string
  model_id: string
  model_type?: string
  enabled?: boolean
}

const props = withDefaults(defineProps<{
  modelValue: number | null
  options: ModelOption[]
  placeholder?: string
  disabled?: boolean
  loading?: boolean
}>(), {
  placeholder: '请选择模型',
  disabled: false,
  loading: false,
})

const emit = defineEmits<{
  'update:modelValue': [id: number | null]
}>()

const isOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const selectedModel = computed(() =>
  props.options.find(m => m.id === props.modelValue) || null
)

function formatLabel(m: ModelOption): string {
  return `${m.name} (${m.model_id})`
}

function toggleDropdown() {
  if (props.disabled || props.loading) return
  isOpen.value = !isOpen.value
}

function selectOption(option: ModelOption) {
  emit('update:modelValue', option.id)
  isOpen.value = false
}

function handleOutsideClick(e: MouseEvent) {
  const wrap = dropdownRef.value?.parentElement
  if (wrap && !wrap.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleOutsideClick, true))
onUnmounted(() => document.removeEventListener('click', handleOutsideClick, true))
</script>

<style scoped>
/* ===== Wrapper ===== */
.model-select-wrap {
  position: relative;
  width: 100%;
  font-family: var(--font-sans);
}

/* ===== Trigger ===== */
.model-select-trigger {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 38px;
  background: var(--admin-input-bg, var(--bg-input, #0f0f1a));
  border: 1.5px solid rgba(20, 184, 166, 0.25);
  border-radius: 9px;
  padding: 0;
  cursor: pointer;
  overflow: hidden;
  transition:
    border-color 200ms var(--ease-smooth),
    box-shadow 200ms var(--ease-smooth),
    background 200ms var(--ease-smooth);
  box-sizing: border-box;
}

.model-select-trigger:hover:not(.is-disabled) {
  border-color: rgba(20, 184, 166, 0.5);
  background: var(--bg-hover, #1a1a28);
}

.model-select-trigger.has-value {
  border-color: rgba(34, 211, 238, 0.45);
  background: rgba(34, 211, 238, 0.04);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.12) inset;
}

.model-select-trigger.has-value:hover:not(.is-disabled) {
  border-color: rgba(34, 211, 238, 0.7);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.18) inset, 0 0 12px rgba(34, 211, 238, 0.08);
}

.model-select-trigger.is-open.has-value {
  border-color: rgba(34, 211, 238, 0.65);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.2) inset;
}

.model-select-trigger.is-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ===== Left indicator bar ===== */
.select-indicator {
  width: 3px;
  min-height: 38px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 200ms var(--ease-smooth);
  border-radius: 9px 0 0 9px;
}

.select-indicator.active {
  background: linear-gradient(180deg, #22d3ee, #06b6d4);
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.4);
}

.select-indicator svg {
  color: #0d0d14;
}

/* ===== Text area ===== */
.select-text {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  min-width: 0;
  overflow: hidden;
}

.selected-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #eeeef0);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.placeholder-label {
  font-size: 13px;
  color: var(--text-muted, #6b7280);
  white-space: nowrap;
}

.selected-id {
  font-size: 11px;
  color: var(--text-muted, #6b7280);
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  white-space: nowrap;
  opacity: 0.7;
  flex-shrink: 0;
}

/* ===== Arrow ===== */
.select-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  flex-shrink: 0;
  color: var(--accent-color, #14b8a6);
  transition: transform 200ms var(--ease-smooth), color 200ms;
}

.is-open .select-arrow {
  transform: rotate(180deg);
}

/* ===== Dropdown panel ===== */
.model-select-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: var(--admin-card-bg, var(--bg-card, #13132a));
  border: 1.5px solid rgba(20, 184, 166, 0.35);
  border-radius: 12px;
  overflow: hidden;
  z-index: 9999;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(20, 184, 166, 0.08) inset;
}

.dropdown-loading,
.dropdown-empty {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--text-muted, #6b7280);
}

.dropdown-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.dropdown-list {
  max-height: 260px;
  overflow-y: auto;
  padding: 6px;
}

.dropdown-list::-webkit-scrollbar {
  width: 4px;
}

.dropdown-list::-webkit-scrollbar-track {
  background: transparent;
}

.dropdown-list::-webkit-scrollbar-thumb {
  background: rgba(20, 184, 166, 0.3);
  border-radius: 2px;
}

/* ===== Dropdown item ===== */
.dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 120ms var(--ease-smooth);
  border: 1px solid transparent;
  gap: 8px;
}

.dropdown-item:hover {
  background: rgba(20, 184, 166, 0.12);
}

.dropdown-item.selected {
  background: rgba(34, 211, 238, 0.08);
  border-color: rgba(34, 211, 238, 0.2);
}

.item-left {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #eeeef0);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-id {
  font-size: 11px;
  color: var(--text-muted, #6b7280);
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.dropdown-item.selected .item-right svg {
  color: #22d3ee;
}

/* ===== Spinner ===== */
.spin {
  animation: spin 800ms linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ===== Dropdown animation ===== */
.dropdown-enter-active {
  transition: opacity 150ms var(--ease-out), transform 150ms var(--ease-out);
}

.dropdown-leave-active {
  transition: opacity 100ms var(--ease-in), transform 100ms var(--ease-in);
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}

/* ===== Reduced motion ===== */
@media (prefers-reduced-motion: reduce) {
  .dropdown-enter-active,
  .dropdown-leave-active {
    transition: none;
  }
  .spin {
    animation: none;
  }
  .model-select-trigger,
  .select-indicator,
  .select-arrow {
    transition: none;
  }
}
</style>
