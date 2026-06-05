<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.push('/admin/stories')">← 返回故事列表</el-button>
        <h2>状态字段配置 - {{ story?.title }}</h2>
      </div>
      <el-button type="primary" @click="addField">添加字段</el-button>
    </div>

    <el-card v-loading="loading">
      <div v-if="fields.length === 0" class="empty">暂无状态字段，点击"添加字段"开始配置</div>

      <div v-for="(field, idx) in fields" :key="idx" class="field-row">
        <el-input v-model="field.key" placeholder="字段key" class="field-key" />
        <el-input v-model="field.label" placeholder="显示名称" class="field-label" />
        <el-select v-model="field.type" class="field-type">
          <el-option label="数值" value="number" />
          <el-option label="文本" value="text" />
        </el-select>
        <template v-if="field.type === 'number'">
          <el-input-number
            v-model="field.default"
            placeholder="默认值"
            :controls="false"
            class="field-default-num"
          />
          <el-input-number
            v-model="field.min"
            placeholder="最小"
            :controls="false"
            class="field-min"
          />
          <el-input-number
            v-model="field.max"
            placeholder="最大"
            :controls="false"
            class="field-max"
          />
        </template>
        <template v-else>
          <el-input v-model="field.default" placeholder="默认值" class="field-default-text" />
        </template>
        <el-button type="danger" text @click="fields.splice(idx, 1)">删除</el-button>
      </div>

      <div v-if="fields.length > 0" class="save-bar">
        <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStory, updateStory } from '../../api'
import { useStoryStore } from '../../stores/story'

const route = useRoute()
const storyId = Number(route.params.storyId)

const story = ref<any>(null)
const fields = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const storyStore = useStoryStore()

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await getStory(storyId)
    story.value = data
    fields.value = JSON.parse(JSON.stringify(data.state_config || []))
  } finally {
    loading.value = false
  }
})

function addField() {
  fields.value.push({ key: '', label: '', type: 'number', default: 0, min: 0, max: 100 })
}

async function handleSave() {
  // 验证
  for (const f of fields.value) {
    if (!f.key || !f.label) {
      ElMessage.warning('每个字段的 key 和名称不能为空')
      return
    }
  }
  saving.value = true
  try {
    await updateStory(storyId, { state_config: fields.value })
    ElMessage.success('已保存')
    storyStore.broadcastStories()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.page-header h2 {
  font-size: 20px;
  color: var(--text-primary);
  margin-top: 4px;
}
.field-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.save-bar {
  margin-top: 20px;
}
.empty {
  color: var(--text-muted);
  text-align: center;
  padding: 40px 0;
}

.field-key,
.field-label {
  flex: 0 0 120px;
  min-width: 100px;
}

.field-type {
  flex: 0 0 100px;
  min-width: 80px;
}

.field-default-num,
.field-min,
.field-max {
  flex: 0 0 80px;
  min-width: 60px;
}

.field-default-text {
  flex: 1 1 150px;
  min-width: 120px;
}

@media (max-width: 767px) {
  .field-row {
    gap: 6px;
  }

  .field-key,
  .field-label {
    flex: 1 1 100%;
  }

  .field-type {
    flex: 1 1 45%;
  }

  .field-default-num,
  .field-min,
  .field-max {
    flex: 1 1 60px;
  }

  .field-default-text {
    flex: 1 1 100%;
  }
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
