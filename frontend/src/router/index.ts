import { createRouter, createWebHistory } from 'vue-router'
import { ALLOWED_SETTINGS_SECTIONS } from '../composables/useSettingsForm'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'StoryHall',
      component: () => import('../views/StoryHall.vue'),
      meta: { title: '故事大厅' },
    },
    {
      path: '/play/:storyId',
      name: 'StoryPlay',
      component: () => import('../views/StoryPlay.vue'),
      meta: { title: '故事互动' },
      beforeEnter: (to) => {
        const id = Number(to.params.storyId)
        if (!Number.isFinite(id) || id <= 0) {
          return { name: 'NotFound' }
        }
      },
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../views/Settings.vue'),
      meta: { title: '设置' },
    },
    {
      path: '/settings-mobile',
      name: 'SettingsMobileHome',
      component: () => import('../views/SettingsMobile.vue'),
      meta: { title: '设置' },
    },
    {
      path: '/settings-mobile/:section',
      name: 'SettingsMobileSection',
      component: () => import('../views/SettingsMobile.vue'),
      meta: { title: '设置' },
      beforeEnter: (to) => {
        const section = String(to.params.section || '')
        if (
          !ALLOWED_SETTINGS_SECTIONS.includes(section as (typeof ALLOWED_SETTINGS_SECTIONS)[number])
        ) {
          return { path: '/settings-mobile', query: to.query }
        }
        return true
      },
    },
    {
      path: '/admin',
      name: 'AdminLayout',
      component: () => import('../views/admin/AdminLayout.vue'),
      meta: { title: '管理后台' },
      children: [
        {
          path: '',
          redirect: '/admin/stories',
        },
        {
          path: 'stories',
          name: 'StoryManage',
          component: () => import('../views/admin/StoryManage.vue'),
        },
        {
          path: 'stories/:storyId/characters',
          name: 'CharacterManage',
          component: () => import('../views/admin/CharacterManage.vue'),
        },
        {
          path: 'stories/:storyId/prompt',
          name: 'PromptManage',
          component: () => import('../views/admin/PromptManage.vue'),
        },
        {
          path: 'stories/:storyId/state-config',
          name: 'StateConfig',
          component: () => import('../views/admin/StateConfig.vue'),
        },
        {
          path: 'models',
          name: 'ModelManage',
          component: () => import('../views/admin/ModelManage.vue'),
        },
        {
          path: 'model-tuning',
          name: 'ModelTuning',
          component: () => import('../views/admin/ModelTuning.vue'),
        },
        {
          path: 'global-prompt',
          name: 'GlobalPromptManage',
          component: () => import('../views/admin/GlobalPromptManage.vue'),
        },
        {
          path: 'metrics',
          name: 'MetricsManage',
          component: () => import('../views/admin/MetricsManage.vue'),
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('../views/NotFound.vue'),
    },
  ],
})

export default router
