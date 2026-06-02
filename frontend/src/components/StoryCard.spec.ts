import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StoryCard from './StoryCard.vue'
import type { Story } from '../stores/story'

const story: Story = {
  id: 7,
  title: '星尘边境',
  cover_image: '',
  background_image: '',
  description: '一段关于失落殖民地的故事。',
  tags: ['科幻', '觉醒'],
  category: '科幻',
  world_setting: '遥远边境。',
  system_prompt: '',
  state_config: [],
  created_at: '2026-05-26T00:00:00Z',
}

function mountStoryCard() {
  return mount(StoryCard, {
    props: { story },
    global: {
      stubs: {
        'el-tag': { template: '<span class="el-tag"><slot /></span>' },
      },
    },
  })
}

describe('StoryCard accessibility', () => {
  beforeEach(() => {
    class IntersectionObserverMock {
      observe = vi.fn()
      unobserve = vi.fn()
      disconnect = vi.fn()
    }

    vi.stubGlobal('IntersectionObserver', IntersectionObserverMock)
  })

  it('lets keyboard users focus and open the story card', async () => {
    const wrapper = mountStoryCard()
    const card = wrapper.find('.story-card')

    expect(card.attributes('role')).toBe('button')
    expect(card.attributes('tabindex')).toBe('0')
    expect(card.attributes('aria-label')).toContain('星尘边境')

    await card.trigger('keydown', { key: 'Enter' })
    await card.trigger('keydown', { key: ' ' })

    expect(wrapper.emitted('click')).toHaveLength(2)
  })
})
