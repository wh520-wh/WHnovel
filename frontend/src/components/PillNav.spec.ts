import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'

const gsapMocks = vi.hoisted(() => ({
  set: vi.fn(),
  to: vi.fn(() => ({ kill: vi.fn() })),
  fromTo: vi.fn(),
  tweenTo: vi.fn(() => ({ kill: vi.fn() })),
  timelineKill: vi.fn(),
  timelineTo: vi.fn(),
  duration: vi.fn(() => 1),
}))

gsapMocks.timelineTo.mockReturnThis()

vi.mock('gsap', () => ({
  gsap: {
    set: gsapMocks.set,
    to: gsapMocks.to,
    fromTo: gsapMocks.fromTo,
    timeline: vi.fn(() => ({
      to: gsapMocks.timelineTo,
      tweenTo: gsapMocks.tweenTo,
      kill: gsapMocks.timelineKill,
      duration: gsapMocks.duration,
    })),
  },
}))

import PillNav from './PillNav.vue'

const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect

function mountPillNav() {
  return mount(PillNav, {
    props: {
      items: [
        { key: 'hall', label: '故事大厅', href: '/' },
        { key: 'settings', label: '设置', href: '/settings' },
        { key: 'theme', label: 'Claude', onClick: vi.fn() },
      ],
      activeKey: 'settings',
      initialLoadAnimation: false,
    },
    global: {
      stubs: {
        RouterLink: defineComponent({
          props: ['to'],
          template: '<a :data-to="to"><slot /></a>',
        }),
      },
    },
    attachTo: document.body,
  })
}

describe('PillNav', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1024,
    })
    HTMLElement.prototype.getBoundingClientRect = vi.fn(() => ({
      width: 120,
      height: 42,
      top: 0,
      left: 0,
      right: 120,
      bottom: 42,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }))
    gsapMocks.set.mockClear()
    gsapMocks.to.mockClear()
    gsapMocks.fromTo.mockClear()
    gsapMocks.tweenTo.mockClear()
    gsapMocks.timelineKill.mockClear()
    gsapMocks.timelineTo.mockClear()
    gsapMocks.duration.mockClear()
  })

  afterEach(() => {
    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect
  })

  it('renders pills without the old logo circle', () => {
    const wrapper = mountPillNav()

    expect(wrapper.find('.pill-logo').exists()).toBe(false)
    expect(wrapper.findAll('.pill').length).toBe(3)

    wrapper.unmount()
  })

  it('keeps the active pill state on desktop', () => {
    const wrapper = mountPillNav()

    expect(wrapper.find('.pill.is-active').text()).toContain('设置')

    wrapper.unmount()
  })

  it('keeps pill hover interaction wiring', async () => {
    const wrapper = mountPillNav()

    await nextTick()
    await wrapper.findAll('.pill')[0].trigger('mouseenter')
    await wrapper.findAll('.pill')[0].trigger('mouseleave')

    expect(gsapMocks.tweenTo).toHaveBeenCalledTimes(2)
    expect(gsapMocks.tweenTo).toHaveBeenNthCalledWith(1, 1, expect.any(Object))
    expect(gsapMocks.tweenTo).toHaveBeenNthCalledWith(2, 0, expect.any(Object))

    wrapper.unmount()
  })

  it('does not render the hamburger trigger on mobile', () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 375,
    })

    const wrapper = mountPillNav()
    const pillList = wrapper.find('.pill-list')

    expect(pillList.exists()).toBe(true)
    expect(pillList.classes()).not.toContain('desktop-only')
    expect(wrapper.find('.pill-nav-track').exists()).toBe(true)
    expect(wrapper.find('.mobile-menu-button').exists()).toBe(false)
    expect(wrapper.find('.mobile-menu-popover').exists()).toBe(false)

    wrapper.unmount()
  })

  it('keeps all nav pills visible on mobile without menu-only indirection', () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 375,
    })

    const wrapper = mountPillNav()

    expect(wrapper.find('.pill-list').exists()).toBe(true)
    expect(wrapper.findAll('.pill-list > li').length).toBe(3)
    expect(wrapper.findAll('.pill').length).toBe(3)
    expect(wrapper.findAll('.mobile-menu-link').length).toBe(0)
    expect(wrapper.find('.mobile-menu-button').exists()).toBe(false)
    expect(wrapper.find('.pill-nav').classes()).toContain('pill-nav--mobile-compact')
    expect(wrapper.find('.pill-list').classes()).toContain('pill-list--mobile-compact')
    expect(wrapper.findAll('.pill-list > li')[0].classes()).toContain(
      'pill-list-item--mobile-compact',
    )
    expect(wrapper.findAll('.pill')[0].classes()).toContain('pill--mobile-compact')

    wrapper.unmount()
  })
})
