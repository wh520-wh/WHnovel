import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  getStories: vi.fn(),
  refreshStories: vi.fn(),
  broadcastStories: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: mocks.routerPush }),
}))

vi.mock('../../api', () => ({
  createStory: vi.fn(),
  deleteStory: vi.fn(),
  getStories: mocks.getStories,
  updateStory: vi.fn(),
  standaloneGenerateCover: vi.fn(),
  standaloneGenerateBackground: vi.fn(),
  uploadStoryImage: vi.fn(),
  getModels: vi.fn(async () => ({ data: [] })),
}))

vi.mock('../../stores/story', () => ({
  useStoryStore: () => ({
    refreshStories: mocks.refreshStories,
    broadcastStories: mocks.broadcastStories,
  }),
}))

vi.mock('../../composables/useStoryGenerate', () => ({
  useStoryGenerate: () => ({
    generating: false,
    generateCover: false,
    coverImageModelId: null,
    generateBackground: false,
    backgroundImageModelId: null,
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

import StoryManage from './StoryManage.vue'

const ElDialogStub = defineComponent({
  inheritAttrs: false,
  template: '<div v-bind="$attrs"><slot /><slot name="footer" /></div>',
})

function mountStoryManage() {
  return mount(StoryManage, {
    global: {
      stubs: {
        ModelSelect: { template: '<div class="model-select-stub" />' },
        Teleport: true,
        Transition: false,
        'el-button': { template: '<button v-bind="$attrs"><slot /></button>' },
        'el-table': { template: '<div class="story-table-stub"><slot /></div>' },
        'el-table-column': { template: '<div />' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-dialog': ElDialogStub,
        'el-form': { template: '<form><slot /></form>' },
        'el-form-item': { template: '<label><slot /></label>' },
        'el-input': { template: '<input />' },
        'el-select': { template: '<select><slot /></select>' },
        'el-option': { template: '<option />' },
        'el-switch': { template: '<button />' },
      },
    },
  })
}

describe('StoryManage responsive UI contract', () => {
  beforeEach(() => {
    mocks.routerPush.mockReset()
    mocks.refreshStories.mockReset()
    mocks.broadcastStories.mockReset()
    mocks.getStories.mockResolvedValue({
      data: [
        {
          id: 7,
          title: 'Mobile story',
          category: 'Adventure',
          tags: ['hot', 'growth'],
          description: 'A long description verifies the mobile card list shows a summary instead of relying on a wide table.',
          cover_image: '',
          background_image: '',
          world_setting: '',
          opening_requirement: '',
          image_style: '',
        },
      ],
    })
  })

  it('renders a dedicated mobile card list instead of relying only on the table', async () => {
    const wrapper = mountStoryManage()
    await flushPromises()

    expect(wrapper.find('.mobile-story-list').exists()).toBe(true)
    expect(wrapper.find('.mobile-story-card').text()).toContain('Mobile story')
    expect(wrapper.find('.mobile-story-actions').exists()).toBe(true)
    expect(wrapper.find('.mobile-story-actions').text()).toContain('状态配置')

    const stateConfigButton = wrapper
      .findAll('.mobile-story-actions button')
      .find((button) => button.text() === '状态配置')
    await stateConfigButton?.trigger('click')
    expect(mocks.routerPush).toHaveBeenCalledWith('/admin/stories/7/state-config')
  })

  it('marks story dialogs with responsive shell classes', async () => {
    const wrapper = mountStoryManage()
    await flushPromises()

    await wrapper.find('.header-actions button:last-child').trigger('click')

    expect(wrapper.find('.story-edit-dialog').exists()).toBe(true)
    expect(wrapper.find('.story-dialog-footer').exists()).toBe(true)
  })

  it('marks bulk delete as desktop-only because mobile cards do not support selection', async () => {
    const wrapper = mountStoryManage()
    await flushPromises()

    expect(wrapper.find('.desktop-bulk-delete').exists()).toBe(true)
  })
})
