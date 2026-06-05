<template>
  <div class="starter-wrap">
    <el-card class="starter-card">
      <template #header>
        <span>开始聊天</span>
      </template>
      <p class="starter-tip">
        输入你想要的开场要求（例如：主角身份、关系基调、冲突方向），系统会用首次模型生成开场。
      </p>
      <div class="preset-openings">
        <span class="preset-label">快速开场</span>
        <div class="preset-btns">
          <button
            v-for="preset in presetOpenings"
            :key="preset.id"
            class="preset-btn"
            type="button"
            @click="$emit('select-preset', preset)"
          >
            {{ preset.label }}
          </button>
        </div>
      </div>
      <textarea
        :key="bounceKey || undefined"
        class="opening-textarea"
        :class="{ 'input-bounce': bounceKey }"
        :model-value="modelValue"
        placeholder="示例：我是刚转学来的学生，希望开场是雨夜校园，先遇到一位看似冷漠但关键的角色。"
        :disabled="disabled"
        rows="5"
        @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        @click="$emit('click')"
      ></textarea>
      <div class="starter-actions">
        <button type="button" class="start-chat-btn" :disabled="disabled" @click="$emit('start')">
          <span v-if="disabled">生成中...</span>
          <span v-else>开始聊天</span>
        </button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
export interface PresetOpening {
  id: number
  label: string
  value: string
}

defineProps<{
  modelValue: string
  bounceKey: number
  disabled: boolean
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'start'): void
  (e: 'click'): void
  (e: 'select-preset', preset: PresetOpening): void
}>()

const presetOpenings: PresetOpening[] = [
  { id: 1, label: '我是转学生', value: '我是一名刚转入这所学校的学生，对这里的一切都很陌生...' },
  {
    id: 2,
    label: '我是新来者',
    value: '作为刚到这座城市/门派/星球的新人，我对这个地方一无所知...',
  },
  { id: 3, label: '我是青梅竹马', value: '我和她是从小一起长大的，但最近她变得有些奇怪...' },
  {
    id: 4,
    label: '我是救命恩人',
    value: '一个月前，我意外救了她一命，从此我们的命运交织在一起...',
  },
  { id: 5, label: '我从梦中醒来', value: '我从梦中惊醒，发现自己躺在一个陌生的房间里...' },
]
</script>

<style scoped>
.starter-wrap {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px 0;
}

.starter-card {
  width: min(680px, 100%);
  border-radius: 16px;
  border-color: var(--border-color);
  background: var(--bg-card);
}

.starter-tip {
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.65;
}

.preset-openings {
  margin-bottom: 12px;
}

.preset-label {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
  margin-bottom: 8px;
}

.preset-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-btn {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-smooth),
    box-shadow var(--duration-fast) var(--ease-smooth),
    background-color var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth);
}

.preset-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.starter-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.opening-textarea {
  width: 100%;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.65;
  outline: none;
  resize: none;
  transition:
    border-color var(--duration-base) var(--ease-smooth),
    box-shadow var(--duration-base) var(--ease-smooth);
  box-shadow: var(--shadow-sm);
}

.opening-textarea::placeholder {
  color: var(--text-muted);
}

.opening-textarea:focus {
  border-color: var(--accent-color);
  box-shadow:
    var(--shadow-sm),
    0 0 0 3px color-mix(in srgb, var(--accent-color) 20%, transparent);
}

/* Q弹动画：每次 key 变化时重挂载后播放 */
/* input-bounce-in 已提取到全局 style.css */
.opening-textarea.input-bounce {
  animation: input-bounce-in 280ms var(--ease-spring) both;
}

.start-chat-btn {
  height: 44px;
  padding: 0 28px;
  border-radius: 22px;
  border: none;
  background: var(--user-bubble);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-smooth),
    box-shadow var(--duration-fast) var(--ease-smooth),
    background-color var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth);
  box-shadow:
    var(--shadow-md),
    0 0 0 0 var(--accent-glow);
}

.start-chat-btn:hover:not(:disabled) {
  transform: scale(1.04);
  box-shadow: var(--shadow-lg), var(--shadow-glow);
}

.start-chat-btn:active:not(:disabled) {
  transform: scale(0.96);
  transition-duration: 80ms;
}

.start-chat-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

@media (max-width: 767px) {
  .preset-btns {
    gap: 6px;
  }

  .preset-btn {
    padding: 5px 10px;
    font-size: 12px;
  }
}
</style>
