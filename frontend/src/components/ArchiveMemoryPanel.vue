<template>
  <div class="memory-log-panel">
    <h3 class="panel-title">记忆更新</h3>
    <div v-if="recentMemory.length === 0" class="empty" role="status">暂无记忆更新</div>
    <ul v-else class="memory-list" aria-label="记忆更新列表">
      <li v-for="(item, index) in recentMemory" :key="`${index}-${item}`" class="memory-item">
        <span class="memory-index">{{ index + 1 }}</span>
        <span class="memory-text">{{ item }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  memoryLog: string[]
}>()

const recentMemory = computed(() => (props.memoryLog || []).slice(-10).reverse())
</script>

<style scoped>
.memory-log-panel {
  padding: 16px;
  border-top: 1px solid var(--border-color);
}
.panel-title {
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.memory-list {
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.memory-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
  padding: 8px 10px;
  background: var(--bg-input);
  border-radius: 6px;
  border-left: 2px solid var(--accent-color);
}

.memory-index {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--accent-color) 20%, transparent);
  color: #f5f5ff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.memory-text {
  flex: 1;
}
.empty {
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
  padding: 12px 0;
}
</style>
