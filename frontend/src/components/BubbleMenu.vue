<template>
  <Teleport to="body">
    <Transition
      name="bubble-menu-fade"
      @before-enter="onBeforeEnter"
      @enter="onEnter"
      @leave="onLeave"
    >
      <div v-if="visible" class="bubble-menu-overlay" @click="handleOverlayClick">
        <div ref="menuRef" class="bubble-menu" :style="menuStyle" @click.stop>
          <div class="bubble-menu-content">
            <template v-for="(item, index) in items" :key="index">
              <div v-if="openSubmenuIndex === index && item.children" class="bubble-submenu">
                <button
                  type="button"
                  class="bubble-menu-item submenu-back"
                  @click="openSubmenuIndex = null"
                >
                  <span class="bubble-menu-icon">
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
                      <polyline points="15 18 9 12 15 6" />
                    </svg>
                  </span>
                  <span class="bubble-menu-text">返回</span>
                </button>
                <button
                  v-for="(child, cIdx) in item.children"
                  :key="cIdx"
                  type="button"
                  class="bubble-menu-item"
                  @click="handleChildClick(child)"
                >
                  <span class="bubble-menu-text">{{ child.label }}</span>
                </button>
              </div>
              <button
                v-else
                type="button"
                class="bubble-menu-item"
                :disabled="item.disabled"
                @click="handleItemClick(item)"
              >
                <span class="bubble-menu-icon" v-html="item.icon"></span>
                <span class="bubble-menu-text">{{ item.label }}</span>
                <span v-if="item.children" class="submenu-arrow">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </span>
              </button>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const ANIM_ENTER_DURATION = 420
const ANIM_LEAVE_DURATION = 220
const SPRING_EASING = 'cubic-bezier(0.34, 1.56, 0.64, 1)'
const EXIT_EASING = 'cubic-bezier(0.4, 0, 0.8, 0.2)'

function onBeforeEnter(el: Element) {
  const menu = el.querySelector('.bubble-menu') as HTMLElement
  if (menu) {
    menu.style.opacity = '0'
    menu.style.transform = 'scale(0.82) translateY(12px)'
  }
}

function onEnter(el: Element, done: () => void) {
  const menu = el.querySelector('.bubble-menu') as HTMLElement
  if (menu) {
    requestAnimationFrame(() => {
      // 一次性设置：opacity + scale 同步开始
      menu.style.transition = [
        `opacity ${ANIM_ENTER_DURATION}ms ${SPRING_EASING}`,
        `transform ${ANIM_ENTER_DURATION}ms ${SPRING_EASING}`,
      ].join(', ')
      menu.style.opacity = '1'
      menu.style.transform = 'scale(1) translateY(0)'
    })
  }
  setTimeout(done, ANIM_ENTER_DURATION)
}

function onLeave(el: Element, done: () => void) {
  const menu = el.querySelector('.bubble-menu') as HTMLElement
  if (menu) {
    menu.style.transition = [
      `opacity ${ANIM_LEAVE_DURATION}ms ${EXIT_EASING}`,
      `transform ${ANIM_LEAVE_DURATION}ms ${EXIT_EASING}`,
    ].join(', ')
    menu.style.opacity = '0'
    menu.style.transform = 'scale(0.88)'
  }
  setTimeout(done, ANIM_LEAVE_DURATION)
}

export interface BubbleMenuItem {
  label: string
  icon: string
  disabled?: boolean
  action?: () => void
  children?: BubbleMenuChild[]
}

export interface BubbleMenuChild {
  label: string
  action: () => void
}

const props = defineProps<{
  visible: boolean
  items: BubbleMenuItem[]
  triggerElement: HTMLElement | null
  position: 'top-right' | 'bottom-left'
}>()

const emit = defineEmits<{
  close: []
}>()

const viewportTick = ref(0)
const openSubmenuIndex = ref<number | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const measuredWidth = ref(0)
let viewportListenersAttached = false

const MENU_GAP = 8

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function measureMenuWidth() {
  if (menuRef.value) {
    measuredWidth.value = menuRef.value.getBoundingClientRect().width
  }
}

function estimateMenuHeight(itemCount: number) {
  const rows = Math.max(itemCount, 1)
  return Math.min(360, rows * 46 + 20)
}

function bumpViewportTick() {
  viewportTick.value++
}

function attachViewportListeners() {
  if (viewportListenersAttached) return
  window.addEventListener('resize', bumpViewportTick, { passive: true })
  window.addEventListener('scroll', bumpViewportTick, { passive: true, capture: true })
  viewportListenersAttached = true
}

function detachViewportListeners() {
  if (!viewportListenersAttached) return
  window.removeEventListener('resize', bumpViewportTick)
  window.removeEventListener('scroll', bumpViewportTick, true)
  viewportListenersAttached = false
}

const menuStyle = computed(() => {
  void viewportTick.value // intentionally trigger reactive dependency
  // Access measuredWidth to make it a reactive dependency
  const actualWidth = measuredWidth.value
  if (!props.triggerElement) return {}

  const rect = props.triggerElement.getBoundingClientRect()
  const estimatedMenuHeight = estimateMenuHeight(props.items.length)
  // Use actual measured width if available, otherwise fall back to estimated
  const menuWidth = actualWidth || 280
  const maxLeft = Math.max(MENU_GAP, window.innerWidth - menuWidth - MENU_GAP)
  const maxTop = Math.max(MENU_GAP, window.innerHeight - estimatedMenuHeight - MENU_GAP)

  const style: Record<string, string> = {
    position: 'fixed',
  }

  if (props.position === 'top-right') {
    let left = rect.right + MENU_GAP
    let top = rect.top - estimatedMenuHeight - MENU_GAP
    let origin = 'left bottom'

    if (top < MENU_GAP) {
      top = rect.bottom + MENU_GAP
      origin = 'left top'
    }

    style.left = `${clamp(left, MENU_GAP, maxLeft)}px`
    style.top = `${clamp(top, MENU_GAP, maxTop)}px`
    style.transformOrigin = origin
  } else {
    let left = rect.left - menuWidth - MENU_GAP
    let top = rect.bottom + MENU_GAP
    let origin = 'right top'

    if (top > maxTop) {
      top = rect.top - estimatedMenuHeight - MENU_GAP
      origin = 'right bottom'
    }

    style.left = `${clamp(left, MENU_GAP, maxLeft)}px`
    style.top = `${clamp(top, MENU_GAP, maxTop)}px`
    style.transformOrigin = origin
  }

  return style
})

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      attachViewportListeners()
      bumpViewportTick()
      // Measure actual menu width after render
      nextTick(() => measureMenuWidth())
      return
    }
    openSubmenuIndex.value = null
    measuredWidth.value = 0
    detachViewportListeners()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  detachViewportListeners()
})

function handleOverlayClick() {
  emit('close')
}

function handleItemClick(item: BubbleMenuItem) {
  if (item.children) {
    // Find the index of this item in the items array
    const index = props.items.indexOf(item)
    openSubmenuIndex.value = index
    return
  }
  if (!item.disabled && item.action) {
    item.action()
    emit('close')
  }
}

function handleChildClick(child: BubbleMenuChild) {
  child.action()
  openSubmenuIndex.value = null
  emit('close')
}
</script>

<style scoped>
.bubble-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  background: transparent;
}

.bubble-menu {
  position: fixed;
  min-width: 220px;
  max-width: 280px;
  padding: 12px;
  background: var(--bubble-menu-solid-bg, var(--bg-elevated));
  border: 1px solid
    var(--bubble-menu-glass-border, color-mix(in srgb, var(--accent-color) 35%, transparent));
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-lg);
  z-index: 9999;
  overflow: hidden;
}

.bubble-menu-content {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: min(70vh, 360px);
  overflow-y: auto;
  scrollbar-width: none;
  isolation: isolate;
  z-index: 1;
}
.bubble-menu-content::-webkit-scrollbar {
  display: none;
}

.bubble-menu-item {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  min-height: 44px;
  border-radius: var(--radius-card);
  border: 1px solid transparent;
  background: transparent;
  color: var(--bubble-menu-text, #f8fafc);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  overflow: hidden;
  transition: background 0.2s var(--ease-smooth);
  text-align: left;
}

.bubble-menu-item:hover:not(:disabled) {
  background: var(
    --bubble-menu-item-hover-bg,
    color-mix(in srgb, var(--accent-color) 10%, transparent)
  );
}

.bubble-menu-item:active:not(:disabled) {
  background: var(
    --bubble-menu-item-active-bg,
    color-mix(in srgb, var(--accent-color) 18%, transparent)
  );
}

.bubble-menu-item:focus-visible {
  outline: 2px solid var(--bubble-menu-focus-ring, var(--accent-color));
  outline-offset: 2px;
}

.bubble-menu-item:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.submenu-arrow {
  margin-left: auto;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  z-index: 2;
}

.bubble-submenu {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bubble-menu-item.submenu-back {
  opacity: 0.7;
}

.bubble-menu-item.submenu-back:hover:not(:disabled) {
  opacity: 1;
}

.bubble-menu-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--bubble-menu-icon, var(--accent-hover));
  transition: color 0.2s var(--ease-smooth);
  z-index: 2;
}

.bubble-menu-icon :deep(svg) {
  width: 20px;
  height: 20px;
}

.bubble-menu-item:hover:not(:disabled) .bubble-menu-icon {
  color: var(--accent-hover);
}

.bubble-menu-item:disabled .bubble-menu-icon {
  color: var(--text-muted);
}

.bubble-menu-text {
  flex: 1;
  white-space: nowrap;
  z-index: 2;
  transition: color 0.2s var(--ease-smooth);
}

.bubble-menu-item:hover:not(:disabled) .bubble-menu-text {
  color: var(--text-primary);
}

@media (prefers-reduced-motion: reduce) {
  .bubble-menu,
  .bubble-menu-item {
    transition-duration: 80ms !important;
    animation: none !important;
  }

  .bubble-menu-item:hover:not(:disabled) {
    transform: none;
  }
}

@media (max-width: 767px) {
  .bubble-menu {
    min-width: min(220px, calc(100vw - 32px));
  }

  .bubble-menu-text {
    text-overflow: ellipsis;
    overflow: hidden;
  }
}
</style>
