<template>
  <Transition name="immersive-fade">
    <header
      v-if="visible"
      class="play-topbar"
      :class="{ scrolled: topbarScrolled }"
    >
      <button class="topbar-back" @click="emit('back')">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>
      <div class="top-center" style="cursor: pointer" @click="emit('top-center-click')">
        <div
          class="char-avatar"
          :class="{ 'char-avatar--img': avatarSrc && !avatarImgError }"
        >
          <img
            v-if="avatarSrc && !avatarImgError"
            :src="avatarSrc"
            class="char-avatar-img"
            alt=""
            @error="avatarImgError = true"
          />
          <span v-else class="char-avatar-mono">{{
            (storyStore.currentStory?.title || 'AI').charAt(0)
          }}</span>
        </div>
        <div class="char-info">
          <span class="char-name">{{ storyStore.currentStory?.title || '故事互动' }}</span>
          <span v-if="currentChapter" class="char-subtitle char-chapter">{{
            currentChapter
          }}</span>
          <span v-else class="char-subtitle world-trigger">
            {{ storyStore.currentStory?.description?.slice(0, 12) || '私密会话' }}
            <svg
              class="char-subtitle-arrow"
              width="10"
              height="10"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </span>
        </div>
      </div>
      <div class="top-actions">
        <button
          class="topbar-icon-btn immersive-toggle"
          :disabled="immersiveTransitioning"
          title="沉浸模式"
          @click="emit('toggle-immersive')"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polygon
              points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
            />
          </svg>
        </button>
        <button
          ref="settingsBtnRef"
          class="topbar-icon-btn"
          :class="{ active: rightMenuVisible }"
          title="设置"
          @click="emit('toggle-right-menu')"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path
              d="M12 1v6m0 6v6m5.2-13.2l-4.2 4.2m0 6l4.2 4.2M23 12h-6m-6 0H1m18.2 5.2l-4.2-4.2m0-6l-4.2-4.2"
            />
          </svg>
        </button>
        <button
          class="topbar-icon-btn timeline-toggle"
          :class="{ active: timelineVisible }"
          title="时间线"
          @click="timelineVisible = !timelineVisible"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </button>
      </div>
    </header>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useStoryStore } from '../../stores/story'
import { useChatStore } from '../../stores/chat'

const props = defineProps<{
  immersiveMode: boolean
  immersiveUiVisible: boolean
  immersiveTransitioning: boolean
  topbarScrolled: boolean
  rightMenuVisible: boolean
}>()

const emit = defineEmits<{
  back: []
  'top-center-click': []
  'toggle-immersive': []
  'toggle-right-menu': []
}>()

const timelineVisible = defineModel<boolean>('timelineVisible', { default: false })

const storyStore = useStoryStore()
const chatStore = useChatStore()

const visible = computed(() => !props.immersiveMode || props.immersiveUiVisible)

// 会话页眉：头像与情境副标
const avatarImgError = ref(false)
const avatarSrc = computed(() => storyStore.currentStory?.cover_image || '')
const currentChapter = computed(() => {
  const ch = chatStore.currentStoryState?.chapter
  return ch && String(ch).trim() ? String(ch).trim() : ''
})

// 切换故事时重置图片错误状态
watch(
  () => storyStore.currentStory?.id,
  () => {
    avatarImgError.value = false
  },
)

const settingsBtnRef = ref<HTMLElement | null>(null)
defineExpose({ settingsBtnRef })
</script>

<style scoped>
.play-topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  border-bottom: 1px solid var(--border-color);
  background: var(--topbar-bg, var(--bg-card));
  gap: 8px;
  transition:
    opacity var(--duration-slow) var(--ease-smooth),
    transform var(--duration-slow) var(--ease-smooth),
    box-shadow var(--duration-fast) var(--ease-smooth);
}

.play-topbar.scrolled {
  box-shadow:
    var(--shadow-md),
    0 0 20px color-mix(in srgb, var(--accent-color) 10%, transparent);
}

[data-theme='light'] .play-topbar {
  background: rgba(250, 249, 252, 0.85);
  border-bottom-color: #e8e4ef;
}

.topbar-back {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-spring);
}
.topbar-back:hover {
  background: var(--bg-hover);
  border-color: var(--border-color);
  transform: scale(1.05);
}

.top-center {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.char-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--user-bubble);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.char-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.char-avatar-mono {
  line-height: 1;
  user-select: none;
}

/* bubble-pop-in 已提取到全局 style.css */

.char-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.char-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-subtitle {
  font-size: var(--text-xs, 12px);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.char-chapter {
  display: block;
}
.world-trigger {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 6px;
  transition:
    background 150ms,
    color 150ms;
}
.world-trigger:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}
.char-subtitle-arrow {
  transition: transform 200ms var(--ease-smooth);
  flex-shrink: 0;
}
.world-trigger:hover .char-subtitle-arrow {
  transform: translateY(1px);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.topbar-icon-btn {
  width: 44px;
  height: 44px;
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
    color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-spring);
}
.topbar-icon-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  transform: scale(1.05);
}
.topbar-icon-btn.active {
  background: color-mix(in srgb, var(--accent-color) 20%, transparent);
  color: var(--accent-color);
}

/* ---- 沉浸模式过渡（顶栏显隐） ---- */
.immersive-fade-enter-active,
.immersive-fade-leave-active {
  transition:
    opacity 300ms var(--ease-smooth),
    transform 300ms var(--ease-smooth),
    filter 300ms var(--ease-smooth);
}
.immersive-fade-enter-from,
.immersive-fade-leave-to {
  opacity: 0;
  transform: scale(0.97);
  filter: blur(4px);
}

/* ---- 时间线切换按钮：默认隐藏（桌面端） ---- */
.timeline-toggle {
  display: none;
}

@media (max-width: 767px) {
  .top-actions {
    gap: 8px;
  }

  .topbar-icon-btn {
    min-width: 44px;
    min-height: 44px;
  }
  .topbar-back {
    min-width: 44px;
    min-height: 44px;
  }

  .timeline-toggle {
    display: flex;
  }
}

@media (max-width: 380px) {
  .play-topbar {
    gap: 4px;
    padding: 0 8px;
  }

  .top-center {
    gap: 8px;
  }

  .char-avatar {
    width: 34px;
    height: 34px;
    font-size: 14px;
  }

  .char-subtitle {
    display: none;
  }

  .top-actions {
    gap: 2px;
  }

  .immersive-toggle {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .immersive-fade-enter-active,
  .immersive-fade-leave-active {
    transition-duration: 80ms !important;
    animation-duration: 1ms !important;
  }
}
</style>
