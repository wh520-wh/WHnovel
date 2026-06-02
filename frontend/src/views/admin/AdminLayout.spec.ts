import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/admin/stories' }),
}))

vi.mock('../../api', () => ({
  getErrorMessage: vi.fn(() => '失败'),
  shutdownSystem: vi.fn(),
}))

import AdminLayout from './AdminLayout.vue'

describe('AdminLayout responsive UI contract', () => {
  it('has a collapsible-sidebar class hook for hiding large footer panels on tablet', () => {
    const wrapper = mount(AdminLayout, {
      global: {
        stubs: {
          RouterView: { template: '<div />' },
          Fold: { template: '<span />' },
          House: { template: '<span />' },
          ChatDotRound: { template: '<span />' },
          Cpu: { template: '<span />' },
          Setting: { template: '<span />' },
          DataAnalysis: { template: '<span />' },
          'el-menu': { template: '<nav><slot /></nav>' },
          'el-menu-item': { template: '<button><slot /></button>' },
          'el-icon': { template: '<span><slot /></span>' },
          'el-drawer': { template: '<aside><slot /></aside>' },
        },
      },
    })

    expect(wrapper.find('.admin-sidebar-footer--collapsible').exists()).toBe(true)
  })
})
