<template>
  <div class="pill-nav-container">
    <nav
      class="pill-nav"
      :class="[className, { 'pill-nav--mobile-compact': isMobileCompactViewport }]"
      aria-label="Primary"
      :style="cssVars"
    >
      <div ref="navItemsRef" class="pill-nav-track">
        <ul
          class="pill-list"
          :class="{ 'pill-list--mobile-compact': isMobileCompactViewport }"
          role="menubar"
        >
          <li
            v-for="(item, i) in items"
            :key="item.key || item.href || `item-${i}`"
            :class="{ 'pill-list-item--mobile-compact': isMobileCompactViewport }"
            role="none"
          >
            <RouterLink
              v-if="isRouterLink(item.href)"
              role="menuitem"
              :to="item.href!"
              :class="[pillClass(item), { 'pill--mobile-compact': isMobileCompactViewport }]"
              :aria-label="item.ariaLabel || item.label"
              @mouseenter="handleEnter(i)"
              @mouseleave="handleLeave(i)"
              @click="handleItemAction(item)"
              @touchstart="handleTouchAction(item, $event)"
            >
              <span :ref="(el) => assignCircleRef(i, el)" class="hover-circle" aria-hidden="true" />
              <span class="label-stack">
                <span class="pill-label">{{ item.label }}</span>
                <span class="pill-label-hover" aria-hidden="true">{{ item.label }}</span>
              </span>
            </RouterLink>
            <a
              v-else-if="item.href"
              role="menuitem"
              :href="item.href"
              :class="[pillClass(item), { 'pill--mobile-compact': isMobileCompactViewport }]"
              :aria-label="item.ariaLabel || item.label"
              @mouseenter="handleEnter(i)"
              @mouseleave="handleLeave(i)"
              @click="handleItemAction(item)"
            >
              <span :ref="(el) => assignCircleRef(i, el)" class="hover-circle" aria-hidden="true" />
              <span class="label-stack">
                <span class="pill-label">{{ item.label }}</span>
                <span class="pill-label-hover" aria-hidden="true">{{ item.label }}</span>
              </span>
            </a>
            <button
              v-else
              type="button"
              role="menuitem"
              :class="[pillClass(item), { 'pill--mobile-compact': isMobileCompactViewport }]"
              :aria-label="item.ariaLabel || item.label"
              @mouseenter="handleEnter(i)"
              @mouseleave="handleLeave(i)"
              @click="handleItemAction(item)"
              @touchstart="handleTouchAction(item, $event)"
            >
              <span :ref="(el) => assignCircleRef(i, el)" class="hover-circle" aria-hidden="true" />
              <span class="label-stack">
                <span class="pill-label">{{ item.label }}</span>
                <span class="pill-label-hover" aria-hidden="true">{{ item.label }}</span>
              </span>
            </button>
          </li>
        </ul>
      </div>
    </nav>
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComponentPublicInstance,
} from 'vue'
import { RouterLink } from 'vue-router'
import { gsap } from 'gsap'

interface PillNavItem {
  label: string
  href?: string
  ariaLabel?: string
  key?: string
  onClick?: () => void
}

const props = withDefaults(
  defineProps<{
    items: PillNavItem[]
    activeHref?: string
    activeKey?: string
    className?: string
    ease?: string
    baseColor?: string
    pillColor?: string
    hoveredPillTextColor?: string
    pillTextColor?: string
    initialLoadAnimation?: boolean
  }>(),
  {
    activeHref: undefined,
    activeKey: undefined,
    className: '',
    ease: 'power3.easeOut',
    baseColor: '#fff',
    pillColor: '#120F17',
    hoveredPillTextColor: '#120F17',
    pillTextColor: undefined,
    initialLoadAnimation: true,
  },
)

const resolvedPillTextColor = computed(() => props.pillTextColor ?? props.baseColor)
const isMobileCompactViewport = ref(
  typeof window !== 'undefined' ? window.innerWidth <= 768 : false,
)
const circleRefs = ref<Array<HTMLElement | null>>([])
const tlRefs = ref<Array<gsap.core.Timeline | null>>([])
const activeTweenRefs = ref<Array<gsap.core.Tween | null>>([])
const navItemsRef = ref<HTMLElement | null>(null)

const cssVars = computed(() => ({
  '--base': props.baseColor,
  '--pill-bg': props.pillColor,
  '--hover-text': props.hoveredPillTextColor,
  '--pill-text': resolvedPillTextColor.value,
}))

function assignCircleRef(index: number, el: Element | ComponentPublicInstance | null) {
  if (el instanceof Element) {
    circleRefs.value[index] = el as HTMLElement
    return
  }
  circleRefs.value[index] = (el?.$el as HTMLElement | undefined) ?? null
}

function isExternalLink(href?: string) {
  if (!href) return false
  return (
    href.startsWith('http://') ||
    href.startsWith('https://') ||
    href.startsWith('//') ||
    href.startsWith('mailto:') ||
    href.startsWith('tel:') ||
    href.startsWith('#')
  )
}

function isRouterLink(href?: string) {
  return !!href && !isExternalLink(href)
}

function isActiveItem(item: PillNavItem) {
  if (props.activeKey && item.key) return props.activeKey === item.key
  return props.activeHref === item.href
}

function pillClass(item: PillNavItem) {
  return `pill${isActiveItem(item) ? ' is-active' : ''}`
}

function handleItemAction(item: PillNavItem) {
  if (recentTouchFlag) return
  item.onClick?.()
}

let recentTouchFlag = false

function handleTouchAction(item: PillNavItem, e: TouchEvent) {
  // 只有 onClick 项目才阻止 click 事件（因为 touchstart 已触发导航）
  // RouterLink 项目不设置 flag，让 click 事件自然触发导航
  if (item.onClick) {
    recentTouchFlag = true
    e.preventDefault()
    item.onClick?.()
    setTimeout(() => {
      recentTouchFlag = false
    }, 350)
  }
}

function handleEnter(index: number) {
  const tl = tlRefs.value[index]
  if (!tl) return
  activeTweenRefs.value[index]?.kill()
  activeTweenRefs.value[index] = tl.tweenTo(tl.duration(), {
    duration: 0.3,
    ease: props.ease,
    overwrite: 'auto',
  })
}

function handleLeave(index: number) {
  const tl = tlRefs.value[index]
  if (!tl) return
  activeTweenRefs.value[index]?.kill()
  activeTweenRefs.value[index] = tl.tweenTo(0, {
    duration: 0.2,
    ease: props.ease,
    overwrite: 'auto',
  })
}

let cleanupAnimations: (() => void) | null = null

async function setupAnimations() {
  cleanupAnimations?.()
  await nextTick()

  const layout = () => {
    isMobileCompactViewport.value = window.innerWidth <= 768
    circleRefs.value.forEach((circle, index) => {
      if (!circle?.parentElement) return

      const pill = circle.parentElement as HTMLElement
      const rect = pill.getBoundingClientRect()
      const { width: w, height: h } = rect
      if (!w || !h) return
      const R = ((w * w) / 4 + h * h) / (2 * h)
      const D = Math.ceil(2 * R) + 2
      const delta = Math.ceil(R - Math.sqrt(Math.max(0, R * R - (w * w) / 4))) + 1
      const originY = D - delta

      circle.style.width = `${D}px`
      circle.style.height = `${D}px`
      circle.style.bottom = `-${delta}px`

      gsap.set(circle, {
        xPercent: -50,
        scale: 0,
        transformOrigin: `50% ${originY}px`,
      })

      const label = pill.querySelector('.pill-label')
      const white = pill.querySelector('.pill-label-hover')

      if (label) gsap.set(label, { y: 0 })
      if (white) gsap.set(white, { y: h + 12, opacity: 0 })

      tlRefs.value[index]?.kill()
      const tl = gsap.timeline({ paused: true })
      tl.to(
        circle,
        { scale: 1.2, xPercent: -50, duration: 2, ease: props.ease, overwrite: 'auto' },
        0,
      )

      if (label) {
        tl.to(label, { y: -(h + 8), duration: 2, ease: props.ease, overwrite: 'auto' }, 0)
      }

      if (white) {
        gsap.set(white, { y: Math.ceil(h + 100), opacity: 0 })
        tl.to(white, { y: 0, opacity: 1, duration: 2, ease: props.ease, overwrite: 'auto' }, 0)
      }

      tlRefs.value[index] = tl
    })
  }

  layout()

  const onResize = () => {
    layout()
  }

  window.addEventListener('resize', onResize)

  if (document.fonts?.ready) {
    document.fonts.ready.then(layout).catch(() => {})
  }

  if (props.initialLoadAnimation) {
    const navItems = navItemsRef.value

    if (navItems) {
      gsap.set(navItems, { width: 0, overflow: 'hidden' })
      gsap.to(navItems, {
        width: 'auto',
        duration: 0.6,
        ease: props.ease,
      })
    }
  }

  cleanupAnimations = () => {
    window.removeEventListener('resize', onResize)
    tlRefs.value.forEach((tl) => tl?.kill())
    activeTweenRefs.value.forEach((tween) => tween?.kill())
  }
}

onMounted(() => {
  setupAnimations()
})

watch(
  () => [props.items, props.ease, props.initialLoadAnimation],
  () => {
    setupAnimations()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  cleanupAnimations?.()
})
</script>

<style scoped>
.pill-nav-container {
  position: relative;
  width: 100%;
  display: flex;
  justify-content: center;
  z-index: 20;
}

@media (max-width: 767px) {
  .pill-nav-container {
    justify-content: stretch;
  }
}

.pill-nav {
  --nav-h: 42px;
  --pill-pad-x: 18px;
  --pill-gap: 3px;
  width: 100%;
  max-width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  box-sizing: border-box;
}

.pill-nav-track {
  display: flex;
  justify-content: center;
  max-width: 100%;
}

.pill-list {
  list-style: none;
  display: flex;
  align-items: stretch;
  gap: var(--pill-gap);
  margin: 0;
  padding: 3px;
  height: var(--nav-h);
  max-width: 100%;
  background: var(--base, #000);
  border-radius: 9999px;
}

.pill-list > li {
  display: flex;
  height: 100%;
}

.pill,
button.pill {
  font: inherit;
}

.pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 0 var(--pill-pad-x);
  background: var(--pill-bg, #fff);
  color: var(--pill-text, var(--base, #000));
  text-decoration: none;
  border-radius: 9999px;
  box-sizing: border-box;
  font-weight: 600;
  font-size: 16px;
  line-height: 0;
  text-transform: uppercase;
  letter-spacing: 0.2px;
  white-space: nowrap;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  border: none;
}

.pill .hover-circle {
  position: absolute;
  left: 50%;
  bottom: 0;
  border-radius: 50%;
  background: var(--base, #000);
  z-index: 1;
  display: block;
  pointer-events: none;
  will-change: transform;
}

.pill .label-stack {
  position: relative;
  display: inline-block;
  line-height: 1;
  z-index: 2;
}

.pill .pill-label {
  position: relative;
  z-index: 2;
  display: inline-block;
  line-height: 1;
  will-change: transform;
}

.pill .pill-label-hover {
  position: absolute;
  left: 0;
  top: 0;
  color: var(--hover-text, #fff);
  z-index: 3;
  display: inline-block;
  will-change: transform, opacity;
}

.pill.is-active::after {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 12px;
  height: 12px;
  background: var(--base, #000);
  border-radius: 50px;
  z-index: 4;
}

@media (max-width: 767px) {
  .pill-nav-container {
    justify-content: stretch;
  }

  .pill-nav {
    min-height: var(--nav-h);
    padding: 0;
  }

  .pill-nav-track {
    width: 100%;
    justify-content: center;
  }

  .pill-list {
    width: 100%;
    max-width: 100%;
    gap: 2px;
    padding: 2px;
    overflow: hidden;
  }

  .pill-list > li {
    flex: 1 1 0;
    min-width: 0;
  }

  .pill {
    width: 100%;
    min-width: 0;
    padding: 0 10px;
    font-size: 13px;
    letter-spacing: 0;
  }
}
</style>
