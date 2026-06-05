import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAppSettings, getModels, updateAppSettings } from '../api'
import { MODEL_TYPE_CHAT, MODEL_TYPE_IMAGE } from '../constants/modelTypes'
import { useSettingsStore } from '../stores/settings'

export const ALLOWED_SETTINGS_SECTIONS = [
  'model',
  'interaction',
  'image',
  'app',
  'plot',
  'appearance',
] as const
export type SettingsSection = (typeof ALLOWED_SETTINGS_SECTIONS)[number]

export const SETTINGS_SECTION_TITLES: Record<SettingsSection, string> = {
  model: '模型配置',
  interaction: '互动设置',
  image: '图片设置',
  app: '全局设置',
  plot: '剧情选项',
  appearance: '外观',
}

interface Model {
  id: number
  name: string
  model_id: string
  model_type: string
  enabled: boolean
}

const DEFAULT_SETTINGS_FORM = {
  primary_model_id: null as number | null,
  backup_model_ids: [] as number[],
  context_length: 10,
  reply_style: 'detailed',
  options_prompt: '',
  auto_generate_options: true,
  copy_image_format: 'url' as 'url' | 'binary',
  disable_chat_bubble_elastic: false,
  show_background_image: true,
  default_system_prompt: '',
  state_broadcast_prompt: '',
  default_image_model_id: null as number | null,
  image_size: '2K',
  image_watermark: false,
  default_image_style: '',
}

export function useSettingsForm() {
  const settingsStore = useSettingsStore()

  const models = ref<Model[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const backupCandidateId = ref<number | null>(null)
  const adminModeEnabled = ref(localStorage.getItem('admin_mode') === '1')

  const form = reactive({ ...DEFAULT_SETTINGS_FORM })

  const enabledModels = computed(() =>
    models.value.filter((m) => !!m.enabled && m.model_type === MODEL_TYPE_CHAT),
  )
  const backupCandidates = computed(() =>
    enabledModels.value.filter(
      (m) => m.id !== form.primary_model_id && !form.backup_model_ids.includes(m.id),
    ),
  )
  const imageModels = computed(() =>
    models.value.filter((m) => m.model_type === MODEL_TYPE_IMAGE && !!m.enabled),
  )

  async function loadSettings() {
    loading.value = true
    try {
      const fetchSettings = settingsStore.initialized
        ? Promise.resolve()
        : settingsStore.fetchSettings()
      const [{ data: modelData }, , appRes] = await Promise.all([
        getModels(),
        fetchSettings,
        getAppSettings(),
      ])
      models.value = modelData

      Object.assign(form, {
        primary_model_id: settingsStore.settings.primary_model_id,
        backup_model_ids: [...(settingsStore.settings.backup_model_ids || [])],
        context_length: settingsStore.settings.context_length,
        reply_style: settingsStore.settings.reply_style,
        options_prompt: settingsStore.settings.options_prompt || '',
        auto_generate_options: !!settingsStore.settings.auto_generate_options,
        copy_image_format: (settingsStore.settings.copy_image_format || 'url') as 'url' | 'binary',
        disable_chat_bubble_elastic: !!settingsStore.settings.disable_chat_bubble_elastic,
        show_background_image: settingsStore.settings.show_background_image !== false,
      })

      const appS = appRes.data
      form.default_system_prompt = appS.default_system_prompt || ''
      form.state_broadcast_prompt = appS.state_broadcast_prompt || ''
      form.default_image_model_id = appS.default_image_model_id
      form.image_size = appS.image_size || '2K'
      form.image_watermark = appS.image_watermark !== false
      form.default_image_style = appS.default_image_style || ''
    } finally {
      loading.value = false
    }
  }

  async function saveSettings() {
    if (saving.value) return
    saving.value = true
    try {
      await settingsStore.saveSettings({
        primary_model_id: form.primary_model_id,
        backup_model_ids: form.backup_model_ids,
        context_length: form.context_length,
        reply_style: form.reply_style,
        options_prompt: form.options_prompt,
        auto_generate_options: form.auto_generate_options,
        copy_image_format: form.copy_image_format,
        disable_chat_bubble_elastic: form.disable_chat_bubble_elastic,
        show_background_image: form.show_background_image,
      })
    } catch {
      saving.value = false
      return
    }
    try {
      await updateAppSettings({
        default_system_prompt: form.default_system_prompt,
        state_broadcast_prompt: form.state_broadcast_prompt,
        default_image_model_id: form.default_image_model_id,
        image_size: form.image_size,
        image_watermark: form.image_watermark,
        default_image_style: form.default_image_style,
      })
    } catch {
      ElMessage.error('图片设置保存失败')
      saving.value = false
      return
    }
    ElMessage.success('设置已保存')
    saving.value = false
  }

  async function resetSettings() {
    try {
      await ElMessageBox.confirm('确定恢复默认设置？', '确认重置', {
        confirmButtonText: '重置',
        cancelButtonText: '取消',
        type: 'warning',
      })
      saving.value = true
      try {
        await settingsStore.saveSettings({
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
      } catch {
        saving.value = false
        return
      }
      try {
        await updateAppSettings({
          default_system_prompt: '',
          state_broadcast_prompt: '',
          default_image_model_id: null,
          image_size: '2K',
          image_watermark: false,
          default_image_style: '',
        })
      } catch {
        ElMessage.error('图片设置重置失败')
        saving.value = false
        return
      }
      Object.assign(form, {
        ...DEFAULT_SETTINGS_FORM,
        primary_model_id: null,
      })
      ElMessage.success('已恢复默认设置')
      saving.value = false
    } catch {
      saving.value = false
    }
  }

  function addBackup() {
    if (!backupCandidateId.value) return
    if (!form.backup_model_ids.includes(backupCandidateId.value)) {
      form.backup_model_ids.push(backupCandidateId.value)
    }
    backupCandidateId.value = null
  }

  function removeBackup(idx: number) {
    form.backup_model_ids.splice(idx, 1)
  }

  function moveBackupUp(idx: number) {
    if (idx <= 0) return
    const arr = form.backup_model_ids
    ;[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
  }

  function moveBackupDown(idx: number) {
    const arr = form.backup_model_ids
    if (idx >= arr.length - 1) return
    ;[arr[idx + 1], arr[idx]] = [arr[idx], arr[idx + 1]]
  }

  return {
    form,
    models,
    loading,
    saving,
    backupCandidateId,
    adminModeEnabled,
    enabledModels,
    backupCandidates,
    imageModels,
    loadSettings,
    saveSettings,
    resetSettings,
    addBackup,
    removeBackup,
    moveBackupUp,
    moveBackupDown,
  }
}
