import { mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const route = reactive({ name: 'StoryHall', path: '/' })
const router = {
  push: vi.fn(),
}

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => router,
}))

const mockToggleTheme = vi.fn()
const themeStore = reactive({
  theme: 'dark' as 'dark' | 'light' | 'enigma' | 'claude',
  toggleTheme: mockToggleTheme,
})

vi.mock('./stores/theme', () => ({
  useThemeStore: () => themeStore,
}))

vi.mock('./components/PillNav.vue', () => ({
  default: defineComponent({
    props: ['items', 'activeHref', 'activeKey', 'logoText'],
    template: `
      <div class="pill-nav-stub">
        <span class="active-href">{{ activeHref }}</span>
        <span class="active-key">{{ activeKey }}</span>
        <span class="logo-text">{{ logoText }}</span>
        <button
          v-for="item in items"
          :key="item.key || item.label"
          type="button"
          class="pill-item"
          :data-key="item.key"
          @click="item.onClick && item.onClick()"
        >
          {{ item.label }}
        </button>
      </div>
    `,
  }),
}))

import App from './App.vue'

function mountApp() {
  const DummyView = defineComponent({ template: '<div />' })

  return mount(App, {
    global: {
      stubs: {
        transition: false,
        'el-config-provider': defineComponent({
          template: '<div><slot /></div>',
        }),
        'el-icon': defineComponent({
          template: '<span><slot /></span>',
        }),
        'el-button': defineComponent({
          emits: ['click'],
          template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
        }),
        'router-link': defineComponent({
          props: ['to'],
          template: '<a><slot /></a>',
        }),
        'router-view': defineComponent({
          setup(_, { slots }) {
            return () => slots.default?.({ Component: DummyView, route: { path: '/' } })
          },
        }),
      },
    },
  })
}

function setViewportWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    value: width,
  })
}

let originalInnerWidth = window.innerWidth

beforeEach(() => {
  route.name = 'StoryHall'
  route.path = '/'
  themeStore.theme = 'dark'
  router.push.mockReset()
  mockToggleTheme.mockReset()
  originalInnerWidth = window.innerWidth
  localStorage.removeItem('admin_mode')
})

afterEach(() => {
  setViewportWidth(originalInnerWidth)
})

describe('App pill navigation entry', () => {
  it('routes settings nav item to mobile settings on mobile viewport', async () => {
    setViewportWidth(768)
    const wrapper = mountApp()

    await wrapper.find('[data-key="settings"]').trigger('click')

    expect(router.push).toHaveBeenCalledWith('/settings-mobile')
    wrapper.unmount()
  })

  it('routes settings nav item to desktop settings on desktop viewport', async () => {
    setViewportWidth(1024)
    const wrapper = mountApp()

    await wrapper.find('[data-key="settings"]').trigger('click')

    expect(router.push).toHaveBeenCalledWith('/settings')
    wrapper.unmount()
  })

  it('uses settings active key for mobile settings routes', async () => {
    route.name = 'SettingsMobileHome'
    route.path = '/settings-mobile'
    const wrapper = mountApp()

    expect(wrapper.find('.active-key').text()).toBe('settings')
    wrapper.unmount()
  })

  it('includes theme action item in pill nav', () => {
    const wrapper = mountApp()

    expect(wrapper.find('[data-key="theme"]').text()).toBe('暗色')
    wrapper.unmount()
  })

  it('keeps mobile nav items in hall settings admin theme order', () => {
    localStorage.setItem('admin_mode', '1')
    const wrapper = mountApp()

    const labels = wrapper.findAll('.pill-item').map((node) => node.text())
    expect(labels).toEqual(['故事大厅', '设置', '管理后台', '暗色'])

    wrapper.unmount()
  })

  it('does not pass the old logo text prop to pill nav', () => {
    const wrapper = mountApp()

    expect(wrapper.find('.logo-text').text()).toBe('')
    wrapper.unmount()
  })
})
