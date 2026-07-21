<template>
  <!-- 世界观弹出层：桌面端玻璃卡片 -->
  <Transition name="world-popup-fade">
    <div
      v-if="popupVisible && !immersive"
      class="world-popup-overlay"
      @click.self="emit('update:popup-visible', false)"
    >
      <div class="world-popup" role="dialog" aria-label="世界观">
        <div class="world-popup-header">
          <span class="world-popup-title">世界观</span>
          <button
            class="world-popup-close"
            type="button"
            aria-label="关闭"
            @click="emit('update:popup-visible', false)"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div class="world-popup-body">
          <div v-if="worldSetting" class="world-popup-text">{{ worldSetting }}</div>
          <div v-else class="world-popup-empty">暂无世界观设定</div>
        </div>
      </div>
    </div>
  </Transition>

  <!-- 移动端世界观抽屉（底部滑出） -->
  <el-drawer
    :model-value="drawerVisible"
    direction="btt"
    size="60%"
    class="world-drawer"
    @update:model-value="emit('update:drawer-visible', $event)"
  >
    <template #title>
      <span class="world-drawer-title">世界观</span>
    </template>
    <div class="world-drawer-content">
      <div v-if="worldSetting" class="world-drawer-text">{{ worldSetting }}</div>
      <div v-else class="world-drawer-empty">暂无世界观设定</div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStoryStore } from '../../stores/story'

defineProps<{
  popupVisible: boolean
  drawerVisible: boolean
  immersive: boolean
}>()

const emit = defineEmits<{
  'update:popup-visible': [value: boolean]
  'update:drawer-visible': [value: boolean]
}>()

const storyStore = useStoryStore()
const worldSetting = computed(() => storyStore.currentStory?.world_setting ?? '')
</script>

<style scoped>
/* ---- 世界观弹出层（桌面端） ---- */
.world-popup-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 56px; /* 顶栏高度 */
}

.world-popup {
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  width: min(560px, calc(100vw - 32px));
  max-height: calc(100vh - 100px);
  max-height: calc(100dvh - 100px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow:
    var(--shadow-lg),
    0 0 0 1px color-mix(in srgb, var(--border-color) 30%, transparent);
}

.world-popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 14px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.world-popup-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-color);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.world-popup-close {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    background 150ms,
    color 150ms,
    border-color 150ms;
}
.world-popup-close:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--accent-color);
}

.world-popup-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
}

.world-popup-text {
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.8;
  white-space: pre-wrap;
}

.world-popup-empty {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  padding: 32px 0;
}

/* ---- 世界观弹出层过渡动画 ---- */
.world-popup-fade-enter-active,
.world-popup-fade-leave-active {
  transition: opacity 220ms var(--ease-smooth);
}
.world-popup-fade-enter-active .world-popup,
.world-popup-fade-leave-active .world-popup {
  transition:
    transform 220ms var(--ease-spring),
    opacity 220ms var(--ease-smooth);
}
.world-popup-fade-enter-from,
.world-popup-fade-leave-to {
  opacity: 0;
}
.world-popup-fade-enter-from .world-popup,
.world-popup-fade-leave-to .world-popup {
  opacity: 0;
  transform: scale(0.95) translateY(-8px);
}

/* ---- 移动端世界观抽屉 ---- */
.world-drawer :deep(.el-drawer__body) {
  padding: 16px 18px calc(16px + env(safe-area-inset-bottom));
  overflow: hidden;
}
.world-drawer-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 100%;
  overflow-y: auto;
  scrollbar-width: none;
}
.world-drawer-content::-webkit-scrollbar {
  display: none;
}

/* ---- 移动端世界观抽屉圆角适配 ---- */
:deep(.world-drawer) {
  border-radius: 20px 20px 0 0;
}
:deep(.world-drawer .el-drawer__header) {
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 0;
  padding: 14px 18px 12px;
}
:deep(.world-drawer .el-drawer__body) {
  padding: 16px 18px calc(16px + env(safe-area-inset-bottom));
  overflow-y: auto;
}
.world-drawer-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-color);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.world-drawer-text {
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.8;
  white-space: pre-wrap;
}
.world-drawer-empty {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  padding: 24px 0;
}
</style>
