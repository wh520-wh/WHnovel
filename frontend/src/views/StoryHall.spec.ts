import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerPush = vi.fn()
const fetchStories = vi.fn()
const subscribe = vi.fn(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: routerPush,
  }),
}))

vi.mock('../stores/story', () => ({
  useStoryStore: () => ({
    loading: false,
    stories: [],
    fetchError: null,
    fetchStories,
    subscribe,
  }),
}))

vi.mock('../composables/useStoryGenerate', () => ({
  useStoryGenerate: () => ({
    generating: false,
    generatingStep: 0,
    generatingSteps: [],
    enableImage: { value: false },
    previewData: null,
    previewVisible: false,
    modelSelectVisible: false,
    selectedModelId: null,
    availableModels: [],
    openModelSelect: vi.fn(),
    confirmGenerate: vi.fn(),
    confirmFill: vi.fn(() => null),
    cancelPreview: vi.fn(),
  }),
}))

import StoryHall from './StoryHall.vue'

function mountStoryHall() {
  return mount(StoryHall, {
    global: {
      stubs: {
        StoryCard: { template: '<div class="story-card-stub" />' },
        SkeletonBlock: { template: '<div />' },
        SkeletonText: { template: '<div />' },
        'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
        'el-tabs': { template: '<div><slot /></div>' },
        'el-tab-pane': { template: '<div />' },
        'el-form': { template: '<form><slot /></form>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': { template: '<input />' },
        'el-select': { template: '<select><slot /></select>' },
        'el-option': { template: '<option />' },
        'el-button': { template: '<button><slot /></button>' },
      },
    },
  })
}

describe('StoryHall header actions', () => {
  beforeEach(() => {
    routerPush.mockReset()
    fetchStories.mockClear()
    subscribe.mockClear()
    localStorage.removeItem('admin_mode')
  })

  it('shows only the create button for non-admin users', async () => {
    const wrapper = mountStoryHall()
    await flushPromises()

    expect(wrapper.find('.hall-actions').exists()).toBe(true)
    expect(wrapper.findAll('.hall-actions .hall-action-btn')).toHaveLength(1)
    expect(wrapper.find('.hall-actions .hall-action-btn').text()).toContain('创建故事')
    wrapper.unmount()
  })

  it('stacks the admin button below the create button for admins', async () => {
    localStorage.setItem('admin_mode', '1')
    const wrapper = mountStoryHall()
    await flushPromises()

    const buttons = wrapper.findAll('.hall-actions .hall-action-btn')
    expect(buttons).toHaveLength(2)
    expect(buttons[0].text()).toContain('创建故事')
    expect(buttons[1].text()).toContain('管理')
    wrapper.unmount()
  })
  it('uses a semantic button for the collapsed search trigger', async () => {
    const wrapper = mountStoryHall()
    await flushPromises()

    const trigger = wrapper.find('button.story-search-trigger')
    expect(trigger.exists()).toBe(true)
    expect(trigger.attributes('aria-expanded')).toBe('false')

    wrapper.unmount()
  })
})
