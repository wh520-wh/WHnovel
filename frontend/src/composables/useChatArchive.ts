import { ref } from 'vue'
import { createArchive, getArchive, getArchives } from '../api'
import type { Archive } from '../stores/chat'

export function useChatArchive() {
  const archives = ref<Archive[]>([])
  const currentArchive = ref<Archive | null>(null)

  async function fetchArchives(storyId: number) {
    const { data } = await getArchives(storyId)
    archives.value = data
  }

  async function startNewArchive(storyId: number, name: string = '默认会话') {
    const { data } = await createArchive(storyId, name)
    currentArchive.value = data
    await fetchArchives(storyId)
    return data
  }

  async function ensureActiveArchive(
    storyId: number,
  ): Promise<{ archiveId: number; isNew: boolean }> {
    await fetchArchives(storyId)
    if (archives.value.length === 0) {
      const archive = await startNewArchive(storyId)
      return { archiveId: archive.id, isNew: true }
    }
    // 名实相符：已有存档路径也要保证 currentArchive 指向本故事的有效存档。
    // 否则 clearChat 之后调用方拿到 null，startStory 的 guard 静默 return
    // （全新故事点"开始聊天"无反应、不发请求的根因）。
    const first = archives.value[0]
    if (
      currentArchive.value?.story_id !== storyId ||
      !archives.value.some((a) => a.id === currentArchive.value?.id)
    ) {
      currentArchive.value = first
    }
    return { archiveId: first.id, isNew: false }
  }

  async function loadArchive(archiveId: number): Promise<Archive | null> {
    const previousArchiveId = currentArchive.value?.id
    if (previousArchiveId !== undefined && previousArchiveId !== archiveId) {
      // Caller should abort image request - we don't import useChatImage to avoid cycle
    }
    const { data: archive } = await getArchive(archiveId)
    currentArchive.value = archive
    return archive
  }

  function clearArchiveState() {
    currentArchive.value = null
    archives.value = []
  }

  return {
    archives,
    currentArchive,
    fetchArchives,
    startNewArchive,
    ensureActiveArchive,
    loadArchive,
    clearArchiveState,
  }
}
