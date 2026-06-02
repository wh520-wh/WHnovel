<template>
  <div class="story-state-panel">
    <h3 class="panel-title">故事进度</h3>
    <div v-if="entries.length === 0" class="empty">暂无故事进度</div>
    <div v-for="[key, value] in entries" :key="key" class="state-row">
      <span class="state-key">{{ key }}</span>
      <span class="state-value">{{ formatValue(value) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  storyState: Record<string, any>
}>()

const entries = computed(() => Object.entries(props.storyState || {}))

function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.join(' / ')
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}
</script>

<style scoped>
.story-state-panel {
  padding: 16px;
  border-top: 1px solid var(--border-color);
}
.panel-title {
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.state-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border-color);
}
.state-key {
  color: var(--text-secondary);
  font-size: 12px;
}
.state-value {
  color: var(--text-primary);
  font-size: 13px;
  text-align: right;
}
.empty {
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
  padding: 12px 0;
}
</style>
