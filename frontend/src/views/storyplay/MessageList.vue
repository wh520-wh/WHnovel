<template>
  <transition-group
    name="chat-fade"
    tag="div"
    class="chat-messages"
    :class="{ 'elastic-disabled': disableElastic }"
    appear
  >
    <ChatMessage
      v-for="(msg, idx) in chatStore.messages"
      :key="msg.id"
      :msg="msg"
      :streaming="
        chatStore.streaming && idx === chatStore.messages.length - 1 && msg.role === 'assistant'
      "
      :select-mode="selectMode"
      :selected="selectedMessageIds.has(msg.id)"
      @recall-animation-end="emit('recall-animation-end', $event)"
      @select="onSelect"
      @long-press="emit('long-press', $event)"
    />
  </transition-group>

  <!-- 底部删除操作栏 -->
  <Transition name="delete-bar-fade">
    <div v-if="selectMode" class="delete-action-bar">
      <button class="delete-bar-btn cancel-btn" @click="emit('exit-select-mode')">取消</button>
      <span class="delete-bar-count">已选 {{ selectedMessageIds.size }} 项</span>
      <button
        v-if="selectedMessageIds.size > 0"
        class="delete-bar-btn clear-btn"
        @click="emit('clear-selected')"
      >
        取消全选
      </button>
      <button
        class="delete-bar-btn confirm-btn"
        :disabled="selectedMessageIds.size === 0 || deletingInProgress"
        @click="emit('bulk-delete')"
      >
        {{ deletingInProgress ? '删除中...' : '删除' }}
      </button>
    </div>
  </Transition>

  <!-- 新消息提示条：用户不在底部时出现 -->
  <button
    v-if="pendingMessageCount > 0 && !autoFollow"
    class="new-message-indicator"
    @click="emit('jump-to-latest')"
  >
    <span class="pending-badge" :class="{ 'badge-bounce': badgeBouncing }">{{
      pendingMessageCount
    }}</span>
    条新消息 ↑
  </button>

  <!-- 回到底部按钮：用户上翻时出现 -->
  <Transition name="back-bottom-fade">
    <button
      v-if="!autoFollow && userScrolledUp && pendingMessageCount === 0"
      class="back-to-bottom-btn"
      title="回到底部"
      @click="emit('scroll-to-latest')"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
  </Transition>
</template>

<script setup lang="ts">
import ChatMessage from '../../components/ChatMessage.vue'
import { useChatStore } from '../../stores/chat'

defineProps<{
  selectMode: boolean
  selectedMessageIds: Set<string | number>
  disableElastic: boolean
  autoFollow: boolean
  pendingMessageCount: number
  badgeBouncing: boolean
  userScrolledUp: boolean
  deletingInProgress: boolean
}>()

const emit = defineEmits<{
  'recall-animation-end': [messageId: string | number]
  select: [messageId: string | number, checked: boolean]
  'long-press': [messageId: string | number]
  'exit-select-mode': []
  'clear-selected': []
  'bulk-delete': []
  'jump-to-latest': []
  'scroll-to-latest': []
}>()

const chatStore = useChatStore()

function onSelect(messageId: string | number, checked: boolean) {
  emit('select', messageId, checked)
}
</script>

<style scoped>
/* ---- 聊天消息容器 ---- */
.chat-messages {
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 2;
}

.chat-fade-enter-active {
  /* 省略 opacity 过渡：bubble-pop-in 已自带完整 opacity 0->1 入场，
     再叠一层 opacity 过渡会造成 60ms 后 bubble 已在 1 但被父级 fade 拉回的视觉冲突。 */
  transition: none;
}
.chat-fade-enter-from {
  opacity: 0;
}

/* ---- 消息入场动画 ---- */

/* AI/助手消息：从底部滑入（:deep 穿透 scoped 到 ChatMessage.vue） */
:deep(.msg-ai) {
  animation: msg-ai-in 300ms cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.chat-messages.elastic-disabled :deep(.msg-ai) {
  animation: msg-ai-in-reduced 180ms ease-out both;
}

/* 用户消息：从右侧滑入 */
:deep(.msg-user) {
  animation: msg-user-in 300ms cubic-bezier(0.34, 1.3, 0.64, 1) both;
}

.chat-messages.elastic-disabled :deep(.msg-user) {
  animation: msg-user-in-reduced 180ms ease-out both;
}

/* 状态播报：从 scale + 淡入 + 边框脉冲 */
:deep(.msg-state) {
  animation:
    msg-state-enter 250ms ease-out both,
    msg-state-pulse 600ms ease-in-out 250ms 1;
}

@keyframes msg-slide-up {
  from {
    transform: translateY(12px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes msg-slide-right {
  from {
    transform: translateX(20px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes msg-state-enter {
  from {
    transform: scale(0.96);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes msg-state-pulse {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent-color) 30%, transparent);
  }
  50% {
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent-color) 15%, transparent);
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
  }
}

/* AI 消息 - 等离子玻璃弹性入场 */
@keyframes msg-ai-in {
  0% {
    opacity: 0;
    transform: scale(0.8) translateY(20px);
    filter: blur(4px);
  }
  50% {
    opacity: 1;
    transform: scale(1.02) translateY(-2px);
    filter: blur(0);
  }
  70% {
    transform: scale(0.98) translateY(1px);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
    filter: blur(0);
  }
}

/* 用户消息 - 右侧滑入 + 发光边框 */
@keyframes msg-user-in {
  0% {
    opacity: 0;
    transform: translateX(30px);
  }
  40% {
    box-shadow:
      0 0 20px rgba(236, 72, 153, 0.4),
      0 0 40px rgba(236, 72, 153, 0.2);
  }
  100% {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes msg-ai-in-reduced {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes msg-user-in-reduced {
  from {
    opacity: 0;
    transform: translateX(12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* prefers-reduced-motion 降级 */
@media (prefers-reduced-motion: reduce) {
  .msg-ai,
  .msg-user,
  .msg-state {
    animation: none;
  }
  .badge-bounce,
  .pending-badge {
    animation: none;
  }
}

/* ---- 新消息提示条 ---- */
.new-message-indicator {
  position: sticky;
  bottom: calc(var(--mobile-input-offset) + var(--mobile-options-height) + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 7px 18px;
  border-radius: 20px;
  border: none;
  background: var(--accent-color);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  box-shadow:
    var(--shadow-md),
    0 0 16px var(--accent-glow);
  z-index: 5;
  width: fit-content;
  margin: 0 auto;
  display: block;
  animation: indicator-pop-in 220ms var(--ease-spring) both;
  transition: transform var(--duration-fast) var(--ease-spring);
}

.new-message-indicator:hover {
  transform: translateX(-50%) scale(1.04);
}

/* ---- 数字徽章弹跳动画 ---- */
.pending-badge {
  transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
  display: inline-block;
}

@keyframes badge-bounce {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.35);
  }
}

.new-message-indicator:active {
  transform: translateX(-50%) scale(0.97);
  transition-duration: 80ms;
}

@keyframes indicator-pop-in {
  0% {
    opacity: 0;
    transform: translateX(-50%) scale(0.7) translateY(10px);
  }
  60% {
    opacity: 1;
    transform: translateX(-50%) scale(1.05) translateY(0);
  }
  100% {
    opacity: 1;
    transform: translateX(-50%) scale(1) translateY(0);
  }
}

/* ---- 回到底部按钮 ---- */
.back-to-bottom-btn {
  position: sticky;
  bottom: calc(var(--mobile-input-offset) + var(--mobile-options-height) + 8px);
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  z-index: 5;
  margin: 0 auto;
  transition:
    background 150ms var(--ease-smooth),
    color 150ms var(--ease-smooth),
    transform 150ms var(--ease-spring),
    box-shadow 150ms var(--ease-smooth);
}

.back-to-bottom-btn:hover {
  background: var(--bg-hover);
  color: var(--accent-color);
  transform: translateX(-50%) scale(1.08);
  box-shadow: var(--shadow-lg);
}

.back-to-bottom-btn:active {
  transform: translateX(-50%) scale(0.95);
  transition-duration: 80ms;
}

.back-bottom-fade-enter-active,
.back-bottom-fade-leave-active {
  transition:
    opacity 200ms var(--ease-smooth),
    transform 200ms var(--ease-spring);
}
.back-bottom-fade-enter-from,
.back-bottom-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

/* ---- 删除操作栏 ---- */
.delete-action-bar {
  position: fixed;
  left: 50%;
  bottom: max(24px, calc(var(--keyboard-offset, 0px) + env(safe-area-inset-bottom)));
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  border-radius: 24px;
  background: var(--bg-card);
  border: 1px solid rgba(20, 184, 166, 0.35);
  z-index: 50;
  box-shadow:
    var(--shadow-lg),
    0 0 24px rgba(20, 184, 166, 0.18);
}

.delete-bar-btn {
  padding: 8px 20px;
  border-radius: 16px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition:
    transform 150ms,
    box-shadow 150ms,
    background-color 150ms,
    border-color 150ms,
    color 150ms;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-secondary);
}
.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}

.clear-btn {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-secondary);
}
.clear-btn:hover {
  background: rgba(255, 255, 255, 0.14);
}

.confirm-btn {
  background: var(--accent-color);
  color: #fff;
}
.confirm-btn:hover:not(:disabled) {
  filter: brightness(1.1);
}
.confirm-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.confirm-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.delete-bar-count {
  flex: 1;
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.delete-bar-fade-enter-active,
.delete-bar-fade-leave-active {
  transition:
    opacity 250ms var(--ease-smooth),
    transform 250ms var(--ease-smooth);
}
.delete-bar-fade-enter-from,
.delete-bar-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(16px);
}

@media (max-width: 767px) {
  /* 消息字体大小 */
  .chat-message .msg-content {
    font-size: 15px;
    line-height: 1.6;
  }

  .msg-time {
    font-size: 11px;
  }

  /* 新消息指示器触控优化 */
  .new-message-indicator {
    min-height: 40px;
    padding: 10px 20px;
  }

  .back-to-bottom-btn {
    width: 44px;
    height: 44px;
  }

  /* 删除操作栏移动端适配：固定定位，确保始终可见 */
  .delete-action-bar {
    left: 16px;
    right: 16px;
    bottom: max(16px, calc(var(--keyboard-offset, 0px) + env(safe-area-inset-bottom)));
    padding: 10px 16px;
    gap: 8px;
  }

  .delete-bar-btn {
    padding: 10px 16px;
    min-height: 44px;
  }

  .delete-bar-count {
    font-size: 12px;
  }
}
</style>
