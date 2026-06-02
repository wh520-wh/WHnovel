<template>
  <el-config-provider :message="{ offset: 40 }">
    <div class="app-container">
      <header class="app-header-shell" v-if="!isPlayRoute">
        <PillNav
          class-name="app-pill-nav"
          :items="navItems"
          :active-href="activeHref"
          :active-key="activeKey"
          :base-color="'var(--bg-elevated)'"
          :pill-color="'var(--bg-card)'"
          :hovered-pill-text-color="'var(--text-primary)'"
          :pill-text-color="'var(--text-primary)'"
          :initial-load-animation="true"
        />
      </header>

      <main class="app-main">
        <router-view v-slot="{ Component, route: currentRoute }">
          <transition name="page" mode="out-in">
            <component :is="Component" :key="currentRoute.path" />
          </transition>
        </router-view>
      </main>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PillNav from './components/PillNav.vue'
import { useThemeStore } from './stores/theme'

function readAdminMode() {
  return localStorage.getItem('admin_mode') === '1'
}

const themeStore = useThemeStore()
const route = useRoute()
const router = useRouter()
const isPlayRoute = computed(() => route.name === 'StoryPlay')
const isAdmin = ref(readAdminMode())
const isMobileNavViewport = ref(typeof window !== 'undefined' ? window.innerWidth <= 768 : false)

const activeHref = computed(() => {
  const currentPath = String(route.path || '')
  if (currentPath === '/') return '/'
  if (currentPath.startsWith('/admin')) return '/admin'
  return undefined
})

const activeKey = computed(() => {
  const currentPath = String(route.path || '')
  if (currentPath === '/') return 'hall'
  if (currentPath.startsWith('/settings')) return 'settings'
  if (currentPath.startsWith('/admin')) return 'admin'
  return undefined
})

const navItems = computed(() => {
  const items = [
    { key: 'hall', label: '故事大厅', href: '/' },
    { key: 'settings', label: '设置', onClick: openSettingsFromHeader },
  ]

  if (isAdmin.value) {
    items.push({ key: 'admin', label: '管理后台', href: '/admin' })
  }

  items.push({
    key: 'theme',
    label: themeLabel.value,
    onClick: () => themeStore.toggleTheme(),
  })

  return items
})

const themeLabel = computed(() => {
  if (themeStore.theme === 'dark') return '暗色'
  if (themeStore.theme === 'light') return '亮色'
  if (themeStore.theme === 'enigma') return 'Enigma'
  return 'Claude'
})

function syncAdminMode() {
  isAdmin.value = readAdminMode()
}

function handleAdminModeChanged() {
  syncAdminMode()
}

function handleAdminModeStorage(e: StorageEvent) {
  if (e.key === 'admin_mode') {
    syncAdminMode()
  }
}

function syncNavViewport() {
  isMobileNavViewport.value = window.innerWidth <= 768
}

function openSettingsFromHeader() {
  router.push(isMobileNavViewport.value ? '/settings-mobile' : '/settings')
}

onMounted(() => {
  syncNavViewport()
  window.addEventListener('resize', syncNavViewport)
  window.addEventListener('admin-mode-changed', handleAdminModeChanged)
  window.addEventListener('storage', handleAdminModeStorage)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncNavViewport)
  window.removeEventListener('admin-mode-changed', handleAdminModeChanged)
  window.removeEventListener('storage', handleAdminModeStorage)
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  height: 100vh;
  height: 100dvh;
}

.app-header-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 20px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

:deep(.app-pill-nav) {
  width: 100%;
}

.app-main {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

@media (max-width: 767px) {
  .app-header-shell {
    padding: 12px 0 10px;
  }
}
</style>

<style>
.page-enter-active {
  animation: page-enter 350ms cubic-bezier(0.4, 0, 0.2, 1) both;
}

.page-leave-active {
  animation: page-leave 200ms cubic-bezier(0.4, 0, 0.8, 0.2) both;
}

@keyframes page-enter {
  from {
    opacity: 0;
    transform: scale(0.97);
    filter: blur(2px);
  }
  to {
    opacity: 1;
    transform: scale(1);
    filter: blur(0);
  }
}

@keyframes page-leave {
  from {
    opacity: 1;
    transform: scale(1);
    filter: blur(0);
  }
  to {
    opacity: 0;
    transform: scale(0.98);
    filter: blur(1px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active {
    animation: none;
    opacity: 1;
  }
}
</style>
