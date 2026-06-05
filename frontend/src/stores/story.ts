import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getStories, getStory } from '../api'
import { getErrorMessage } from '../api'
import { useStorageSync } from '../composables/useStorageSync'

export interface Story {
  id: number
  title: string
  cover_image: string
  background_image?: string
  description: string
  tags: string[]
  category: string
  world_setting: string
  system_prompt: string
  state_config: StateField[]
  opening_requirement?: string
  image_style?: string
  preference?: string
  created_at: string
}

export interface StateField {
  key: string
  label: string
  type: 'number' | 'text'
  default: number | string
  max?: number
  min?: number
}

export const useStoryStore = defineStore('story', () => {
  const stories = ref<Story[]>([])
  const currentStory = ref<Story | null>(null)
  const loading = ref(false)
  const fetchError = ref<string | null>(null)

  const sync = useStorageSync()

  // Pub-sub: same-tab listeners
  const subscribers = new Set<() => void>()

  // Request version counter to handle race conditions
  let requestVersion = 0
  let storyRequestVersion = 0

  // Cross-tab sync via storage event
  sync.watch('stories', () => fetchStories())

  async function fetchStories() {
    // Increment version at request start (not completion)
    // so any in-flight request with a smaller version is considered stale
    const myVersion = ++requestVersion

    loading.value = true
    fetchError.value = null
    try {
      const { data } = await getStories()
      // Only apply if this is still the latest request
      if (myVersion === requestVersion) {
        stories.value = data
      }
    } catch (e: unknown) {
      fetchError.value = getErrorMessage(e, '加载失败')
      ElMessage.error(getErrorMessage(e, '加载故事列表失败'))
      console.error('fetchStories error:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStory(id: number) {
    const myVersion = ++storyRequestVersion
    loading.value = true
    currentStory.value = null
    try {
      const { data } = await getStory(id)
      if (myVersion === storyRequestVersion) {
        currentStory.value = data
      }
    } catch (e: unknown) {
      ElMessage.error(getErrorMessage(e, '加载故事详情失败'))
      console.error('fetchStory error:', e)
    } finally {
      loading.value = false
    }
  }

  // Broadcast to other tabs via storage event
  function broadcastStories() {
    sync.broadcast('stories')
  }

  // Refresh and notify all same-tab subscribers
  // fetchStories already uses requestVersion to handle race conditions
  async function refreshStories() {
    await fetchStories()
    subscribers.forEach((fn) => fn())
  }

  // Subscribe to story list changes — returns proper unsubscribe function
  function subscribe(fn: () => void): () => void {
    subscribers.add(fn)
    return () => {
      subscribers.delete(fn)
    }
  }

  return {
    stories,
    currentStory,
    loading,
    fetchError,
    fetchStories,
    fetchStory,
    broadcastStories,
    refreshStories,
    subscribe,
  }
})
