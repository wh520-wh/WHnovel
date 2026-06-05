import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeName = 'dark' | 'light' | 'enigma' | 'claude'

export const useThemeStore = defineStore('theme', () => {
  // Migrate old localStorage.theme === 'claude' (teal theme) → 'enigma' (renamed)
  const raw = localStorage.getItem('theme')
  if (raw === 'claude' && !localStorage.getItem('theme_migrated_v2')) {
    localStorage.setItem('theme', 'enigma')
    localStorage.setItem('theme_migrated_v2', '1')
  }

  const theme = ref<ThemeName>((localStorage.getItem('theme') as ThemeName) || 'dark')

  function setTheme(t: ThemeName) {
    theme.value = t
    localStorage.setItem('theme', t)
    applyTheme()
  }

  function toggleTheme() {
    const cycle: ThemeName[] = ['dark', 'light', 'enigma', 'claude']
    const idx = cycle.indexOf(theme.value)
    const next = cycle[(idx + 1) % cycle.length]
    setTheme(next)
  }

  function applyTheme() {
    document.documentElement.setAttribute('data-theme', theme.value)
    document.body.setAttribute('data-theme', theme.value)
  }

  applyTheme()

  return { theme, setTheme, toggleTheme, applyTheme }
})
