<template>
  <!-- 桌面端时间线（常驻左侧） -->
  <aside class="story-timeline" :class="{ 'is-immersive': immersive }">
    <StoryTimeline :messages="chatStore.messages" @jump="emit('jump', $event)" />
  </aside>

  <!-- 手机模式：时间线底部弹出面板 -->
  <Teleport to="body">
    <div
      v-if="mobileVisible"
      class="timeline-mobile-overlay"
      @click.self="emit('update:mobile-visible', false)"
    >
      <div class="timeline-mobile-sheet">
        <div class="timeline-mobile-handle" @click="emit('update:mobile-visible', false)"></div>
        <div class="timeline-mobile-header">
          <span>剧情时间线</span>
          <button class="timeline-close-btn" @click="emit('update:mobile-visible', false)">
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
        </div>
        <StoryTimeline
          class="timeline-mobile-body"
          :messages="chatStore.messages"
          @jump="emit('jump', $event)"
        />
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import StoryTimeline from '../../components/StoryTimeline.vue'
import { useChatStore } from '../../stores/chat'

defineProps<{
  immersive: boolean
}>()

const emit = defineEmits<{
  jump: [messageId: string | number]
  'update:mobile-visible': [value: boolean]
}>()

const mobileVisible = defineModel<boolean>('mobileVisible', { default: false })

const chatStore = useChatStore()
</script>

<style scoped>
.story-timeline {
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  scrollbar-width: none;
}

.story-timeline::-webkit-scrollbar {
  display: none;
}

.story-timeline.is-immersive {
  opacity: 0.85;
}

.timeline-close-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth);
}
.timeline-close-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* ---- 手机模式：时间线弹出面板 ---- */
@media (max-width: 767px) {
  .story-timeline {
    display: none;
  }

  .timeline-mobile-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
    animation: fade-in 150ms ease;
  }

  .timeline-mobile-sheet {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60vh;
    height: 60dvh;
    background: var(--bg-secondary);
    border-radius: 16px 16px 0 0;
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    animation: timeline-sheet-up 200ms var(--ease-out);
    padding-bottom: env(safe-area-inset-bottom);
  }

  .timeline-mobile-handle {
    width: 36px;
    height: 4px;
    background: var(--border-color);
    border-radius: 2px;
    margin: 8px auto;
    flex-shrink: 0;
  }

  .timeline-mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    flex-shrink: 0;
  }

  .timeline-mobile-body {
    flex: 1;
    overflow-y: auto;
  }

  .timeline-close-btn {
    min-width: 44px;
    min-height: 44px;
  }
}

@keyframes timeline-sheet-up {
  from {
    transform: translateY(100%);
  }
  to {
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .timeline-mobile-overlay,
  .timeline-mobile-sheet {
    animation: none;
  }
  .timeline-mobile-overlay {
    opacity: 1;
  }
}
</style>
