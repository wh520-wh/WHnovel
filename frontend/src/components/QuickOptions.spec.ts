import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import QuickOptions from './QuickOptions.vue'

describe('QuickOptions', () => {
  it('shows the locked selected option when options are hidden', () => {
    const wrapper = mount(QuickOptions, {
      props: {
        options: [],
        disabled: true,
        locked: true,
        lockedOption: '观察四周',
      },
    })

    expect(wrapper.find('.locked-option-bubble').exists()).toBe(true)
    expect(wrapper.text()).toContain('已选择')
    expect(wrapper.text()).toContain('观察四周')
  })

  it('does not emit select again from the locked feedback bubble', async () => {
    const wrapper = mount(QuickOptions, {
      props: {
        options: [],
        disabled: true,
        locked: true,
        lockedOption: '观察四周',
      },
    })

    await wrapper.find('.locked-option-bubble').trigger('click')

    expect(wrapper.emitted('select')).toBeUndefined()
  })

  it('emits selected option from normal option buttons', async () => {
    const wrapper = mount(QuickOptions, {
      props: {
        options: ['观察四周'],
        disabled: false,
        locked: false,
        lockedOption: '',
      },
    })

    await wrapper.find('.option-btn').trigger('click')

    expect(wrapper.emitted('select')).toEqual([['观察四周']])
  })

  it('shows normal options instead of locked feedback when options are present', () => {
    const wrapper = mount(QuickOptions, {
      props: {
        options: ['观察四周'],
        disabled: true,
        locked: true,
        lockedOption: '直接追问',
      },
    })

    expect(wrapper.find('.options-list').exists()).toBe(true)
    expect(wrapper.find('.option-btn').exists()).toBe(true)
    expect(wrapper.find('.locked-option-bubble').exists()).toBe(false)
  })

  it('does not reset active state after unmount', () => {
    vi.useFakeTimers()
    const wrapper = mount(QuickOptions, {
      props: {
        options: ['观察四周'],
        disabled: false,
      },
    })

    wrapper.find('.option-btn').trigger('click')
    wrapper.unmount()

    expect(() => vi.runAllTimers()).not.toThrow()
    vi.useRealTimers()
  })
})
