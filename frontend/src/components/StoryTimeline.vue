<template>
  <div class="story-timeline-panel">
    <div class="timeline-header">
      <span class="timeline-title">剧情导航</span>
    </div>
    <div class="timeline-nodes" v-if="nodes.length > 0">
      <div
        v-for="(node, idx) in nodes"
        :key="node.id"
        class="timeline-node"
        :class="{ active: activeId === node.id }"
        :style="{ animationDelay: `${idx * 60}ms` }"
        @click="handleNodeClick(node)"
      >
        <div class="node-line">
          <div class="node-dot"></div>
          <div
            class="node-connector"
            v-if="idx < nodes.length - 1"
            :style="{ animationDelay: `${idx * 60}ms` }"
          ></div>
        </div>
        <div class="node-content">
          <span class="node-label">{{ node.plot_label }}</span>
          <span class="node-time">{{ formatTime(node.created_at) }}</span>
        </div>
      </div>
    </div>
    <div class="timeline-empty" v-else>
      <div class="empty-state-card">
        <svg class="empty-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" role="img" aria-label="暂无剧情节点" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        <span class="empty-title">暂无剧情节点</span>
        <span class="empty-hint">与AI互动后会自动生成</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatMsg } from '../stores/chat'
import { formatTime } from '../utils/time'

const props = defineProps<{
  messages: ChatMsg[]
}>()

const emit = defineEmits<{
  (event: 'jump', messageId: string | number): void
}>()

// 从 messages 中提取有 plot_label 的消息作为节点
const nodes = computed(() => {
  return props.messages
    .filter(msg => msg.role === 'assistant' && msg.plot_label)
    .map(msg => ({
      id: msg.id,
      plot_label: msg.plot_label as string,
      created_at: msg.created_at
    }))
})

const activeId = ref<string | number | null>(null)

function handleNodeClick(node: { id: string | number }) {
  activeId.value = node.id
  emit('jump', node.id)
}

</script>

<style scoped>
.story-timeline-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  padding: 12px 0;
}

.timeline-header {
  padding: 0 16px 12px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 12px;
}

.timeline-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.timeline-nodes {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

/* Plasma glass node card */
.timeline-node {
  position: relative;
  display: flex;
  gap: 10px;
  cursor: pointer;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid rgba(20, 184, 166, 0.25);
  box-shadow: 0 0 20px rgba(20, 184, 166, 0.15);
  transition:
    background 0.25s ease,
    transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow 0.25s ease,
    border-color 0.25s ease;
  /* Entry animation */
  opacity: 0;
  transform: translateY(12px);
  animation: node-enter 0.4s ease forwards;
}

.timeline-node:hover {
  background: rgba(20, 184, 166, 0.14);
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 0 30px rgba(20, 184, 166, 0.25), 0 4px 16px rgba(0, 0, 0, 0.2);
  border-color: rgba(20, 184, 166, 0.4);
}

/* Active node: left highlight bar + glow */
.timeline-node.active {
  background: rgba(20, 184, 166, 0.15);
  border-color: var(--accent-color);
  box-shadow: 0 0 0 1px var(--accent-color), 0 0 16px rgba(20, 184, 166, 0.3);
}

.timeline-node.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  background: var(--accent-color);
  border-radius: 0 2px 2px 0;
  box-shadow: 0 0 10px var(--accent-color);
}

/* Staggered entry animation for nodes */
@keyframes timeline-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes node-enter {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.node-line {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.node-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent-color);
  border: 2px solid var(--bg-secondary);
  box-shadow: 0 0 0 2px var(--accent-color), 0 0 12px rgba(20, 184, 166, 0.5);
  flex-shrink: 0;
  transition: box-shadow 0.25s ease;
}

.timeline-node:hover .node-dot {
  box-shadow: 0 0 0 2px var(--accent-color), 0 0 18px rgba(20, 184, 166, 0.7);
}

.timeline-node.active .node-dot {
  box-shadow: 0 0 0 2px var(--accent-color), 0 0 16px rgba(20, 184, 166, 0.6);
}

/* Connector line with gradient glow + sequential reveal */
.node-connector {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: linear-gradient(to bottom, rgba(20, 184, 166, 0.6), rgba(20, 184, 166, 0.1));
  margin-top: 4px;
  border-radius: 1px;
  position: relative;
  overflow: hidden;
  /* Sequential reveal animation (delay set via inline style) */
  opacity: 0;
  transform-origin: top center;
  animation: connector-reveal 300ms ease-out forwards;
}

.node-connector::after {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 100%;
  background: linear-gradient(to bottom, rgba(20, 184, 166, 0.4), transparent);
  filter: blur(3px);
  opacity: 0.4;
}

@keyframes connector-reveal {
  from {
    opacity: 0;
    transform: scaleY(0.3);
  }
  to {
    opacity: 1;
    transform: scaleY(1);
  }
}

/* 减少动画偏好：connector-reveal 基态 opacity:0，禁用动画后须显式设回 1，否则连线隐形。 */
@media (prefers-reduced-motion: reduce) {
  .node-connector {
    animation: none;
    opacity: 1;
    transform: scaleY(1);
  }
}

.node-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-label {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  text-shadow: 0 0 8px rgba(20, 184, 166, 0.3);
  transition: text-shadow 0.25s ease;
}

.timeline-node:hover .node-label {
  text-shadow: 0 0 12px rgba(20, 184, 166, 0.5);
}

.node-time {
  font-size: 11px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
}

.timeline-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.empty-state-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 16px;
  background: transparent;
  border: 1px solid color-mix(in srgb, var(--border-color) 70%, transparent);
  border-radius: 12px;
  animation: timeline-fade-in 300ms ease;
  width: 100%;
}

.empty-icon {
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0.85;
}

.empty-title {
  font-size: 14px;
  font-weight: 400;
  color: var(--text-secondary);
}

.empty-hint {
  font-size: 12px;
  color: var(--text-muted);
}

</style>
