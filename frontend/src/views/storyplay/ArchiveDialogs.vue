<template>
  <!-- 会话管理对话框 -->
  <el-dialog v-model="archiveDialogVisible" title="会话管理" width="600px">
    <ArchiveList
      :archives="chatStore.archives"
      :current-id="chatStore.currentArchive?.id ?? null"
      :bulk-mode="archiveBulkMode"
      :selection="archiveSelection"
      :deleting="deletingArchives"
      @create="emit('create')"
      @load="emit('load', $event)"
      @delete="emit('delete', $event)"
      @toggle-bulk-mode="emit('toggle-bulk-mode')"
      @selection-change="emit('selection-change', $event)"
      @bulk-delete="emit('bulk-delete')"
      @rename="emit('rename', $event)"
      @export="emit('export', $event)"
      @import="handleImportClick"
    />
    <input
      ref="importFileRef"
      type="file"
      accept=".json"
      style="display: none"
      @change="onImportFile"
    />
  </el-dialog>

  <el-dialog
    v-model="archiveNameDialogVisible"
    title="命名存档"
    width="360px"
    :close-on-click-modal="false"
  >
    <div style="display: flex; flex-direction: column; gap: 12px">
      <el-input
        v-model="newArchiveNameInput"
        placeholder="输入存档名称"
        maxlength="50"
        @keydown.enter="emit('confirm-archive-name')"
      />
    </div>
    <template #footer>
      <el-button @click="archiveNameDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="emit('confirm-archive-name')">确认</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="logDialogVisible" title="剧情日志" width="680px">
    <div class="log-list">
      <div v-for="msg in chatStore.messages" :key="msg.id" class="log-row">
        <div class="log-meta">
          <span class="log-time">{{ formatTimeSeconds(msg.created_at) }}</span>
          <span class="log-role" :class="msg.role === 'assistant' ? 'ai-tag' : 'user-tag'">{{
            msg.role === 'assistant' ? 'AI' : '你'
          }}</span>
        </div>
        <div class="log-content">{{ msg.content }}</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ArchiveList from '../../components/ArchiveList.vue'
import { useChatStore } from '../../stores/chat'
import { formatTimeSeconds } from '../../utils/time'

defineProps<{
  archiveBulkMode: boolean
  archiveSelection: number[]
  deletingArchives: boolean
}>()

const emit = defineEmits<{
  create: []
  load: [archiveId: number]
  delete: [archiveId: number]
  'toggle-bulk-mode': []
  'selection-change': [payload: { id: number; checked: boolean }]
  'bulk-delete': []
  rename: [payload: { id: number; name: string }]
  export: [archiveId: number]
  'import-file': [file: File]
  'confirm-archive-name': []
}>()

const archiveDialogVisible = defineModel<boolean>('archiveDialogVisible', { default: false })
const archiveNameDialogVisible = defineModel<boolean>('archiveNameDialogVisible', {
  default: false,
})
const logDialogVisible = defineModel<boolean>('logDialogVisible', { default: false })
const newArchiveNameInput = defineModel<string>('newArchiveNameInput', { default: '' })

const chatStore = useChatStore()
const importFileRef = ref<HTMLInputElement | null>(null)

function handleImportClick() {
  importFileRef.value?.click()
}

function onImportFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  emit('import-file', file)
  input.value = ''
}
</script>

<style scoped>
.log-list {
  max-height: 62vh;
  max-height: 62dvh;
  overflow-y: auto;
  border-radius: 12px;
  overflow: hidden;
}

.log-row {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 4px;
}

.log-row:last-child {
  border-bottom: none;
}

.log-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.log-role {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 10px;
}

.log-role.ai-tag {
  color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 15%, transparent);
}

.log-role.user-tag {
  color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 15%, transparent);
}

.log-time {
  font-size: 12px;
  color: var(--text-muted);
}

.log-content {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  color: var(--text-primary);
}

/* ---- 会话管理/剧情日志弹窗圆角 ---- */
:deep(.el-dialog) {
  border-radius: 16px;
}
:deep(.el-dialog__header) {
  border-bottom: 1px solid var(--border-color);
}
:deep(.el-dialog__body) {
  padding: 16px 20px;
}
</style>
