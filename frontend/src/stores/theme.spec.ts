import { describe, expect, it, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useThemeStore } from './theme'

describe('theme store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    document.body.removeAttribute('data-theme')
  })

  it('migrates old localStorage claude → enigma on first init', () => {
    localStorage.setItem('theme', 'claude')
    const store = useThemeStore()
    expect(store.theme).toBe('enigma')
    expect(localStorage.getItem('theme')).toBe('enigma')
    expect(localStorage.getItem('theme_migrated_v2')).toBe('1')
  })

  it('does not migrate already-migrated user', () => {
    localStorage.setItem('theme', 'claude')
    localStorage.setItem('theme_migrated_v2', '1')
    const store = useThemeStore()
    expect(store.theme).toBe('claude')
  })

  it('cycles dark → light → enigma → claude → dark', () => {
    const store = useThemeStore()
    store.setTheme('dark')
    store.toggleTheme()
    expect(store.theme).toBe('light')
    store.toggleTheme()
    expect(store.theme).toBe('enigma')
    store.toggleTheme()
    expect(store.theme).toBe('claude')
    store.toggleTheme()
    expect(store.theme).toBe('dark')
  })

  it('applies data-theme attribute to html and body', () => {
    const store = useThemeStore()
    store.setTheme('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(document.body.getAttribute('data-theme')).toBe('light')
  })
})
