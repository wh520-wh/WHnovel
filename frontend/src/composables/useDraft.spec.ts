import { describe, it, expect, beforeEach } from 'vitest'
import { useDraft } from './useDraft'

const STORY_ID = 1
const ARCHIVE_ID = 100

function setupStoryDraft() {
  return useDraft({
    currentStoryId: { value: STORY_ID },
    currentArchiveId: { value: null },
  })
}

function setupArchiveDraft() {
  return useDraft({
    currentStoryId: { value: STORY_ID },
    currentArchiveId: { value: ARCHIVE_ID },
  })
}

describe('开场草稿', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('保存后能读取相同内容', () => {
    const draft = setupStoryDraft()
    draft.saveDraft('这是一段开场白')
    expect(draft.loadDraft()).toBe('这是一段开场白')
  })

  it('空字符串不保存', () => {
    const draft = setupStoryDraft()
    draft.saveDraft('')
    expect(draft.loadDraft()).toBeNull()
  })

  it('7 天后过期返回 null', () => {
    const draft = setupStoryDraft()
    const oldTime = Date.now() - (7 * 24 * 60 * 60 * 1000 + 1)
    localStorage.setItem(`draft:story:${STORY_ID}`, JSON.stringify({ text: '旧草稿', updatedAt: oldTime }))
    expect(draft.loadDraft()).toBeNull()
  })

  it('清除后返回 null', () => {
    const draft = setupStoryDraft()
    draft.saveDraft('内容')
    draft.clearDraft()
    expect(draft.loadDraft()).toBeNull()
  })
})

describe('聊天草稿', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('保存后能读取相同内容', () => {
    const draft = setupArchiveDraft()
    draft.saveDraft('聊天内容')
    expect(draft.loadDraft()).toBe('聊天内容')
  })

  it('不同 archiveId 互不污染', () => {
    const draft1 = useDraft({ currentStoryId: { value: 1 }, currentArchiveId: { value: 100 } })
    const draft2 = useDraft({ currentStoryId: { value: 1 }, currentArchiveId: { value: 101 } })
    draft1.saveDraft('存档100的草稿')
    draft2.saveDraft('存档101的草稿')
    expect(draft1.loadDraft()).toBe('存档100的草稿')
    expect(draft2.loadDraft()).toBe('存档101的草稿')
  })
})
