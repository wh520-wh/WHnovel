import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockSaveSettings = vi.fn()
const mockFetchSettings = vi.fn()
const mockGetModels = vi.fn()
const mockGetAppSettings = vi.fn()
const mockUpdateAppSettings = vi.fn()
const mockElMessageSuccess = vi.fn()
const mockElMessageError = vi.fn()
const mockElMessageBoxConfirm = vi.fn()

vi.mock('../stores/settings', () => ({
  useSettingsStore: () => ({
    settings: {
      primary_model_id: 1,
      backup_model_ids: [3],
      context_length: 12,
      reply_style: 'creative',
      options_prompt: 'old prompt',
      auto_generate_options: false,
      disable_chat_bubble_elastic: true,
      copy_image_format: 'binary',
      show_background_image: true,
    },
    fetchSettings: mockFetchSettings,
    saveSettings: mockSaveSettings,
  }),
}))

vi.mock('../api', () => ({
  getModels: mockGetModels,
  getAppSettings: mockGetAppSettings,
  updateAppSettings: mockUpdateAppSettings,
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mockElMessageSuccess,
    error: mockElMessageError,
  },
  ElMessageBox: {
    confirm: mockElMessageBoxConfirm,
  },
}))

describe('useSettingsForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()

    mockGetModels.mockResolvedValue({
      data: [
        { id: 1, name: 'Chat-A', model_id: 'chat-a', model_type: 'chat', enabled: true },
        { id: 2, name: 'Chat-B', model_id: 'chat-b', model_type: 'chat', enabled: true },
        { id: 3, name: 'Chat-C', model_id: 'chat-c', model_type: 'chat', enabled: true },
        { id: 4, name: 'Image-A', model_id: 'img-a', model_type: 'image', enabled: true },
        { id: 5, name: 'Disabled', model_id: 'chat-d', model_type: 'chat', enabled: false },
      ],
    })

    mockGetAppSettings.mockResolvedValue({
      data: {
        default_system_prompt: 'sys',
        state_broadcast_prompt: 'state',
        enable_image_generation: true,
        default_image_model_id: 4,
        image_size: '1K',
        image_watermark: false,
        default_image_style: 'style',
      },
    })

    mockElMessageBoxConfirm.mockResolvedValue(undefined)
  })

  it('exports canonical sections and titles', async () => {
    const mod = await import('./useSettingsForm')

    expect(mod.ALLOWED_SETTINGS_SECTIONS).toEqual([
      'model',
      'interaction',
      'image',
      'app',
      'plot',
      'appearance',
    ])
    expect(mod.SETTINGS_SECTION_TITLES.model).toBe('模型配置')
    expect(mod.SETTINGS_SECTION_TITLES.interaction).toBe('互动设置')
    expect(mod.SETTINGS_SECTION_TITLES.image).toBe('图片设置')
    expect(mod.SETTINGS_SECTION_TITLES.app).toBe('全局设置')
    expect(mod.SETTINGS_SECTION_TITLES.plot).toBe('剧情选项')
    expect(mod.SETTINGS_SECTION_TITLES.appearance).toBe('外观')
  })

  it('loads shared form state and computes candidates', async () => {
    const { useSettingsForm } = await import('./useSettingsForm')
    const s = useSettingsForm()

    await s.loadSettings()

    expect(mockGetModels).toHaveBeenCalledTimes(1)
    expect(mockFetchSettings).toHaveBeenCalledTimes(1)
    expect(mockGetAppSettings).toHaveBeenCalledTimes(1)
    expect(s.models.value).toHaveLength(5)
    expect(s.form.primary_model_id).toBe(1)
    expect(s.form.backup_model_ids).toEqual([3])
    expect(s.form.context_length).toBe(12)
    expect(s.form.reply_style).toBe('creative')
    expect(s.form.options_prompt).toBe('old prompt')
    expect(s.form.auto_generate_options).toBe(false)
    expect(s.form.copy_image_format).toBe('binary')
    expect(s.form.disable_chat_bubble_elastic).toBe(true)
    expect(s.form.default_system_prompt).toBe('sys')
    expect(s.form.state_broadcast_prompt).toBe('state')
    expect(s.form.default_image_model_id).toBe(4)
    expect(s.form.image_size).toBe('1K')
    expect(s.form.image_watermark).toBe(false)
    expect(s.form.default_image_style).toBe('style')
    expect(s.enabledModels.value.map((m) => m.id)).toEqual([1, 2, 3])
    expect(s.backupCandidates.value.map((m) => m.id)).toEqual([2])
    expect(s.imageModels.value.map((m) => m.id)).toEqual([4])
  })

  it('adds, removes and reorders backup models', async () => {
    const { useSettingsForm } = await import('./useSettingsForm')
    const s = useSettingsForm()
    await s.loadSettings()

    s.backupCandidateId.value = 2
    s.addBackup()
    expect(s.form.backup_model_ids).toEqual([3, 2])
    expect(s.backupCandidateId.value).toBeNull()

    s.moveBackupUp(1)
    expect(s.form.backup_model_ids).toEqual([2, 3])

    s.moveBackupDown(0)
    expect(s.form.backup_model_ids).toEqual([3, 2])

    s.removeBackup(0)
    expect(s.form.backup_model_ids).toEqual([2])
  })

  it('saves settings through both APIs', async () => {
    const { useSettingsForm } = await import('./useSettingsForm')
    const s = useSettingsForm()
    await s.loadSettings()

    await s.saveSettings()

    expect(mockSaveSettings).toHaveBeenCalledWith({
      primary_model_id: 1,
      backup_model_ids: [3],
      context_length: 12,
      reply_style: 'creative',
      options_prompt: 'old prompt',
      auto_generate_options: false,
      copy_image_format: 'binary',
      disable_chat_bubble_elastic: true,
      show_background_image: true,
    })
    expect(mockUpdateAppSettings).toHaveBeenCalledWith({
      default_system_prompt: 'sys',
      state_broadcast_prompt: 'state',
      default_image_model_id: 4,
      image_size: '1K',
      image_watermark: false,
      default_image_style: 'style',
    })
    expect(mockElMessageSuccess).toHaveBeenCalledWith('设置已保存')
  })

  it('resets to defaults after confirmation', async () => {
    const { useSettingsForm } = await import('./useSettingsForm')
    const s = useSettingsForm()
    await s.loadSettings()

    await s.resetSettings()

    expect(mockElMessageBoxConfirm).toHaveBeenCalledTimes(1)
    expect(mockSaveSettings).toHaveBeenCalledWith({
      primary_model_id: null,
      backup_model_ids: [],
      context_length: 10,
      reply_style: 'detailed',
      options_prompt: '',
      auto_generate_options: true,
      copy_image_format: 'url',
      disable_chat_bubble_elastic: false,
      show_background_image: true,
    })
    expect(mockUpdateAppSettings).toHaveBeenCalledWith({
      default_system_prompt: '',
      state_broadcast_prompt: '',
      default_image_model_id: null,
      image_size: '2K',
      image_watermark: false,
      default_image_style: '',
    })
    expect(s.form.primary_model_id).toBeNull()
    expect(s.form.backup_model_ids).toEqual([])
    expect(s.form.context_length).toBe(10)
    expect(s.form.reply_style).toBe('detailed')
    expect(s.form.options_prompt).toBe('')
    expect(s.form.auto_generate_options).toBe(true)
    expect(s.form.copy_image_format).toBe('url')
    expect(s.form.disable_chat_bubble_elastic).toBe(false)
    expect(s.form.default_system_prompt).toBe('')
    expect(s.form.state_broadcast_prompt).toBe('')
    expect(s.form.default_image_model_id).toBeNull()
    expect(s.form.image_size).toBe('2K')
    expect(s.form.image_watermark).toBe(false)
    expect(s.form.default_image_style).toBe('')
    expect(mockElMessageSuccess).toHaveBeenCalledWith('已恢复默认设置')
  })
})
