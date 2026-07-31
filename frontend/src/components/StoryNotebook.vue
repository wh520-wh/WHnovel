<template>
  <div class="story-notebook">
    <template v-if="notebook && hasEntries">
      <section v-for="line in LINES" :key="line.key" class="notebook-line">
        <h4 class="notebook-line-title">{{ line.label }}</h4>
        <ul class="notebook-entries">
          <li
            v-for="(entry, idx) in notebook[line.key]"
            :key="`${line.key}-${idx}`"
            class="notebook-entry"
          >
            <span class="notebook-entry-text">{{ entry.text }}</span>
            <span
              class="notebook-entry-status"
              :class="entry.status === 'closed' ? 'is-closed' : 'is-active'"
            >
              {{ entry.status === 'closed' ? '已结束' : '进行中' }}
            </span>
          </li>
        </ul>
      </section>
    </template>
    <div v-else class="notebook-empty">
      <p>笔记本还是空的</p>
      <p class="notebook-empty-hint">聊几轮后，AI 会把世界大事、角色处境、人物关系记在这里</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StoryNotebook } from '../types/notebook'

const props = defineProps<{
  notebook: StoryNotebook | null
}>()

const LINES = [
  { key: 'world_line' as const, label: '世界线' },
  { key: 'character_line' as const, label: '人物线' },
  { key: 'relationship_line' as const, label: '感情线' },
]

const hasEntries = computed(() =>
  LINES.some((line) => (props.notebook?.[line.key]?.length ?? 0) > 0),
)
</script>

<style scoped>
.story-notebook {
  padding: 12px;
  font-size: 13px;
}
.notebook-line {
  margin-bottom: 14px;
}
.notebook-line-title {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.notebook-entries {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.notebook-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--bg-hover);
}
.notebook-entry-text {
  color: var(--text-primary);
  line-height: 1.4;
}
.notebook-entry-status {
  flex-shrink: 0;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 999px;
}
.notebook-entry-status.is-active {
  color: #67c23a;
  background: rgba(103, 194, 58, 0.12);
}
.notebook-entry-status.is-closed {
  color: var(--text-secondary);
  background: var(--border-color);
}
.notebook-empty {
  text-align: center;
  padding: 24px 12px;
  color: var(--text-secondary);
}
.notebook-empty-hint {
  margin-top: 6px;
  font-size: 12px;
  opacity: 0.8;
}
</style>
