const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

export function useDraft(params: {
  currentStoryId: { value: number | null }
  currentArchiveId: { value: number | null }
}) {
  function getKey(): string | null {
    if (params.currentArchiveId.value != null) {
      return `draft:archive:${params.currentArchiveId.value}`
    }
    if (params.currentStoryId.value != null) {
      return `draft:story:${params.currentStoryId.value}`
    }
    return null
  }

  function saveDraft(text: string): void {
    if (text === '') return
    const key = getKey()
    if (!key) return
    localStorage.setItem(key, JSON.stringify({ text, updatedAt: Date.now() }))
  }

  function loadDraft(): string | null {
    const key = getKey()
    if (!key) return null
    const raw = localStorage.getItem(key)
    if (!raw) return null
    try {
      const parsed = JSON.parse(raw) as { text: string; updatedAt: number }
      if (Date.now() - parsed.updatedAt > SEVEN_DAYS_MS) {
        localStorage.removeItem(key)
        return null
      }
      return parsed.text
    } catch {
      return null
    }
  }

  function clearDraft(): void {
    const key = getKey()
    if (!key) return
    localStorage.removeItem(key)
  }

  return {
    saveDraft,
    loadDraft,
    clearDraft,
  }
}
