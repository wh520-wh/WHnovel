<template>
  <div ref="storyPlayRef" class="story-play" :class="{ immersive: immersiveMode }">
    <PlayTopbar
      ref="playTopbarInstance"
      v-model:timeline-visible="timelineVisible"
      :immersive-mode="immersiveMode"
      :immersive-ui-visible="immersiveUiVisible"
      :immersive-transitioning="immersiveTransitioning"
      :topbar-scrolled="topbarScrolled"
      :right-menu-visible="rightMenuVisible"
      @back="router.back()"
      @top-center-click="handleTopCenterClick"
      @toggle-immersive="toggleImmersive"
      @toggle-right-menu="toggleRightMenu"
    />

    <ImmersiveMode
      :visible="immersiveMode"
      :ui-visible="immersiveUiVisible"
      :hint-visible="immersiveHintVisible"
      :dot-pos="immersiveDotPos"
      @exit="forceExitImmersive"
      @show-ui="showImmersiveUi"
    />

    <WorldSettingPanel
      v-model:popup-visible="worldSettingPopupVisible"
      v-model:drawer-visible="storyDrawerVisible"
      :immersive="immersiveMode"
    />

    <main class="play-main">
      <TimelinePanel
        v-model:mobile-visible="timelineVisible"
        :immersive="immersiveMode"
        @jump="handleJumpToMessage"
      />
      <section class="center-panel">
        <ChatArea
          ref="chatAreaInstance"
          v-model:opening-requirement="openingRequirement"
          :immersive="immersiveMode"
          :select-mode="selectMode"
          :selected-message-ids="selectedMessageIds"
          :auto-follow="autoFollow"
          :pending-message-count="pendingMessageCount"
          :badge-bouncing="badgeBouncing"
          :user-scrolled-up="userScrolledUp"
          :deleting-in-progress="deletingInProgress"
          @start-story="handleStartStory"
          @recall-animation-end="handleRecallAnimationEnd"
          @select="handleMsgSelect"
          @long-press="handleLongPress"
          @exit-select-mode="exitSelectMode"
          @clear-selected="clearSelectedMessages"
          @bulk-delete="handleBulkDelete"
          @jump-to-latest="jumpToLatest"
          @scroll-to-latest="scrollToLatest"
        />
        <PlayBottomBar
          ref="playBottomBarInstance"
          v-model:input-text="inputText"
          v-model:left-menu-visible="leftMenuVisible"
          :has-started="hasStarted"
          :immersive="immersiveMode"
          :immersive-ui-visible="immersiveUiVisible"
          :select-mode="selectMode"
          :left-menu-items="leftMenuItems"
          :story-id="storyIdForComposer"
          :archive-id="archiveIdForComposer"
          @select-option="handleSelectOption"
          @restore-options="chatStore.restorePreviousOptions()"
          @send="handleSend"
          @toggle-menu="toggleLeftMenu"
          @focus="handleMobileComposerFocus"
          @blur="handleMobileComposerBlur"
          @resized="handleMobileComposerResize"
          @retry-options="handleManualGenerateOptions"
        />
      </section>
    </main>

    <!-- 右侧气泡菜单 -->
    <BubbleMenu
      :visible="rightMenuVisible"
      :items="rightMenuItems"
      :trigger-element="settingsBtnRef"
      position="bottom-left"
      @close="rightMenuVisible = false"
    />

    <ArchiveDialogs
      v-model:archive-dialog-visible="archiveDialogVisible"
      v-model:archive-name-dialog-visible="archiveNameDialogVisible"
      v-model:log-dialog-visible="logDialogVisible"
      v-model:new-archive-name-input="newArchiveNameInput"
      :archive-bulk-mode="archiveBulkMode"
      :archive-selection="archiveSelection"
      :deleting-archives="deletingArchives"
      @create="handleNewArchive"
      @load="handleLoadArchive"
      @delete="handleDeleteArchive"
      @toggle-bulk-mode="toggleArchiveBulkMode"
      @selection-change="handleArchiveSelectionChange"
      @bulk-delete="handleBulkDeleteArchives"
      @rename="handleRenameArchive"
      @export="handleExportArchive"
      @import-file="onImportFile"
      @confirm-archive-name="confirmArchiveName"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { debounce } from 'lodash'

import { useChatViewportFollow } from '../composables/useChatViewportFollow'
import { useMobileInputBar } from '../composables/useMobileInputBar'
import { deleteArchive, getErrorMessage, renameArchive, exportArchive, importArchive } from '../api'
import { useChatStore } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'
import { useStoryStore } from '../stores/story'

import BubbleMenu, { type BubbleMenuItem } from '../components/BubbleMenu.vue'

import { useDraft } from '../composables/useDraft'

import PlayTopbar from './storyplay/PlayTopbar.vue'
import ChatArea from './storyplay/ChatArea.vue'
import PlayBottomBar from './storyplay/PlayBottomBar.vue'
import ImmersiveMode from './storyplay/ImmersiveMode.vue'
import WorldSettingPanel from './storyplay/WorldSettingPanel.vue'
import TimelinePanel from './storyplay/TimelinePanel.vue'
import ArchiveDialogs from './storyplay/ArchiveDialogs.vue'

const route = useRoute()
const router = useRouter()
const storyStore = useStoryStore()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()
const { streaming, streamingFollow } = storeToRefs(chatStore)

const FONT_SCALE_KEY = 'fontScale'

function getFontScale(): number {
  return parseFloat(localStorage.getItem(FONT_SCALE_KEY) || '1')
}

function setFontScale(scale: number) {
  document.documentElement.style.setProperty('--font-scale', String(scale))
  localStorage.setItem(FONT_SCALE_KEY, String(scale))
}

function restoreFontScale() {
  const saved = getFontScale()
  document.documentElement.style.setProperty('--font-scale', String(saved))
}

const routeStoryId = computed(() => Number(route.params.storyId))
const routeArchiveId = computed(() => Number(route.query.archiveId))

const inputText = ref('')
const openingRequirement = ref('')
const storyIdForComposer = ref<number | null>(null)
const archiveIdForComposer = ref<number | null>(null)
const storyPlayRef = ref<HTMLElement | null>(null)

// 子组件实例：用于取内部 ref / 暴露接口
const playTopbarInstance = ref<InstanceType<typeof PlayTopbar> | null>(null)
const chatAreaInstance = ref<InstanceType<typeof ChatArea> | null>(null)
const playBottomBarInstance = ref<InstanceType<typeof PlayBottomBar> | null>(null)

const settingsBtnRef = computed(() => playTopbarInstance.value?.settingsBtnRef ?? null)
const chatAreaRef = computed(() => chatAreaInstance.value?.chatAreaRef ?? null)
const composerRef = computed(() => playBottomBarInstance.value?.composerRef ?? null)
const quickOptionsRef = computed(() => playBottomBarInstance.value?.quickOptionsRef ?? null)
const inputAreaRef = computed(() => playBottomBarInstance.value?.inputAreaRef ?? null)
const textareaRef = computed(() => playBottomBarInstance.value?.textareaRef ?? null)

const leftMenuVisible = ref(false)
const rightMenuVisible = ref(false)
const timelineVisible = ref(false)
const archiveDialogVisible = ref(false)
const storyDrawerVisible = ref(false)
const worldSettingPopupVisible = ref(false)
const immersiveMode = ref(false)
const immersiveUiVisible = ref(false) // 沉浸模式下UI的显示状态
const immersiveHintVisible = ref(false) // 沉浸模式提示是否显示
const immersiveTransitioning = ref(false) // 防止连续切换的过渡锁
let immersiveScrollTop = 0 // 进入沉浸模式前的滚动位置，退出时恢复
const immersiveDotPos = reactive({ bottom: 24, right: 24 }) // 小圆点位置（离开屏幕边缘的边距）
const logDialogVisible = ref(false)
const savingOptionToggle = ref(false)
const archiveBulkMode = ref(false)
const archiveSelection = ref<number[]>([])
const deletingArchives = ref(false)
const archiveNameDialogVisible = ref(false)
const newArchiveNameInput = ref('')
const selectMode = ref(false)
const selectedMessageIds = ref<Set<string | number>>(new Set())
const deletingInProgress = ref(false)
const pendingRecallIds = ref<Set<string | number>>(new Set())
let recallFallbackTimer: ReturnType<typeof window.setTimeout> | null = null
let immersiveHideTimer: ReturnType<typeof setTimeout> | null = null
const IMMERSIVE_HIDE_DELAY = 3000
const IMMERSIVE_TRANSITION_DURATION = 350 // 与 CSS transition 时间匹配，防止连续切换
let immersiveTransitionTimer: ReturnType<typeof setTimeout> | null = null

const isFullscreen = () => !!document.fullscreenElement

const hasStarted = computed(() => chatStore.messages.some((m) => m.role === 'assistant'))
const assistantMessageCount = computed(
  () => chatStore.messages.filter((m) => m.role === 'assistant').length,
)
const autoGenerateOptions = computed(() => chatStore.autoGenerateOptions)

const {
  topbarScrolled,
  autoFollow,
  pendingMessageCount,
  badgeBouncing,
  syncFollowerState,
  forceScrollToBottom,
  jumpToLatest,
  queueBottomFollow,
  attachChatScrollListener,
  userScrolledUp,
} = useChatViewportFollow({
  storyPlayRef,
  chatAreaRef,
  inputAreaRef,
  quickOptionsRef,
  textareaRef,
  assistantMessageCount,
  streaming,
  streamingFollow,
})

const {
  handleComposerResize: handleMobileComposerResize,
  handleComposerFocus: handleMobileComposerFocus,
  handleComposerBlur: handleMobileComposerBlur,
  syncViewportHeight: syncMobileViewportHeight,
  syncMobileLayoutVars: syncMobileLayoutVarsFromBar,
  bindMobileLayoutObserver: bindMobileLayoutObserverFromBar,
  startViewportTracking: startMobileViewportTracking,
  setBottomFollowFn,
} = useMobileInputBar({
  rootRef: storyPlayRef,
  inputAreaRef,
  quickOptionsRef,
  textareaRef,
})

// Register queueBottomFollow callback for mobile keyboard scroll
setBottomFollowFn(queueBottomFollow)

const SPINNER_ICON =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 800ms linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>'

function clearRecallFallbackTimer() {
  if (recallFallbackTimer === null) return
  window.clearTimeout(recallFallbackTimer)
  recallFallbackTimer = null
}

function resetTransientLocalState() {
  archiveBulkMode.value = false
  archiveSelection.value = []
  openingRequirement.value = ''
  inputText.value = ''
  pendingRecallIds.value = new Set()
  clearRecallFallbackTimer()
  selectMode.value = false
  selectedMessageIds.value = new Set()
  deletingInProgress.value = false
}

function enterSelectMode() {
  selectMode.value = true
  selectedMessageIds.value = new Set()
  rightMenuVisible.value = false
}

function handleLongPress(messageId: string | number) {
  selectMode.value = true
  rightMenuVisible.value = false
  selectedMessageIds.value = new Set([messageId])
}

function exitSelectMode() {
  selectMode.value = false
  selectedMessageIds.value = new Set()
}

function clearSelectedMessages() {
  selectedMessageIds.value = new Set()
}

function handleMsgSelect(messageId: string | number, checked: boolean) {
  const next = new Set(selectedMessageIds.value)
  if (checked) {
    next.add(messageId)
  } else {
    next.delete(messageId)
  }
  selectedMessageIds.value = next
}

async function handleBulkDelete() {
  const ids = Array.from(selectedMessageIds.value)
  if (ids.length === 0) return

  const msgs = chatStore.messages
  const firstAiIdx = msgs.findIndex((m) => m.role === 'assistant')
  const firstUserIdx = firstAiIdx > 0 && msgs[firstAiIdx - 1]?.role === 'user' ? firstAiIdx - 1 : -1
  const idSet = new Set(ids)
  const openingContent =
    firstUserIdx >= 0 && idSet.has(msgs[firstUserIdx].id) ? msgs[firstUserIdx].content : ''

  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 条消息？删除后不可恢复。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  deletingInProgress.value = true
  try {
    await chatStore.deleteMessages(ids)
    ElMessage.success(`已删除 ${ids.length} 条消息`)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '删除失败，请重试'))
    return
  } finally {
    deletingInProgress.value = false
  }

  if (openingContent) {
    openingRequirement.value = openingContent
  }

  exitSelectMode()
}

// 左侧菜单项
const leftMenuItems = computed<BubbleMenuItem[]>(() => [
  {
    label: '生成剧情选项',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    disabled: !hasStarted.value || chatStore.sending || chatStore.optionsLocked,
    action: handleManualGenerateOptions,
  },
  {
    label: '生成状态播报',
    icon: chatStore.generatingStateBroadcast
      ? SPINNER_ICON
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    disabled:
      !hasStarted.value ||
      chatStore.sending ||
      chatStore.streaming ||
      chatStore.generatingStateBroadcast,
    action: handleGenerateState,
  },
  {
    label: '生成图片',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
    disabled: !hasStarted.value || chatStore.isGeneratingImage,
    action: () => chatStore.generateImage(),
  },
  {
    label: '冒险日志',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    disabled: chatStore.messages.length === 0,
    action: openLogs,
  },
  {
    label: '撤回最后一轮',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.12 12.76a6 6 0 1 1-1.77-4.24l-2.9.65"/><path d="M20.88 18.12a6 6 0 1 1-1.77-4.24"/></svg>',
    disabled: !canRecall.value,
    action: handleRecallLastRound,
  },
  {
    label: '沉浸模式',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    disabled: immersiveTransitioning.value,
    action: toggleImmersive,
  },
])

// 右侧菜单项
const rightMenuItems = computed<BubbleMenuItem[]>(() => [
  {
    label: chatStore.streamingFollow ? '关闭流式跟随' : '开启流式跟随',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>',
    disabled: false,
    action: () => {
      const newValue = !chatStore.streamingFollow
      chatStore.setStreamingFollow(newValue)
    },
  },
  {
    label: autoGenerateOptions.value ? '关闭自动生成选项' : '开启自动生成选项',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    disabled: savingOptionToggle.value,
    action: () => {
      const newValue = !autoGenerateOptions.value
      chatStore.setAutoGenerateOptions(newValue)
      handleToggleAutoOptions(newValue)
    },
  },
  {
    label: '会话管理',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    disabled: false,
    action: () => {
      archiveDialogVisible.value = true
    },
  },
  {
    label: '前往设置',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    disabled: false,
    action: openSettingsFromPlay,
  },
  {
    label: '字号',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>',
    disabled: false,
    children: [
      { label: '小', action: () => setFontScale(0.85) },
      { label: '中', action: () => setFontScale(1.0) },
      { label: '大', action: () => setFontScale(1.2) },
    ],
  },
  {
    label: '删除消息',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="m9 12 2 2 4-4"/></svg>',
    disabled: chatStore.sending || chatStore.streaming || chatStore.optionsLocked,
    action: () => enterSelectMode(),
  },
  {
    label: '重置对话',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    disabled: false,
    action: () => handleResetArchive(),
  },
])

function toggleLeftMenu() {
  leftMenuVisible.value = !leftMenuVisible.value
}

function toggleRightMenu() {
  rightMenuVisible.value = !rightMenuVisible.value
  if (rightMenuVisible.value) {
    worldSettingPopupVisible.value = false
  }
}

function isMobileViewport() {
  return window.innerWidth <= 768
}

function openSettingsFromPlay() {
  const targetPath = isMobileViewport() ? '/settings-mobile' : '/settings'
  const storyId = routeStoryId.value
  if (Number.isFinite(storyId) && storyId > 0) {
    const query: Record<string, string> = { from: 'play', storyId: String(storyId) }
    if (chatStore.currentArchive?.id) {
      query.archiveId = String(chatStore.currentArchive.id)
    }
    router.push({ path: targetPath, query })
    return
  }
  router.push(targetPath)
}

let initToken = 0

async function initByStoryId(targetStoryId: number, preferredArchiveId?: number | null) {
  if (!Number.isFinite(targetStoryId) || targetStoryId <= 0) {
    ElMessage.error('故事ID无效')
    return
  }
  const myToken = ++initToken
  chatStore.loading = true
  await Promise.all([storyStore.fetchStory(targetStoryId), settingsStore.fetchSettings()])
  if (myToken !== initToken) {
    chatStore.loading = false
    return
  }
  chatStore.setAutoGenerateOptions(!!settingsStore.settings.auto_generate_options)

  if (preferredArchiveId && Number.isFinite(preferredArchiveId) && preferredArchiveId > 0) {
    try {
      await chatStore.loadArchive(preferredArchiveId)
      if (chatStore.currentArchive?.story_id !== targetStoryId) {
        await chatStore.ensureActiveArchive(targetStoryId)
      }
    } catch {
      chatStore.clearChat()
      await chatStore.ensureActiveArchive(targetStoryId)
    }
  } else {
    const result = await chatStore.ensureActiveArchive(targetStoryId)
    // ensureActiveArchive 对已有存档只设置了 currentArchive，需要再加载消息
    if (!result.isNew) {
      await chatStore.loadArchive(result.archiveId)
    } else {
      // 新存档：需要清理上一个故事的残留消息
      chatStore.clearChat()
    }
  }

  // 同步 storyId 和 archiveId 给 ChatComposer（initByStoryId 中的 loadArchive 路径也需要）
  storyIdForComposer.value = targetStoryId
  archiveIdForComposer.value = chatStore.currentArchive?.id ?? null

  // 尝试恢复聊天草稿
  if (chatStore.currentArchive?.id) {
    const draft = useDraft({
      currentStoryId: { value: targetStoryId },
      currentArchiveId: { value: chatStore.currentArchive.id },
    })
    const chatDraft = draft.loadDraft()
    if (chatDraft) {
      inputText.value = chatDraft
    }
  }

  // 尝试恢复开场草稿
  const draft = useDraft({
    currentStoryId: { value: targetStoryId },
    currentArchiveId: { value: null },
  })
  const openingDraft = draft.loadDraft()
  if (openingDraft) {
    openingRequirement.value = openingDraft
  }

  if (myToken !== initToken) return
  syncFollowerState()
  await nextTick()
  forceScrollToBottom()
  chatStore.loading = false
}

onMounted(async () => {
  restoreFontScale()
  window.addEventListener('keydown', handleWindowKeydown)
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  attachChatScrollListener()
  bindMobileLayoutObserverFromBar()
  syncMobileViewportHeight()
  startMobileViewportTracking()
  const preferredArchiveId =
    Number.isFinite(routeArchiveId.value) && routeArchiveId.value > 0 ? routeArchiveId.value : null
  await initByStoryId(routeStoryId.value, preferredArchiveId)
  await nextTick()
  syncMobileLayoutVarsFromBar()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleWindowKeydown)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  clearRecallFallbackTimer()
  clearImmersiveHideTimer()
  clearImmersiveTransitionTimer()
})

function openLogs() {
  logDialogVisible.value = true
}

function enterImmersive() {
  if (immersiveTransitioning.value) return
  immersiveTransitioning.value = true
  clearImmersiveTransitionTimer()
  immersiveTransitionTimer = setTimeout(() => {
    immersiveTransitioning.value = false
  }, IMMERSIVE_TRANSITION_DURATION)

  // 保存进入前的滚动位置，退出时恢复
  immersiveScrollTop = chatAreaRef.value?.scrollTop ?? 0

  try {
    const result = document.documentElement.requestFullscreen?.()
    if (result instanceof Promise) {
      result.catch(() => {
        // 全屏被拒绝或不支持，静默进入窗口内沉浸模式
      })
    }
  } catch {
    // 浏览器不支持，静默进入窗口内沉浸模式
  }
  immersiveMode.value = true
  immersiveUiVisible.value = true
  // 显示沉浸模式提示，3秒后自动隐藏
  immersiveHintVisible.value = true
  setTimeout(() => {
    immersiveHintVisible.value = false
  }, 3000)
  startImmersiveHideTimer()
}

function exitImmersive() {
  if (immersiveTransitioning.value) return
  immersiveTransitioning.value = true
  clearImmersiveTransitionTimer()
  immersiveTransitionTimer = setTimeout(() => {
    immersiveTransitioning.value = false
  }, IMMERSIVE_TRANSITION_DURATION)

  // 恢复退出前的滚动位置
  const savedScrollTop = immersiveScrollTop
  immersiveMode.value = false
  immersiveUiVisible.value = false
  immersiveHintVisible.value = false
  if (isFullscreen()) {
    try {
      document.exitFullscreen?.()
    } catch {
      // Safari 非全屏状态调用会抛异常，静默忽略
    }
  }
  clearImmersiveHideTimer()
  // 全屏退出后 nextTick 再恢复滚动（避免浏览器重置）
  nextTick(() => {
    chatAreaRef.value?.scrollTo({ top: savedScrollTop, behavior: 'smooth' })
  })
}

function toggleImmersive() {
  if (immersiveMode.value) {
    // 如果被 transitioning 锁卡住，使用强制退出
    if (immersiveTransitioning.value) {
      forceExitImmersive()
    } else {
      exitImmersive()
    }
  } else {
    enterImmersive()
  }
}

function showImmersiveUi(event?: MouseEvent) {
  immersiveUiVisible.value = true
  // 记录点击位置，小圆点出现在该位置附近
  if (event) {
    const edge = 20
    const x = event.clientX
    const y = event.clientY
    // 靠边 20px，显示在对角象限
    if (x < window.innerWidth / 2) {
      immersiveDotPos.right = window.innerWidth - x - edge
      immersiveDotPos.bottom = y + edge
    } else {
      immersiveDotPos.right = edge
      immersiveDotPos.bottom = window.innerHeight - y - edge
    }
  }
  startImmersiveHideTimer()
}

function startImmersiveHideTimer() {
  clearImmersiveHideTimer()
  immersiveHideTimer = setTimeout(() => {
    if (immersiveMode.value) {
      immersiveUiVisible.value = false
    }
  }, IMMERSIVE_HIDE_DELAY)
}

function clearImmersiveHideTimer() {
  if (immersiveHideTimer !== null) {
    clearTimeout(immersiveHideTimer)
    immersiveHideTimer = null
  }
}

function clearImmersiveTransitionTimer() {
  if (immersiveTransitionTimer !== null) {
    clearTimeout(immersiveTransitionTimer)
    immersiveTransitionTimer = null
  }
}

function handleTopCenterClick() {
  if (window.innerWidth < 768) {
    storyDrawerVisible.value = true
  } else {
    worldSettingPopupVisible.value = !worldSettingPopupVisible.value
    if (worldSettingPopupVisible.value) {
      rightMenuVisible.value = false
    }
  }
}

function resizeComposer() {
  composerRef.value?.resizeTextarea()
}

// 浏览器 Escape 键：退出沉浸模式（全屏状态下也会触发 fullscreenchange）
function handleWindowKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && immersiveMode.value) {
    // 强制退出，不受 immersiveTransitioning 锁影响
    forceExitImmersive()
  }
}

// 强制退出沉浸模式（不受 transitioning 锁限制）
function forceExitImmersive() {
  clearImmersiveTransitionTimer()
  clearImmersiveHideTimer()
  const savedScrollTop = immersiveScrollTop
  immersiveMode.value = false
  immersiveUiVisible.value = false
  immersiveTransitioning.value = false // 重置锁状态
  if (isFullscreen()) {
    try {
      document.exitFullscreen?.()
    } catch {
      // Safari 非全屏状态调用会抛异常，静默忽略
    }
  }
  nextTick(() => {
    chatAreaRef.value?.scrollTo({ top: savedScrollTop, behavior: 'smooth' })
  })
}

// 全屏状态变化：用户通过浏览器 UI 退出全屏时，同步退出沉浸模式
// 注意：Escape 键会同时触发 keydown 和 fullscreenchange，exitImmersive 已被 keydown 调过，
// fullscreenchange 到达时 immersiveMode 已经是 false，不会重复退出
function handleFullscreenChange() {
  if (!isFullscreen() && immersiveMode.value) {
    exitImmersive()
  }
}

async function handleToggleAutoOptions(val: boolean) {
  savingOptionToggle.value = true
  try {
    await settingsStore.saveSettings({ auto_generate_options: val })
    ElMessage.success('设置已保存')
  } catch (e: unknown) {
    // 保存失败时回滚到服务器值
    chatStore.setAutoGenerateOptions(!!settingsStore.settings.auto_generate_options)
    ElMessage.error(getErrorMessage(e, '保存失败'))
  } finally {
    savingOptionToggle.value = false
  }
}

async function handleStartStory() {
  const requirement =
    openingRequirement.value.trim() || storyStore.currentStory?.opening_requirement || ''
  if (!requirement) {
    ElMessage.warning('请先输入开场要求')
    return
  }

  try {
    const task = chatStore.startStory(routeStoryId.value, requirement)
    await nextTick()
    resizeComposer()
    queueBottomFollow({ behavior: 'smooth', frames: 6 })
    await task
    // 清除开场草稿（进入聊天阶段）
    composerRef.value?.clearDraft()
    openingRequirement.value = ''
  } catch (e: unknown) {
    if ((e as { partial?: boolean })?.partial) {
      ElMessage.warning(getErrorMessage(e, '开场已保留，部分数据生成失败'))
    } else {
      ElMessage.error(getErrorMessage(e, '开始聊天失败'))
    }
  }
}

async function handleSend(text: string, source: 'input' | 'option' = 'input') {
  const content = text.trim()
  if (!content) return
  if (!hasStarted.value) {
    ElMessage.warning('请先完成开场生成后再发送消息')
    return
  }

  try {
    const task = chatStore.sendStream(content, { fromOption: source === 'option' })
    if (source === 'input') {
      inputText.value = ''
      // 清除聊天草稿
      composerRef.value?.clearDraft()
    }
    await nextTick()
    resizeComposer()
    queueBottomFollow({ behavior: 'smooth', frames: 8 })
    await task
  } catch (e: unknown) {
    if ((e as { partial?: boolean })?.partial) {
      ElMessage.warning(getErrorMessage(e, '本轮正文已保留，结构化数据生成失败'))
    } else {
      ElMessage.error(getErrorMessage(e, '模型调用失败，请稍后重试'))
    }
  }
}

const canRecall = computed(() => {
  if (!hasStarted.value) return false
  if (chatStore.sending || chatStore.streaming || chatStore.optionsLocked) return false
  if (chatStore.recallInProgress) return false
  if (pendingRecallIds.value.size > 0) return false
  return chatStore.canRecallLastRound
})

async function handleRecallLastRound() {
  if (pendingRecallIds.value.size > 0) return
  try {
    const ids = await chatStore.recallLastRound()
    if (!ids || ids.length === 0) {
      ElMessage.warning('最后一轮消息尚未完成落库，暂时不能撤回')
      return
    }
    const recallUserMsg = ids.find((id) => typeof id === 'string')
    if (recallUserMsg) {
      const userMsg = chatStore.messages.find((m) => m.id === recallUserMsg)
      if (userMsg && userMsg.role === 'user') {
        openingRequirement.value = userMsg.content
      }
    }
    // 动画完成后真正从数组移除
    pendingRecallIds.value = new Set(ids)
    clearRecallFallbackTimer()
    recallFallbackTimer = window.setTimeout(() => {
      const remainingIds = Array.from(pendingRecallIds.value)
      if (remainingIds.length === 0) return
      chatStore.confirmRecall(remainingIds)
      pendingRecallIds.value = new Set()
      recallFallbackTimer = null
    }, 1200)
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '撤回失败'))
  }
}

function handleRecallAnimationEnd(messageId: string | number) {
  if (!pendingRecallIds.value.has(messageId)) return
  chatStore.confirmRecall([messageId])
  const nextPendingIds = new Set(pendingRecallIds.value)
  nextPendingIds.delete(messageId)
  pendingRecallIds.value = nextPendingIds
  if (pendingRecallIds.value.size === 0) {
    clearRecallFallbackTimer()
  }
}

function scrollToLatest() {
  jumpToLatest()
}

function handleSelectOption(option: string) {
  handleSend(option, 'option')
}

async function handleGenerateState() {
  try {
    await chatStore.generateStateBroadcast()
    await nextTick()
    queueBottomFollow({ behavior: 'smooth', frames: 4 })
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '生成状态播报失败'))
  }
}

async function handleResetArchive() {
  try {
    await ElMessageBox.confirm('确定重置对话？当前进度将清空，不可恢复。', '确认重置', {
      confirmButtonText: '重置',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await handleNewArchive()
  } catch {
    // cancelled
  }
}

async function handleManualGenerateOptions() {
  try {
    const options = await chatStore.manualGenerateOptions(3)
    if (!options || options.length === 0) {
      ElMessage.warning('未生成可用选项，请稍后重试')
      return
    }
    ElMessage.success({ message: '已生成剧情选择项', duration: 1500 })
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '生成剧情选择项失败'))
  }
}

async function handleNewArchive() {
  const previousArchiveId = chatStore.currentArchive?.id
  const data = await chatStore.startNewArchive(routeStoryId.value)
  // 清除旧存档的草稿（若有）
  if (previousArchiveId !== undefined) {
    const oldDraft = useDraft({
      currentStoryId: { value: routeStoryId.value },
      currentArchiveId: { value: previousArchiveId },
    })
    oldDraft.clearDraft()
  }
  // 更新 composer 的 storyId/archiveId
  storyIdForComposer.value = routeStoryId.value
  archiveIdForComposer.value = data.id
  resetTransientLocalState()
  syncFollowerState()
  // 弹出命名框
  newArchiveNameInput.value = ''
  archiveNameDialogVisible.value = true

  // 通知 ChatComposer 清除旧草稿
  nextTick(() => {
    composerRef.value?.clearDraft()
  })

  return data
}

async function confirmArchiveName() {
  const name = newArchiveNameInput.value.trim()
  if (name && chatStore.currentArchive) {
    try {
      await renameArchive(chatStore.currentArchive.id, name)
      const archive = chatStore.archives.find((a) => a.id === chatStore.currentArchive!.id)
      if (archive) archive.name = name
    } catch (e: unknown) {
      ElMessage.error(getErrorMessage(e, '重命名失败'))
    }
  }
  archiveNameDialogVisible.value = false
}

async function handleLoadArchive(archiveId: number) {
  await chatStore.loadArchive(archiveId)
  if (Number(route.query.archiveId) !== archiveId) {
    await router.replace({
      path: `/play/${routeStoryId.value}`,
      query: {
        ...route.query,
        archiveId: String(archiveId),
      },
    })
  }
  // 同步 storyId 和 archiveId 给 ChatComposer（先于 resetTransientLocalState，因为草稿恢复依赖它们）
  storyIdForComposer.value = routeStoryId.value
  archiveIdForComposer.value = archiveId

  resetTransientLocalState()

  // 恢复聊天草稿（在 resetTransientLocalState 清空 inputText 之后）
  const draft = useDraft({
    currentStoryId: { value: routeStoryId.value },
    currentArchiveId: { value: archiveId },
  })
  const chatDraft = draft.loadDraft()
  if (chatDraft) {
    inputText.value = chatDraft
  }

  syncFollowerState()
  await nextTick()
  forceScrollToBottom()
}

async function handleDeleteArchive(archiveId: number) {
  try {
    await ElMessageBox.confirm('确定删除该会话？删除后不可恢复。', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })

    await deleteArchive(archiveId)

    if (chatStore.currentArchive?.id === archiveId) {
      chatStore.clearChat()
      resetTransientLocalState()
      await chatStore.ensureActiveArchive(routeStoryId.value)
    } else {
      await chatStore.fetchArchives(routeStoryId.value)
      archiveSelection.value = archiveSelection.value.filter((id) => id !== archiveId)
    }
    ElMessage.success('已删除')
  } catch {
    // ignore cancel
  }
}

function toggleArchiveBulkMode() {
  archiveBulkMode.value = !archiveBulkMode.value
  archiveSelection.value = []
}

function handleArchiveSelectionChange(payload: { id: number; checked: boolean }) {
  if (payload.checked) {
    archiveSelection.value = Array.from(new Set([...archiveSelection.value, payload.id]))
    return
  }
  archiveSelection.value = archiveSelection.value.filter((id) => id !== payload.id)
}

async function handleBulkDeleteArchives() {
  if (archiveSelection.value.length === 0) return

  await ElMessageBox.confirm(
    `确定批量删除 ${archiveSelection.value.length} 个会话？删除后不可恢复。`,
    '确认删除',
    {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    },
  )

  deletingArchives.value = true
  const targetIds = [...archiveSelection.value]
  try {
    const results = await Promise.allSettled(targetIds.map((id) => deleteArchive(id)))
    const failed = results.filter((result) => result.status === 'rejected')
    const deletedCurrent =
      !!chatStore.currentArchive && targetIds.includes(chatStore.currentArchive.id)

    await chatStore.fetchArchives(routeStoryId.value)
    if (deletedCurrent) {
      chatStore.clearChat()
      resetTransientLocalState()
      await chatStore.ensureActiveArchive(routeStoryId.value)
    }

    archiveSelection.value = []
    archiveBulkMode.value = false
    if (failed.length === 0) {
      ElMessage.success(`批量删除完成，共删除 ${results.length} 项`)
    } else {
      ElMessage.warning(
        `批量删除完成，成功 ${results.length - failed.length} 项，失败 ${failed.length} 项`,
      )
    }
  } finally {
    deletingArchives.value = false
  }
}

async function handleRenameArchive(payload: { id: number; name: string }) {
  try {
    await renameArchive(payload.id, payload.name)
    const archive = chatStore.archives.find((a) => a.id === payload.id)
    if (archive) archive.name = payload.name
    ElMessage.success('已重命名')
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '重命名失败'))
  }
}

async function handleExportArchive(archiveId: number) {
  try {
    const data = await exportArchive(archiveId)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `存档_${data.archive.name}_${archiveId}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出')
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '导出失败'))
  }
}

async function onImportFile(file: File) {
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    await importArchive(data)
    await chatStore.fetchArchives(routeStoryId.value)
    ElMessage.success('导入成功')
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '导入失败'))
  }
}

// 跳转到指定消息位置
function handleJumpToMessage(messageId: string | number) {
  const index = chatStore.messages.findIndex((m) => m.id === messageId)
  if (index === -1 || !chatAreaRef.value) return

  // 找到消息元素并滚动到可视区
  const chatMessages = chatAreaRef.value.querySelectorAll('.chat-message')
  const targetEl = chatMessages[index] as HTMLElement
  if (targetEl) {
    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

watch(
  () => routeStoryId.value,
  async (newStoryId, oldStoryId) => {
    if (newStoryId === oldStoryId) return
    archiveDialogVisible.value = false
    logDialogVisible.value = false
    worldSettingPopupVisible.value = false
    storyDrawerVisible.value = false
    resetTransientLocalState()
    const preferredArchiveId =
      Number.isFinite(routeArchiveId.value) && routeArchiveId.value > 0
        ? routeArchiveId.value
        : null
    await initByStoryId(newStoryId, preferredArchiveId)
  },
)

watch(
  () => routeArchiveId.value,
  async (newArchiveId, oldArchiveId) => {
    if (newArchiveId === oldArchiveId) return
    if (!Number.isFinite(newArchiveId) || newArchiveId <= 0) return
    if (!Number.isFinite(routeStoryId.value) || routeStoryId.value <= 0) return
    if (
      chatStore.currentArchive?.id === newArchiveId &&
      chatStore.currentArchive?.story_id === routeStoryId.value
    )
      return
    resetTransientLocalState()
    await initByStoryId(routeStoryId.value, newArchiveId)
  },
)

watch(
  () => chatStore.currentArchive?.story_id,
  async (archiveStoryId) => {
    if (!archiveStoryId) return
    if (archiveStoryId === routeStoryId.value) return
    const preferredArchiveId =
      Number.isFinite(routeArchiveId.value) && routeArchiveId.value > 0
        ? routeArchiveId.value
        : null
    await initByStoryId(routeStoryId.value, preferredArchiveId)
  },
)

watch(
  () => [
    hasStarted.value,
    immersiveMode.value,
    immersiveUiVisible.value,
    chatStore.currentOptions.length,
  ],
  async () => {
    await nextTick()
    bindMobileLayoutObserverFromBar()
    syncMobileLayoutVarsFromBar()
  },
)

// 开场草稿自动保存（debounce 500ms）
const debouncedSaveOpeningDraft = debounce((text: string) => {
  if (!routeStoryId.value) return
  const draft = useDraft({
    currentStoryId: { value: routeStoryId.value },
    currentArchiveId: { value: null },
  })
  if (text.trim()) {
    draft.saveDraft(text)
  } else {
    draft.clearDraft()
  }
}, 500)

watch(
  () => openingRequirement.value,
  (text) => {
    debouncedSaveOpeningDraft(text)
  },
)
</script>

<style scoped>
.story-play {
  --play-viewport-height: 100%;
  --mobile-input-offset: 0px;
  --mobile-options-height: 0px;
  --visual-viewport-offset-top: 0px;
  --keyboard-offset: 0px;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--bg-primary);
}

.play-main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.center-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.story-play.immersive .center-panel {
  position: relative;
  z-index: 9996;
}

@media (min-width: 768px) {
  .story-play.immersive .play-main {
    grid-template-columns: 240px 1fr;
  }
}

@media (max-width: 767px) {
  .story-play {
    height: var(--play-viewport-height);
    min-height: var(--play-viewport-height);
    padding-top: var(--visual-viewport-offset-top);
  }

  /* 移动端隐藏左侧时间线（TimelinePanel 内已处理 display:none，此处保留布局兜底） */
  .play-main {
    grid-template-columns: 1fr;
  }

  .center-panel {
    flex: 1;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    min-height: 0;
    scroll-padding-bottom: calc(var(--mobile-input-offset) + var(--mobile-options-height) + 24px);
  }

  /* 图片操作按钮触控适配（ChatMessage 内部，保留与原一致的 scoped 写法） */
  .image-op-btn {
    padding: 8px 12px;
    font-size: 12px;
    min-height: 40px;
  }
}

/* ---- 以下为历史残留样式（当前 template 未直接使用，保留以免回归） ---- */
.magic-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: var(--user-bubble);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: var(--shadow-md);
  transition:
    background var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-spring),
    box-shadow var(--duration-fast) var(--ease-smooth);
}
.magic-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: scale(1.05);
  box-shadow: var(--shadow-lg);
}
.magic-btn:active:not(:disabled) {
  transform: scale(0.95);
}
.magic-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.quick-bar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.quick-bar-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth);
}
.quick-bar-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--accent-color);
}
.quick-bar-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.drawer-menu {
  padding: 16px 0;
}

.drawer-group-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 0 20px;
  margin-bottom: 4px;
  margin-top: 16px;
}

.drawer-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 13px 20px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 15px;
  cursor: pointer;
  text-align: left;
  transition: background var(--duration-fast) var(--ease-smooth);
}
.drawer-item:hover:not(:disabled) {
  background: var(--bg-hover);
}
.drawer-item:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.drawer-item--switch {
  justify-content: space-between;
  cursor: default;
}
.drawer-item--switch:hover {
  background: transparent;
}
.drawer-item-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.drawer-item--danger {
  color: var(--color-danger);
}
.drawer-item--danger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-danger) 10%, transparent);
}

.drawer-divider {
  height: 1px;
  background: var(--border-color);
  margin: 8px 0;
}
</style>
