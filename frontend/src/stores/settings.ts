import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings } from '../api'
import { getErrorMessage } from '../api'
import { useStorageSync } from '../composables/useStorageSync'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref({
    id: 0,
    model_name: 'gpt-3.5-turbo',
    api_base_url: 'https://api.openai.com/v1',
    api_key: '',
    context_length: 10,
    reply_style: 'detailed',
    primary_model_id: null as number | null,
    backup_model_ids: [] as number[],
    auto_generate_options: true,
    theme: 'dark',
    options_prompt: '',
    copy_image_format: 'url' as 'url' | 'binary',
    disable_chat_bubble_elastic: false,
    show_background_image: true,
  })
  const initialized = ref(false)

  const sync = useStorageSync()

  // 其他 Tab 修改了设置并广播，当前 Tab 重新拉取
  sync.watch('settings', () => fetchSettings())

  async function fetchSettings() {
    try {
      const { data } = await getSettings()
      settings.value = data
      initialized.value = true
    } catch (e: unknown) {
      ElMessage.error(getErrorMessage(e, '加载设置失败'))
      console.error('fetchSettings error:', e)
    }
  }

  async function saveSettings(patch: Record<string, unknown>) {
    try {
      const { data } = await updateSettings(patch)
      settings.value = data
      sync.broadcast('settings')
      ElMessage.success('设置已保存')
    } catch (e: unknown) {
      ElMessage.error(getErrorMessage(e, '保存设置失败'))
      console.error('saveSettings error:', e)
      throw e
    }
  }

  return { settings, initialized, fetchSettings, saveSettings }
})
