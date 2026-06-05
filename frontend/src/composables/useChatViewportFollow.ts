import { nextTick, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { throttle } from 'lodash'

type NullableElementRef<T extends HTMLElement> = Readonly<Ref<T | null>>

interface UseChatViewportFollowOptions {
  storyPlayRef: NullableElementRef<HTMLElement>
  chatAreaRef: NullableElementRef<HTMLElement>
  inputAreaRef: NullableElementRef<HTMLElement>
  quickOptionsRef: NullableElementRef<HTMLElement>
  textareaRef: NullableElementRef<HTMLTextAreaElement>
  assistantMessageCount: Readonly<Ref<number>>
  streaming: Readonly<Ref<boolean>>
  streamingFollow: Readonly<Ref<boolean>>
}

export function useChatViewportFollow(options: UseChatViewportFollowOptions) {
  const topbarScrolled = ref(false)
  const autoFollow = ref(true)
  const pendingMessageCount = ref(0)
  const lastAIMessageCount = ref(0)
  const badgeBouncing = ref(false)
  const userScrolledUp = ref(false)

  let followScrollFrame: number | null = null
  let streamFollowFrame: number | null = null
  let lastStreamScrollHeight = -1
  let lastStreamFollowAt = 0
  let streamFollowTarget = -1
  let lastBottomScrollTop = -1
  let lastBottomScrollAt = 0

  const BOTTOM_SCROLL_DEDUPE_WINDOW_MS = 90
  // 流式正文增长时两次滚动之间的最小间隔：太快会在安卓机上造成滚动不流畅
  const STREAM_FOLLOW_MIN_INTERVAL_MS = 60
  // 渐进跟随系数：每帧向目标移动剩余距离的 45%，约 5 帧 (~80ms) 到达目标
  const STREAM_FOLLOW_EASE_FACTOR = 0.45
  // 每帧最小移动像素，防止接近目标时停滞
  const STREAM_FOLLOW_MIN_STEP = 4
  // 距目标小于此值时直接吸附，避免无限逼近
  const STREAM_FOLLOW_SNAP_THRESHOLD = 2

  let _prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const prefersReducedMotion = () => _prefersReducedMotion
  const _reducedMotionMql = window.matchMedia('(prefers-reduced-motion: reduce)')
  _reducedMotionMql.addEventListener('change', (e) => {
    _prefersReducedMotion = e.matches
  })

  /**
   * 解析实际滚动容器：
   * 桌面端 .chat-area 本身 `overflow-y: auto`，是滚动容器；
   * 移动端 .chat-area `overflow: visible`，真正滚动的是它的祖先 .center-panel。
   * 因此不能把 chatAreaRef 直接当作滚动容器——要沿祖先链找到第一个 overflow-y 为 auto/scroll/overlay 的元素。
   */
  function resolveScrollContainer(): HTMLElement | null {
    const anchor = options.chatAreaRef.value
    if (!anchor) return null
    let node: HTMLElement | null = anchor
    // 最多向上走 6 层，避免极端情况下无限循环
    for (let depth = 0; depth < 6 && node; depth += 1) {
      const style = window.getComputedStyle(node)
      const overflowY = style.overflowY
      if (overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') {
        return node
      }
      node = node.parentElement
    }
    // 兜底：如果找不到明确滚动祖先，回退到 anchor 本身（桌面端常态）。
    return anchor
  }

  function syncFollowerState() {
    pendingMessageCount.value = 0
    lastAIMessageCount.value = options.assistantMessageCount.value
    autoFollow.value = true
  }

  function isNearBottom(): boolean {
    const el = resolveScrollContainer()
    if (!el) return true
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    return distanceFromBottom <= 80
  }

  function scrollToBottom(behavior: ScrollBehavior = 'auto') {
    const el = resolveScrollContainer()
    if (!el) return
    const targetTop = el.scrollHeight
    if (Math.abs(targetTop - el.scrollTop) <= 2) return
    const now = performance.now()
    const duplicateTarget = Math.abs(targetTop - lastBottomScrollTop) <= 2
    if (duplicateTarget && now - lastBottomScrollAt < BOTTOM_SCROLL_DEDUPE_WINDOW_MS) {
      return
    }
    const resolvedBehavior = prefersReducedMotion() ? 'auto' : behavior
    lastBottomScrollTop = targetTop
    lastBottomScrollAt = now
    el.scrollTo({ top: targetTop, behavior: resolvedBehavior })
  }

  function cancelQueuedBottomFollow() {
    if (followScrollFrame === null) return
    cancelAnimationFrame(followScrollFrame)
    followScrollFrame = null
  }

  function cancelStreamFollow() {
    if (streamFollowFrame !== null) {
      cancelAnimationFrame(streamFollowFrame)
      streamFollowFrame = null
    }
    lastStreamScrollHeight = -1
  }

  function ensureStreamFollowRunning() {
    if (streamFollowFrame !== null) return
    if (!options.streaming.value || !options.streamingFollow.value) return
    startStreamFollow()
  }

  /**
   * 流式跟随 rAF 循环：只在 streaming && streamingFollow 都为真时运行。
   * 每帧读 scrollHeight，若增长且用户未向上翻（autoFollow 或仍接近底部），
   * 更新目标位置并以指数衰减渐进逼近（~80ms 到达），避免 `scrollTop = h`
   * 硬切造成的断续感。目标更新保留 60ms 节流，防止安卓机连帧滚写卡顿。
   * prefers-reduced-motion 时降级为瞬跳。
   */
  function startStreamFollow() {
    cancelStreamFollow()
    streamFollowTarget = -1
    const tick = () => {
      if (!options.streaming.value || !options.streamingFollow.value) {
        streamFollowFrame = null
        lastStreamScrollHeight = -1
        streamFollowTarget = -1
        return
      }
      const container = resolveScrollContainer()
      if (!container) {
        streamFollowFrame = requestAnimationFrame(tick)
        return
      }

      // 单次批量读，避免同帧 read→write→read 布局抖动 + 重复 resolveScrollContainer
      const scrollHeight = container.scrollHeight
      const scrollTop = container.scrollTop
      const clientHeight = container.clientHeight
      const near = scrollHeight - scrollTop - clientHeight <= 80

      if (!autoFollow.value && !near) {
        streamFollowFrame = null
        lastStreamScrollHeight = -1
        streamFollowTarget = -1
        return
      }
      if (autoFollow.value || near) {
        const t = performance.now()
        const grew = scrollHeight > lastStreamScrollHeight
        const cooldownOk = t - lastStreamFollowAt >= STREAM_FOLLOW_MIN_INTERVAL_MS

        // 正文增长时更新目标位置（保留 60ms 节流）
        if (grew && cooldownOk) {
          streamFollowTarget = scrollHeight
          lastStreamScrollHeight = scrollHeight
          lastStreamFollowAt = t
        }

        // 逐帧渐进逼近目标
        if (streamFollowTarget > 0) {
          const remaining = streamFollowTarget - scrollTop

          if (remaining <= 0) {
            streamFollowTarget = -1
          } else if (prefersReducedMotion()) {
            // 减少动画偏好：保持原有瞬跳行为
            container.scrollTop = streamFollowTarget
            lastBottomScrollTop = streamFollowTarget
            lastBottomScrollAt = t
            streamFollowTarget = -1
          } else if (remaining <= STREAM_FOLLOW_SNAP_THRESHOLD) {
            // 距离足够近，直接吸附
            container.scrollTop = streamFollowTarget
            lastBottomScrollTop = streamFollowTarget
            lastBottomScrollAt = t
            streamFollowTarget = -1
          } else {
            const step = Math.max(remaining * STREAM_FOLLOW_EASE_FACTOR, STREAM_FOLLOW_MIN_STEP)
            const next = scrollTop + step
            container.scrollTop = next
            lastBottomScrollTop = next
            lastBottomScrollAt = t
          }
        }
      }
      streamFollowFrame = requestAnimationFrame(tick)
    }
    streamFollowFrame = requestAnimationFrame(tick)
  }

  function queueBottomFollow(config: { behavior?: ScrollBehavior; frames?: number } = {}) {
    const requestedBehavior = config.behavior ?? 'auto'
    const behavior = prefersReducedMotion() ? 'auto' : requestedBehavior
    const frames = config.frames ?? 4
    cancelQueuedBottomFollow()
    let remaining = frames
    const tick = () => {
      if (autoFollow.value || isNearBottom()) {
        scrollToBottom(behavior)
      }
      remaining -= 1
      if (remaining > 0) {
        followScrollFrame = requestAnimationFrame(tick)
        return
      }
      followScrollFrame = null
    }
    followScrollFrame = requestAnimationFrame(tick)
  }

  /**
   * 打开聊天界面时的强制滚到底：
   * - 轮询 scrollHeight 直到稳定（应对 transition-group 入场、字体/图片延迟加载改变高度的情况）
   * - 绕过 scrollToBottom 的 "duplicateTarget" 去重（初次渲染 scrollTop=scrollHeight=0，会被误判为已在底部）
   * - 有硬超时兜底（默认 900ms）防止无限循环
   * - 监听 chat-messages 内所有 <img> 的 load 事件，图片到位后再补一次滚到底
   */
  function forceScrollToBottom(maxDuration = 900) {
    const el = options.chatAreaRef.value
    if (!el) return
    cancelQueuedBottomFollow()
    autoFollow.value = true
    const start = performance.now()
    let prevScrollHeight = -1
    let stableFrames = 0

    const tick = () => {
      const container = resolveScrollContainer()
      if (!container) {
        followScrollFrame = null
        return
      }
      const h = container.scrollHeight
      if (h > 0) {
        container.scrollTop = h
        lastBottomScrollTop = h
        lastBottomScrollAt = performance.now()
      }
      if (h > 0 && h === prevScrollHeight) {
        stableFrames += 1
      } else {
        stableFrames = 0
      }
      prevScrollHeight = h
      const elapsed = performance.now() - start
      if (stableFrames >= 3 || elapsed > maxDuration) {
        followScrollFrame = null
        return
      }
      followScrollFrame = requestAnimationFrame(tick)
    }
    followScrollFrame = requestAnimationFrame(tick)

    // 图片延迟加载导致高度继续变化：每张图 load 后都补一次滚底
    try {
      const imgs = el.querySelectorAll<HTMLImageElement>('img')
      imgs.forEach((img) => {
        if (img.complete) return
        const onDone = () => {
          img.removeEventListener('load', onDone)
          img.removeEventListener('error', onDone)
          const container = resolveScrollContainer()
          if (!container) return
          // 仅在用户仍在底部时补滚，避免打断手动上翻
          if (autoFollow.value || isNearBottom()) {
            container.scrollTop = container.scrollHeight
          }
        }
        img.addEventListener('load', onDone, { once: true })
        img.addEventListener('error', onDone, { once: true })
      })
    } catch {
      // 忽略异常环境（如 SSR / 测试环境无 DOM）
    }
  }

  function handleChatScroll() {
    const chatArea = resolveScrollContainer()
    if (!chatArea) return

    // 单次批量读，避免重复解析容器 + 同帧多次布局读
    const scrollTop = chatArea.scrollTop
    const scrollHeight = chatArea.scrollHeight
    const clientHeight = chatArea.clientHeight
    const nearBottom = scrollHeight - scrollTop - clientHeight <= 80

    topbarScrolled.value = scrollTop > 8
    userScrolledUp.value = !nearBottom && scrollHeight > clientHeight + 80

    if (nearBottom) {
      autoFollow.value = true
      ensureStreamFollowRunning()
      if (pendingMessageCount.value > 0) {
        pendingMessageCount.value = 0
        lastAIMessageCount.value = options.assistantMessageCount.value
      }
    } else if (pendingMessageCount.value === 0) {
      autoFollow.value = false
    }
  }

  const throttledScrollHandler = throttle(handleChatScroll, 16)

  function jumpToLatest() {
    autoFollow.value = true
    pendingMessageCount.value = 0
    lastAIMessageCount.value = options.assistantMessageCount.value
    scrollToBottom('smooth')
  }

  // 当前绑定 scroll 监听的容器（桌面=.chat-area, 移动=.center-panel）
  let attachedScrollEl: HTMLElement | null = null

  function attachChatScrollListener() {
    const el = resolveScrollContainer()
    if (!el) return
    // 已经绑定到同一个元素则不重复绑定
    if (attachedScrollEl === el) return
    // 若之前绑到了别的元素（如切换过屏幕尺寸），先卸载
    if (attachedScrollEl) {
      attachedScrollEl.removeEventListener('scroll', throttledScrollHandler)
    }
    el.addEventListener('scroll', throttledScrollHandler)
    attachedScrollEl = el
  }

  function detachChatScrollListener() {
    throttledScrollHandler.cancel()
    if (attachedScrollEl) {
      attachedScrollEl.removeEventListener('scroll', throttledScrollHandler)
      attachedScrollEl = null
    }
  }

  watch(options.assistantMessageCount, async (newCount) => {
    await nextTick()
    const added = newCount - lastAIMessageCount.value
    if (added <= 0) {
      lastAIMessageCount.value = newCount
      return
    }
    lastAIMessageCount.value = newCount

    if (autoFollow.value) {
      if (options.streamingFollow.value || !options.streaming.value) {
        scrollToBottom()
      }
    } else {
      pendingMessageCount.value += added
    }
  })

  watch(
    () => options.streaming.value,
    (isStreaming) => {
      if (isStreaming && options.streamingFollow.value) {
        startStreamFollow()
      } else {
        cancelStreamFollow()
      }
    },
    { immediate: true },
  )

  watch(
    () => options.streamingFollow.value,
    (enabled) => {
      if (enabled && options.streaming.value) {
        startStreamFollow()
      } else if (!enabled) {
        cancelStreamFollow()
      }
    },
  )

  watch(pendingMessageCount, (newVal, oldVal) => {
    if (!newVal || !oldVal) return
    if (newVal <= 0 || oldVal <= 0) return
    if (newVal === oldVal) return
    badgeBouncing.value = true
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        badgeBouncing.value = false
      })
    })
  })

  onMounted(() => {
    attachChatScrollListener()
  })

  onUnmounted(() => {
    detachChatScrollListener()
    cancelQueuedBottomFollow()
    cancelStreamFollow()
  })

  return {
    topbarScrolled,
    autoFollow,
    pendingMessageCount,
    badgeBouncing,
    userScrolledUp,
    syncFollowerState,
    scrollToBottom,
    forceScrollToBottom,
    isNearBottom,
    jumpToLatest,
    queueBottomFollow,
    attachChatScrollListener,
    detachChatScrollListener,
  }
}
