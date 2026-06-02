<template>
  <div class="settings-mobile-page">
    <header class="settings-mobile-header">
      <button type="button" class="header-back mobile-action-btn" @click="handleBack">返回</button>
      <h1 class="header-title">{{ pageTitle }}</h1>
      <button
        v-if="isSectionPage"
        type="button"
        class="header-reset mobile-action-btn"
        @click="handleReset"
      >
        重置
      </button>
      <span v-else class="header-spacer" aria-hidden="true" />
    </header>

    <main class="settings-mobile-body" v-if="!isSectionPage">
      <button
        v-for="section in sectionList"
        :key="section"
        type="button"
        class="settings-mobile-card mobile-surface mobile-control-card"
        @click="openSection(section)"
      >
        {{ SETTINGS_SECTION_TITLES[section] }}
      </button>
    </main>

    <main class="settings-mobile-body settings-mobile-detail settings-mobile-scroll" :style="{ '--settings-mobile-detail-bottom': detailBottomSpacing }" v-else>
      <section v-if="currentSection === 'app'" class="detail-section">
        <label class="field-block mobile-surface">
          <span class="field-label">全局默认系统提示词</span>
          <el-input v-model="form.default_system_prompt" type="textarea" autosize resize="none" />
        </label>
        <label class="field-block mobile-surface">
          <span class="field-label">状态播报提示词</span>
          <el-input v-model="form.state_broadcast_prompt" type="textarea" autosize resize="none" />
        </label>
      </section>

      <section v-else-if="currentSection === 'image'" class="detail-section">
        <label class="field-block mobile-surface">
          <span class="field-label">使用模型</span>
          <ModelSelect
            v-model="form.default_image_model_id"
            :options="imageModels"
            placeholder="选择图片模型"
          />
        </label>

        <div class="field-block mobile-surface">
          <span class="field-label">图片尺寸</span>
          <div class="choice-row">
            <button
              type="button"
              :class="{ active: form.image_size === '1K' }"
              @click="form.image_size = '1K'"
            >
              1K
            </button>
            <button
              type="button"
              :class="{ active: form.image_size === '2K' }"
              @click="form.image_size = '2K'"
            >
              2K
            </button>
            <button
              type="button"
              :class="{ active: form.image_size === '3K' }"
              @click="form.image_size = '3K'"
            >
              3K
            </button>
          </div>
        </div>

        <label class="field-row mobile-surface">
          <span class="field-label">添加水印</span>
          <input v-model="form.image_watermark" type="checkbox" />
        </label>

        <label class="field-block mobile-surface">
          <span class="field-label">全局风格</span>
          <el-input
            v-model="form.default_image_style"
            type="textarea"
            autosize
            resize="none"
          />
        </label>
      </section>

      <section v-else-if="currentSection === 'model'" class="detail-section">
        <label class="field-block mobile-surface">
          <span class="field-label">主用模型</span>
          <ModelSelect v-model="form.primary_model_id" :options="enabledModels" placeholder="请选择主用模型" />
        </label>

        <div class="field-block mobile-surface">
          <span class="field-label">备用模型</span>
          <div class="backup-list" v-if="form.backup_model_ids.length > 0">
            <div v-for="(id, idx) in form.backup_model_ids" :key="`${id}-${idx}`" class="backup-item">
              <span class="backup-name">{{ modelNameById(id) }}</span>
              <div class="backup-actions">
                <button type="button" @click="moveBackupUp(idx)" :disabled="idx === 0">上移</button>
                <button type="button" @click="moveBackupDown(idx)" :disabled="idx === form.backup_model_ids.length - 1">下移</button>
                <button type="button" @click="removeBackup(idx)">删除</button>
              </div>
            </div>
          </div>
          <div v-else class="backup-empty">暂无备用模型</div>

          <div class="backup-add-row">
            <ModelSelect v-model="backupCandidateId" :options="backupCandidates" placeholder="选择备用模型" />
            <button type="button" @click="addBackup" :disabled="!backupCandidateId">添加</button>
          </div>
        </div>
      </section>

      <section v-else-if="currentSection === 'interaction'" class="detail-section">
        <label class="field-block mobile-surface">
          <span class="field-label">上下文长度</span>
          <input v-model.number="form.context_length" type="range" min="2" max="30" step="1" />
          <span class="field-hint">{{ form.context_length }} 轮</span>
        </label>

        <div class="field-block mobile-surface">
          <span class="field-label">回复风格</span>
          <div class="choice-row">
            <button
              v-for="style in replyStyles"
              :key="style.value"
              type="button"
              :class="{ active: form.reply_style === style.value }"
              @click="form.reply_style = style.value"
            >
              {{ style.label }}
            </button>
          </div>
        </div>

        <label class="field-row mobile-surface">
          <span class="field-label">自动生成选项</span>
          <input v-model="form.auto_generate_options" type="checkbox" />
        </label>

        <div class="field-block mobile-surface">
          <span class="field-label">复制图片格式</span>
          <div class="choice-row">
            <button type="button" :class="{ active: form.copy_image_format === 'url' }" @click="form.copy_image_format = 'url'">URL</button>
            <button type="button" :class="{ active: form.copy_image_format === 'binary' }" @click="form.copy_image_format = 'binary'">图片</button>
          </div>
        </div>

        <label class="field-row mobile-surface">
          <span class="field-label">关闭聊天气泡弹性效果</span>
          <input v-model="form.disable_chat_bubble_elastic" type="checkbox" />
        </label>

        <label class="field-row mobile-surface">
          <span class="field-label">管理员模式</span>
          <input v-model="adminModeEnabled" type="checkbox" @change="handleAdminModeToggle" />
        </label>
      </section>

      <section v-else-if="currentSection === 'plot'" class="detail-section">
        <label class="field-block mobile-surface">
          <span class="field-label">选项提示词</span>
          <el-input v-model="form.options_prompt" type="textarea" autosize resize="none" />
        </label>
      </section>

      <section v-else-if="currentSection === 'appearance'" class="detail-section">
        <div class="field-block mobile-surface">
          <span class="field-label">主题</span>
          <div class="choice-row">
            <button type="button" :class="{ active: themeStore.theme === 'dark' }" @click="themeStore.setTheme('dark')">暗色</button>
            <button type="button" :class="{ active: themeStore.theme === 'light' }" @click="themeStore.setTheme('light')">亮色</button>
            <button type="button" :class="{ active: themeStore.theme === 'enigma' }" @click="themeStore.setTheme('enigma')">Enigma</button>
            <button type="button" :class="{ active: themeStore.theme === 'claude' }" @click="themeStore.setTheme('claude')">Claude</button>
          </div>
        </div>
        <label class="field-row mobile-surface">
          <span class="field-label">聊天背景图</span>
          <input v-model="form.show_background_image" type="checkbox" />
        </label>
      </section>
    </main>

    <footer ref="footerRef" class="settings-mobile-footer mobile-surface" v-if="isSectionPage">
      <button type="button" class="save-btn" :disabled="saving" @click="handleSave">
        {{ saving ? '保存中...' : '保存设置' }}
      </button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ModelSelect from '../components/ModelSelect.vue'
import { useThemeStore } from '../stores/theme'
import {
  ALLOWED_SETTINGS_SECTIONS,
  SETTINGS_SECTION_TITLES,
  type SettingsSection,
  useSettingsForm,
} from '../composables/useSettingsForm'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const footerRef = ref<HTMLElement | null>(null)
const {
  form,
  models,
  saving,
  backupCandidateId,
  adminModeEnabled,
  enabledModels,
  backupCandidates,
  imageModels,
  loadSettings,
  saveSettings,
  resetSettings,
  addBackup,
  removeBackup,
  moveBackupUp,
  moveBackupDown,
} = useSettingsForm()

const sectionList = ALLOWED_SETTINGS_SECTIONS
const replyStyles = [
  { value: 'concise', label: '简洁 (~173字)' },
  { value: 'detailed', label: '详细 (~280字)' },
  { value: 'creative', label: '创意 (~360字)' },
]

const currentSection = computed<SettingsSection | null>(() => {
  const raw = String(route.params.section || '')
  return ALLOWED_SETTINGS_SECTIONS.includes(raw as SettingsSection)
    ? (raw as SettingsSection)
    : null
})

const isSectionPage = computed(() => currentSection.value !== null)
const pageTitle = computed(() =>
  currentSection.value ? SETTINGS_SECTION_TITLES[currentSection.value] : '设置',
)
const detailBottomSpacing = computed(() => {
  const footerHeight = footerRef.value?.offsetHeight ?? 0
  return `${footerHeight + 12}px`
})

onMounted(async () => {
  await loadSettings()
})

function openSection(section: SettingsSection) {
  router.push({ path: `/settings-mobile/${section}`, query: route.query })
}

function modelNameById(id: number) {
  const model = models.value.find((m) => m.id === id)
  return model ? `${model.name} (${model.model_id})` : `模型 #${id}`
}

function handleAdminModeToggle() {
  if (adminModeEnabled.value) {
    localStorage.setItem('admin_mode', '1')
  } else {
    localStorage.removeItem('admin_mode')
  }
  window.dispatchEvent(new Event('admin-mode-changed'))
}

async function handleSave() {
  await saveSettings()
}

async function handleReset() {
  await resetSettings()
}

function handleBack() {
  if (isSectionPage.value) {
    router.push({ path: '/settings-mobile', query: route.query })
    return
  }

  const from = String(route.query.from || '')
  const storyId = Number(route.query.storyId)
  const archiveId = Number(route.query.archiveId)

  if (from === 'play' && Number.isFinite(storyId) && storyId > 0) {
    const query: Record<string, string> = {}
    if (Number.isFinite(archiveId) && archiveId > 0) {
      query.archiveId = String(archiveId)
    }
    router.push({ path: `/play/${storyId}`, query })
    return
  }

  router.push('/')
}
</script>

<style scoped>
.settings-mobile-page {
  --mobile-surface-radius: 12px;
  --mobile-control-radius: 10px;

  min-height: 100%;
  height: 100%;
  width: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.mobile-surface {
  border: 1px solid var(--border-color);
  border-radius: var(--mobile-surface-radius);
  background: var(--bg-card);
  color: var(--text-primary);
}

.settings-mobile-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 12px;
}

.header-title {
  margin: 0;
  text-align: center;
  font-size: 16px;
}

.header-reset,
.header-back,
.settings-mobile-card {
  width: 100%;
}

.header-back,
.header-reset {
  width: auto;
}

.mobile-action-btn {
  min-width: 44px;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition:
    background var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-smooth);
}

.mobile-action-btn:hover,
.mobile-action-btn:focus-visible {
  background: var(--bg-hover);
  border-color: color-mix(in srgb, var(--accent-color) 45%, var(--border-color));
  color: var(--text-primary);
}

.header-spacer {
  display: block;
  width: 40px;
}

.settings-mobile-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  min-height: 0;
}

.settings-mobile-card {
  display: block;
  text-align: left;
  padding: 12px;
  border-radius: var(--mobile-surface-radius);
  min-height: 44px;
  font: inherit;
  color: var(--text-primary);
  cursor: pointer;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-smooth);
}

.settings-mobile-card:hover,
.settings-mobile-card:focus-visible {
  background: var(--bg-hover);
  border-color: color-mix(in srgb, var(--accent-color) 45%, var(--border-color));
}

.settings-mobile-detail {
  flex: 1;
  padding-bottom: calc(var(--settings-mobile-detail-bottom, 108px) + env(safe-area-inset-bottom));
}

.settings-mobile-scroll {
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-block,
.field-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.field-row {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.field-label {
  font-size: 14px;
  line-height: 1.4;
}

.field-hint {
  font-size: 12px;
  opacity: 0.75;
}

.choice-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.header-back,
.header-reset,
.save-btn,
.choice-row button,
.backup-actions button,
.backup-add-row button {
  border-radius: var(--mobile-control-radius);
}

.choice-row button,
.backup-actions button,
.backup-add-row button {
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-primary);
  font: inherit;
  cursor: pointer;
  transition:
    background var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth),
    transform var(--duration-fast) var(--ease-smooth);
}

.choice-row button:hover:not(:disabled),
.backup-actions button:hover:not(:disabled),
.backup-add-row button:hover:not(:disabled),
.choice-row button:focus-visible,
.backup-actions button:focus-visible,
.backup-add-row button:focus-visible {
  background: var(--bg-hover);
  border-color: color-mix(in srgb, var(--accent-color) 45%, var(--border-color));
}

.choice-row button:disabled,
.backup-actions button:disabled,
.backup-add-row button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.header-back:active,
.header-reset:active,
.settings-mobile-card:active,
.save-btn:active,
.choice-row button:active,
.backup-actions button:active,
.backup-add-row button:active {
  transform: translateY(1px);
}

.choice-row button.active {
  border-color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 16%, var(--bg-input));
  color: var(--text-primary);
}

.backup-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.backup-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.backup-name {
  word-break: break-all;
}

.backup-actions,
.backup-add-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.settings-mobile-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border-color);
  background: var(--bg-elevated, var(--bg-card));
}

.save-btn {
  width: 100%;
  padding: 12px;
  min-height: 44px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-primary);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.save-btn:hover:not(:disabled),
.save-btn:focus-visible {
  background: var(--bg-hover);
  border-color: color-mix(in srgb, var(--accent-color) 45%, var(--border-color));
}

.save-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 767px) {
  .choice-row button,
  .backup-actions button,
  .backup-add-row button {
    min-height: 44px;
  }
}
</style>
