<template>
  <el-dialog v-model="visible" title="剧情日志" width="680px">
    <div class="log-list">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="log-row"
        :class="msg.role === 'assistant' ? 'ai-msg' : 'user-msg'"
      >
        <div class="log-meta" :class="msg.role === 'user' ? 'user-meta' : ''">
          <span class="log-role" :class="msg.role === 'assistant' ? 'ai-tag' : 'user-tag'">
            {{ msg.role === 'assistant' ? 'AI' : '你' }}
          </span>
          <span class="log-time">{{ formatTimeSeconds(msg.created_at) }}</span>
        </div>
        <div class="log-content">{{ msg.content }}</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import type { ChatMsg } from '../stores/chat'
import { formatTimeSeconds } from '../utils/time'

defineProps<{
  messages: ChatMsg[]
}>()

const visible = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
.log-list {
  max-height: 62vh;
  max-height: 62dvh;
  overflow-y: auto;
  border-radius: 12px;
  overflow: hidden;
  padding-right: 4px;
}

/* Custom glass scrollbar */
.log-list::-webkit-scrollbar {
  width: 6px;
}
.log-list::-webkit-scrollbar-track {
  background: color-mix(in srgb, var(--accent-color) 5%, transparent);
  border-radius: 3px;
}
.log-list::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--accent-color) 25%, transparent);
  border-radius: 3px;
}
.log-list::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--accent-color) 40%, transparent);
}

.log-row {
  padding: 10px 14px;
  border-radius: 10px;
  margin-bottom: 6px;
}

.log-row:last-child {
  margin-bottom: 0;
}

/* AI message: left teal border + light teal bg */
.log-row.ai-msg {
  border-left: 3px solid color-mix(in srgb, var(--accent-color) 60%, transparent);
  background: color-mix(in srgb, var(--accent-color) 8%, transparent);
  text-align: left;
}

/* User message: right-aligned + darker bg */
.log-row.user-msg {
  background: color-mix(in srgb, var(--accent-color) 14%, transparent);
  text-align: right;
}

.log-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.log-meta.user-meta {
  justify-content: flex-end;
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
  color: #22d3ee;
  background: rgba(34, 211, 238, 0.15);
}

.log-time {
  font-size: 12px;
  color: color-mix(in srgb, var(--accent-color) 85%, transparent);
}

.log-content {
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  color: var(--text-primary);
}

/* Glass dialog override */
:deep(.el-dialog) {
  background: var(--bg-card);
  border: 1px solid color-mix(in srgb, var(--accent-color) 30%, transparent);
  border-radius: 20px;
  box-shadow:
    0 0 40px color-mix(in srgb, var(--accent-color) 20%, transparent),
    0 0 80px color-mix(in srgb, var(--accent-color) 10%, transparent);
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
</style>
