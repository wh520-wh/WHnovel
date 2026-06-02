<template>
  <div class="status-panel">
    <h3 class="panel-title">状态面板</h3>
    <div v-if="stateConfig.length === 0" class="empty" role="status">暂无状态配置</div>
    <div v-for="field in stateConfig" :key="field.key" class="status-item">
      <div class="status-label">{{ field.label }}</div>

      <!-- 数值类型：显示进度条 -->
      <template v-if="field.type === 'number'">
        <div class="status-bar-wrap">
          <el-progress
            :percentage="getPercent(field)"
            :color="getColor(field)"
            :stroke-width="14"
            :show-text="false"
            :aria-label="`${field.label}: ${stateData[field.key] ?? field.default} / ${field.max ?? 100}`"
          />
          <span class="status-value">{{ stateData[field.key] ?? field.default }} / {{ field.max ?? 100 }}</span>
        </div>
      </template>

      <!-- 文本类型 -->
      <template v-else>
        <div class="status-text">{{ stateData[field.key] ?? field.default }}</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { StateField } from '../stores/story'

const props = defineProps<{
  stateConfig: StateField[]
  stateData: Record<string, any>
}>()

function getPercent(field: StateField) {
  const val = Number(props.stateData[field.key] ?? field.default ?? 0)
  const max = field.max ?? 100
  return Math.round((val / max) * 100)
}

function getColor(field: StateField) {
  const p = getPercent(field)
  if (p > 60) return '#00cec9'
  if (p > 30) return '#fdcb6e'
  return 'var(--color-danger)'
}
</script>

<style scoped>
.status-panel {
  padding: 16px;
}
.panel-title {
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}
.status-item {
  margin-bottom: 14px;
}
.status-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.status-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-bar-wrap .el-progress {
  flex: 1;
}
.status-value {
  font-size: 12px;
  color: var(--text-muted);
  min-width: 60px;
  text-align: right;
}
.status-text {
  font-size: 14px;
  color: var(--text-primary);
  padding: 4px 8px;
  background: var(--bg-input);
  border-radius: 6px;
}
.empty {
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
  padding: 20px 0;
}
</style>
