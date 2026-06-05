import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({
  generateStoryOptions: vi.fn(),
}))

import { useChatOptions } from './useChatOptions'

const { generateStoryOptions } = (await import('../api')) as any

describe('useChatOptions - history stack', () => {
  let module: ReturnType<typeof useChatOptions>

  beforeEach(() => {
    vi.clearAllMocks()
    module = useChatOptions()
    module.currentOptions.value = []
    module.optionsLocked.value = false
    module.generatingOptions.value = false
    module.generatingOptionsFailed.value = false
    module.optionsHistory.value = []
  })

  it('pushes current options to history before generating new ones', async () => {
    module.currentOptions.value = ['选项A', '选项B']
    generateStoryOptions.mockResolvedValue({
      data: { options: ['选项C', '选项D', '选项E'] },
    })

    await module.manualGenerateOptions(1, 3)

    expect(module.optionsHistory.value).toHaveLength(1)
    expect(module.optionsHistory.value[0]).toEqual(['选项A', '选项B'])
    expect(module.currentOptions.value).toEqual(['选项C', '选项D', '选项E'])
  })

  it('does not push empty options to history', async () => {
    module.currentOptions.value = []
    generateStoryOptions.mockResolvedValue({
      data: { options: ['选项A'] },
    })

    await module.manualGenerateOptions(1, 3)

    expect(module.optionsHistory.value).toHaveLength(0)
  })

  it('caps history at 2 entries', async () => {
    for (let i = 0; i < 3; i++) {
      module.currentOptions.value = [`第${i}组`]
      generateStoryOptions.mockResolvedValue({
        data: { options: [`第${i + 1}组`] },
      })
      await module.manualGenerateOptions(1, 3)
    }

    expect(module.optionsHistory.value).toHaveLength(2)
    expect(module.optionsHistory.value[0]).toEqual(['第1组'])
  })

  it('restores previous options from history', () => {
    module.currentOptions.value = ['旧选项A', '旧选项B']
    module.optionsHistory.value = [['更早选项A', '更早选项B']]

    const result = module.restorePreviousOptions()

    expect(result).toBe(true)
    expect(module.currentOptions.value).toEqual(['更早选项A', '更早选项B'])
    expect(module.optionsHistory.value).toHaveLength(0)
  })

  it('returns false when history is empty', () => {
    const result = module.restorePreviousOptions()
    expect(result).toBe(false)
  })

  it('clears history on beginOptionLock', () => {
    module.currentOptions.value = ['选项A']
    module.optionsHistory.value = [['旧选项B']]

    module.beginOptionLock('选项A')

    expect(module.optionsHistory.value).toHaveLength(0)
  })

  it('clears history on dismissCurrentOptions', () => {
    module.currentOptions.value = ['选项A']
    module.optionsHistory.value = [['旧选项B']]

    module.dismissCurrentOptions()

    expect(module.optionsHistory.value).toHaveLength(0)
  })

  it('optionsHistoryDepth reflects stack size', () => {
    expect(module.optionsHistoryDepth.value).toBe(0)

    module.optionsHistory.value = [['A'], ['B']]
    expect(module.optionsHistoryDepth.value).toBe(2)
  })

  it('auto-generate also pushes to history', async () => {
    module.currentOptions.value = ['现有选项A']
    generateStoryOptions.mockResolvedValue({
      data: { options: ['新选项A', '新选项B', '新选项C'] },
    })

    await module.autoGenerateOptionsAsync(1)

    expect(module.optionsHistory.value).toHaveLength(1)
    expect(module.optionsHistory.value[0]).toEqual(['现有选项A'])
  })
  it('stores the selected option while option lock is active', () => {
    module.currentOptions.value = ['观察四周', '直接追问']

    const locked = module.beginOptionLock('直接追问')

    expect(locked).toBe(true)
    expect(module.lockedOption.value).toBe('直接追问')
    expect(module.currentOptions.value).toEqual([])
    expect(module.optionsLocked.value).toBe(true)
  })

  it('clears locked option after successful option send', () => {
    module.currentOptions.value = ['观察四周']
    module.beginOptionLock('观察四周')

    module.finishOptionLock(true)

    expect(module.lockedOption.value).toBe('')
    expect(module.lastOptionsSnapshot.value).toEqual([])
    expect(module.optionsLocked.value).toBe(false)
  })

  it('restores options and clears locked option after failed option send', () => {
    module.currentOptions.value = ['观察四周', '直接追问']
    module.beginOptionLock('观察四周')

    module.finishOptionLock(false)

    expect(module.currentOptions.value).toEqual(['观察四周', '直接追问'])
    expect(module.lockedOption.value).toBe('')
    expect(module.optionsLocked.value).toBe(false)
  })

  it('does not lock an option that is not currently displayed', () => {
    module.currentOptions.value = ['观察四周']

    const locked = module.beginOptionLock('不存在的选项')

    expect(locked).toBe(false)
    expect(module.lockedOption.value).toBe('')
    expect(module.currentOptions.value).toEqual(['观察四周'])
  })
})

describe('useChatOptions - dedup guidance', () => {
  let module: ReturnType<typeof useChatOptions>

  beforeEach(() => {
    vi.clearAllMocks()
    module = useChatOptions()
    module.currentOptions.value = []
    module.optionsLocked.value = false
    module.generatingOptions.value = false
    module.generatingOptionsFailed.value = false
    module.optionsHistory.value = []
  })

  it('passes guidance with dedup hint when current options exist', async () => {
    module.currentOptions.value = ['拿起武器', '逃跑']
    generateStoryOptions.mockResolvedValue({
      data: { options: ['观察环境', '呼救', '谈判'] },
    })

    await module.manualGenerateOptions(1, 3)

    const callArgs = generateStoryOptions.mock.calls[0]
    const guidance = callArgs[2]
    expect(guidance).toContain('以下剧情选项已经生成过')
    expect(guidance).toContain('拿起武器')
    expect(guidance).toContain('逃跑')
  })

  it('does not inject dedup when current options are empty', async () => {
    module.currentOptions.value = []
    generateStoryOptions.mockResolvedValue({
      data: { options: ['选项A'] },
    })

    await module.manualGenerateOptions(1, 3, '用户要求')

    const callArgs = generateStoryOptions.mock.calls[0]
    const guidance = callArgs[2]
    expect(guidance).toBe('用户要求')
    expect(guidance).not.toContain('以下剧情选项已经生成过')
  })

  it('includes history rounds in dedup guidance', async () => {
    module.currentOptions.value = ['当前选项A']
    module.optionsHistory.value = [['历史选项X', '历史选项Y']]
    generateStoryOptions.mockResolvedValue({
      data: { options: ['新选项'] },
    })

    await module.manualGenerateOptions(1, 3)

    const callArgs = generateStoryOptions.mock.calls[0]
    const guidance = callArgs[2]
    expect(guidance).toContain('第1轮')
    expect(guidance).toContain('历史选项X')
    expect(guidance).toContain('当前选项A')
    expect(guidance).toContain('第2轮')
  })

  it('appends user guidance after dedup hint', async () => {
    module.currentOptions.value = ['选项A']
    generateStoryOptions.mockResolvedValue({
      data: { options: ['新选项'] },
    })

    await module.manualGenerateOptions(1, 3, '用户要求')

    const callArgs = generateStoryOptions.mock.calls[0]
    const guidance = callArgs[2]
    expect(guidance).toContain('额外要求：用户要求')
    expect(guidance.indexOf('以下剧情选项已经生成过')).toBeLessThan(guidance.indexOf('额外要求'))
  })
})
