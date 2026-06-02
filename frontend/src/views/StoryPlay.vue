<template>
  <div class="story-play" ref="storyPlayRef" :class="{ immersive: immersiveMode }">
    <transition name="immersive-fade">
      <header class="play-topbar" :class="{ scrolled: topbarScrolled }" v-if="!immersiveMode || immersiveUiVisible">
        <button class="topbar-back" @click="router.back()">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
        <div class="top-center" @click="handleTopCenterClick" style="cursor:pointer">
          <div class="char-avatar" :class="{ 'char-avatar--img': avatarSrc && !avatarImgError }">
            <img
              v-if="avatarSrc && !avatarImgError"
              :src="avatarSrc"
              class="char-avatar-img"
              alt=""
              @error="avatarImgError = true"
            />
            <span v-else class="char-avatar-mono">{{ (storyStore.currentStory?.title || 'AI').charAt(0) }}</span>
          </div>
          <div class="char-info">
            <span class="char-name">{{ storyStore.currentStory?.title || '故事互动' }}</span>
            <span v-if="currentChapter" class="char-subtitle char-chapter">{{ currentChapter }}</span>
            <span v-else class="char-subtitle world-trigger">
              {{ storyStore.currentStory?.description?.slice(0, 12) || '私密会话' }}
              <svg class="char-subtitle-arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </div>
        </div>
        <div class="top-actions">
          <button class="topbar-icon-btn immersive-toggle" :disabled="immersiveTransitioning" @click="toggleImmersive" title="沉浸模式">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          </button>
          <button class="topbar-icon-btn" :class="{ active: rightMenuVisible }" @click="toggleRightMenu" title="设置" ref="settingsBtnRef">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v6m5.2-13.2l-4.2 4.2m0 6l4.2 4.2M23 12h-6m-6 0H1m18.2 5.2l-4.2-4.2m0-6l-4.2-4.2"/></svg>
          </button>
          <button class="topbar-icon-btn timeline-toggle" :class="{ active: timelineVisible }" @click="timelineVisible = !timelineVisible" title="时间线">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          </button>
        </div>
      </header>
    </transition>

    <!-- 沉浸模式退出按钮 -->
    <Transition name="immersive-exit-fade">
      <button v-if="immersiveMode" class="immersive-exit" type="button" @click="forceExitImmersive">
        <span class="exit-hint">Esc</span>退出沉浸
      </button>
    </Transition>

    <!-- 沉浸模式小圆点：跟随用户上次点击位置 -->
    <Transition name="immersive-dot-fade">
      <div
        v-if="immersiveMode && !immersiveUiVisible"
        class="immersive-dot"
        :style="{ bottom: immersiveDotPos.bottom + 'px', right: immersiveDotPos.right + 'px' }"
        @click="showImmersiveUi"
        title="点击呼出控制"
      ></div>
    </Transition>

    <!-- 沉浸模式透明点击层：UI隐藏时覆盖聊天区，点击任意位置呼出UI -->
    <div
      v-if="immersiveMode && !immersiveUiVisible"
      class="immersive-overlay"
      :class="{ 'immersive-hint-visible': immersiveHintVisible }"
      @click.stop="showImmersiveUi($event)"
    >
      <div class="immersive-center-dot"></div>
      <div class="immersive-hint" :class="{ visible: immersiveHintVisible }">
        点击任意位置呼出 UI
      </div>
    </div>

    <!-- 世界观弹出层：桌面端玻璃卡片 -->
    <Transition name="world-popup-fade">
      <div
        v-if="worldSettingPopupVisible && !immersiveMode"
        class="world-popup-overlay"
        @click.self="worldSettingPopupVisible = false"
      >
        <div class="world-popup" role="dialog" aria-label="世界观">
          <div class="world-popup-header">
            <span class="world-popup-title">世界观</span>
            <button class="world-popup-close" @click="worldSettingPopupVisible = false" type="button" aria-label="关闭">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div class="world-popup-body">
            <div v-if="storyStore.currentStory?.world_setting" class="world-popup-text">{{ storyStore.currentStory.world_setting }}</div>
            <div v-else class="world-popup-empty">暂无世界观设定</div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 移动端世界观抽屉（底部滑出） -->
    <el-drawer
      v-model="storyDrawerVisible"
      direction="btt"
      size="60%"
      class="world-drawer"
    >
      <template #title>
        <span class="world-drawer-title">世界观</span>
      </template>
      <div class="world-drawer-content">
        <div v-if="storyStore.currentStory?.world_setting" class="world-drawer-text">{{ storyStore.currentStory.world_setting }}</div>
        <div v-else class="world-drawer-empty">暂无世界观设定</div>
      </div>
    </el-drawer>

    <main class="play-main">
      <aside class="story-timeline">
        <StoryTimeline
          :messages="chatStore.messages"
          @jump="handleJumpToMessage"
        />
      </aside>
      <section class="center-panel">
        <div
          class="chat-area"
          :class="{ 'has-bg': !!storyStore.currentStory?.background_image && settingsStore.settings.show_background_image !== false }"
          :style="storyStore.currentStory?.background_image && settingsStore.settings.show_background_image !== false ? { backgroundImage: `url(${storyStore.currentStory.background_image})` } : undefined"
          ref="chatAreaRef"
          v-loading="storyStore.loading || chatStore.loading"
        >
          <template v-if="!hasStarted">
            <transition name="starter-fade" mode="out-in">
              <div class="starter-wrap">
                <el-card class="starter-card">
                  <template #header>
                    <span>开始聊天</span>
                  </template>
                  <p class="starter-tip">
                    输入你想要的开场要求（例如：主角身份、关系基调、冲突方向），系统会用首次模型生成开场。
                  </p>
                  <textarea
                    class="opening-textarea"
                    v-model="openingRequirement"
                    :key="openingBounceKey || undefined"
                    :placeholder="storyStore.currentStory?.opening_requirement || '请输入开场要求...'"
                    :disabled="chatStore.sending"
                    rows="5"
                    @click="handleOpeningClick"
                  ></textarea>
                  <div class="starter-actions">
                    <button class="start-chat-btn" :disabled="chatStore.sending" @click="handleStartStory">
                      <span v-if="chatStore.sending">生成中...</span>
                      <span v-else>开始聊天</span>
                    </button>
                  </div>
                </el-card>
              </div>
            </transition>
          </template>

          <template v-else>
            <transition-group
              name="chat-fade"
              tag="div"
              class="chat-messages"
              :class="{ 'elastic-disabled': settingsStore.settings.disable_chat_bubble_elastic }"
              appear
            >
              <ChatMessage
                v-for="(msg, idx) in chatStore.messages"
                :key="msg.id"
                :msg="msg"
                :streaming="chatStore.streaming && idx === chatStore.messages.length - 1 && msg.role === 'assistant'"
                :selectMode="selectMode"
                :selected="selectedMessageIds.has(msg.id)"
                @recall-animation-end="handleRecallAnimationEnd"
                @select="handleMsgSelect"
                @long-press="handleLongPress"
              />
            </transition-group>

            <!-- 底部删除操作栏 -->
            <Transition name="delete-bar-fade">
              <div v-if="selectMode" class="delete-action-bar">
                <button class="delete-bar-btn cancel-btn" @click="exitSelectMode">取消</button>
                <span class="delete-bar-count">已选 {{ selectedMessageIds.size }} 项</span>
                <button
                  v-if="selectedMessageIds.size > 0"
                  class="delete-bar-btn clear-btn"
                  @click="clearSelectedMessages"
                >取消全选</button>
                <button
                  class="delete-bar-btn confirm-btn"
                  :disabled="selectedMessageIds.size === 0 || deletingInProgress"
                  @click="handleBulkDelete"
                >{{ deletingInProgress ? '删除中...' : '删除' }}</button>
              </div>
            </Transition>

            <!-- 新消息提示条：用户不在底部时出现 -->
            <button
              v-if="pendingMessageCount > 0 && !autoFollow"
              class="new-message-indicator"
              @click="jumpToLatest"
            >
              <span class="pending-badge" :class="{ 'badge-bounce': badgeBouncing }">{{ pendingMessageCount }}</span> 条新消息 ↑
            </button>

            <!-- 回到底部按钮：用户上翻时出现 -->
            <Transition name="back-bottom-fade">
              <button
                v-if="!autoFollow && userScrolledUp && pendingMessageCount === 0 && hasStarted"
                class="back-to-bottom-btn"
                @click="scrollToLatest"
                title="回到底部"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
            </Transition>
          </template>
        </div>

        <transition name="input-fade">
          <div v-if="hasStarted && !selectMode" ref="quickOptionsRef" class="quick-options-wrap">
            <QuickOptions
              :options="displayOptions"
              :disabled="chatStore.sending || chatStore.optionsLocked"
              :loading="chatStore.generatingOptions"
              :locked="chatStore.optionsLocked && !chatStore.generatingOptions"
              :locked-option="chatStore.lockedOption"
              :history-depth="chatStore.optionsHistoryDepth"
              @select="handleSelectOption"
              @restore="chatStore.restorePreviousOptions()"
            />
          </div>
        </transition>

        <transition name="input-fade">
          <ChatComposer
            v-if="(!immersiveMode || immersiveUiVisible) && !selectMode"
            ref="composerRef"
            v-model="inputText"
            :disabled="!hasStarted"
            :send-busy="chatStore.sending"
            :thinking="chatStore.streaming && !chatStore.awaitingTail"
            :awaiting-tail="chatStore.awaitingTail"
            :menu-active="leftMenuVisible"
            :show-spinner="chatStore.sending || chatStore.streaming || chatStore.awaitingTail"
            :generating-options="chatStore.generatingOptions"
            :generating-options-failed="chatStore.generatingOptionsFailed"
            :story-id="storyIdForComposer"
            :archive-id="archiveIdForComposer"
            @send="handleSend"
            @toggle-menu="toggleLeftMenu"
            @focus="handleMobileComposerFocus"
            @blur="handleMobileComposerBlur"
            @resized="handleMobileComposerResize"
            @retry-options="handleManualGenerateOptions"
          />
        </transition>
      </section>
    </main>

    <!-- 左侧气泡菜单 -->
    <BubbleMenu
      :visible="leftMenuVisible"
      :items="leftMenuItems"
      :trigger-element="plusBtnRef"
      position="top-right"
      @close="leftMenuVisible = false"
    />

    <!-- 右侧气泡菜单 -->
    <BubbleMenu
      :visible="rightMenuVisible"
      :items="rightMenuItems"
      :trigger-element="settingsBtnRef"
      position="bottom-left"
      @close="rightMenuVisible = false"
    />

    <!-- 会话管理对话框 -->
    <el-dialog v-model="archiveDialogVisible" title="会话管理" width="600px">
      <ArchiveList
        :archives="chatStore.archives"
        :current-id="chatStore.currentArchive?.id ?? null"
        :bulk-mode="archiveBulkMode"
        :selection="archiveSelection"
        :deleting="deletingArchives"
        @create="handleNewArchive"
        @load="handleLoadArchive"
        @delete="handleDeleteArchive"
        @toggle-bulk-mode="toggleArchiveBulkMode"
        @selection-change="handleArchiveSelectionChange"
        @bulk-delete="handleBulkDeleteArchives"
        @rename="handleRenameArchive"
        @export="handleExportArchive"
        @import="handleImportArchive"
      />
      <input ref="importFileRef" type="file" accept=".json" style="display:none" @change="onImportFile" />
    </el-dialog>

    <el-dialog
      v-model="archiveNameDialogVisible"
      title="命名存档"
      width="360px"
      :close-on-click-modal="false"
    >
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <el-input
          v-model="newArchiveNameInput"
          placeholder="输入存档名称"
          maxlength="50"
          @keydown.enter="confirmArchiveName"
        />
      </div>
      <template #footer>
        <el-button @click="archiveNameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmArchiveName">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logDialogVisible" title="剧情日志" width="680px">
      <div class="log-list">
        <div v-for="msg in chatStore.messages" :key="msg.id" class="log-row">
          <div class="log-meta">
            <span class="log-time">{{ formatTimeSeconds(msg.created_at) }}</span>
            <span class="log-role" :class="msg.role === 'assistant' ? 'ai-tag' : 'user-tag'">{{ msg.role === 'assistant' ? 'AI' : '你' }}</span>
          </div>
          <div class="log-content">{{ msg.content }}</div>
        </div>
      </div>
    </el-dialog>

    <!-- 手机模式：时间线底部弹出面板 -->
    <Teleport to="body">
      <div class="timeline-mobile-overlay" v-if="timelineVisible" @click.self="timelineVisible = false">
        <div class="timeline-mobile-sheet">
          <div class="timeline-mobile-handle" @click="timelineVisible = false"></div>
          <div class="timeline-mobile-header">
            <span>剧情时间线</span>
            <button class="topbar-icon-btn" @click="timelineVisible = false">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <StoryTimeline
            class="timeline-mobile-body"
            :messages="chatStore.messages"
            @jump="handleJumpToMessage"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { debounce } from 'lodash'

import ArchiveList from '../components/ArchiveList.vue'
import ChatComposer from '../components/ChatComposer.vue'
import ChatMessage from '../components/ChatMessage.vue'
import QuickOptions from '../components/QuickOptions.vue'
import { useChatViewportFollow } from '../composables/useChatViewportFollow'
import { useMobileInputBar } from '../composables/useMobileInputBar'
import { deleteArchive, getErrorMessage, renameArchive, exportArchive, importArchive } from '../api'
import { useChatStore } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'
import { useStoryStore } from '../stores/story'

import BubbleMenu, { type BubbleMenuItem } from '../components/BubbleMenu.vue'
import StoryTimeline from '../components/StoryTimeline.vue'

import { useDraft } from '../composables/useDraft'
import { formatTimeSeconds } from '../utils/time'

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
const chatAreaRef = ref<HTMLElement | null>(null)
const quickOptionsRef = ref<HTMLElement | null>(null)
const importFileRef = ref<HTMLInputElement | null>(null)
const composerRef = ref<{
  rootEl: HTMLDivElement | null
  textareaEl: HTMLTextAreaElement | null
  plusButtonEl: HTMLButtonElement | null
  resizeTextarea: () => void
  focusTextarea: () => void
  clearDraft: () => void
  loadDraft: (storyId: number, archiveId: number) => string
} | null>(null)
const inputAreaRef = computed(() => composerRef.value?.rootEl ?? null)
const textareaRef = computed(() => composerRef.value?.textareaEl ?? null)

const openingBounceKey = ref(0)

const plusBtnRef = computed(() => composerRef.value?.plusButtonEl ?? null)
const settingsBtnRef = ref<HTMLElement | null>(null)

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
const IMMERSIVE_TRANSITION_DURATION = 350  // 与 CSS transition 时间匹配，防止连续切换
let immersiveTransitionTimer: ReturnType<typeof setTimeout> | null = null

const isFullscreen = () => !!document.fullscreenElement

// 会话页眉：头像与情境副标
const avatarImgError = ref(false)
const avatarSrc = computed(() => storyStore.currentStory?.cover_image || '')
const currentChapter = computed(() => {
  const ch = chatStore.currentStoryState?.chapter
  return ch && String(ch).trim() ? String(ch).trim() : ''
})

// 切换故事时重置图片错误状态
watch(() => storyStore.currentStory?.id, () => {
  avatarImgError.value = false
})

const hasStarted = computed(() => chatStore.messages.some((m) => m.role === 'assistant'))
const assistantMessageCount = computed(() => chatStore.messages.filter((m) => m.role === 'assistant').length)
const displayOptions = computed(() => {
  if (chatStore.currentOptions.length > 0) return chatStore.currentOptions
  return []
})
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

const SPINNER_ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 800ms linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>'

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
    action: handleManualGenerateOptions
  },
  {
    label: '生成状态播报',
    icon: chatStore.generatingStateBroadcast ? SPINNER_ICON : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    disabled: !hasStarted.value || chatStore.sending || chatStore.streaming || chatStore.generatingStateBroadcast,
    action: handleGenerateState
  },
  {
    label: '生成图片',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
    disabled: !hasStarted.value || chatStore.isGeneratingImage,
    action: () => chatStore.generateImage()
  },
  {
    label: '冒险日志',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    disabled: chatStore.messages.length === 0,
    action: openLogs
  },
  {
    label: '撤回最后一轮',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-color)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.12 12.76a6 6 0 1 1-1.77-4.24l-2.9.65"/><path d="M20.88 18.12a6 6 0 1 1-1.77-4.24"/></svg>',
    disabled: !canRecall.value,
    action: handleRecallLastRound
  },
  {
    label: '沉浸模式',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    disabled: immersiveTransitioning.value,
    action: toggleImmersive
  }
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
    }
  },
  {
    label: autoGenerateOptions.value ? '关闭自动生成选项' : '开启自动生成选项',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    disabled: savingOptionToggle.value,
    action: () => {
      const newValue = !autoGenerateOptions.value
      chatStore.setAutoGenerateOptions(newValue)
      handleToggleAutoOptions(newValue)
    }
  },
  {
    label: '会话管理',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    disabled: false,
    action: () => { archiveDialogVisible.value = true }
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
    ]
  },
  {
    label: '删除消息',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="m9 12 2 2 4-4"/></svg>',
    disabled: chatStore.sending || chatStore.streaming || chatStore.optionsLocked,
    action: () => enterSelectMode()
  },
  {
    label: '重置对话',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    disabled: false,
    action: () => handleResetArchive()
  }
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
  const preferredArchiveId = Number.isFinite(routeArchiveId.value) && routeArchiveId.value > 0
    ? routeArchiveId.value
    : null
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
  immersiveTransitionTimer = setTimeout(() => { immersiveTransitioning.value = false }, IMMERSIVE_TRANSITION_DURATION)

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
  immersiveTransitionTimer = setTimeout(() => { immersiveTransitioning.value = false }, IMMERSIVE_TRANSITION_DURATION)

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

function handleOpeningClick() {
  openingBounceKey.value++
  nextTick(() => {
    const el = document.querySelector('.opening-textarea') as HTMLTextAreaElement
    el?.focus()
  })
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
  immersiveTransitioning.value = false  // 重置锁状态
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
  const requirement = openingRequirement.value.trim() || storyStore.currentStory?.opening_requirement || ''
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

  await ElMessageBox.confirm(`确定批量删除 ${archiveSelection.value.length} 个会话？删除后不可恢复。`, '确认删除', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })

  deletingArchives.value = true
  const targetIds = [...archiveSelection.value]
  try {
    const results = await Promise.allSettled(targetIds.map((id) => deleteArchive(id)))
    const failed = results.filter((result) => result.status === 'rejected')
    const deletedCurrent = !!chatStore.currentArchive && targetIds.includes(chatStore.currentArchive.id)

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
      ElMessage.warning(`批量删除完成，成功 ${results.length - failed.length} 项，失败 ${failed.length} 项`)
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

function handleImportArchive() {
  importFileRef.value?.click()
}

async function onImportFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    await importArchive(data)
    await chatStore.fetchArchives(routeStoryId.value)
    ElMessage.success('导入成功')
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '导入失败'))
  } finally {
    input.value = ''
  }
}

// 跳转到指定消息位置
function handleJumpToMessage(messageId: string | number) {
  const index = chatStore.messages.findIndex(m => m.id === messageId)
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
    const preferredArchiveId = Number.isFinite(routeArchiveId.value) && routeArchiveId.value > 0
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
    if (chatStore.currentArchive?.id === newArchiveId && chatStore.currentArchive?.story_id === routeStoryId.value) return
    resetTransientLocalState()
    await initByStoryId(routeStoryId.value, newArchiveId)
  },
)

watch(
  () => chatStore.currentArchive?.story_id,
  async (archiveStoryId) => {
    if (!archiveStoryId) return
    if (archiveStoryId === routeStoryId.value) return
    const preferredArchiveId = Number.isFinite(routeArchiveId.value) && routeArchiveId.value > 0
      ? routeArchiveId.value
      : null
    await initByStoryId(routeStoryId.value, preferredArchiveId)
  },
)

watch(
  () => [hasStarted.value, immersiveMode.value, immersiveUiVisible.value, chatStore.currentOptions.length],
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

.play-topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  border-bottom: 1px solid var(--border-color);
  background: var(--topbar-bg, var(--bg-card));
  gap: 8px;
  transition:
    opacity var(--duration-slow) var(--ease-smooth),
    transform var(--duration-slow) var(--ease-smooth),
    box-shadow var(--duration-fast) var(--ease-smooth);
}

.play-topbar.scrolled {
  box-shadow: var(--shadow-md), 0 0 20px color-mix(in srgb, var(--accent-color) 10%, transparent);
}

[data-theme="light"] .play-topbar {
  background: rgba(250, 249, 252, 0.85);
  border-bottom-color: #e8e4ef;
}

.topbar-back {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-spring);
}
.topbar-back:hover {
  background: var(--bg-hover);
  border-color: var(--border-color);
  transform: scale(1.05);
}

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
  transition: color 0.15s, border-color 0.15s;
  display: flex;
  align-items: center;
  gap: 5px;
}
.immersive-exit:hover { color: var(--text-primary); border-color: var(--accent-color); }
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
  transition: opacity 250ms var(--ease-smooth), transform 250ms var(--ease-smooth);
}
.immersive-exit-fade-enter-from,
.immersive-exit-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.immersive-dot-fade-enter-active,
.immersive-dot-fade-leave-active {
  transition: opacity 300ms var(--ease-smooth), transform 300ms var(--ease-smooth);
}
.immersive-dot-fade-enter-from,
.immersive-dot-fade-leave-to {
  opacity: 0;
  transform: scale(0.5);
}

.top-center {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.char-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--user-bubble);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.char-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.char-avatar-mono {
  line-height: 1;
  user-select: none;
}

/* bubble-pop-in 已提取到全局 style.css */

.char-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.char-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-subtitle {
  font-size: var(--text-xs, 12px);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.char-chapter {
  display: block;
}
.world-trigger {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 6px;
  transition: background 150ms, color 150ms;
}
.world-trigger:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}
.char-subtitle-arrow {
  transition: transform 200ms var(--ease-smooth);
  flex-shrink: 0;
}
.world-trigger:hover .char-subtitle-arrow {
  transform: translateY(1px);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.topbar-icon-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-spring);
}
.topbar-icon-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  transform: scale(1.05);
}
.topbar-icon-btn.active {
  background: color-mix(in srgb, var(--accent-color) 20%, transparent);
  color: var(--accent-color);
}

.play-main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.story-timeline {
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  scrollbar-width: none;
}

.story-timeline::-webkit-scrollbar {
  display: none;
}

.center-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px 0;
  background: var(--chat-area-gradient);
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
  scroll-padding-bottom: calc(var(--mobile-input-offset) + var(--mobile-options-height) + 24px);
  position: relative;
}

.chat-area.has-bg {
  background-size: cover;
  background-position: center;
}

.chat-area.has-bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--chat-bg-overlay);
  z-index: 1;
  pointer-events: none;
}

.starter-wrap {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px 0;
  position: relative;
  z-index: 2;
}

.starter-card {
  width: min(680px, 100%);
  border-radius: 16px;
  border-color: var(--border-color);
  background: var(--bg-card);
}

.starter-tip {
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.65;
}

.starter-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.opening-textarea {
  width: 100%;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.65;
  outline: none;
  resize: none;
  transition:
    border-color var(--duration-base) var(--ease-smooth),
    box-shadow var(--duration-base) var(--ease-smooth);
  box-shadow: var(--shadow-sm);
}

.opening-textarea::placeholder {
  color: var(--text-muted);
}

.opening-textarea:focus {
  border-color: var(--accent-color);
  box-shadow: var(--shadow-sm), 0 0 0 3px color-mix(in srgb, var(--accent-color) 20%, transparent);
}

/* Q弹动画：每次 key 变化时重挂载后播放 */
.opening-textarea.input-bounce {
  animation: input-bounce-in 280ms var(--ease-spring) both;
}

/* input-bounce-in 已提取到全局 style.css */

.start-chat-btn {
  height: 44px;
  padding: 0 28px;
  border-radius: 22px;
  border: none;
  background: var(--user-bubble);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: transform var(--duration-fast) var(--ease-smooth), box-shadow var(--duration-fast) var(--ease-smooth), background-color var(--duration-fast) var(--ease-smooth), border-color var(--duration-fast) var(--ease-smooth), color var(--duration-fast) var(--ease-smooth);
  box-shadow: var(--shadow-md), 0 0 0 0 var(--accent-glow);
}

.start-chat-btn:hover:not(:disabled) {
  transform: scale(1.04);
  box-shadow: var(--shadow-lg), var(--shadow-glow);
}

.start-chat-btn:active:not(:disabled) {
  transform: scale(0.96);
  transition-duration: 80ms;
}

.start-chat-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* ---- 聊天消息容器 ---- */
.chat-messages {
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 2;
}

/* ---- 开场卡淡出 + 聊天淡入过渡 ---- */
.starter-fade-leave-active {
  transition: opacity 300ms var(--ease-smooth);
}
.starter-fade-leave-to {
  opacity: 0;
}

.chat-fade-enter-active {
  /* 省略 opacity 过渡：bubble-pop-in 已自带完整 opacity 0→1 入场，
     再叠一层 opacity 过渡会造成 60ms 后 bubble 已在 1 但被父级 fade 拉回的视觉冲突。 */
  transition: none;
}
.chat-fade-enter-from {
  opacity: 0;
}

/* ---- 沉浸模式过渡 ---- */
.immersive-fade-enter-active,
.immersive-fade-leave-active {
  transition: opacity 300ms var(--ease-smooth), transform 300ms var(--ease-smooth), filter 300ms var(--ease-smooth);
}
.immersive-fade-enter-from,
.immersive-fade-leave-to {
  opacity: 0;
  transform: scale(0.97);
  filter: blur(4px);
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

/* ---- 会话管理/剧情日志弹窗圆角 ---- */
:deep(.el-dialog) {
  border-radius: 16px;
}
:deep(.el-dialog__header) {
  border-bottom: 1px solid var(--border-color);
}
:deep(.el-dialog__body) {
  padding: 16px 20px;
}

/* ---- 剧情选项气泡：靠左对齐，右边不超过视口一半，半透明 ---- */
.quick-options {
  max-width: 50vw;
  padding: 10px 0 6px;
  min-height: 40px;
  background: var(--bg-primary);
}

@media (max-width: 767px) {
  .story-play {
    height: var(--play-viewport-height);
    min-height: var(--play-viewport-height);
    padding-top: var(--visual-viewport-offset-top);
  }

  .quick-options {
    max-width: min(80vw, 300px);
  }

  .quick-options-wrap {
    padding: 6px 12px 0;
  }

  .top-actions {
    gap: 8px;
  }

  /* 移动端隐藏左侧时间线 */
  .story-timeline {
    display: none;
  }

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

  .chat-area {
    flex: 1;
    overflow: visible;
    padding-bottom: 12px;
  }

  /* 选项按钮触控区域 */
  .option-btn {
    min-height: 44px;
    padding: 10px 16px;
    font-size: 14px;
  }

  /* 消息字体大小 */
  .chat-message .msg-content {
    font-size: 15px;
    line-height: 1.6;
  }

  /* 开场卡适配 */
  .starter-tip {
    font-size: 14px;
    padding: 0 4px;
  }

  .start-chat-btn {
    width: 100%;
    height: 48px;
  }

  .msg-time {
    font-size: 11px;
  }

  .topbar-icon-btn {
    min-width: 44px;
    min-height: 44px;
  }
  .topbar-back {
    min-width: 44px;
    min-height: 44px;
  }
  .timeline-mobile-header .topbar-icon-btn {
    min-width: 44px;
    min-height: 44px;
  }

  /* 图片操作按钮触控适配 */
  .image-op-btn {
    padding: 8px 12px;
    font-size: 12px;
    min-height: 40px;
  }

  /* 新消息指示器触控优化 */
  .new-message-indicator {
    min-height: 40px;
    padding: 10px 20px;
  }

  .back-to-bottom-btn {
    width: 44px;
    height: 44px;
  }

  /* 沉浸式退出按钮 */
  .immersive-exit {
    min-height: 44px;
    padding: 8px 14px;
  }

  /* 删除操作栏移动端适配：固定定位，确保始终可见 */
  .delete-action-bar {
    left: 16px;
    right: 16px;
    bottom: max(16px, calc(var(--keyboard-offset, 0px) + env(safe-area-inset-bottom)));
    padding: 10px 16px;
    gap: 8px;
  }

  .delete-bar-btn {
    padding: 10px 16px;
    min-height: 44px;
  }

  .delete-bar-count {
    font-size: 12px;
  }
}

@media (max-width: 380px) {
  .play-topbar {
    gap: 4px;
    padding: 0 8px;
  }

  .top-center {
    gap: 8px;
  }

  .char-avatar {
    width: 34px;
    height: 34px;
    font-size: 14px;
  }

  .char-subtitle {
    display: none;
  }

  .top-actions {
    gap: 2px;
  }

  .immersive-toggle {
    display: none;
  }
}

/* ---- 新消息提示条 ---- */
.new-message-indicator {
  position: sticky;
  bottom: calc(var(--mobile-input-offset) + var(--mobile-options-height) + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 7px 18px;
  border-radius: 20px;
  border: none;
  background: var(--accent-color);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  box-shadow: var(--shadow-md), 0 0 16px var(--accent-glow);
  z-index: 5;
  width: fit-content;
  margin: 0 auto;
  display: block;
  animation: indicator-pop-in 220ms var(--ease-spring) both;
  transition: transform var(--duration-fast) var(--ease-spring);
}

.new-message-indicator:hover {
  transform: translateX(-50%) scale(1.04);
}

/* ---- 数字徽章弹跳动画 ---- */
.pending-badge {
  transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
  display: inline-block;
}

@keyframes badge-bounce {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.35); }
}

.new-message-indicator:active {
  transform: translateX(-50%) scale(0.97);
  transition-duration: 80ms;
}

@keyframes indicator-pop-in {
  0%   { opacity: 0; transform: translateX(-50%) scale(0.7) translateY(10px); }
  60%  { opacity: 1; transform: translateX(-50%) scale(1.05) translateY(0); }
  100% { opacity: 1; transform: translateX(-50%) scale(1) translateY(0); }
}

/* ---- 回到底部按钮 ---- */
.back-to-bottom-btn {
  position: sticky;
  bottom: calc(var(--mobile-input-offset) + var(--mobile-options-height) + 8px);
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  z-index: 5;
  margin: 0 auto;
  transition:
    background 150ms var(--ease-smooth),
    color 150ms var(--ease-smooth),
    transform 150ms var(--ease-spring),
    box-shadow 150ms var(--ease-smooth);
}

.back-to-bottom-btn:hover {
  background: var(--bg-hover);
  color: var(--accent-color);
  transform: translateX(-50%) scale(1.08);
  box-shadow: var(--shadow-lg);
}

.back-to-bottom-btn:active {
  transform: translateX(-50%) scale(0.95);
  transition-duration: 80ms;
}

.back-bottom-fade-enter-active,
.back-bottom-fade-leave-active {
  transition: opacity 200ms var(--ease-smooth), transform 200ms var(--ease-spring);
}
.back-bottom-fade-enter-from,
.back-bottom-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

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
.drawer-item--switch:hover { background: transparent; }
.drawer-item-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.drawer-item--danger { color: var(--color-danger); }
.drawer-item--danger:hover:not(:disabled) { background: color-mix(in srgb, var(--color-danger) 10%, transparent); }

.drawer-divider {
  height: 1px;
  background: var(--border-color);
  margin: 8px 0;
}

.log-list {
  max-height: 62vh;
  max-height: 62dvh;
  overflow-y: auto;
  border-radius: 12px;
  overflow: hidden;
}

.log-row {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 4px;
}

.log-row:last-child {
  border-bottom: none;
}

.log-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.log-role {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 10px;
}

.log-role.ai-tag {
  color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 15%, transparent);
}

.log-role.user-tag {
  color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 15%, transparent);
}

.log-time {
  font-size: 12px;
  color: var(--text-muted);
}

.log-content {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  color: var(--text-primary);
}

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
  box-shadow: var(--shadow-lg), 0 0 0 1px color-mix(in srgb, var(--border-color) 30%, transparent);
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
  transition: background 150ms, color 150ms, border-color 150ms;
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
  transition: transform 220ms var(--ease-spring), opacity 220ms var(--ease-smooth);
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

@media (min-width: 768px) and (max-width: 1199px) {
  .chat-area {
    padding: 16px 18px 0;
  }

  .starter-card {
    width: min(760px, 100%);
  }
}

@media (min-width: 1200px) {
  .chat-area {
    padding: 16px 24px 0;
  }
}

@media (min-width: 768px) {
  .story-play.immersive .play-main {
    grid-template-columns: 240px 1fr;
  }
}

.story-play.immersive .story-timeline {
  opacity: 0.85;
}

.story-play.immersive .center-panel {
  position: relative;
  z-index: 9996;
}

.story-play.immersive .chat-area {
  max-width: 820px;
  margin: 0 auto;
}

/* ---- 沉浸模式 reduced motion ---- */
@media (prefers-reduced-motion: reduce) {
  .immersive-dot-fade-enter-active,
  .immersive-dot-fade-leave-active,
  .immersive-exit-fade-enter-active,
  .immersive-exit-fade-leave-active,
  .immersive-fade-enter-active,
  .immersive-fade-leave-active {
    transition-duration: 80ms !important;
    animation-duration: 1ms !important;
  }
}

/* ---- 消息入场动画 ---- */

/* AI/助手消息：从底部滑入（:deep 穿透 scoped 到 ChatMessage.vue） */
:deep(.msg-ai) {
  animation: msg-ai-in 300ms cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.chat-messages.elastic-disabled :deep(.msg-ai) {
  animation: msg-ai-in-reduced 180ms ease-out both;
}

/* 用户消息：从右侧滑入 */
:deep(.msg-user) {
  animation: msg-user-in 300ms cubic-bezier(0.34, 1.3, 0.64, 1) both;
}

.chat-messages.elastic-disabled :deep(.msg-user) {
  animation: msg-user-in-reduced 180ms ease-out both;
}

/* 状态播报：从 scale + 淡入 + 边框脉冲 */
:deep(.msg-state) {
  animation: msg-state-enter 250ms ease-out both,
             msg-state-pulse 600ms ease-in-out 250ms 1;
}

@keyframes msg-slide-up {
  from { transform: translateY(12px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}

@keyframes msg-slide-right {
  from { transform: translateX(20px); opacity: 0; }
  to   { transform: translateX(0);   opacity: 1; }
}

@keyframes msg-state-enter {
  from { transform: scale(0.96); opacity: 0; }
  to   { transform: scale(1);    opacity: 1; }
}

@keyframes msg-state-pulse {
  0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent-color) 30%, transparent); }
  50%  { box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent-color) 15%, transparent); }
  100% { box-shadow: 0 0 0 0 transparent; }
}

/* AI 消息 - 等离子玻璃弹性入场 */
@keyframes msg-ai-in {
  0%   { opacity: 0; transform: scale(0.8) translateY(20px); filter: blur(4px); }
  50%  { opacity: 1; transform: scale(1.02) translateY(-2px); filter: blur(0); }
  70%  { transform: scale(0.98) translateY(1px); }
  100% { opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }
}

/* 用户消息 - 右侧滑入 + 发光边框 */
@keyframes msg-user-in {
  0%   { opacity: 0; transform: translateX(30px); }
  40%  { box-shadow: 0 0 20px rgba(236,72,153,0.4), 0 0 40px rgba(236,72,153,0.2); }
  100% { opacity: 1; transform: translateX(0); }
}

@keyframes msg-ai-in-reduced {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes msg-user-in-reduced {
  from { opacity: 0; transform: translateX(12px); }
  to { opacity: 1; transform: translateX(0); }
}

/* prefers-reduced-motion 降级 */
@media (prefers-reduced-motion: reduce) {
  .msg-ai, .msg-user, .msg-state {
    animation: none;
  }
  .badge-bounce, .pending-badge {
    animation: none;
  }
}

/* ---- 时间线切换按钮：默认隐藏（桌面端） ---- */
.timeline-toggle {
  display: none;
}

/* ---- 手机模式：时间线弹出面板 ---- */
@media (max-width: 767px) {
  .timeline-toggle {
    display: flex;
  }

  .timeline-mobile-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
    animation: fade-in 150ms ease;
  }

  .timeline-mobile-sheet {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60vh;
    height: 60dvh;
    background: var(--bg-secondary);
    border-radius: 16px 16px 0 0;
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    animation: timeline-sheet-up 200ms var(--ease-out);
    padding-bottom: env(safe-area-inset-bottom);
  }

  .timeline-mobile-handle {
    width: 36px;
    height: 4px;
    background: var(--border-color);
    border-radius: 2px;
    margin: 8px auto;
    flex-shrink: 0;
  }

  .timeline-mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    flex-shrink: 0;
  }

  .timeline-mobile-body {
    flex: 1;
    overflow-y: auto;
  }
}

@keyframes timeline-sheet-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .timeline-mobile-overlay,
  .timeline-mobile-sheet {
    animation: none;
  }
  .timeline-mobile-overlay {
    opacity: 1;
  }
}

/* ---- 删除操作栏 ---- */
.delete-action-bar {
  position: fixed;
  left: 50%;
  bottom: max(24px, calc(var(--keyboard-offset, 0px) + env(safe-area-inset-bottom)));
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  border-radius: 24px;
  background: var(--bg-card);
  border: 1px solid rgba(20, 184, 166, 0.35);
  z-index: 50;
  box-shadow: var(--shadow-lg), 0 0 24px rgba(20, 184, 166, 0.18);
}

/* 输入/选项淡入淡出过渡 */
.input-fade-enter-active,
.input-fade-leave-active {
  transition: opacity 350ms var(--ease-smooth), transform 350ms var(--ease-smooth);
}
.input-fade-enter-from,
.input-fade-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

.delete-bar-btn {
  padding: 8px 20px;
  border-radius: 16px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: transform 150ms, box-shadow 150ms, background-color 150ms, border-color 150ms, color 150ms;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-secondary);
}
.cancel-btn:hover { background: rgba(255, 255, 255, 0.15); }

.clear-btn {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-secondary);
}
.clear-btn:hover { background: rgba(255, 255, 255, 0.14); }

.confirm-btn {
  background: var(--accent-color);
  color: #fff;
}
.confirm-btn:hover:not(:disabled) { filter: brightness(1.1); }
.confirm-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.confirm-btn:active:not(:disabled) { transform: scale(0.96); }

.delete-bar-count {
  flex: 1;
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.delete-bar-fade-enter-active,
.delete-bar-fade-leave-active {
  transition: opacity 250ms var(--ease-smooth), transform 250ms var(--ease-smooth);
}
.delete-bar-fade-enter-from,
.delete-bar-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(16px);
}
</style>


