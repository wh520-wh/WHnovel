import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { aiGenerateStory, getErrorMessage, getModels } from '../api'
import { MODEL_TYPE_CHAT } from '../constants/modelTypes'
import { sanitizeAiDisplayText, sanitizeAiInlineText, sanitizeAiStringList } from '../utils/aiText'

export interface GeneratedStory {
  title: string
  category: string
  tags: string[]
  cover_url: string
  background_url: string
  description: string
  world_setting: string
  image_style: string
  opening_requirement: string
}

const LAST_MODEL_KEY = 'last_generate_model_id'

function sanitizeGeneratedStory(data: GeneratedStory): GeneratedStory {
  return {
    title: sanitizeAiInlineText(data.title),
    category: sanitizeAiInlineText(data.category),
    tags: sanitizeAiStringList(data.tags),
    cover_url: String(data.cover_url || '').trim(),
    background_url: String(data.background_url || '').trim(),
    description: sanitizeAiDisplayText(data.description),
    world_setting: sanitizeAiDisplayText(data.world_setting),
    image_style: sanitizeAiDisplayText(data.image_style),
    opening_requirement: sanitizeAiDisplayText(data.opening_requirement || ''),
  }
}

export function useStoryGenerate() {
  const generating = ref(false)
  const generatingStep = ref(-1)
  const generatingStepText = ref('')

  const generateCover = ref(false)
  const coverImageModelId = ref<number | null>(null)
  const generateBackground = ref(false)
  const backgroundImageModelId = ref<number | null>(null)

  const previewData = ref<GeneratedStory | null>(null)
  const previewVisible = ref(false)
  const modelSelectVisible = ref(false)
  const selectedModelId = ref<number | null>(null)
  const availableModels = ref<{ id: number; name: string; model_id: string; api_base_url: string }[]>([])

  async function loadAvailableModels() {
    try {
      const resp = await getModels()
      const modelsData = resp.data as { id: number; name: string; model_id: string; api_base_url: string; enabled?: boolean; model_type?: string }[]
      availableModels.value = modelsData.filter((m) => !!m.enabled && m.model_type === MODEL_TYPE_CHAT)
    } catch {
      availableModels.value = []
    }
  }

  async function openModelSelect() {
    modelSelectVisible.value = true
    selectedModelId.value = Number(localStorage.getItem(LAST_MODEL_KEY) || '0') || null
    await loadAvailableModels()
  }

  const generatingSteps = ref<string[]>([])

  function _setStep(idx: number, text: string) {
    generatingStep.value = idx
    generatingStepText.value = text
  }

  function _buildSteps() {
    const steps = ['正在生成故事内容...']
    if (generateCover.value) {
      steps.push('正在生成封面图...')
    }
    if (generateBackground.value) {
      steps.push('正在生成背景图...')
    }
    generatingSteps.value = steps
  }

  async function confirmGenerate(params: {
    category: string
    title_hint: string
    tags_hint: string
    image_style?: string
    preference?: string
  }) {
    if (selectedModelId.value) {
      localStorage.setItem(LAST_MODEL_KEY, String(selectedModelId.value))
    }

    _buildSteps()
    generating.value = true

    try {
      // 生成故事内容（含封面/背景，由后端统一处理）
      _setStep(0, generatingSteps.value[0])

      let stepIdx = 1

      const { data } = await aiGenerateStory({
        category: params.category,
        title_hint: params.title_hint,
        tags_hint: params.tags_hint,
        model_id: selectedModelId.value ?? undefined,
        image_style: params.image_style,
        preference: params.preference,
        generate_cover: generateCover.value || undefined,
        cover_image_model_id: generateCover.value ? (coverImageModelId.value ?? undefined) : undefined,
        generate_background: generateBackground.value || undefined,
        background_image_model_id: generateBackground.value ? (backgroundImageModelId.value ?? undefined) : undefined,
      })

      let result = sanitizeGeneratedStory(data)

      // 后端已处理封面/背景生成，只需更新步骤显示
      if (generateCover.value) {
        _setStep(stepIdx, generatingSteps.value[stepIdx])
        stepIdx++
      }
      if (generateBackground.value) {
        _setStep(stepIdx, generatingSteps.value[stepIdx])
        stepIdx++
      }

      previewData.value = result
      previewVisible.value = true
      modelSelectVisible.value = false
    } catch (e: any) {
      ElMessage.error('生成失败：' + getErrorMessage(e))
    } finally {
      generating.value = false
      generatingStep.value = -1
      generatingStepText.value = ''
    }
  }

  function confirmFill(): GeneratedStory | null {
    previewVisible.value = false
    const result = previewData.value
    previewData.value = null
    return result
  }

  function cancelPreview() {
    previewVisible.value = false
    previewData.value = null
  }

  return {
    generating,
    generatingStep,
    generatingStepText,
    generatingSteps,
    generateCover,
    coverImageModelId,
    generateBackground,
    backgroundImageModelId,
    previewData,
    previewVisible,
    modelSelectVisible,
    selectedModelId,
    availableModels,
    openModelSelect,
    confirmGenerate,
    confirmFill,
    cancelPreview,
  }
}
