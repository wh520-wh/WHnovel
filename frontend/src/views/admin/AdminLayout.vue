<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <h2 class="admin-title">管理后台</h2>
      <el-menu :default-active="activeMenu" router>
        <el-menu-item index="/admin/stories">
          <span>故事管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/global-prompt">
          <span>全局提示词</span>
        </el-menu-item>
        <el-menu-item index="/admin/models">
          <span>模型配置</span>
        </el-menu-item>
        <el-menu-item index="/admin/model-tuning">
          <span>文笔风格</span>
        </el-menu-item>
        <el-menu-item index="/admin/metrics">
          <span>调用统计</span>
        </el-menu-item>
      </el-menu>
      <div class="admin-sidebar-footer admin-sidebar-footer--collapsible">
        <button
          type="button"
          class="shutdown-panel"
          :disabled="shutdownBusy"
          @click="handleEmergencyShutdown"
        >
          <span class="shutdown-panel__badge">Emergency</span>
          <strong class="shutdown-panel__title">彻底关闭前后端</strong>
          <span class="shutdown-panel__desc">先确认后端释放，再清理前端服务，避免假死残留。</span>
        </button>
      </div>
    </aside>
    <main class="admin-main">
      <!-- 手机模式 hamburger bar -->
      <button
        type="button"
        class="admin-hamburger-bar"
        aria-label="打开管理菜单"
        @click="drawerVisible = true"
      >
        <el-icon :size="20"><Fold /></el-icon>
        <span class="admin-hamburger-title">管理后台</span>
      </button>
      <router-view />

      <!-- 左侧 Drawer -->
      <div class="admin-drawer-wrapper">
        <el-drawer
          v-model="drawerVisible"
          direction="ltr"
          :size="200"
          :show-close="false"
          :with-header="false"
        >
        <div class="admin-sidebar-mobile">
          <h2 class="admin-title">管理后台</h2>
          <el-menu :default-active="activeMenu" router @select="drawerVisible = false">
            <el-menu-item index="/admin/stories">
              <el-icon><House /></el-icon>
              <span>故事管理</span>
            </el-menu-item>
            <el-menu-item index="/admin/global-prompt">
              <el-icon><ChatDotRound /></el-icon>
              <span>全局提示词</span>
            </el-menu-item>
            <el-menu-item index="/admin/models">
              <el-icon><Cpu /></el-icon>
              <span>模型配置</span>
            </el-menu-item>
            <el-menu-item index="/admin/model-tuning">
              <el-icon><Setting /></el-icon>
              <span>文笔风格</span>
            </el-menu-item>
            <el-menu-item index="/admin/metrics">
              <el-icon><DataAnalysis /></el-icon>
              <span>调用统计</span>
            </el-menu-item>
          </el-menu>
          <div class="admin-sidebar-footer mobile">
            <button
              type="button"
              class="shutdown-panel"
              :disabled="shutdownBusy"
              @click="handleEmergencyShutdown"
            >
              <span class="shutdown-panel__badge">Emergency</span>
              <strong class="shutdown-panel__title">彻底关闭前后端</strong>
              <span class="shutdown-panel__desc">点击后会先清后端，再清前端。</span>
            </button>
          </div>
        </div>
      </el-drawer>
      </div>

      <transition name="shutdown-fade">
        <div v-if="shutdownOverlayVisible" class="shutdown-overlay">
          <div class="shutdown-dialog">
            <div class="shutdown-dialog__eyebrow">System Shutdown</div>
            <h3 class="shutdown-dialog__title">紧急停机执行中</h3>
            <p class="shutdown-dialog__message">{{ shutdownMessage }}</p>

            <div class="shutdown-steps">
              <div class="shutdown-step" :class="getStepClass('scheduled')">
                <span class="shutdown-step__index">01</span>
                <div>
                  <div class="shutdown-step__label">关停指令已发出</div>
                  <div class="shutdown-step__hint">独立关停进程已经接管，不依赖当前页面继续存活。</div>
                </div>
              </div>
              <div class="shutdown-step" :class="getStepClass('backend_down')">
                <span class="shutdown-step__index">02</span>
                <div>
                  <div class="shutdown-step__label">确认后端关闭</div>
                  <div class="shutdown-step__hint">轮询 `8000`，只要端口还活着就继续等待，不会误判。</div>
                </div>
              </div>
              <div class="shutdown-step" :class="getStepClass('frontend_down')">
                <span class="shutdown-step__index">03</span>
                <div>
                  <div class="shutdown-step__label">清理前端服务</div>
                  <div class="shutdown-step__hint">后端确认释放后，再回收 `5173` 和前端 PID。</div>
                </div>
              </div>
            </div>

            <div class="shutdown-dialog__meta">
              <span>后端计划延迟 {{ backendDelayMs }}ms</span>
              <span>前端计划延迟 {{ frontendDelayMs }}ms</span>
            </div>

            <button
              v-if="shutdownPhase === 'frontend_down' || shutdownPhase === 'timeout' || shutdownPhase === 'failed'"
              type="button"
              class="shutdown-dialog__close"
              @click="shutdownOverlayVisible = false"
            >
              收起反馈面板
            </button>
          </div>
        </div>
      </transition>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import { getErrorMessage, shutdownSystem } from '../../api'

const route = useRoute()
const drawerVisible = ref(false)
const shutdownBusy = ref(false)
const shutdownOverlayVisible = ref(false)
const shutdownPhase = ref<'idle' | 'scheduled' | 'backend_down' | 'frontend_down' | 'timeout' | 'failed'>('idle')
const shutdownMessage = ref('正在准备紧急停机...')
const backendDelayMs = ref(900)
const frontendDelayMs = ref(2600)
let backendProbeTimer: number | null = null
let frontendProbeTimer: number | null = null
let shutdownTimeoutTimer: number | null = null

const activeMenu = computed(() => {
  if (route.path.startsWith('/admin/global-prompt')) return '/admin/global-prompt'
  if (route.path.startsWith('/admin/models')) return '/admin/models'
  if (route.path.startsWith('/admin/model-tuning')) return '/admin/model-tuning'
  if (route.path.startsWith('/admin/metrics')) return '/admin/metrics'
  return '/admin/stories'
})

function clearShutdownTimers() {
  if (backendProbeTimer !== null) {
    window.clearInterval(backendProbeTimer)
    backendProbeTimer = null
  }
  if (frontendProbeTimer !== null) {
    window.clearInterval(frontendProbeTimer)
    frontendProbeTimer = null
  }
  if (shutdownTimeoutTimer !== null) {
    window.clearTimeout(shutdownTimeoutTimer)
    shutdownTimeoutTimer = null
  }
}

async function probeUrl(url: string): Promise<boolean> {
  const separator = url.includes('?') ? '&' : '?'
  try {
    const response = await fetch(`${url}${separator}shutdown_probe=${Date.now()}`, {
      method: 'GET',
      cache: 'no-store',
    })
    return response.ok
  } catch {
    return false
  }
}

function startFrontendProbe() {
  if (frontendProbeTimer !== null) return

  frontendProbeTimer = window.setInterval(async () => {
    const frontendAlive = await probeUrl(window.location.origin)
    if (frontendAlive) return

    clearShutdownTimers()
    shutdownBusy.value = false
    shutdownPhase.value = 'frontend_down'
    shutdownMessage.value = '前后端服务都已关闭。本页现在只是保留的静态反馈面板，可以直接关闭。'
  }, 500)
}

function startShutdownProbeLoop() {
  clearShutdownTimers()

  backendProbeTimer = window.setInterval(async () => {
    const backendAlive = await probeUrl('http://127.0.0.1:8000/openapi.json')
    if (backendAlive) return

    if (backendProbeTimer !== null) {
      window.clearInterval(backendProbeTimer)
      backendProbeTimer = null
    }

    shutdownPhase.value = 'backend_down'
    shutdownMessage.value = '后端已确认关闭，正在继续清理前端服务...'
    startFrontendProbe()
  }, 450)

  shutdownTimeoutTimer = window.setTimeout(() => {
    clearShutdownTimers()
    shutdownBusy.value = false
    shutdownPhase.value = 'timeout'
    shutdownMessage.value = '关停确认超时，请手动检查 8000 与 5173 是否仍在监听。'
  }, Math.max(frontendDelayMs.value + 12000, 16000))
}

function getStepClass(target: 'scheduled' | 'backend_down' | 'frontend_down') {
  if (shutdownPhase.value === 'failed') return 'is-pending'
  if (shutdownPhase.value === 'timeout') {
    return target === 'frontend_down' ? 'is-warning' : 'is-done'
  }
  if (target === 'scheduled') return 'is-done'
  if (target === 'backend_down') {
    return shutdownPhase.value === 'scheduled' ? 'is-active' : 'is-done'
  }
  if (target === 'frontend_down') {
    return shutdownPhase.value === 'frontend_down'
      ? 'is-done'
      : shutdownPhase.value === 'backend_down'
        ? 'is-active'
        : 'is-pending'
  }
  return 'is-pending'
}

async function handleEmergencyShutdown() {
  if (shutdownBusy.value) return

  try {
    await ElMessageBox.confirm(
      '这会彻底关闭 8000 后端和 5173 前端，并清理对应 PID。确认继续吗？',
      '紧急停机确认',
      {
        type: 'error',
        confirmButtonText: '立即停机',
        cancelButtonText: '取消',
        distinguishCancelAndClose: true,
      },
    )
  } catch {
    return
  }

  shutdownBusy.value = true
  shutdownOverlayVisible.value = true
  shutdownPhase.value = 'scheduled'
  shutdownMessage.value = '关停指令已发送，正在等待后端释放 8000...'
  drawerVisible.value = false

  try {
    const { data } = await shutdownSystem()
    backendDelayMs.value = data.backend_delay_ms || backendDelayMs.value
    frontendDelayMs.value = data.frontend_delay_ms || frontendDelayMs.value
    shutdownMessage.value = data.message || shutdownMessage.value
    ElMessage.success('关停任务已启动')
    startShutdownProbeLoop()
  } catch (error) {
    clearShutdownTimers()
    shutdownBusy.value = false
    shutdownPhase.value = 'failed'
    shutdownMessage.value = getErrorMessage(error, '紧急停机启动失败')
    ElMessage.error(shutdownMessage.value)
  }
}

onBeforeUnmount(() => {
  clearShutdownTimers()
})
</script>

<style scoped>
.admin-layout {
  display: flex;
  height: 100%;
}

.admin-sidebar {
  width: 200px;
  border-right: 1px solid var(--border-color);
  flex-shrink: 0;
  background: var(--admin-sidebar-bg);
  display: flex;
  flex-direction: column;
}

.admin-title {
  padding: 16px 20px;
  font-size: 16px;
  color: var(--accent-color);
  font-weight: 700;
  border-bottom: 1px solid var(--border-color);
  text-shadow: 0 0 20px color-mix(in srgb, var(--accent-color) 30%, transparent);
}

.admin-sidebar .el-menu {
  border-right: none;
  background: transparent;
  flex: 1;
}

.admin-sidebar :deep(.el-menu-item) {
  color: var(--text-secondary);
  transition: color var(--duration-fast) var(--ease-smooth),
              background var(--duration-fast) var(--ease-smooth);
}

.admin-sidebar :deep(.el-menu-item:hover) {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.admin-sidebar :deep(.el-menu-item.is-active) {
  color: var(--accent-color);
  font-weight: 600;
  background: color-mix(in srgb, var(--accent-color) 12%, transparent) !important;
  border-left: 3px solid var(--accent-color);
  padding-left: 17px;
}

.admin-main {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  background: var(--admin-main-bg);
  border-radius: 16px 0 0 0;
  position: relative;
}

.admin-sidebar-footer {
  padding: 16px;
  border-top: 1px solid color-mix(in srgb, #ff7a7a 18%, var(--border-color));
  background:
    radial-gradient(circle at top right, rgba(255, 115, 115, 0.16), transparent 55%),
    linear-gradient(180deg, rgba(10, 12, 18, 0.08), rgba(10, 12, 18, 0.22));
}

.admin-sidebar-footer.mobile {
  padding-top: 20px;
}

.shutdown-panel {
  width: 100%;
  border: 1px solid rgba(255, 109, 109, 0.45);
  border-radius: 20px;
  padding: 14px 14px 15px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background:
    linear-gradient(145deg, rgba(110, 10, 24, 0.98), rgba(53, 8, 16, 0.92)),
    radial-gradient(circle at top right, rgba(255, 190, 190, 0.32), transparent 42%);
  color: #fff6f6;
  text-align: left;
  box-shadow:
    0 18px 34px rgba(80, 7, 16, 0.34),
    inset 0 1px 0 rgba(255, 230, 230, 0.18);
  cursor: pointer;
  transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease, filter 180ms ease;
}

.shutdown-panel:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(255, 153, 153, 0.7);
  box-shadow:
    0 24px 42px rgba(107, 9, 23, 0.42),
    inset 0 1px 0 rgba(255, 230, 230, 0.24);
  filter: saturate(1.05);
}

.shutdown-panel:active:not(:disabled) {
  transform: translateY(0);
}

.shutdown-panel:disabled {
  opacity: 0.8;
  cursor: wait;
}

.shutdown-panel__badge {
  width: fit-content;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(255, 233, 233, 0.14);
  border: 1px solid rgba(255, 214, 214, 0.25);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.shutdown-panel__title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.shutdown-panel__desc {
  font-size: 12px;
  line-height: 1.55;
  color: rgba(255, 236, 236, 0.8);
}

@media (min-width: 768px) and (max-width: 1199px) {
  .admin-sidebar {
    width: 64px;
  }
  .admin-sidebar-footer--collapsible {
    display: none;
  }
  .admin-title {
    display: none;
  }
  .admin-sidebar :deep(.el-menu-item span) {
    display: none;
  }
  .admin-sidebar :deep(.el-menu-item) {
    padding-left: 0 !important;
    justify-content: center;
  }
  .admin-sidebar :deep(.el-menu-item.is-active) {
    padding-left: 0 !important;
  }
}

/* 手机模式 hamburger bar */
.admin-hamburger-bar {
  display: none;
  align-items: center;
  gap: 8px;
  padding: 0 16px;
  width: 100%;
  min-height: 44px;
  border: 0;
  border-bottom: 1px solid var(--border-color);
  background: transparent;
  cursor: pointer;
  color: var(--text-secondary);
  flex-shrink: 0;
  font: inherit;
  text-align: left;
}
.admin-hamburger-bar:active {
  background: var(--bg-hover);
}
.admin-hamburger-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-color);
}

/* 移动端侧边栏（用于 Drawer） */
.admin-sidebar-mobile {
  height: 100%;
  background: var(--admin-sidebar-bg);
  display: flex;
  flex-direction: column;
}
.admin-sidebar-mobile .admin-title {
  display: block;
}

.admin-sidebar-mobile .el-menu {
  flex: 1;
}

/* 手机模式（< 768px）：隐藏原有 sidebar，显示 hamburger bar */
@media (max-width: 767px) {
  .admin-sidebar {
    display: none;
  }
  .admin-hamburger-bar {
    display: flex;
  }
  .admin-main {
    border-radius: 0;
    overflow-x: hidden;
  }
}

/* iPad safe-area: 抽屉右侧不被 home indicator 遮挡 */
.admin-drawer-wrapper {
  padding-right: env(safe-area-inset-right);
}

.shutdown-overlay {
  position: fixed;
  inset: 0;
  background:
    radial-gradient(circle at top, rgba(255, 126, 126, 0.18), transparent 35%),
    rgba(7, 8, 12, 0.76);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 4000;
}

.shutdown-dialog {
  width: min(560px, 100%);
  border-radius: 28px;
  padding: 26px;
  color: #fff7f7;
  background:
    linear-gradient(160deg, rgba(58, 10, 16, 0.96), rgba(17, 10, 16, 0.94)),
    radial-gradient(circle at top right, rgba(255, 194, 194, 0.18), transparent 42%);
  border: 1px solid rgba(255, 153, 153, 0.22);
  box-shadow:
    0 28px 90px rgba(0, 0, 0, 0.45),
    0 18px 48px rgba(128, 11, 23, 0.2),
    inset 0 1px 0 rgba(255, 230, 230, 0.12);
}

.shutdown-dialog__eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.28em;
  color: rgba(255, 211, 211, 0.68);
  margin-bottom: 10px;
}

.shutdown-dialog__title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.shutdown-dialog__message {
  margin: 12px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: rgba(255, 234, 234, 0.84);
}

.shutdown-steps {
  display: grid;
  gap: 12px;
  margin-top: 22px;
}

.shutdown-step {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 170, 170, 0.12);
  background: rgba(255, 255, 255, 0.04);
}

.shutdown-step__index {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 231, 231, 0.86);
}

.shutdown-step__label {
  font-size: 15px;
  font-weight: 700;
}

.shutdown-step__hint {
  margin-top: 5px;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 228, 228, 0.68);
}

.shutdown-step.is-active {
  border-color: rgba(255, 170, 170, 0.34);
  background: linear-gradient(135deg, rgba(255, 91, 91, 0.14), rgba(255, 255, 255, 0.04));
}

.shutdown-step.is-active .shutdown-step__index {
  background: linear-gradient(135deg, #ff7e7e, #ffb6b6);
  color: #5b0b14;
}

.shutdown-step.is-done {
  border-color: rgba(255, 198, 198, 0.26);
  background: linear-gradient(135deg, rgba(255, 164, 164, 0.16), rgba(255, 255, 255, 0.05));
}

.shutdown-step.is-done .shutdown-step__index {
  background: linear-gradient(135deg, #ffd0d0, #ff9e9e);
  color: #5b0b14;
}

.shutdown-step.is-warning {
  border-color: rgba(255, 212, 117, 0.34);
  background: linear-gradient(135deg, rgba(255, 191, 73, 0.14), rgba(255, 255, 255, 0.04));
}

.shutdown-step.is-pending {
  opacity: 0.72;
}

.shutdown-dialog__meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 18px;
  font-size: 12px;
  color: rgba(255, 224, 224, 0.7);
}

.shutdown-dialog__close {
  margin-top: 22px;
  border: 1px solid rgba(255, 202, 202, 0.26);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #fff4f4;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 160ms ease, transform 160ms ease;
}

.shutdown-dialog__close:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}

.shutdown-fade-enter-active,
.shutdown-fade-leave-active {
  transition: opacity 180ms ease;
}

.shutdown-fade-enter-from,
.shutdown-fade-leave-to {
  opacity: 0;
}

@media (max-width: 767px) {
  .shutdown-dialog {
    padding: 20px;
    border-radius: 22px;
  }

  .shutdown-dialog__title {
    font-size: 24px;
  }

  .shutdown-step {
    grid-template-columns: 44px 1fr;
    gap: 12px;
  }

  .shutdown-step__index {
    width: 44px;
    height: 44px;
    border-radius: 14px;
  }
}
</style>


