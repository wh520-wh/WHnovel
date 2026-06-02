<template>
  <div class="table-scroll-mobile">
    <div class="page-header">
      <h2>模型配置</h2>
      <div class="header-actions">
        <el-button type="danger" plain :disabled="selectedIds.length === 0" @click="handleBulkDelete">
          批量删除
        </el-button>
        <el-button type="primary" @click="openDialog()">添加模型</el-button>
      </div>
    </div>

    <div class="filter-row">
      <el-radio-group v-model="typeFilter" size="small">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="chat">文字模型</el-radio-button>
        <el-radio-button value="image">图片模型</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="filteredModels" stripe v-loading="loading" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="48" />
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="model_id" label="模型 ID" width="180" />
      <el-table-column label="API 地址" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.model_type === MODEL_TYPE_IMAGE ? row.image_api_base : row.api_base_url }}
        </template>
      </el-table-column>
      <el-table-column label="Key" width="90">
        <template #default="{ row }">
          <el-tag :type="row.has_api_key ? 'success' : 'info'" size="small">
            {{ row.has_api_key ? '已配置' : '未配置' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="调用" width="70">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="80" />
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag :type="row.model_type === MODEL_TYPE_IMAGE ? 'warning' : 'info'" size="small">
            {{ row.model_type === MODEL_TYPE_IMAGE ? '图片' : '文字' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" :loading="testingIds.has(row.id)" :disabled="testingIds.has(row.id)" @click="handleTest(row.id, row.name)">检测</el-button>
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <Transition name="batch-bar">
      <div v-if="selectedIds.length > 0" class="batch-action-bar">
        <span class="batch-tip">已选择 {{ selectedIds.length }} 个模型</span>
        <el-button size="small" @click="handleBatchToggle(1)">启用</el-button>
        <el-button size="small" @click="handleBatchToggle(0)">禁用</el-button>
        <el-divider direction="vertical" />
        <el-button size="small" type="danger" @click="handleBulkDelete">删除</el-button>
      </div>
    </Transition>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模型' : '添加模型'" width="500px">
      <el-form :model="form" label-width="115px">
        <el-form-item label="模型类型">
          <el-radio-group v-model="form.model_type">
            <el-radio :value="MODEL_TYPE_CHAT">文字模型</el-radio>
            <el-radio :value="MODEL_TYPE_IMAGE">图片模型</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="如：GPT-4" />
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" label="模型 ID">
          <el-input v-model="form.model_id" placeholder="如：gpt-4" />
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" label="API 模式">
          <el-select v-model="form.api_mode" style="width: 100%;">
            <el-option
              v-for="opt in API_MODE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" label="API 地址">
          <el-input
            v-model="form.api_base_url"
            :placeholder="form.api_mode === 'custom_chat' ? '输入完整 API 地址' : 'https://api.openai.com'"
          />
          <p class="api-suffix-hint">{{ fullApiUrl }}</p>
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_IMAGE" label="图片模型 ID">
          <el-input v-model="form.image_model_id" placeholder="如：doubao-seedream-5-0-260128" />
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_IMAGE" label="图片 API 模式">
          <el-select v-model="form.image_api_mode" style="width: 100%;">
            <el-option
              v-for="opt in IMAGE_API_MODE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_IMAGE" label="图片 API Base">
          <el-input
            v-model="form.image_api_base"
            :placeholder="form.image_api_mode === 'comfyui' ? 'http://127.0.0.1:8188' : (form.image_api_mode === 'custom_image' || form.image_api_mode === 'minimax_images' ? '输入完整 API 地址' : '如：https://api.openai.com')"
          />
          <p class="api-suffix-hint">{{ fullApiUrl }}</p>
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_IMAGE && form.image_api_mode !== 'comfyui'" label="图片 API Key">
          <el-input v-model="form.image_api_key" type="password" show-password placeholder="图片模型专用 Key" />
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_IMAGE && form.image_api_mode === 'comfyui'" label="Workflow 模板">
          <el-input v-model="form.image_workflow_template" type="textarea" :rows="8" placeholder="粘贴 ComfyUI 导出的 workflow JSON（提示词文本替换为 {prompt}）" />
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" label="API Key">
          <el-input v-model="form.api_key" type="password" show-password placeholder="留空表示保留旧 Key" />
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" label="温度 (Temperature)">
          <div style="display: flex; flex-direction: column; gap: 8px; width: 100%;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <el-slider
                v-model="tempValue"
                :min="0"
                :max="1"
                :step="0.05"
                :show-tooltip="false"
                style="flex: 1;"
              />
              <span style="min-width: 44px; text-align: right; font-weight: 600; font-variant-numeric: tabular-nums;">
                {{ tempValue.toFixed(2) }}
              </span>
            </div>
            <el-radio-group v-model="tempValue" size="small">
              <el-radio-button label="精确" :value="0.3" />
              <el-radio-button label="均衡" :value="0.7" />
              <el-radio-button label="创意" :value="0.9" />
            </el-radio-group>
            <el-button size="small" text @click="tempValue = 0.7; form.temperature = null">
              恢复默认 (0.7)
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="参与 AI 调用">
          <el-switch v-model="isEnabled" />
          <p class="api-suffix-hint">关闭后该模型不会被聊天、故事生成等调用选中</p>
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" label="结构化输出格式">
          <el-select v-model="form.response_format_mode" style="width: 100%;">
            <el-option label="JSON Schema（严格模式）" value="json_schema" />
            <el-option label="JSON Object（兼容模式）" value="json_object" />
          </el-select>
          <p class="api-suffix-hint">若模型不支持 JSON Schema 会产生额外 400 请求，可切换为 JSON Object</p>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" label="计费单位">
          <el-radio-group v-model="form.pricing_unit">
            <el-radio value="per_1k">每 1K tokens</el-radio>
            <el-radio value="per_1m">每 1M tokens</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" :label="'输入单价/' + (form.pricing_unit === 'per_1m' ? '1M' : '1K')">
          <div style="display: flex; gap: 8px; align-items: center;">
            <el-select v-model="priceInputEnabled" style="width: 90px;">
              <el-option label="无" :value="false" />
              <el-option label="自定义" :value="true" />
            </el-select>
            <el-input-number
              v-if="priceInputEnabled"
              v-model="form.price_input_per_1k"
              :precision="6"
              :min="0"
              :step="0.0001"
              style="flex: 1;"
            />
          </div>
        </el-form-item>
        <el-form-item v-if="form.model_type === MODEL_TYPE_CHAT" :label="'输出单价/' + (form.pricing_unit === 'per_1m' ? '1M' : '1K')">
          <div style="display: flex; gap: 8px; align-items: center;">
            <el-select v-model="priceOutputEnabled" style="width: 90px;">
              <el-option label="无" :value="false" />
              <el-option label="自定义" :value="true" />
            </el-select>
            <el-input-number
              v-if="priceOutputEnabled"
              v-model="form.price_output_per_1k"
              :precision="6"
              :min="0"
              :step="0.0001"
              style="flex: 1;"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createModel, deleteModel, getModels, testModelConnection, updateModel } from '../../api'
import { MODEL_TYPE_CHAT, MODEL_TYPE_IMAGE } from '../../constants/modelTypes'

const API_MODE_OPTIONS = [
  { label: 'OpenAI API 兼容', value: 'openai_chat_completions' },
  { label: 'OpenAI Responses API', value: 'openai_responses' },
  { label: 'Claude API', value: 'claude_messages' },
  { label: 'Google Gemini API', value: 'gemini_generate_content' },
  { label: '自定义', value: 'custom_chat' },
]

const IMAGE_API_MODE_OPTIONS = [
  { label: 'OpenAI Images API', value: 'openai_images' },
  { label: 'MiniMax 图片生成', value: 'minimax_images' },
  { label: 'ComfyUI 本地', value: 'comfyui' },
  { label: '自定义', value: 'custom_image' },
]

const API_MODE_SUFFIX: Record<string, string> = {
  openai_chat_completions: '/v1/chat/completions',
  openai_responses: '/v1/responses',
  claude_messages: '/v1/messages',
  gemini_generate_content: '/v1beta/models/{model_id}:generateContent',
  openai_images: '/v1/images/generations',
  custom_image: '',
  comfyui: '',
  custom_chat: '',
}

const models = ref<any[]>([])
const selectedIds = ref<number[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const testingIds = ref<Set<number>>(new Set())
const isEnabled = ref(true)
const typeFilter = ref('')
const priceInputEnabled = ref(false)
const priceOutputEnabled = ref(false)
const filteredModels = computed(() => {
  if (!typeFilter.value) return models.value
  return models.value.filter((m) => m.model_type === typeFilter.value)
})

const form = reactive({
  name: '',
  model_id: '',
  api_base_url: '',
  api_key: '',
  priority: 100,
  price_input_per_1k: null,
  price_output_per_1k: null,
  pricing_unit: 'per_1k' as string,
  model_type: 'chat',
  image_api_base: '',
  image_api_key: '',
  image_model_id: '',
  api_mode: 'openai_chat_completions',
  image_api_mode: 'openai_images',
  image_workflow_template: '',
  temperature: null as number | null,
  response_format_mode: 'json_schema' as string,
})

const tempValue = computed({
  get: () => form.temperature ?? 0.7,
  set: (v: number) => { form.temperature = v },
})

const fullApiUrl = computed(() => {
  const isImage = form.model_type === MODEL_TYPE_IMAGE
  const mode = isImage ? form.image_api_mode : form.api_mode
  if (isImage) {
    const imgBase = (form.image_api_base || '').trim()
    if (mode === 'custom_image' || mode === 'minimax_images' || mode === 'comfyui') {
      return imgBase
    }
    return imgBase ? `${imgBase.replace(/\/+$/, '')}${API_MODE_SUFFIX[mode] || ''}` : ''
  }
  if (!isImage && mode === 'custom_chat') {
    return (form.api_base_url || '').trim()
  }
  const base = (form.api_base_url || '').trim().replace(/\/+$/, '')
  let suffix = API_MODE_SUFFIX[mode] || ''
  if (mode === 'gemini_generate_content' && form.model_id) {
    suffix = suffix.replace('{model_id}', form.model_id)
  }
  return base ? `${base}${suffix}` : ''
})

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getModels()
    models.value = data
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(rows: any[]) {
  selectedIds.value = rows.map((row) => row.id)
}

function openDialog(row?: any) {
  if (row) {
    editingId.value = row.id
    Object.assign(form, {
      name: row.name,
      model_id: row.model_type === MODEL_TYPE_CHAT ? row.model_id : '',
      api_base_url: row.api_base_url,
      api_key: '',
      priority: row.priority,
      price_input_per_1k: row.price_input_per_1k,
      price_output_per_1k: row.price_output_per_1k,
      priceInputEnabled: !!(row.price_input_per_1k),
      priceOutputEnabled: !!(row.price_output_per_1k),
      model_type: row.model_type || MODEL_TYPE_CHAT,
      image_api_base: row.image_api_base || '',
      image_api_key: '',
      image_model_id: row.model_type === MODEL_TYPE_IMAGE ? row.model_id : '',
      api_mode: row.api_mode || 'openai_chat_completions',
      image_api_mode: row.image_api_mode || 'openai_images',
      image_workflow_template: row.image_workflow_template || '',
      pricing_unit: row.pricing_unit || 'per_1k',
      temperature: row.temperature ?? null,
      response_format_mode: row.response_format_mode || 'json_schema',
    })
    isEnabled.value = !!row.enabled
  } else {
    editingId.value = null
    Object.assign(form, {
      name: '',
      model_id: '',
      api_base_url: '',
      api_key: '',
      priority: 100,
      price_input_per_1k: 0,
      price_output_per_1k: 0,
      model_type: MODEL_TYPE_CHAT,
      image_api_base: '',
      image_api_key: '',
      image_model_id: '',
      api_mode: 'openai_chat_completions',
      image_api_mode: 'openai_images',
      image_workflow_template: '',
      pricing_unit: 'per_1k',
      temperature: null,
      response_format_mode: 'json_schema',
    })
    isEnabled.value = true
  }
  dialogVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    const payload = {
      ...form,
      enabled: isEnabled.value ? 1 : 0,
      // 图片模型用 image_model_id 作为 model_id
      model_id: form.model_type === MODEL_TYPE_IMAGE ? form.image_model_id : form.model_id,
    }
    if (editingId.value) {
      await updateModel(editingId.value, payload)
    } else {
      await createModel(payload)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await fetchList()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该模型？', '确认', { type: 'warning' })
    await deleteModel(id)
    ElMessage.success('已删除')
    await fetchList()
  } catch {
    // ignore cancel
  }
}

async function handleBatchToggle(enabled: 0 | 1) {
  const action = enabled === 1 ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定${action}选中的 ${selectedIds.value.length} 个模型？`, '确认', { type: 'warning' })
    const results = await Promise.allSettled(selectedIds.value.map(id => updateModel(id, { enabled })))
    const failed = results.filter(r => r.status === 'rejected')
    selectedIds.value = []
    await fetchList()
    if (failed.length === 0) {
      ElMessage.success(`批量${action}成功，共 ${results.length} 项`)
    } else {
      ElMessage.warning(`成功 ${results.length - failed.length} 项，失败 ${failed.length} 项`)
    }
  } catch {
    // 用户取消
  }
}

async function handleBulkDelete() {
  if (selectedIds.value.length === 0) return

  try {
    await ElMessageBox.confirm(`确定批量删除 ${selectedIds.value.length} 个模型？`, '确认', { type: 'warning' })
    const results = await Promise.allSettled(selectedIds.value.map((id) => deleteModel(id)))
    const failed = results.filter((result) => result.status === 'rejected')
    selectedIds.value = []
    await fetchList()
    if (failed.length === 0) {
      ElMessage.success(`批量删除完成，共删除 ${results.length} 项`)
    } else {
      ElMessage.warning(`批量删除完成，成功 ${results.length - failed.length} 项，失败 ${failed.length} 项`)
    }
  } catch {
    // ignore cancel
  }
}

async function handleTest(modelId: number, modelName: string) {
  testingIds.value.add(modelId)
  try {
    const res = await testModelConnection(modelId)
    if (res.data.success) {
      ElMessage.success(`模型「${modelName}」检测成功，响应 ${res.data.duration_ms}ms`)
    } else {
      ElMessage.error(`模型「${modelName}」检测失败：${res.data.error}`)
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    ElMessage.error(`模型「${modelName}」检测失败：${msg}`)
  } finally {
    testingIds.value.delete(modelId)
  }
}

onMounted(fetchList)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 20px;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-row {
  margin-bottom: 16px;
}

/* Glass el-table */
:deep(.el-table) {
  background: transparent;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: color-mix(in srgb, var(--accent-color) 8%, transparent);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.el-table th.el-table__cell) {
  background: color-mix(in srgb, var(--accent-color) 10%, transparent) !important;
  color: var(--text-primary);
  font-weight: 600;
  border-bottom: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid color-mix(in srgb, var(--accent-color) 10%, transparent);
}

:deep(.el-table__body tr:hover > td.el-table__cell) {
  background: color-mix(in srgb, var(--accent-color) 6%, transparent) !important;
}

:deep(.el-table--stripe .el-table__body tr.el-table__row--striped > td.el-table__cell) {
  background: color-mix(in srgb, var(--accent-color) 3%, transparent);
}

/* Glass el-dialog */
:deep(.el-dialog) {
  background: var(--admin-card-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 30%, transparent);
  border-radius: 20px;
  box-shadow: 0 0 40px color-mix(in srgb, var(--accent-color) 20%, transparent), 0 0 80px color-mix(in srgb, var(--accent-color) 10%, transparent);
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  padding: 16px 20px;
  margin-right: 0;
}

:deep(.el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

:deep(.el-dialog__headerbtn) {
  width: 28px;
  height: 28px;
  background: color-mix(in srgb, var(--accent-color) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 50%;
  top: 12px;
  right: 16px;
}

:deep(.el-dialog__headerbtn:hover) {
  background: color-mix(in srgb, var(--accent-color) 20%, transparent);
}

:deep(.el-dialog__headerbtn .el-dialog__close) {
  color: var(--text-secondary);
}

:deep(.el-dialog__body) {
  padding: 16px 20px;
}

/* Glass el-form */
:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: var(--admin-input-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 10px;
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
  :deep(.el-dialog),
  :deep(.el-table) {
    transition: none;
  }
}

.batch-action-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin-top: 12px;
  background: var(--bg-card);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 12px;
}
.batch-tip {
  font-size: 13px;
  color: var(--text-secondary);
  margin-right: 4px;
}
.batch-bar-enter-active,
.batch-bar-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}
.batch-bar-enter-from,
.batch-bar-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (max-width: 767px) {
  .batch-action-bar {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 12px;
  }
  .batch-tip {
    width: 100%;
    margin-right: 0;
    margin-bottom: 2px;
  }
}

.api-suffix-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
  word-break: break-all;
}
</style>
