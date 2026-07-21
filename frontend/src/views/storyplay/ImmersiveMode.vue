<template>
  <!-- 沉浸模式退出按钮 -->
  <Transition name="immersive-exit-fade">
    <button v-if="visible" class="immersive-exit" type="button" @click="emit('exit')">
      <span class="exit-hint">Esc</span>退出沉浸
    </button>
  </Transition>

  <!-- 沉浸模式小圆点：跟随用户上次点击位置 -->
  <Transition name="immersive-dot-fade">
    <div
      v-if="visible && !uiVisible"
      class="immersive-dot"
      :style="{ bottom: dotPos.bottom + 'px', right: dotPos.right + 'px' }"
      title="点击呼出控制"
      @click="emit('show-ui', $event)"
    ></div>
  </Transition>

  <!-- 沉浸模式透明点击层：UI隐藏时覆盖聊天区，点击任意位置呼出UI -->
  <div
    v-if="visible && !uiVisible"
    class="immersive-overlay"
    :class="{ 'immersive-hint-visible': hintVisible }"
    @click.stop="emit('show-ui', $event)"
  >
    <div class="immersive-center-dot"></div>
    <div class="immersive-hint" :class="{ visible: hintVisible }">点击任意位置呼出 UI</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  uiVisible: boolean
  hintVisible: boolean
  dotPos: { bottom: number; right: number }
}>()

const emit = defineEmits<{
  exit: []
  'show-ui': [event?: MouseEvent]
}>()
</script>

<style scoped>
.immersive-exit {
  position: fixed;
  top: max(10px, env(safe-area-inset-top));
  right: max(12px, env(safe-area-inset-right));
  z-index: 9998;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 4px 10px 4px 8px;
  cursor: pointer;
  font-size: 12px;
  transition:
    color 0.15s,
    border-color 0.15s;
  display: flex;
  align-items: center;
  gap: 5px;
}
.immersive-exit:hover {
  color: var(--text-primary);
  border-color: var(--accent-color);
}
.exit-hint {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--bg-hover) 60%, transparent);
  border: 1px solid var(--border-color);
  letter-spacing: 0;
  line-height: 1;
}

/* ---- 沉浸模式小圆点 ---- */
.immersive-dot {
  position: fixed;
  /* bottom/right 由 inline style 动态控制 */
  width: 44px;
  height: 44px;
  cursor: pointer;
  z-index: 9997;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: env(safe-area-inset-bottom);
  margin-right: env(safe-area-inset-right);
}
.immersive-dot::after {
  content: '';
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--accent-color);
  opacity: 0.6;
  transition: transform 300ms var(--ease-spring);
}
.immersive-dot:hover::after {
  transform: scale(1.4);
}

/* ---- 沉浸模式透明点击层 ---- */
.immersive-overlay {
  position: fixed;
  inset: 0;
  z-index: 9995;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

/* 沉浸模式中央指示点 */
.immersive-center-dot {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 8px;
  height: 8px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 50%;
  pointer-events: none;
  transition: opacity 300ms ease;
}

/* 沉浸模式提示文字 */
.immersive-hint {
  position: fixed;
  bottom: calc(100px + env(safe-area-inset-bottom));
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 16px;
  background: var(--bg-elevated);
  color: rgba(255, 255, 255, 0.7);
  border-radius: 20px;
  font-size: var(--text-xs);
  pointer-events: none;
  opacity: 0;
  transition: opacity 300ms ease;
  white-space: nowrap;
  z-index: 9996;
}

.immersive-hint.visible {
  opacity: 1;
}

/* ---- 沉浸模式退出/小圆点淡入淡出 ---- */
.immersive-exit-fade-enter-active,
.immersive-exit-fade-leave-active {
  transition:
    opacity 250ms var(--ease-smooth),
    transform 250ms var(--ease-smooth);
}
.immersive-exit-fade-enter-from,
.immersive-exit-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.immersive-dot-fade-enter-active,
.immersive-dot-fade-leave-active {
  transition:
    opacity 300ms var(--ease-smooth),
    transform 300ms var(--ease-smooth);
}
.immersive-dot-fade-enter-from,
.immersive-dot-fade-leave-to {
  opacity: 0;
  transform: scale(0.5);
}

@media (max-width: 767px) {
  /* 沉浸式退出按钮 */
  .immersive-exit {
    min-height: 44px;
    padding: 8px 14px;
  }
}

/* ---- 沉浸模式 reduced motion ---- */
@media (prefers-reduced-motion: reduce) {
  .immersive-dot-fade-enter-active,
  .immersive-dot-fade-leave-active,
  .immersive-exit-fade-enter-active,
  .immersive-exit-fade-leave-active {
    transition-duration: 80ms !important;
    animation-duration: 1ms !important;
  }
}
</style>
