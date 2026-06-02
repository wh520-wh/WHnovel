<template>
  <div
    class="story-card"
    ref="cardRef"
    role="button"
    tabindex="0"
    :aria-label="`进入故事：${displayTitle}`"
    @click="emit('click')"
    @keydown.enter.prevent="emit('click')"
    @keydown.space.prevent="emit('click')"
    @mousemove="handleMouseMove"
    @mouseleave="handleMouseLeave"
  >
    <div class="cardcover">
      <div class="card-cover-skeleton" :class="{ hidden: imageLoaded }"></div>
      <img
        :src="story.cover_image || defaultCover"
        :alt="displayTitle"
        loading="lazy"
        @load="handleImageLoad"
        :class="{ loaded: imageLoaded }"
      />
      <span class="card-category">{{ story.category }}</span>
      <button class="card-duplicate-btn" type="button" @click.stop="emit('duplicate', story.id)" title="复制故事">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      </button>
    </div>
    <div class="card-body">
      <h3 class="card-title">{{ displayTitle }}</h3>
      <p class="card-desc">{{ displayDescription }}</p>
      <p class="card-world-setting">{{ getFirstSentence(displayWorldSetting) }}</p>
      <div class="card-tags">
        <el-tag v-for="tag in displayTags" :key="tag" size="small" type="info" effect="dark">
          {{ tag }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import type { Story } from '../stores/story'
import { sanitizeAiDisplayText, sanitizeAiInlineText, sanitizeAiStringList } from '../utils/aiText'

const props = defineProps<{ story: Story }>()
const emit = defineEmits<{
  click: []
  duplicate: [id: number]
}>()

const displayTitle = computed(() => sanitizeAiInlineText(props.story.title) || props.story.title)
const displayDescription = computed(() => sanitizeAiDisplayText(props.story.description))
const displayWorldSetting = computed(() => sanitizeAiDisplayText(props.story.world_setting))
const displayTags = computed(() => sanitizeAiStringList(props.story.tags))

function getFirstSentence(text: string | undefined): string {
  if (!text) return ''
  // 取第一句话，以句号、问号、感叹号或换行分隔
  const match = text.match(/[^。！？\n]+[。！？\n]?/)
  return match ? match[0].trim() : text.slice(0, 30)
}

const cardRef = ref<HTMLElement>()
const imageLoaded = ref(false)

// 3D tilt state
const tiltX = ref(0)
const tiltY = ref(0)
const isHovering = ref(false)

// IntersectionObserver 修复内存泄漏
let observer: IntersectionObserver | null = null

onMounted(() => {
  if (!cardRef.value) return
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('card-visible')
          observer?.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.1 }
  )
  observer.observe(cardRef.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
})

function handleImageLoad() {
  imageLoaded.value = true
}

function handleMouseMove(e: MouseEvent) {
  if (!cardRef.value) return
  isHovering.value = true
  cardRef.value.classList.add('tilting')

  const rect = cardRef.value.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2

  // Calculate tilt angle based on mouse position
  // Max tilt: ±8 degrees
  const maxTilt = 8
  const mouseX = e.clientX - centerX
  const mouseY = e.clientY - centerY

  tiltX.value = (mouseY / (rect.height / 2)) * -maxTilt // Y axis rotation
  tiltY.value = (mouseX / (rect.width / 2)) * maxTilt // X axis rotation

  // Apply transform
  cardRef.value.style.transform = `
    perspective(1000px)
    rotateX(${tiltX.value}deg)
    rotateY(${tiltY.value}deg)
    translateY(-8px)
    scale(1.015)
  `
}

function handleMouseLeave() {
  if (!cardRef.value) return
  isHovering.value = false
  tiltX.value = 0
  tiltY.value = 0
  cardRef.value.classList.remove('tilting')
  cardRef.value.style.transform = ''
}

const defaultCover = 'data:image/svg+xml,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240" fill="%231a1a2e"><rect width="400" height="240"/><text x="200" y="130" text-anchor="middle" fill="%23555" font-size="24">No Cover</text></svg>'
)
</script>

<style scoped>
.story-card {
  background: var(--bg-card);
  border-radius: 16px;
  overflow: hidden;
  clip-path: inset(0 round 16px);
  cursor: pointer;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-md);
  opacity: 0;
  transform: translateY(16px);
  transition:
    box-shadow var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-smooth);
  will-change: transform;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}

/* 按压反馈 */
.story-card:active {
  transform: translateY(0) scale(0.98) !important;
  transition-duration: 80ms;
}

.story-card.card-visible {
  animation: card-enter 300ms var(--ease-spring) forwards;
}

@keyframes card-enter {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.story-card:hover {
  box-shadow: var(--shadow-lg), 0 0 0 1px color-mix(in srgb, var(--accent-color) 30%, transparent);
  border-color: color-mix(in srgb, var(--accent-color) 50%, transparent);
}

.story-card:hover:not(.tilting) {
  transform: translateY(-6px) scale(1.02);
  transition: transform var(--duration-base) var(--ease-spring),
              box-shadow var(--duration-base) var(--ease-smooth),
              border-color var(--duration-base) var(--ease-smooth);
}

.cardcover {
  position: relative;
  width: 100%;
  height: 180px;
  overflow: hidden;
  border-radius: 16px 16px 0 0;
}

/* 图片骨架屏 */
.card-cover-skeleton {
  position: absolute;
  inset: 0;
  background: var(--skeleton-base);
  z-index: 1;
  transition: opacity 300ms ease;
  border-radius: inherit;
}

.card-cover-skeleton.hidden {
  opacity: 0;
  pointer-events: none;
}

.cardcover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 350ms var(--ease-smooth), opacity 300ms ease;
  opacity: 0;
  border-radius: inherit;
}

.cardcover img.loaded {
  opacity: 1;
}

.story-card:hover .cardcover img {
  transform: scale(1.08);
}

.cardcover::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to bottom, transparent 40%, rgba(0,0,0,0.55) 100%);
  pointer-events: none;
  border-radius: inherit;
}

.card-category {
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--user-bubble);
  color: #fff;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  box-shadow: var(--shadow-sm);
  z-index: 1;
}

.card-duplicate-btn {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-smooth), transform var(--duration-fast) var(--ease-spring);
}

.story-card:hover .card-duplicate-btn {
  opacity: 1;
}

.card-duplicate-btn:hover {
  transform: scale(1.12);
  background: rgba(20, 184, 166, 0.6);
}

/* 移动端始终显示复制按钮（无 hover 状态） */
@media (max-width: 767px) {
  .card-duplicate-btn {
    opacity: 1;
    width: 36px;
    height: 36px;
  }
}

.card-body {
  padding: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-primary);
  font-family: var(--heading);
}

.card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 6px;
}

.card-world-setting {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
  opacity: 0.8;
  line-height: 1.4;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* 玻璃拟态标签 */
.card-tags :deep(.el-tag) {
  background: rgba(20, 184, 166, 0.15);
  border-color: rgba(20, 184, 166, 0.3);
  color: var(--accent-color);
}
</style>


