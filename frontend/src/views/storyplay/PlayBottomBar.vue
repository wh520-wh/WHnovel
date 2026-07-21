<template>
  <transition name="input-fade">
    <div v-if="hasStarted && !selectMode" ref="quickOptionsRef" class="quick-options-wrap">
      <QuickOptions
        :options="displayOptions"
        :disabled="chatStore.sending || chatStore.optionsLocked"
        :loading="chatStore.generatingOptions"
        :locked="chatStore.optionsLocked && !chatStore.generatingOptions"
        :locked-option="chatStore.lockedOption"
        :history-depth="chatStore.optionsHistoryDepth"
        @select="emit('select-option', $event)"
        @restore="emit('restore-options')"
      />
    </div>
  </transition>

  <transition name="input-fade">
    <ChatComposer
      v-if="(!immersive || immersiveUiVisible) && !selectMode"
      ref="composerRef"
      v-model="inputText"
      :disabled="!hasStarted"
      :send-busy="chatStore.sending"
      :thinking="chatStore.streaming && !chatStore.awaitingTail"
      :awaiting-tail="chatStore.awaitingTail"
      :menu-active="leftMenuVisible"
      :show-spinner="chatStore.sending || chatStore.streaming || chatStore.awaitingTail"
      :generating-options="chatStore.generatingOptions"
      :generating-options-failed="chatStore.generatingOptionsFailed"
      :story-id="storyId"
      :archive-id="archiveId"
      @send="emit('send', $event)"
      @toggle-menu="emit('toggle-menu')"
      @focus="emit('focus')"
      @blur="emit('blur')"
      @resized="emit('resized', $event)"
      @retry-options="emit('retry-options')"
    />
  </transition>

  <!-- 左侧气泡菜单 -->
  <BubbleMenu
    :visible="leftMenuVisible"
    :items="leftMenuItems"
    :trigger-element="plusBtnRef"
    position="top-right"
    @close="leftMenuVisible = false"
  />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import ChatComposer from '../../components/ChatComposer.vue'
import QuickOptions from '../../components/QuickOptions.vue'
import BubbleMenu, { type BubbleMenuItem } from '../../components/BubbleMenu.vue'
import { useChatStore } from '../../stores/chat'

defineProps<{
  hasStarted: boolean
  immersive: boolean
  immersiveUiVisible: boolean
  selectMode: boolean
  leftMenuItems: BubbleMenuItem[]
  storyId: number | null
  archiveId: number | null
}>()

const emit = defineEmits<{
  'select-option': [option: string]
  'restore-options': []
  send: [value: string]
  'toggle-menu': []
  focus: []
  blur: []
  resized: [payload: { previousHeight: number; nextHeight: number }]
  'retry-options': []
}>()

const inputText = defineModel<string>('inputText', { default: '' })
const leftMenuVisible = defineModel<boolean>('leftMenuVisible', { default: false })

const chatStore = useChatStore()

const displayOptions = computed(() => {
  if (chatStore.currentOptions.length > 0) return chatStore.currentOptions
  return []
})

const quickOptionsRef = ref<HTMLElement | null>(null)
const composerRef = ref<{
  rootEl: HTMLDivElement | null
  textareaEl: HTMLTextAreaElement | null
  plusButtonEl: HTMLButtonElement | null
  resizeTextarea: () => void
  focusTextarea: () => void
  loadDraft: () => string | null
  clearDraft: () => void
} | null>(null)

const inputAreaRef = computed(() => composerRef.value?.rootEl ?? null)
const textareaRef = computed(() => composerRef.value?.textareaEl ?? null)
const plusBtnRef = computed(() => composerRef.value?.plusButtonEl ?? null)

defineExpose({
  composerRef,
  quickOptionsRef,
  inputAreaRef,
  textareaRef,
  plusBtnRef,
})
</script>

<style scoped>
.quick-options {
  max-width: 50vw;
  padding: 10px 0 6px;
  min-height: 40px;
  background: var(--bg-primary);
}

@media (max-width: 767px) {
  .quick-options {
    max-width: min(80vw, 300px);
  }

  .quick-options-wrap {
    padding: 6px 12px 0;
  }

  /* 选项按钮触控区域 */
  .option-btn {
    min-height: 44px;
    padding: 10px 16px;
    font-size: 14px;
  }
}

/* 输入/选项淡入淡出过渡 */
.input-fade-enter-active,
.input-fade-leave-active {
  transition:
    opacity 350ms var(--ease-smooth),
    transform 350ms var(--ease-smooth);
}
.input-fade-enter-from,
.input-fade-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
