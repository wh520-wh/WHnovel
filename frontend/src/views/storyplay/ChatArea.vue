<template>
  <div
    ref="chatAreaRef"
    v-loading="storyStore.loading || chatStore.loading"
    class="chat-area"
    :class="{
      'has-bg':
        !!storyStore.currentStory?.background_image &&
        settingsStore.settings.show_background_image !== false,
      'is-immersive': immersive,
    }"
    :style="
      storyStore.currentStory?.background_image &&
      settingsStore.settings.show_background_image !== false
        ? { backgroundImage: `url(${storyStore.currentStory.background_image})` }
        : undefined
    "
  >
    <template v-if="!hasStarted">
      <transition name="starter-fade" mode="out-in">
        <!-- eslint-disable-next-line vue/require-toggle-inside-transition -- v-if on parent template controls visibility -->
        <div class="starter-wrap">
          <el-card class="starter-card">
            <template #header>
              <span>开始聊天</span>
            </template>
            <p class="starter-tip">
              输入你想要的开场要求（例如：主角身份、关系基调、冲突方向），系统会用首次模型生成开场。
            </p>
            <textarea
              :key="openingBounceKey || undefined"
              v-model="openingRequirement"
              class="opening-textarea"
              :placeholder="
                storyStore.currentStory?.opening_requirement || '请输入开场要求...'
              "
              :disabled="chatStore.sending"
              rows="5"
              @click="handleOpeningClick"
            ></textarea>
            <div class="starter-actions">
              <button class="start-chat-btn" :disabled="chatStore.sending" @click="emit('start-story')">
                <span v-if="chatStore.sending">生成中...</span>
                <span v-else>开始聊天</span>
              </button>
            </div>
          </el-card>
        </div>
      </transition>
    </template>

    <template v-else>
      <MessageList
        :select-mode="selectMode"
        :selected-message-ids="selectedMessageIds"
        :disable-elastic="!!settingsStore.settings.disable_chat_bubble_elastic"
        :auto-follow="autoFollow"
        :pending-message-count="pendingMessageCount"
        :badge-bouncing="badgeBouncing"
        :user-scrolled-up="userScrolledUp"
        :deleting-in-progress="deletingInProgress"
        @recall-animation-end="emit('recall-animation-end', $event)"
        @select="onSelect"
        @long-press="emit('long-press', $event)"
        @exit-select-mode="emit('exit-select-mode')"
        @clear-selected="emit('clear-selected')"
        @bulk-delete="emit('bulk-delete')"
        @jump-to-latest="emit('jump-to-latest')"
        @scroll-to-latest="emit('scroll-to-latest')"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import MessageList from './MessageList.vue'
import { useChatStore } from '../../stores/chat'
import { useStoryStore } from '../../stores/story'
import { useSettingsStore } from '../../stores/settings'

defineProps<{
  immersive: boolean
  selectMode: boolean
  selectedMessageIds: Set<string | number>
  autoFollow: boolean
  pendingMessageCount: number
  badgeBouncing: boolean
  userScrolledUp: boolean
  deletingInProgress: boolean
}>()

const emit = defineEmits<{
  'update:openingRequirement': [value: string]
  'start-story': []
  'recall-animation-end': [messageId: string | number]
  select: [messageId: string | number, checked: boolean]
  'long-press': [messageId: string | number]
  'exit-select-mode': []
  'clear-selected': []
  'bulk-delete': []
  'jump-to-latest': []
  'scroll-to-latest': []
}>()

const storyStore = useStoryStore()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()

const openingRequirement = defineModel<string>('openingRequirement', { default: '' })

const hasStarted = computed(() => chatStore.messages.some((m) => m.role === 'assistant'))

const chatAreaRef = ref<HTMLElement | null>(null)
defineExpose({ chatAreaRef })

// MessageList 的 select 事件携带 (messageId, checked) 两个参数，透传给父
function onSelect(messageId: string | number, checked: boolean) {
  emit('select', messageId, checked)
}

// Q弹动画：每次点击重挂载后播放
const openingBounceKey = ref(0)
function handleOpeningClick() {
  openingBounceKey.value++
  nextTick(() => {
    const el = document.querySelector('.opening-textarea') as HTMLTextAreaElement
    el?.focus()
  })
}
</script>

<style scoped>
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px 0;
  background: var(--chat-area-gradient);
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
  scroll-padding-bottom: calc(var(--mobile-input-offset) + var(--mobile-options-height) + 24px);
  position: relative;
}

.chat-area.has-bg {
  background-size: cover;
  background-position: center;
}

.chat-area.has-bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--chat-bg-overlay);
  z-index: 1;
  pointer-events: none;
}

.chat-area.is-immersive {
  max-width: 820px;
  margin: 0 auto;
}

.starter-wrap {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px 0;
  position: relative;
  z-index: 2;
}

.starter-card {
  width: min(680px, 100%);
  border-radius: 16px;
  border-color: var(--border-color);
  background: var(--bg-card);
}

.starter-tip {
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.65;
}

.starter-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.opening-textarea {
  width: 100%;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.65;
  outline: none;
  resize: none;
  transition:
    border-color var(--duration-base) var(--ease-smooth),
    box-shadow var(--duration-base) var(--ease-smooth);
  box-shadow: var(--shadow-sm);
}

.opening-textarea::placeholder {
  color: var(--text-muted);
}

.opening-textarea:focus {
  border-color: var(--accent-color);
  box-shadow:
    var(--shadow-sm),
    0 0 0 3px color-mix(in srgb, var(--accent-color) 20%, transparent);
}

/* Q弹动画：每次 key 变化时重挂载后播放 */
.opening-textarea.input-bounce {
  animation: input-bounce-in 280ms var(--ease-spring) both;
}

/* input-bounce-in 已提取到全局 style.css */

.start-chat-btn {
  height: 44px;
  padding: 0 28px;
  border-radius: 22px;
  border: none;
  background: var(--user-bubble);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-smooth),
    box-shadow var(--duration-fast) var(--ease-smooth),
    background-color var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth);
  box-shadow:
    var(--shadow-md),
    0 0 0 0 var(--accent-glow);
}

.start-chat-btn:hover:not(:disabled) {
  transform: scale(1.04);
  box-shadow: var(--shadow-lg), var(--shadow-glow);
}

.start-chat-btn:active:not(:disabled) {
  transform: scale(0.96);
  transition-duration: 80ms;
}

.start-chat-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* ---- 开场卡淡出过渡 ---- */
.starter-fade-leave-active {
  transition: opacity 300ms var(--ease-smooth);
}
.starter-fade-leave-to {
  opacity: 0;
}

@media (max-width: 767px) {
  .chat-area {
    flex: 1;
    overflow: visible;
    padding-bottom: 12px;
  }

  /* 开场卡适配 */
  .starter-tip {
    font-size: 14px;
    padding: 0 4px;
  }

  .start-chat-btn {
    width: 100%;
    height: 48px;
  }
}

@media (min-width: 768px) and (max-width: 1199px) {
  .chat-area {
    padding: 16px 18px 0;
  }

  .starter-card {
    width: min(760px, 100%);
  }
}

@media (min-width: 1200px) {
  .chat-area {
    padding: 16px 24px 0;
  }
}
</style>
