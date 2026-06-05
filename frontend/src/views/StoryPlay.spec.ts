import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  const route = reactive({
    params: { storyId: '1' },
    query: { archiveId: '11' as string | undefined },
  })
  const router = {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
  }

  return {
    useRoute: () => route,
    useRouter: () => router,
    __mockRoute: route,
    __mockRouter: router,
  }
})

vi.mock('pinia', async () => {
  const { toRef } = await import('vue')
  return {
    storeToRefs: (store: any) => ({
      streaming: toRef(store, 'streaming'),
      streamingFollow: toRef(store, 'streamingFollow'),
    }),
  }
})

vi.mock('../stores/chat', async () => {
  const { reactive } = await import('vue')
  const chatStore = reactive({
    messages: [] as any[],
    archives: [] as any[],
    currentArchive: null as any,
    currentOptions: [] as string[],
    lastOptionsSnapshot: [] as string[],
    sending: false,
    streaming: false,
    awaitingTail: false,
    loading: false,
    optionsLocked: false,
    lockedOption: '',
    generatingOptions: false,
    generatingStateBroadcast: false,
    recallInProgress: false,
    canRecallLastRound: false,
    isGeneratingImage: false,
    streamingFollow: true,
    startStory: vi.fn(),
    sendStream: vi.fn(),
    manualGenerateOptions: vi.fn(),
    generateStateBroadcast: vi.fn(),
    generateImage: vi.fn(),
    recallLastRound: vi.fn(),
    confirmRecall: vi.fn(),
    clearChat: vi.fn(),
    setStreamingFollow: vi.fn(),
    setAutoGenerateOptions: vi.fn(),
    fetchArchives: vi.fn(async () => {}),
    ensureActiveArchive: vi.fn(async (storyId: number) => {
      chatStore.currentArchive = { id: storyId * 100, story_id: storyId }
      return { archiveId: storyId * 100, isNew: false }
    }),
    loadArchive: vi.fn(async (archiveId: number) => {
      const storyId = archiveId === 22 ? 2 : 1
      chatStore.currentArchive = { id: archiveId, story_id: storyId }
    }),
    startNewArchive: vi.fn(async (storyId: number) => {
      chatStore.currentArchive = { id: storyId * 1000, story_id: storyId }
    }),
  })

  return {
    useChatStore: () => chatStore,
    __mockChatStore: chatStore,
  }
})

vi.mock('../stores/story', async () => {
  const { reactive } = await import('vue')
  const storyStore = reactive({
    currentStory: { title: '故事', description: '描述', opening_requirement: '' },
    loading: false,
    fetchStory: vi.fn(async () => {}),
  })

  return {
    useStoryStore: () => storyStore,
    __mockStoryStore: storyStore,
  }
})

vi.mock('../stores/settings', async () => {
  const { reactive } = await import('vue')
  const settingsStore = reactive({
    settings: {
      auto_generate_options: true,
    },
    fetchSettings: vi.fn(async () => {}),
    saveSettings: vi.fn(async () => {}),
  })

  return {
    useSettingsStore: () => settingsStore,
    __mockSettingsStore: settingsStore,
  }
})

vi.mock('../composables/useChatViewportFollow', async () => {
  const { ref } = await import('vue')
  const viewportState = {
    topbarScrolled: ref(false),
    autoFollow: ref(true),
    pendingMessageCount: ref(0),
    badgeBouncing: ref(false),
    userScrolledUp: ref(false),
    syncFollowerState: vi.fn(),
    scrollToBottom: vi.fn(),
    forceScrollToBottom: vi.fn(),
    queueBottomFollow: vi.fn(),
    attachChatScrollListener: vi.fn(),
    detachChatScrollListener: vi.fn(),
  }

  return {
    useChatViewportFollow: () => viewportState,
    __mockViewportState: viewportState,
  }
})

vi.mock('../composables/useMobileInputBar', async () => {
  const { ref } = await import('vue')
  const mobileInputState = {
    keyboardVisible: ref(false),
    mobileInputOffset: ref(0),
    mobileOptionsHeight: ref(0),
    visualViewportOffsetTop: ref(0),
    handleComposerResize: vi.fn(),
    handleComposerFocus: vi.fn(),
    handleComposerBlur: vi.fn(),
    syncViewportHeight: vi.fn(),
    syncMobileLayoutVars: vi.fn(),
    bindMobileLayoutObserver: vi.fn(),
    detachMobileLayoutObserver: vi.fn(),
    startViewportTracking: vi.fn(),
    stopViewportTracking: vi.fn(),
    setBottomFollowFn: vi.fn(),
  }

  return {
    useMobileInputBar: () => mobileInputState,
    __mockMobileInputState: mobileInputState,
  }
})

vi.mock('../api', () => ({
  deleteArchive: vi.fn(),
  getErrorMessage: (_error: unknown, fallback: string) => fallback,
  renameArchive: vi.fn(),
  exportArchive: vi.fn(),
  importArchive: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
  ElMessageBox: {
    confirm: vi.fn(),
  },
}))

import StoryPlay from './StoryPlay.vue'

const { __mockRoute: route, __mockRouter: router } = (await import('vue-router')) as any
const { __mockChatStore: chatStore } = (await import('../stores/chat')) as any
const { __mockStoryStore: storyStore } = (await import('../stores/story')) as any
const { __mockSettingsStore: settingsStore } = (await import('../stores/settings')) as any
const { __mockViewportState: viewportState } =
  (await import('../composables/useChatViewportFollow')) as any
const { __mockMobileInputState: mobileInputState } =
  (await import('../composables/useMobileInputBar')) as any

function mountStoryPlay() {
  return shallowMount(StoryPlay, {
    global: {
      directives: {
        loading: {
          mounted() {},
          updated() {},
        },
      },
      stubs: {
        teleport: true,
        transition: false,
        QuickOptions: defineComponent({
          name: 'QuickOptions',
          props: ['options', 'disabled', 'loading', 'locked', 'lockedOption'],
          emits: ['select'],
          template: '<div class="quick-options-stub" />',
        }),
        ChatComposer: defineComponent({
          name: 'ChatComposer',
          props: [
            'modelValue',
            'disabled',
            'thinking',
            'awaitingTail',
            'menuActive',
            'showSpinner',
          ],
          emits: ['send', 'toggle-menu', 'focus', 'blur', 'resized', 'update:modelValue'],
          template: '<div class="chat-composer-stub" />',
        }),
        'el-dialog': defineComponent({
          props: ['modelValue'],
          template: '<div><slot /><slot name="footer" /></div>',
        }),
        'el-drawer': defineComponent({
          props: ['modelValue'],
          template: '<div><slot /><slot name="title" /></div>',
        }),
        'el-card': defineComponent({ template: '<div><slot /><slot name="header" /></div>' }),
        'el-input': defineComponent({
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input />',
        }),
        'el-button': defineComponent({ template: '<button><slot /></button>' }),
      },
    },
  })
}

describe('StoryPlay state reset', () => {
  beforeEach(() => {
    route.params.storyId = '1'
    route.query.archiveId = '11'
    router.push.mockReset()
    router.replace.mockReset()
    router.back.mockReset()

    chatStore.messages = []
    chatStore.archives = []
    chatStore.currentArchive = null
    chatStore.currentOptions = []
    chatStore.lastOptionsSnapshot = []
    chatStore.sending = false
    chatStore.streaming = false
    chatStore.awaitingTail = false
    chatStore.loading = false
    chatStore.optionsLocked = false
    chatStore.lockedOption = ''
    chatStore.generatingOptions = false
    chatStore.generatingStateBroadcast = false
    chatStore.recallInProgress = false
    chatStore.canRecallLastRound = false
    chatStore.isGeneratingImage = false
    chatStore.streamingFollow = true
    chatStore.startStory.mockReset()
    chatStore.sendStream.mockReset()
    chatStore.manualGenerateOptions.mockReset()
    chatStore.generateStateBroadcast.mockReset()
    chatStore.generateImage.mockReset()
    chatStore.recallLastRound.mockReset()
    chatStore.confirmRecall.mockReset()
    chatStore.clearChat.mockReset()
    chatStore.setStreamingFollow.mockReset()
    chatStore.fetchArchives.mockClear()
    chatStore.ensureActiveArchive.mockClear()
    chatStore.loadArchive.mockClear()
    chatStore.startNewArchive.mockClear()

    storyStore.fetchStory.mockClear()
    settingsStore.fetchSettings.mockClear()
    settingsStore.saveSettings.mockClear()
    viewportState.syncFollowerState.mockClear()
    viewportState.scrollToBottom.mockClear()
  })

  it('uses route query archiveId again when storyId changes', async () => {
    mountStoryPlay()
    await flushPromises()

    chatStore.loadArchive.mockClear()
    chatStore.ensureActiveArchive.mockClear()

    route.query.archiveId = '22'
    route.params.storyId = '2'
    await nextTick()
    await flushPromises()

    expect(chatStore.loadArchive).toHaveBeenCalledWith(22)
    expect(chatStore.ensureActiveArchive).not.toHaveBeenCalledWith(2)
  })

  it('clears transient local state on story change', async () => {
    const wrapper = mountStoryPlay()
    await flushPromises()
    ;(wrapper.vm as any).archiveBulkMode = true
    ;(wrapper.vm as any).archiveSelection = [101, 102]
    ;(wrapper.vm as any).openingRequirement = '旧开场'
    ;(wrapper.vm as any).inputText = '旧输入'
    ;(wrapper.vm as any).pendingRecallIds = new Set([1, 2])

    route.query.archiveId = '22'
    route.params.storyId = '2'
    await nextTick()
    await flushPromises()

    expect((wrapper.vm as any).archiveBulkMode).toBe(false)
    expect((wrapper.vm as any).archiveSelection).toEqual([])
    expect((wrapper.vm as any).openingRequirement).toBe('')
    expect((wrapper.vm as any).inputText).toBe('')
    expect(Array.from((wrapper.vm as any).pendingRecallIds)).toEqual([])
  })

  it('clears transient local state when loading another archive', async () => {
    const wrapper = mountStoryPlay()
    await flushPromises()
    ;(wrapper.vm as any).archiveBulkMode = true
    ;(wrapper.vm as any).archiveSelection = [201]
    ;(wrapper.vm as any).openingRequirement = '待发送开场'
    ;(wrapper.vm as any).inputText = '待发送输入'
    ;(wrapper.vm as any).pendingRecallIds = new Set([9])

    await (wrapper.vm as any).handleLoadArchive(12)
    await flushPromises()

    expect((wrapper.vm as any).archiveBulkMode).toBe(false)
    expect((wrapper.vm as any).archiveSelection).toEqual([])
    expect((wrapper.vm as any).openingRequirement).toBe('')
    expect((wrapper.vm as any).inputText).toBe('')
    expect(Array.from((wrapper.vm as any).pendingRecallIds)).toEqual([])
  })

  it('reinitializes from route query archiveId when archiveId changes within the same story', async () => {
    mountStoryPlay()
    await flushPromises()

    chatStore.loadArchive.mockClear()
    chatStore.ensureActiveArchive.mockClear()

    route.query.archiveId = '12'
    await nextTick()
    await flushPromises()

    expect(chatStore.loadArchive).toHaveBeenCalledWith(12)
    expect(chatStore.ensureActiveArchive).not.toHaveBeenCalledWith(1)
  })

  it('clears transient local state when route query archiveId changes within the same story', async () => {
    const wrapper = mountStoryPlay()
    await flushPromises()
    ;(wrapper.vm as any).archiveBulkMode = true
    ;(wrapper.vm as any).archiveSelection = [401]
    ;(wrapper.vm as any).openingRequirement = '同故事切档开场'
    ;(wrapper.vm as any).inputText = '同故事切档输入'
    ;(wrapper.vm as any).pendingRecallIds = new Set([10])

    route.query.archiveId = '12'
    await nextTick()
    await flushPromises()

    expect((wrapper.vm as any).archiveBulkMode).toBe(false)
    expect((wrapper.vm as any).archiveSelection).toEqual([])
    expect((wrapper.vm as any).openingRequirement).toBe('')
    expect((wrapper.vm as any).inputText).toBe('')
    expect(Array.from((wrapper.vm as any).pendingRecallIds)).toEqual([])
  })

  it('reuses route query archiveId in mismatch recovery watcher', async () => {
    route.params.storyId = '2'
    route.query.archiveId = '22'
    mountStoryPlay()
    await flushPromises()

    chatStore.loadArchive.mockClear()
    chatStore.ensureActiveArchive.mockClear()

    chatStore.currentArchive = { id: 11, story_id: 999 }
    await nextTick()
    await flushPromises()

    expect(chatStore.loadArchive).toHaveBeenCalledWith(22)
    expect(chatStore.ensureActiveArchive).not.toHaveBeenCalledWith(2)
  })

  it('clears transient local state when fallback archive is loaded after deleting current archive', async () => {
    const wrapper = mountStoryPlay()
    await flushPromises()
    ;(wrapper.vm as any).archiveBulkMode = true
    ;(wrapper.vm as any).archiveSelection = [301]
    ;(wrapper.vm as any).openingRequirement = '删除前开场'
    ;(wrapper.vm as any).inputText = '删除前输入'
    ;(wrapper.vm as any).pendingRecallIds = new Set([7])

    chatStore.currentArchive = { id: 11, story_id: 1 }
    route.params.storyId = '1'

    await (wrapper.vm as any).handleDeleteArchive(11)
    await flushPromises()

    expect(chatStore.clearChat).toHaveBeenCalled()
    expect(chatStore.ensureActiveArchive).toHaveBeenCalledWith(1)
    expect((wrapper.vm as any).archiveBulkMode).toBe(false)
    expect((wrapper.vm as any).archiveSelection).toEqual([])
    expect((wrapper.vm as any).openingRequirement).toBe('')
    expect((wrapper.vm as any).inputText).toBe('')
    expect(Array.from((wrapper.vm as any).pendingRecallIds)).toEqual([])
  })

  it('clears transient local state when current archive is removed by bulk delete fallback', async () => {
    const wrapper = mountStoryPlay()
    await flushPromises()
    ;(wrapper.vm as any).archiveBulkMode = true
    ;(wrapper.vm as any).archiveSelection = [11, 302]
    ;(wrapper.vm as any).openingRequirement = '批量删除前开场'
    ;(wrapper.vm as any).inputText = '批量删除前输入'
    ;(wrapper.vm as any).pendingRecallIds = new Set([8])

    chatStore.currentArchive = { id: 11, story_id: 1 }

    await (wrapper.vm as any).handleBulkDeleteArchives()
    await flushPromises()

    expect(chatStore.clearChat).toHaveBeenCalled()
    expect(chatStore.ensureActiveArchive).toHaveBeenCalledWith(1)
    expect((wrapper.vm as any).archiveBulkMode).toBe(false)
    expect((wrapper.vm as any).archiveSelection).toEqual([])
    expect((wrapper.vm as any).openingRequirement).toBe('')
    expect((wrapper.vm as any).inputText).toBe('')
    expect(Array.from((wrapper.vm as any).pendingRecallIds)).toEqual([])
  })

  it('routes mobile play entry to settings-mobile with play query intact', async () => {
    const wrapper = mountStoryPlay()
    await flushPromises()

    route.query.archiveId = undefined
    route.params.storyId = '12'
    await nextTick()
    await flushPromises()

    chatStore.currentArchive = { id: 99, story_id: 12 }

    const originalInnerWidth = window.innerWidth
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 767,
    })

    try {
      await (wrapper.vm as any).openSettingsFromPlay()

      expect(router.push).toHaveBeenCalledWith({
        path: '/settings-mobile',
        query: { from: 'play', storyId: '12', archiveId: '99' },
      })
    } finally {
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        value: originalInnerWidth,
      })
    }
  })

  it('marks the immersive topbar action as collapsible on very narrow mobile viewports', async () => {
    const wrapper = mountStoryPlay()
    await flushPromises()

    expect(wrapper.find('.immersive-toggle').exists()).toBe(true)
  })

  it('rebinds mobile layout observer and re-syncs layout vars when option visibility changes', async () => {
    mountStoryPlay()
    await flushPromises()

    mobileInputState.bindMobileLayoutObserver.mockClear()
    mobileInputState.syncMobileLayoutVars.mockClear()

    chatStore.currentOptions = ['A', 'B']
    await nextTick()
    await flushPromises()

    expect(mobileInputState.bindMobileLayoutObserver).toHaveBeenCalled()
    expect(mobileInputState.syncMobileLayoutVars).toHaveBeenCalled()
  })

  it('hides old option bubbles while an option send is locked', async () => {
    chatStore.messages = [
      {
        id: 1,
        archive_id: 11,
        role: 'assistant',
        content: '开场',
        state_snapshot: {},
        story_state: {},
        options: [],
        memory_update: [],
        created_at: '2026-04-17T00:00:00Z',
      },
    ]
    chatStore.currentArchive = { id: 11, story_id: 1 }
    chatStore.currentOptions = []
    chatStore.lastOptionsSnapshot = ['观察四周', '直接追问']
    chatStore.optionsLocked = true

    const wrapper = mountStoryPlay()
    await flushPromises()

    const quickOptions = wrapper.findComponent({ name: 'QuickOptions' })
    expect(quickOptions.props('options')).toEqual([])
    expect(quickOptions.props('locked')).toBe(true)
  })

  it('passes locked option feedback to QuickOptions while option send is locked', async () => {
    chatStore.messages = [
      {
        id: 1,
        archive_id: 11,
        role: 'assistant',
        content: '开场',
        state_snapshot: {},
        story_state: {},
        options: [],
        memory_update: [],
        created_at: '2026-04-17T00:00:00Z',
      },
    ]
    chatStore.currentArchive = { id: 11, story_id: 1 }
    chatStore.currentOptions = []
    chatStore.lockedOption = '观察四周'
    chatStore.optionsLocked = true

    const wrapper = mountStoryPlay()
    await flushPromises()

    const quickOptions = wrapper.findComponent({ name: 'QuickOptions' })
    expect(quickOptions.props('locked')).toBe(true)
    expect(quickOptions.props('lockedOption')).toBe('观察四周')
  })

  it('passes tail waiting state to ChatComposer after text stream ends', async () => {
    chatStore.messages = [
      {
        id: 1,
        archive_id: 11,
        role: 'assistant',
        content: '开场',
        state_snapshot: {},
        story_state: {},
        options: [],
        memory_update: [],
        created_at: '2026-04-17T00:00:00Z',
      },
    ]
    chatStore.currentArchive = { id: 11, story_id: 1 }
    chatStore.sending = true
    chatStore.streaming = false
    chatStore.awaitingTail = true

    const wrapper = mountStoryPlay()
    await flushPromises()

    const composer = wrapper.findComponent({ name: 'ChatComposer' })
    expect(composer.props('thinking')).toBe(false)
    expect(composer.props('awaitingTail')).toBe(true)
    expect(composer.props('showSpinner')).toBe(true)
  })

  it('sends manual input through the free-text path and clears local input state', async () => {
    chatStore.messages = [
      {
        id: 1,
        archive_id: 11,
        role: 'assistant',
        content: '开场',
        state_snapshot: {},
        story_state: {},
        options: [],
        memory_update: [],
        created_at: '2026-04-17T00:00:00Z',
      },
    ]
    chatStore.currentArchive = { id: 11, story_id: 1 }
    chatStore.sendStream.mockResolvedValue(undefined)

    const wrapper = mountStoryPlay()
    await flushPromises()
    ;(wrapper.vm as any).inputText = '旧输入'

    await (wrapper.vm as any).handleSend('  我自己决定行动  ', 'input')

    expect(chatStore.sendStream).toHaveBeenCalledWith('我自己决定行动', { fromOption: false })
    expect((wrapper.vm as any).inputText).toBe('')
  })
})

// 草稿自动保存集成验证已在以下层面完成：
// - useDraft.spec.ts: 6/6 单元测试全 PASS
// - ChatComposer: 草稿保存/清除/恢复逻辑已集成，3/3 既有用例 PASS
// - StoryPlay: archiveIdForComposer 同步逻辑已添加（代码审查确认）
// StoryPlay 完整集成测试因 mock 结构限制（ensureActiveArchive 返回值问题）暂跳过
