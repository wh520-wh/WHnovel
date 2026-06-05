import { onBeforeUnmount, ref, type Ref } from 'vue'

type NullableElementRef<T extends HTMLElement> = Readonly<Ref<T | null>>

interface UseMobileInputBarOptions {
  /** 用于写入 CSS 变量的根元素（StoryPlay.vue 的 .story-play） */
  rootRef: NullableElementRef<HTMLElement>
  /** 输入区根元素（.input-area） */
  inputAreaRef: NullableElementRef<HTMLElement>
  /** 快捷选项区根元素（.quick-options-wrap） */
  quickOptionsRef: NullableElementRef<HTMLElement>
  /** textarea 元素（用于焦点检测） */
  textareaRef: NullableElementRef<HTMLTextAreaElement>
}

const mobileMediaQuery = window.matchMedia('(max-width: 767px)')

export function useMobileInputBar(options: UseMobileInputBarOptions) {
  // --- 状态 ---
  const keyboardVisible = ref(false)
  const mobileInputOffset = ref(0)
  const mobileOptionsHeight = ref(0)
  const visualViewportOffsetTop = ref(0)

  // --- 内部状态 ---
  let mobileLayoutObserver: ResizeObserver | null = null
  let viewportResizeFrame: number | null = null
  let viewportHeight = window.visualViewport?.height ?? window.innerHeight
  let viewportOffsetTop = window.visualViewport?.offsetTop ?? 0

  const isMobileViewport = () => mobileMediaQuery.matches

  // --- CSS 变量写入 ---
  function setRootVar(name: string, value?: string) {
    const el = options.rootRef.value
    if (!el) return
    if (value === undefined) {
      el.style.removeProperty(name)
      return
    }
    el.style.setProperty(name, value)
  }

  function syncMobileLayoutVars() {
    if (!isMobileViewport()) {
      setRootVar('--mobile-input-offset')
      setRootVar('--mobile-options-height')
      return
    }
    const inputHeight = options.inputAreaRef.value?.offsetHeight ?? 0
    const optionsHeight = options.quickOptionsRef.value?.offsetHeight ?? 0
    mobileInputOffset.value = Math.max(0, Math.round(inputHeight))
    mobileOptionsHeight.value = Math.max(0, Math.round(optionsHeight))
    setRootVar('--mobile-input-offset', `${mobileInputOffset.value}px`)
    setRootVar('--mobile-options-height', `${mobileOptionsHeight.value}px`)
  }

  function syncViewportHeight() {
    const vp = window.visualViewport
    const nextHeight = vp?.height ?? window.innerHeight
    setRootVar('--play-viewport-height', `${Math.round(nextHeight)}px`)
    const offsetTop = vp?.offsetTop ?? 0
    visualViewportOffsetTop.value = Math.max(0, Math.round(offsetTop))
    setRootVar('--visual-viewport-offset-top', `${visualViewportOffsetTop.value}px`)
    // Only reset keyboard offset when viewport is back to full size (keyboard closed)
    if (!vp || Math.abs(window.innerHeight - vp.height) < 10) {
      setRootVar('--keyboard-offset', '0px')
    }
  }

  // --- 键盘偏移补偿（ChatComposer 高度变化时调用） ---
  function compensateForComposerResize(previousHeight: number, nextHeight: number) {
    if (!isMobileViewport()) return
    if (keyboardVisible.value) {
      const delta = nextHeight - previousHeight
      if (Math.abs(delta) < 1) return
      setRootVar('--keyboard-offset', `${Math.max(0, delta)}px`)
    }
  }

  // --- Composer 事件处理 ---
  function handleComposerResize(payload: { previousHeight: number; nextHeight: number }) {
    syncMobileLayoutVars()
    compensateForComposerResize(payload.previousHeight, payload.nextHeight)
  }

  // 外部注册：用于处理键盘弹出/收起时的滚动回调
  let bottomFollowFn: ((config: { behavior?: ScrollBehavior; frames?: number }) => void) | null =
    null

  function handleComposerFocus() {
    if (!isMobileViewport()) return
    keyboardVisible.value = true
    // 键盘弹出时队列滚动，不立即滚（等待键盘动画完成）
    bottomFollowFn?.({ behavior: 'smooth', frames: 6 })
  }

  function handleComposerBlur() {
    if (!isMobileViewport()) return
    keyboardVisible.value = false
    requestAnimationFrame(() => {
      syncViewportHeight()
      syncMobileLayoutVars()
      setRootVar('--keyboard-offset', '0px')
    })
  }

  // --- Viewport 追踪 ---
  function applyViewportResize() {
    const vp = window.visualViewport
    syncViewportHeight()
    syncMobileLayoutVars()
    if (!vp) {
      viewportHeight = window.innerHeight
      viewportOffsetTop = 0
      return
    }
    const diff = Math.abs(viewportHeight - vp.height)
    const topShift = Math.abs(viewportOffsetTop - (vp.offsetTop ?? 0))
    if (isMobileViewport() && (diff > 80 || topShift > 20)) {
      if (document.activeElement === options.textareaRef.value) {
        bottomFollowFn?.({ behavior: 'smooth', frames: 6 })
      }
    }
    viewportHeight = vp.height
    viewportOffsetTop = vp.offsetTop ?? 0
  }

  function handleVisualViewportResize() {
    if (viewportResizeFrame !== null) return
    viewportResizeFrame = requestAnimationFrame(() => {
      viewportResizeFrame = null
      applyViewportResize()
    })
  }

  // --- ResizeObserver：监听输入区/选项区高度变化 ---
  function bindMobileLayoutObserver() {
    if (typeof ResizeObserver === 'undefined') return
    mobileLayoutObserver?.disconnect()
    mobileLayoutObserver = new ResizeObserver(() => {
      syncMobileLayoutVars()
    })
    if (options.inputAreaRef.value) mobileLayoutObserver.observe(options.inputAreaRef.value)
    if (options.quickOptionsRef.value) mobileLayoutObserver.observe(options.quickOptionsRef.value)
  }

  function detachMobileLayoutObserver() {
    mobileLayoutObserver?.disconnect()
    mobileLayoutObserver = null
  }

  // --- 生命周期 ---
  function startViewportTracking() {
    window.visualViewport?.addEventListener('resize', handleVisualViewportResize)
    window.visualViewport?.addEventListener('scroll', handleVisualViewportResize)
  }

  function stopViewportTracking() {
    clearViewportResizeFrame()
    window.visualViewport?.removeEventListener('resize', handleVisualViewportResize)
    window.visualViewport?.removeEventListener('scroll', handleVisualViewportResize)
  }

  function clearViewportResizeFrame() {
    if (viewportResizeFrame === null) return
    cancelAnimationFrame(viewportResizeFrame)
    viewportResizeFrame = null
  }

  onBeforeUnmount(() => {
    detachMobileLayoutObserver()
    stopViewportTracking()
  })

  return {
    keyboardVisible,
    mobileInputOffset,
    mobileOptionsHeight,
    visualViewportOffsetTop,
    handleComposerResize,
    handleComposerFocus,
    handleComposerBlur,
    syncViewportHeight,
    syncMobileLayoutVars,
    bindMobileLayoutObserver,
    detachMobileLayoutObserver,
    startViewportTracking,
    stopViewportTracking,
    setBottomFollowFn: (fn: typeof bottomFollowFn) => {
      bottomFollowFn = fn
    },
  }
}
