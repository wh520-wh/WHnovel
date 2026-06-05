import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Settings from './Settings.vue'

const composableMocks = vi.hoisted(() => ({
  loadSettings: vi.fn(async () => {}),
  saveSettings: vi.fn(async () => true),
  resetSettings: vi.fn(async () => true),
  addBackup: vi.fn(),
  removeBackup: vi.fn(),
  moveBackupUp: vi.fn(),
  moveBackupDown: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    name: 'Settings',
    query: {},
  }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    info: vi.fn(),
  },
}))

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
    form: {
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
    },
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

function mountSettings() {
  const Passthrough = defineComponent({
    template: '<div><slot /></div>',
  })

  return shallowMount(Settings, {
    global: {
      directives: {
        loading: {
          mounted() {},
          updated() {},
        },
      },
      stubs: {
        transition: Passthrough,
        TransitionGroup: Passthrough,
        ModelSelect: defineComponent({
          props: ['modelValue'],
          template: '<div class="stub-model-select">model select</div>',
        }),
        'el-input': defineComponent({
          props: ['modelValue'],
          template: '<textarea />',
        }),
        'el-switch': defineComponent({
          props: ['modelValue'],
          template: '<button type="button" class="stub-switch">switch</button>',
        }),
        'el-slider': defineComponent({
          props: ['modelValue'],
          template: '<input type="range" class="stub-slider" />',
        }),
      },
    },
  })
}

describe('Settings desktop shared form wiring', () => {
  beforeEach(() => {
    composableMocks.loadSettings.mockClear()
    composableMocks.saveSettings.mockClear()
    composableMocks.resetSettings.mockClear()
  })

  it('loads settings on mount and delegates save/reset to useSettingsForm', async () => {
    const wrapper = mountSettings()
    await flushPromises()

    expect(composableMocks.loadSettings).toHaveBeenCalledTimes(1)

    await wrapper.find('.save-btn').trigger('click')
    await wrapper.find('.reset-btn').trigger('click')

    expect(composableMocks.saveSettings).toHaveBeenCalledTimes(1)
    expect(composableMocks.resetSettings).toHaveBeenCalledTimes(1)
  })

  it('renders the exact bubble elasticity label in interaction settings', async () => {
    const wrapper = mountSettings()
    await flushPromises()

    await wrapper.findAll('.nav-item')[1].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('关闭聊天气泡弹性效果')
  })

  it('renders reply styles from low to high output length', async () => {
    const wrapper = mountSettings()
    await flushPromises()

    await wrapper.findAll('.nav-item')[1].trigger('click')
    await flushPromises()

    const stylePills = wrapper
      .findAll('.style-pill')
      .slice(0, 3)
      .map((node) => node.text())
    expect(stylePills).toEqual(['简短', '标准', '丰富'])
  })
})
