<template>
  <div class="prompt-manage table-scroll-mobile">
    <div class="page-header">
      <div>
        <el-button text @click="$router.push('/admin/stories')">← 返回故事列表</el-button>
        <h2>提示词管理 - {{ story?.title }}</h2>
      </div>
    </div>

    <div class="main-layout">
      <!-- 左栏：编辑器 -->
      <div class="editor-panel">
        <el-card v-loading="loading">
          <el-form label-width="100px" label-position="top">
            <el-form-item label="系统提示词（System Prompt）">
              <el-input
                v-model="systemPrompt"
                type="textarea"
                :rows="6"
                placeholder="定义AI的角色和行为规则，例如：你扮演一位温柔的女高中生..."
              />
            </el-form-item>

            <el-form-item label="世界观设定">
              <div class="section-toolbar">
                <span class="toolbar-label">插入章节：</span>
                <el-button
                  v-for="sec in SECTION_TEMPLATES"
                  :key="sec"
                  size="small"
                  @click="insertSection(sec)"
                  >{{ sec }}</el-button
                >
              </div>
              <el-input
                ref="worldSettingRef"
                v-model="worldSetting"
                type="textarea"
                :rows="14"
                placeholder="描述故事世界的背景设定，可使用 {char:N} 引用角色..."
                class="world-textarea"
                @keydown.tab.prevent="handleTab"
              />
              <div class="char-ref-hint">
                <span>引用角色格式：</span>
                <code>{char:1}</code>
                <span>（角色管理中添加后，在此插入）</span>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card style="margin-top: 14px">
          <template #header><span>提示词组合顺序（固定）</span></template>
          <ol class="order-list">
            <li>全局默认系统提示词</li>
            <li>故事专属系统提示词（本页配置）</li>
            <li>故事世界观提示词（本页配置）</li>
            <li>结构化输出规则</li>
            <li>最近上下文</li>
          </ol>
        </el-card>
      </div>

      <!-- 右栏：角色参考面板 -->
      <div class="char-panel">
        <el-card v-loading="loadingChars">
          <template #header>
            <div class="char-panel-header">
              <span>角色参考</span>
              <el-button size="small" text @click="loadCharacters">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>

          <div v-if="characters.length === 0" class="char-empty">
            暂无角色，
            <el-link type="primary" :href="`/admin/stories/${storyId}/characters`" target="_blank"
              >去添加</el-link
            >
          </div>

          <div v-for="char in characters" :key="char.id" class="char-item">
            <div class="char-info">
              <div class="char-name">{{ char.name }}</div>
              <div v-if="char.personality" class="char-trait">性格：{{ char.personality }}</div>
              <div v-if="char.background" class="char-trait">背景：{{ char.background }}</div>
            </div>
            <div class="char-actions">
              <el-button size="small" title="插入角色引用" @click="insertCharRef(char.id)">
                插入 {char:{{ char.id }}}
              </el-button>
            </div>
          </div>

          <div v-if="pendingCharRef" class="pending-ref-notice">
            <el-alert type="info" :closable="false" show-icon>
              待插入：{char:{{ pendingCharRef }}}（点击世界观输入框后生效）
            </el-alert>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getStory, updateStory, getCharacters } from '../../api'

const SECTION_TEMPLATES = [
  '【背景设定】',
  '【人物关系】',
  '【世界规则】',
  '【重要地点】',
  '【关键物品】',
  '【当前局势】',
]

const route = useRoute()
const storyId = Number(route.params.storyId)

const story = ref<any>(null)
const systemPrompt = ref('')
const worldSetting = ref('')
const loading = ref(false)
const saving = ref(false)
const worldSettingRef = ref<any>(null)
const characters = ref<any[]>([])
const loadingChars = ref(false)
const pendingCharRef = ref<number | null>(null)

async function loadStory() {
  loading.value = true
  try {
    const { data } = await getStory(storyId)
    story.value = data
    systemPrompt.value = data.system_prompt || ''
    worldSetting.value = data.world_setting || ''
  } finally {
    loading.value = false
  }
}

async function loadCharacters() {
  loadingChars.value = true
  try {
    const { data } = await getCharacters(storyId)
    characters.value = data
  } finally {
    loadingChars.value = false
  }
}

function handleTab() {
  // Allow tab insertion
  const ta = worldSettingRef.value?.$el?.querySelector('textarea')
  if (!ta) return
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const before = worldSetting.value.substring(0, start)
  const after = worldSetting.value.substring(end)
  worldSetting.value = before + '  ' + after
  // restore cursor
  setTimeout(() => {
    ta.selectionStart = ta.selectionEnd = start + 2
  }, 0)
}

function insertSection(section: string) {
  const ta = worldSettingRef.value?.$el?.querySelector('textarea')
  if (!ta) {
    // Fallback: append to end
    worldSetting.value += '\n' + section + '\n'
    return
  }
  const pos = ta.selectionStart
  const before = worldSetting.value.substring(0, pos)
  const after = worldSetting.value.substring(pos)
  worldSetting.value = before + '\n' + section + '\n' + after
  setTimeout(() => {
    ta.selectionStart = ta.selectionEnd = pos + section.length + 2
    ta.focus()
  }, 0)
}

function insertCharRef(charId: number) {
  const ref = '{char:' + charId + '}'
  const ta = worldSettingRef.value?.$el?.querySelector('textarea')
  if (!ta) {
    worldSetting.value += ref
    return
  }
  const pos = ta.selectionStart
  const before = worldSetting.value.substring(0, pos)
  const after = worldSetting.value.substring(pos)
  worldSetting.value = before + ref + after
  setTimeout(() => {
    ta.selectionStart = ta.selectionEnd = pos + ref.length
    ta.focus()
  }, 0)
  pendingCharRef.value = null
}

async function handleSave() {
  saving.value = true
  try {
    await updateStory(storyId, {
      system_prompt: systemPrompt.value,
      world_setting: worldSetting.value,
    })
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadStory(), loadCharacters()])
  // Handle pending character reference from CharacterManage
  try {
    const pending = localStorage.getItem('pending_char_ref')
    if (pending) {
      pendingCharRef.value = parseInt(pending, 10)
      localStorage.removeItem('pending_char_ref')
    }
  } catch {
    // ignore
  }
})
</script>

<style scoped>
.prompt-manage {
  padding: 20px;
  max-width: 1200px;
}

.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  font-size: 20px;
  color: var(--text-primary);
  margin-top: 4px;
}

.main-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 16px;
  align-items: start;
}

.section-toolbar {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.toolbar-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.world-textarea :deep(textarea) {
  font-family: monospace;
  font-size: 13px;
  line-height: 1.6;
}

.char-ref-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.char-ref-hint code {
  background: var(--bg-input);
  padding: 1px 5px;
  border-radius: 4px;
  color: var(--accent-color);
}

.order-list {
  color: var(--text-primary);
  line-height: 1.9;
  padding-left: 18px;
}

.char-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.char-empty {
  color: var(--text-muted);
  font-size: 13px;
  padding: 10px 0;
}

.char-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}
.char-item:last-of-type {
  border-bottom: none;
}

.char-info {
  margin-bottom: 6px;
}

.char-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.char-trait {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-actions {
  display: flex;
  gap: 4px;
}

.pending-ref-notice {
  margin-top: 10px;
}

/* Glass el-card */
:deep(.el-card) {
  background: var(--admin-card-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 16px;
  box-shadow: 0 0 20px color-mix(in srgb, var(--accent-color) 8%, transparent);
}

:deep(.el-card__header) {
  border-bottom: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  color: var(--text-primary);
  font-weight: 600;
}

/* Glass el-input/textarea */
:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: var(--admin-input-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 10px;
  box-shadow: none;
}

:deep(.el-input__wrapper:hover),
:deep(.el-textarea__inner:hover) {
  border-color: color-mix(in srgb, var(--accent-color) 40%, transparent);
}

:deep(.el-input__wrapper.is-focus),
:deep(.el-textarea__inner:focus) {
  border-color: var(--accent-color);
  box-shadow: 0 0 12px color-mix(in srgb, var(--accent-color) 20%, transparent);
}

@media (prefers-reduced-motion: reduce) {
  :deep(.el-card),
  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner) {
    transition: none;
  }
}
</style>
