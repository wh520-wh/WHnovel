<template>
  <div class="archive-list">
    <div class="archive-header">
      <h3>会话列表</h3>
      <div class="archive-actions">
        <el-select v-model="sortOrder" size="small" style="width: 100px">
          <el-option label="最新在前" value="newest" />
          <el-option label="最旧在前" value="oldest" />
        </el-select>
        <el-button size="small" @click="$emit('toggle-bulk-mode')">
          {{ bulkMode ? '取消批量' : '批量管理' }}
        </el-button>
        <el-button size="small" @click="$emit('import')">导入</el-button>
        <el-input
          v-if="!bulkMode"
          v-model="searchQuery"
          size="small"
          placeholder="搜索会话..."
          clearable
          style="width: 140px"
          :prefix-icon="Search"
        />
        <el-button size="small" type="primary" @click="$emit('create')">新建会话</el-button>
      </div>
    </div>

    <div v-if="bulkMode" class="bulk-toolbar">
      <el-checkbox
        :model-value="sortedArchives.length > 0 && selection.length === sortedArchives.length"
        :indeterminate="selection.length > 0 && selection.length < sortedArchives.length"
        @change="handleSelectAll"
      >全选</el-checkbox>
      <span class="bulk-count">已选 {{ selection.length }} 项</span>
      <el-button
        size="small"
        type="danger"
        :disabled="selection.length === 0 || deleting"
        @click="$emit('bulk-delete')"
      >
        批量删除
      </el-button>
    </div>

    <div v-if="sortedArchives.length === 0" class="empty-state-card">
      <svg class="empty-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" role="img" aria-label="暂无会话" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <span class="empty-title">暂无会话</span>
      <span class="empty-hint">开始一段新的故事旅程</span>
      <el-button type="primary" size="small" @click="$emit('create')">新建会话</el-button>
    </div>

    <div
      v-for="(arc, index) in sortedArchives"
      :key="arc.id"
      class="archive-item"
      :class="{ active: currentId === arc.id, selected: selection.includes(arc.id), bulk: bulkMode }"
      :style="{ animationDelay: `${index * 40}ms` }"
      @click="handleItemClick(arc.id)"
    >
      <el-checkbox
        v-if="bulkMode"
        :model-value="selection.includes(arc.id)"
        @change="handleCheckboxChange(arc.id, $event)"
        @click.stop
      />

      <div class="arc-main">
        <div class="arc-name" v-if="editingId !== arc.id" @dblclick="startEdit(arc)" :title="'双击重命名'">
          {{ arc.name }}
        </div>
        <el-input
          v-else
          :ref="(el: any) => editInputRefs[arc.id] = el"
          v-model="editName"
          size="small"
          class="name-edit-input"
          @keydown.enter="saveEdit(arc.id)"
          @keydown.escape="cancelEdit"
          @blur="saveEdit(arc.id)"
        />
        <div class="arc-preview" :title="arc.first_message || '暂无预览'">
          {{ arc.first_message || '暂无预览' }}
        </div>
        <div class="arc-time">{{ formatDate(arc.updated_at) }}</div>
      </div>

      <div v-if="!bulkMode" class="arc-actions">
        <el-button size="small" text @click.stop="startEdit(arc)" title="重命名">重命名</el-button>
        <el-button size="small" text @click.stop="$emit('export', arc.id)" title="导出">导出</el-button>
        <el-button size="small" text type="danger" @click.stop="$emit('delete', arc.id)" title="删除">删除</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { Archive } from '../stores/chat'

const props = defineProps<{
  archives: Archive[]
  currentId: number | null
  bulkMode: boolean
  selection: number[]
  deleting?: boolean
}>()

const emit = defineEmits(['create', 'load', 'delete', 'toggle-bulk-mode', 'selection-change', 'bulk-delete', 'rename', 'export', 'import'])

const sortOrder = ref<'newest' | 'oldest'>('newest')
const editingId = ref<number | null>(null)
const editName = ref('')
const editInputRefs = ref<Record<number, HTMLInputElement | null>>({})
const searchQuery = ref('')

function startEdit(arc: Archive) {
  editingId.value = arc.id
  editName.value = arc.name
  nextTick(() => {
    const el = editInputRefs.value[arc.id]
    if (el) el.focus()
  })
}

function saveEdit(id: number) {
  if (editingId.value !== id) return
  const name = editName.value.trim()
  if (name) {
    emit('rename', { id, name })
  }
  editingId.value = null
}

function cancelEdit() {
  editingId.value = null
}

const filteredArchives = computed(() => {
  let list = [...props.archives]
  const q = searchQuery.value.trim()
  if (q) {
    const low = q.toLowerCase()
    list = list.filter(a =>
      a.name.toLowerCase().includes(low) ||
      (a.first_message && a.first_message.toLowerCase().includes(low))
    )
  }
  return list
})

const sortedArchives = computed(() => {
  const list = [...filteredArchives.value]
  return list.sort((a, b) => sortOrder.value === 'newest' ? b.id - a.id : a.id - b.id)
})

function formatDate(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 60) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  if (days < 30) return `${Math.floor(days / 7)}周前`
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function handleItemClick(id: number) {
  if (!props.bulkMode) {
    emit('load', id)
    return
  }

  emit('selection-change', {
    id,
    checked: !props.selection.includes(id),
  })
}

function handleCheckboxChange(id: number, checked: string | number | boolean) {
  emit('selection-change', { id, checked: !!checked })
}

function handleSelectAll(checked: string | number | boolean) {
  for (const arc of props.archives) {
    emit('selection-change', { id: arc.id, checked: !!checked })
  }
}
</script>

<style scoped>
.archive-list {
  padding: 16px;
}

.archive-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.archive-header h3 {
  font-size: 15px;
  color: var(--text-primary);
}

.archive-actions {
  display: flex;
  gap: 8px;
}

.bulk-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-input);
  color: var(--text-secondary);
  font-size: 12px;
}

.bulk-count {
  flex: 1;
  color: var(--text-secondary);
}

.archive-item {
  padding: 12px 14px;
  border-radius: 12px;
  cursor: pointer;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  transition: background 0.2s ease-out, border-color 0.2s ease-out, transform 0.2s ease-out, box-shadow 0.2s ease-out;
  animation: fadeSlideIn 0.3s ease-out backwards;
}

.archive-item:hover {
  background: color-mix(in srgb, var(--bg-card) 90%, var(--accent-color) 10%);
  border-color: rgba(20, 184, 166, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.archive-item.selected {
  background: rgba(20, 184, 166, 0.05);
}

.archive-item.active {
  border: 1px solid var(--accent-color);
  background: rgba(20, 184, 166, 0.08);
  box-shadow: 0 0 0 1px var(--accent-color) inset, 0 4px 12px rgba(20, 184, 166, 0.15);
}

.archive-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  background: var(--accent-color);
  border-radius: 0 2px 2px 0;
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.arc-main {
  flex: 1;
  min-width: 0;
  position: relative;
}

.arc-name {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 4px;
  cursor: text;
  user-select: none;
}

.arc-name:hover {
  color: var(--accent-color);
}

.name-edit-input {
  margin-bottom: 4px;
}

.arc-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.archive-item:hover .arc-actions {
  opacity: 1;
}

.arc-actions :deep(.el-button) {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  transition: color 0.2s ease-out, background-color 0.2s ease-out;
}

.arc-actions :deep(.el-button)::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: rgba(20, 184, 166, 0.15);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: width 0.3s ease-out, height 0.3s ease-out;
}

.arc-actions :deep(.el-button:hover::before) {
  width: 28px;
  height: 28px;
}

.arc-actions :deep(.el-button--danger:hover) {
  color: #f56c6c;
  background: rgba(245, 108, 108, 0.1);
}

.arc-time {
  font-size: 11px;
  color: var(--text-muted);
}

.arc-preview {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.empty-state-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.empty-icon {
  color: var(--accent-color);
  flex-shrink: 0;
}

.empty-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

@media (max-width: 767px) {
  /* 移动端始终显示操作按钮（无 hover） */
  .arc-actions {
    opacity: 1;
    flex-wrap: wrap;
    gap: 4px;
  }

  .archive-header {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .archive-actions {
    flex-wrap: wrap;
    gap: 6px;
  }

  .archive-actions :deep(.el-button) {
    padding: 8px 12px;
    min-height: 40px;
  }

  .bulk-toolbar {
    flex-wrap: wrap;
    gap: 6px;
  }

  .archive-header :deep(.el-select) {
    width: auto !important;
    min-width: 80px;
  }

  .archive-header :deep(.el-date-editor) {
    width: auto !important;
    min-width: 120px;
  }
}
</style>
