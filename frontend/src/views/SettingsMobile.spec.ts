import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import router from '../router'
import { ALLOWED_SETTINGS_SECTIONS } from '../composables/useSettingsForm'
import SettingsMobile from './SettingsMobile.vue'

const composableMocks = vi.hoisted(() => {
  const createFormState = () => ({
    primary_model_id: 1,
    backup_model_ids: [2],
    context_length: 10,
    reply_style: 'detailed',
    options_prompt: 'opts',
    auto_generate_options: true,
    copy_image_format: 'url',
    disable_chat_bubble_elastic: false,
    default_system_prompt: 'sys',
    state_broadcast_prompt: 'state',
    default_image_model_id: 101,
    image_size: '2K',
    image_watermark: false,
    default_image_style: 'comic',
  })

  const formState = createFormState()

  return {
    loadSettings: vi.fn(async () => {}),
    saveSettings: vi.fn(async () => true),
    resetSettings: vi.fn(async () => true),
    addBackup: vi.fn(),
    removeBackup: vi.fn(),
    moveBackupUp: vi.fn(),
    moveBackupDown: vi.fn(),
    formState,
    resetFormState: () => Object.assign(formState, createFormState()),
  }
})

vi.mock('../stores/theme', () => ({
  useThemeStore: () => ({
    theme: ref<'dark' | 'light' | 'enigma' | 'claude'>('dark'),
    setTheme: vi.fn(),
  }),
}))

vi.mock('../composables/useSettingsForm', () => ({
  ALLOWED_SETTINGS_SECTIONS: ['model', 'interaction', 'image', 'app', 'plot', 'appearance'],
  SETTINGS_SECTION_TITLES: {
    model: '模型配置',
    interaction: '互动设置',
    image: '图片设置',
    app: '全局设置',
    plot: '剧情选项',
    appearance: '外观',
  },
  useSettingsForm: () => ({
    form: reactive(composableMocks.formState),
    models: ref([
      { id: 1, name: '主模型', model_id: 'main', model_type: 'chat', enabled: true },
      { id: 2, name: '备份模型', model_id: 'backup', model_type: 'chat', enabled: true },
      { id: 101, name: '图片模型', model_id: 'img-main', model_type: 'image', enabled: true },
    ]),
    loading: ref(false),
    saving: ref(false),
    backupCandidateId: ref(null),
    adminModeEnabled: ref(false),
    enabledModels: ref([
      { id: 1, name: '主模型', model_id: 'main', model_type: 'chat', enabled: true },
      { id: 2, name: '备份模型', model_id: 'backup', model_type: 'chat', enabled: true },
    ]),
    backupCandidates: ref([]),
    imageModels: ref([
      { id: 101, name: '图片模型', model_id: 'img-main', model_type: 'image', enabled: true },
    ]),
    loadSettings: composableMocks.loadSettings,
    saveSettings: composableMocks.saveSettings,
    resetSettings: composableMocks.resetSettings,
    addBackup: composableMocks.addBackup,
    removeBackup: composableMocks.removeBackup,
    moveBackupUp: composableMocks.moveBackupUp,
    moveBackupDown: composableMocks.moveBackupDown,
  }),
}))

function createMobileRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/play/:storyId', component: { template: '<div />' } },
      { path: '/settings-mobile/:section?', component: SettingsMobile },
    ],
  })
}

beforeEach(() => {
  composableMocks.loadSettings.mockClear()
  composableMocks.saveSettings.mockClear()
  composableMocks.resetSettings.mockClear()
  composableMocks.addBackup.mockClear()
  composableMocks.removeBackup.mockClear()
  composableMocks.moveBackupUp.mockClear()
  composableMocks.moveBackupDown.mockClear()
  composableMocks.resetFormState()
})

describe('settings mobile routes', () => {
  it('registers mobile settings routes and redirects invalid section to home with query preserved', async () => {
    const homeRoute = router.getRoutes().find((r) => r.name === 'SettingsMobileHome')
    const sectionRoute = router.getRoutes().find((r) => r.name === 'SettingsMobileSection')

    expect(homeRoute?.path).toBe('/settings-mobile')
    expect(sectionRoute?.path).toBe('/settings-mobile/:section')
    expect(sectionRoute?.beforeEnter).toBeTruthy()

    const guard = sectionRoute?.beforeEnter as any
    const invalidTo = {
      params: { section: 'invalid-section' },
      query: { from: 'play', storyId: '12', archiveId: '99' },
    }
    const validTo = {
      params: { section: ALLOWED_SETTINGS_SECTIONS[0] },
      query: { from: 'play' },
    }

    const invalidResult = await guard(invalidTo, {})
    expect(invalidResult).toEqual({ path: '/settings-mobile', query: invalidTo.query })

    const validResult = await guard(validTo, {})
    expect(validResult).toBe(true)
  })
})

describe('SettingsMobile home', () => {
  it('shows section cards on /settings-mobile and loads settings on mount', async () => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push('/settings-mobile')
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
      },
    })

    await flushPromises()

    const cards = wrapper.findAll('.settings-mobile-card')
    expect(cards).toHaveLength(ALLOWED_SETTINGS_SECTIONS.length)
    expect(wrapper.text()).toContain('模型配置')
    expect(wrapper.text()).toContain('互动设置')
    expect(wrapper.text()).toContain('图片设置')
    expect(wrapper.text()).toContain('全局设置')
    expect(wrapper.text()).toContain('剧情选项')
    expect(wrapper.text()).toContain('外观')
    expect(composableMocks.loadSettings).toHaveBeenCalledTimes(1)
  })

  it('opens a section route and preserves query context', async () => {
    const mobileRouter = createMobileRouter()
    const query = { from: 'play', storyId: '12', archiveId: '99' }

    await mobileRouter.push({ path: '/settings-mobile', query })
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
      },
    })

    await flushPromises()
    await wrapper.findAll('.settings-mobile-card')[0].trigger('click')
    await flushPromises()

    expect(mobileRouter.currentRoute.value.path).toBe('/settings-mobile/model')
    expect(mobileRouter.currentRoute.value.query).toEqual(query)
  })

  it('returns to play context from mobile settings home when query is present', async () => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push({
      path: '/settings-mobile',
      query: { from: 'play', storyId: '12', archiveId: '99' },
    })
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
      },
    })

    await flushPromises()
    await wrapper.find('.header-back').trigger('click')
    await flushPromises()

    expect(mobileRouter.currentRoute.value.path).toBe('/play/12')
    expect(mobileRouter.currentRoute.value.query.archiveId).toBe('99')
  })

  it('returns to play context without archiveId when archive query is absent', async () => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push({
      path: '/settings-mobile',
      query: { from: 'play', storyId: '12' },
    })
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
      },
    })

    await flushPromises()
    await wrapper.find('.header-back').trigger('click')
    await flushPromises()

    expect(mobileRouter.currentRoute.value.path).toBe('/play/12')
    expect(mobileRouter.currentRoute.value.query.archiveId).toBeUndefined()
  })

  it('falls back to home when play query has invalid storyId', async () => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push({
      path: '/settings-mobile',
      query: { from: 'play', storyId: 'invalid', archiveId: '99' },
    })
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
      },
    })

    await flushPromises()
    await wrapper.find('.header-back').trigger('click')
    await flushPromises()

    expect(mobileRouter.currentRoute.value.path).toBe('/')
  })
})

describe('SettingsMobile section shell', () => {
  it('applies shared mobile surface hooks across cards, fields, and footer', async () => {
    const homeRouter = createMobileRouter()

    await homeRouter.push('/settings-mobile')
    await homeRouter.isReady()

    const homeWrapper = mount(SettingsMobile, {
      global: {
        plugins: [homeRouter],
      },
    })

    await flushPromises()

    expect(homeWrapper.findAll('.settings-mobile-card.mobile-surface')).toHaveLength(
      ALLOWED_SETTINGS_SECTIONS.length,
    )
    expect(homeWrapper.find('.header-back').classes()).toContain('mobile-action-btn')
    expect(homeWrapper.findAll('.settings-mobile-card')[0].classes()).toContain(
      'mobile-control-card',
    )

    const detailRouter = createMobileRouter()

    await detailRouter.push('/settings-mobile/image')
    await detailRouter.isReady()

    const detailWrapper = mount(SettingsMobile, {
      global: {
        plugins: [detailRouter],
        stubs: {
          ModelSelect: {
            template: '<div class="stub-model-select">model select</div>',
          },
          'el-input': {
            props: ['modelValue'],
            template: '<textarea />',
          },
        },
      },
    })

    await flushPromises()

    expect(detailWrapper.find('.settings-mobile-footer.mobile-surface').exists()).toBe(true)
    expect(detailWrapper.findAll('.field-block.mobile-surface').length).toBeGreaterThan(0)
  })

  it('shows section-specific fields and save button on detail route', async () => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push('/settings-mobile/image')
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
        stubs: {
          ModelSelect: {
            template: '<div class="stub-model-select">model select</div>',
          },
          'el-input': {
            props: ['modelValue'],
            template: '<textarea />',
          },
          'el-switch': {
            props: ['modelValue'],
            template: '<button type="button" class="stub-switch">switch</button>',
          },
          'el-slider': {
            props: ['modelValue'],
            template: '<input type="range" class="stub-slider" />',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('使用模型')
    expect(wrapper.text()).toContain('图片尺寸')
    expect(wrapper.text()).toContain('添加水印')
    expect(wrapper.text()).toContain('全局风格')
    expect(wrapper.text()).toContain('保存设置')
    expect(wrapper.find('.settings-mobile-footer').exists()).toBe(true)
    expect(wrapper.find('.stub-model-select').exists()).toBe(true)

    await wrapper.find('.save-btn').trigger('click')
    expect(composableMocks.saveSettings).toHaveBeenCalledTimes(1)
  })

  it('returns from detail route to mobile settings home with query preserved', async () => {
    const mobileRouter = createMobileRouter()
    const query = { from: 'play', storyId: '12', archiveId: '99' }

    await mobileRouter.push({ path: '/settings-mobile/app', query })
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
      },
    })

    await flushPromises()
    await wrapper.find('.header-back').trigger('click')
    await flushPromises()

    expect(mobileRouter.currentRoute.value.path).toBe('/settings-mobile')
    expect(mobileRouter.currentRoute.value.query).toEqual(query)
  })

  it('renders reply styles from low to high output length on mobile', async () => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push('/settings-mobile/interaction')
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
        stubs: {
          ModelSelect: {
            template: '<div class="stub-model-select">model select</div>',
          },
          'el-input': {
            props: ['modelValue'],
            template: '<textarea />',
          },
          'el-switch': {
            props: ['modelValue'],
            template: '<button type="button" class="stub-switch">switch</button>',
          },
          'el-slider': {
            props: ['modelValue'],
            template: '<input type="range" class="stub-slider" />',
          },
        },
      },
    })

    await flushPromises()

    const buttons = wrapper
      .findAll('.choice-row')
      .at(0)
      ?.findAll('button')
      .map((node) => node.text())
    expect(buttons).toEqual(['简洁 (~173字)', '详细 (~280字)', '创意 (~360字)'])
  })

  it.each([
    ['/settings-mobile/model', '主用模型'],
    ['/settings-mobile/interaction', '上下文长度'],
    ['/settings-mobile/image', '图片尺寸'],
    ['/settings-mobile/plot', '选项提示词'],
    ['/settings-mobile/appearance', '主题'],
  ])('renders section shell for %s', async (path, expectedLabel) => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push(path)
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
        stubs: {
          ModelSelect: {
            template: '<div class="stub-model-select">model select</div>',
          },
          'el-input': {
            props: ['modelValue'],
            template: '<textarea />',
          },
          'el-switch': {
            props: ['modelValue'],
            template: '<button type="button" class="stub-switch">switch</button>',
          },
          'el-slider': {
            props: ['modelValue'],
            template: '<input type="range" class="stub-slider" />',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain(expectedLabel)
    expect(wrapper.find('.settings-mobile-footer').exists()).toBe(true)
  })

  it('adds a dedicated detail scroll container on section routes', async () => {
    const mobileRouter = createMobileRouter()

    await mobileRouter.push('/settings-mobile/app')
    await mobileRouter.isReady()

    const wrapper = mount(SettingsMobile, {
      global: {
        plugins: [mobileRouter],
        stubs: {
          ModelSelect: {
            template: '<div class="stub-model-select">model select</div>',
          },
          'el-input': {
            props: ['modelValue', 'disabled'],
            template: '<textarea :disabled="disabled" />',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('.settings-mobile-scroll').exists()).toBe(true)
  })
})
