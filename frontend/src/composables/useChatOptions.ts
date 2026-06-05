import { computed, ref } from 'vue'
import { generateStoryOptions } from '../api'
import { normalizeOptions } from '../utils/text'

export function useChatOptions() {
  const currentOptions = ref<string[]>([])
  const optionsLocked = ref(false)
  const lockedOption = ref('')
  const generatingOptions = ref(false)
  const generatingOptionsFailed = ref(false)
  const awaitingOptions = ref(false)
  const lastOptionsSnapshot = ref<string[]>([])
  const _MAX_OPTIONS_HISTORY = 2
  const optionsHistory = ref<string[][]>([])
  const optionsHistoryDepth = computed(() => optionsHistory.value.length)
  const autoGenerateOptions = ref(true)

  function setAutoGenerateOptions(value: boolean) {
    autoGenerateOptions.value = value
  }

  function beginOptionLock(option: string) {
    if (optionsLocked.value || !currentOptions.value.includes(option)) return false
    lastOptionsSnapshot.value = [...currentOptions.value]
    lockedOption.value = option
    currentOptions.value = []
    optionsHistory.value = []
    optionsLocked.value = true
    return true
  }

  function finishOptionLock(success: boolean) {
    if (!optionsLocked.value) return
    if (!success) {
      currentOptions.value = [...lastOptionsSnapshot.value]
    }
    if (success) {
      lastOptionsSnapshot.value = []
    }
    lockedOption.value = ''
    optionsLocked.value = false
  }

  function dismissCurrentOptions() {
    currentOptions.value = []
    lastOptionsSnapshot.value = []
    lockedOption.value = ''
    optionsHistory.value = []
  }

  function restorePreviousOptions(): boolean {
    if (optionsHistory.value.length === 0) return false
    currentOptions.value = optionsHistory.value.pop()!
    return true
  }

  function _buildDedupGuidance(
    current: string[],
    history: string[][],
    userGuidance: string,
  ): string {
    if (current.length === 0) return userGuidance
    const allRounds: string[][] = [current]
    const historySlice = history.slice(-_MAX_OPTIONS_HISTORY)
    for (const h of historySlice) {
      if (h.length > 0) allRounds.unshift(h)
    }
    let dedup = '以下剧情选项已经生成过，请生成不同方向的选项：'
    for (let i = 0; i < allRounds.length; i++) {
      dedup += `\n第${i + 1}轮：${allRounds[i].map((o, j) => `${j + 1}. ${o}`).join(' ')}`
    }
    if (userGuidance) {
      dedup += `\n额外要求：${userGuidance}`
    }
    return dedup
  }

  async function manualGenerateOptions(
    archiveId: number,
    count: number = 3,
    guidance: string = '',
  ) {
    if (generatingOptions.value || optionsLocked.value) return []
    const autoGuidance = _buildDedupGuidance(currentOptions.value, optionsHistory.value, guidance)
    if (currentOptions.value.length > 0) {
      optionsHistory.value.push([...currentOptions.value])
      if (optionsHistory.value.length > _MAX_OPTIONS_HISTORY) {
        optionsHistory.value.shift()
      }
    }
    generatingOptions.value = true
    generatingOptionsFailed.value = false
    try {
      const { data } = await generateStoryOptions(archiveId, count, autoGuidance)
      currentOptions.value = normalizeOptions(data.options)
      return currentOptions.value
    } catch {
      generatingOptionsFailed.value = true
      return []
    } finally {
      generatingOptions.value = false
    }
  }

  async function autoGenerateOptionsAsync(archiveId: number) {
    if (generatingOptions.value || optionsLocked.value) return
    awaitingOptions.value = true
    generatingOptionsFailed.value = false
    try {
      const options = await manualGenerateOptions(archiveId, 3)
      currentOptions.value = options
    } finally {
      awaitingOptions.value = false
      generatingOptions.value = false
    }
  }

  return {
    currentOptions,
    optionsLocked,
    lockedOption,
    generatingOptions,
    generatingOptionsFailed,
    awaitingOptions,
    autoGenerateOptions,
    setAutoGenerateOptions,
    lastOptionsSnapshot,
    beginOptionLock,
    finishOptionLock,
    dismissCurrentOptions,
    optionsHistory,
    optionsHistoryDepth,
    restorePreviousOptions,
    manualGenerateOptions,
    autoGenerateOptionsAsync,
  }
}
