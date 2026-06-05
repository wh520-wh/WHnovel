<template>
  <div class="table-scroll-mobile">
    <div class="page-header">
      <h2>全局提示词</h2>
    </div>

    <el-card v-loading="loading" class="section-card">
      <template #header>
        <span>全局默认系统提示词（每次聊天都会注入）</span>
      </template>
      <div class="prompt-source">
        <span class="source-label">当前来源：</span>
        <el-tag size="small" effect="dark">{{ promptSourceLabel }}</el-tag>
        <span class="source-desc">{{ promptSourceDesc }}</span>
      </div>
      <el-input
        v-model="promptText"
        type="textarea"
        :rows="12"
        placeholder="请输入全局系统提示词"
      />
    </el-card>

    <el-card v-loading="loading" class="section-card">
      <template #header>
        <span>状态播报提示词</span>
      </template>
      <p class="prompt-hint">
        用户点击「生成状态」时，AI 将以此提示词结合对话上下文生成状态播报消息。留空则禁用该功能。
      </p>
      <el-input
        v-model="stateBroadcastPrompt"
        type="textarea"
        :rows="6"
        :placeholder="stateBroadcastPlaceholder"
      />
    </el-card>

    <div class="actions">
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </div>

    <el-card class="section-card">
      <template #header>
        <span>提示词组合顺序（固定）</span>
      </template>
      <ol class="order-list">
        <li>全局默认系统提示词</li>
        <li>故事专属系统提示词</li>
        <li>故事世界观提示词</li>
        <li>结构化输出规则</li>
        <li>最近上下文</li>
      </ol>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAppSettings, updateAppSettings, getErrorMessage } from '../../api'

const loading = ref(false)
const saving = ref(false)

const promptText = ref('')
const promptSource = ref<'example_default' | 'custom' | 'empty' | string>('custom')
const stateBroadcastPrompt = ref('')

const stateBroadcastPlaceholder =
  '请根据当前小说世界观和上下文，生成角色/剧情状态的键值对列表。\n\n要求：\n- 根据小说设定和当前剧情上下文自行判断应展示哪些属性，不要使用固定字段列表\n- 每行一个属性，格式为：属性名 | 属性值\n- 空值显示"无"，不省略\n- 仅输出键值对，不要任何解释或描述\n\n示例（仅供参考，实际字段由AI根据上下文自行判断）：\n地点 | 废弃神社后院\n时间 | 子夜\n情绪 | 警觉中带着不安'
const promptSourceLabel = computed(() => {
  if (promptSource.value === 'example_default') return '示例默认提示词'
  if (promptSource.value === 'custom') return '后台自定义内容'
  return '空值（将触发回填）'
})
const promptSourceDesc = computed(() => {
  if (promptSource.value === 'example_default') {
    return '来自内置默认提示词的自动注入或回填。'
  }
  if (promptSource.value === 'custom') {
    return '来自后台保存的非空内容，不会被自动覆盖。'
  }
  return '当前为空，服务启动时会自动回填示例默认提示词。'
})

onMounted(async () => {
  loading.value = true
  try {
    const { data: appSettings } = await getAppSettings()
    promptText.value = appSettings.default_system_prompt || ''
    promptSource.value = appSettings.default_system_prompt_source || 'custom'
    stateBroadcastPrompt.value = appSettings.state_broadcast_prompt || ''
  } finally {
    loading.value = false
  }
})

async function handleSave() {
  saving.value = true
  try {
    await updateAppSettings({
      default_system_prompt: promptText.value,
      state_broadcast_prompt: stateBroadcastPrompt.value,
    })
    const { data } = await getAppSettings()
    promptSource.value = data.default_system_prompt_source || 'custom'
    promptText.value = data.default_system_prompt || ''
    stateBroadcastPrompt.value = data.state_broadcast_prompt || ''
    ElMessage.success('已保存')
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '保存失败'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  font-size: 20px;
  color: var(--text-primary);
}
.section-card {
  margin-bottom: 16px;
}
.prompt-source {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}
.source-label {
  color: var(--text-muted);
}
.source-desc {
  color: var(--text-secondary);
}
.actions {
  margin-top: 12px;
}
.order-list {
  color: var(--text-primary);
  line-height: 1.9;
  padding-left: 18px;
}
.prompt-hint {
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 10px;
  line-height: 1.6;
}

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
  :deep(.el-card) {
    transition: none;
  }
}
</style>
