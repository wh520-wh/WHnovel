<template>
  <div class="model-tuning-page" v-loading="loading">
    <div class="page-header">
      <h2>文笔风格</h2>
    </div>

    <div class="tuning-panel">
      <h3>中文文笔 Skill</h3>

      <div class="skill-toggle">
        <span>启用文笔 Skill</span>
        <el-switch v-model="skillEnabled" />
      </div>

      <template v-if="skillEnabled">
        <el-input
          v-model="skillContent"
          type="textarea"
          :rows="14"
          placeholder="请输入文笔 Skill 内容"
          class="skill-textarea"
        />
        <div class="skill-footer">
          <span
            class="char-count"
            :class="{
              'char-warn': skillLength > 0 && skillLength < 200,
              'char-error': skillLength > 1500,
            }"
          >
            {{ skillLength }} / 1500
          </span>
          <span v-if="skillLength > 0 && skillLength < 200" class="char-hint">
            建议不少于 200 字符，以获得稳定效果
          </span>
          <span v-if="skillLength > 1500" class="char-hint char-hint--error">
            超出推荐上限，可能被模型截断
          </span>
        </div>
      </template>

      <el-button
        type="primary"
        :loading="savingSkill"
        @click="saveSkill"
      >
        保存文笔 Skill
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAppSettings, updateAppSettings, getErrorMessage } from '../../api'

const DEFAULT_SKILL_TEMPLATE = `----- SKILL START -----
【核心理念】
你是一位文学功底深厚的中文小说作家，擅长用细腻的笔触描绘场景、刻画人物内心。你的文字兼具画面感与情绪张力，能让读者身临其境。

【开局要炸】
每段开场必须用一个强有力的句子抓住读者注意力——可以是悬念、冲突、环境氛围或人物状态。

【文风要点】
1. 多感官描写：调动视觉、听觉、嗅觉、触觉，让场景立体
2. 内心独白：适当穿插角色的心理活动，增强代入感
3. 节奏控制：紧张场景用短句、快节奏；抒情场景用长句、留白
4. 对话自然：人物对话要符合身份和性格，避免说教感
5. 留白艺术：不必事事说明，留给读者想象空间

【禁忌】
- 不要使用网络流行语和现代口语
- 不要过度解释，相信读者的理解力
- 不要滥用感叹号和省略号
----- SKILL END -----`

const loading = ref(false)
const savingSkill = ref(false)

// ---- Skill ----
const skillEnabled = ref(false)
const skillContent = ref(DEFAULT_SKILL_TEMPLATE)

const skillLength = computed(() => skillContent.value.length)

onMounted(async () => {
  loading.value = true
  try {
    const { data: appSettings } = await getAppSettings()
    skillEnabled.value = !!(appSettings.style_skill_enabled)
    skillContent.value = appSettings.style_skill_content || DEFAULT_SKILL_TEMPLATE
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '加载配置失败'))
  } finally {
    loading.value = false
  }
})

async function saveSkill() {
  savingSkill.value = true
  try {
    await updateAppSettings({
      style_skill_enabled: skillEnabled.value ? 1 : 0,
      style_skill_content: skillContent.value,
    })
    ElMessage.success('文笔Skill已更新')
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '保存文笔Skill失败'))
  } finally {
    savingSkill.value = false
  }
}
</script>

<style scoped>
.model-tuning-page {
  max-width: 700px;
}

.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  font-size: 20px;
  color: var(--text-primary);
}

/* ---- Panel ---- */
.tuning-panel {
  background: var(--admin-card-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 0 20px color-mix(in srgb, var(--accent-color) 8%, transparent);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.tuning-panel h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ---- Skill ---- */
.skill-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-primary);
  font-size: 14px;
}

.skill-textarea {
  width: 100%;
}

.skill-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.char-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.char-count.char-warn {
  color: #e6a23c;
}

.char-count.char-error {
  color: #f56c6c;
}

.char-hint {
  font-size: 12px;
  color: #e6a23c;
}

.char-hint--error {
  color: #f56c6c;
}

/* ---- Deep Selectors for Element Plus ---- */
:deep(.el-textarea__inner) {
  background: var(--admin-input-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 10px;
  box-shadow: none;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', sans-serif;
  line-height: 1.7;
}

:deep(.el-textarea__inner:hover) {
  border-color: color-mix(in srgb, var(--accent-color) 40%, transparent);
}

:deep(.el-textarea__inner:focus) {
  border-color: var(--accent-color);
  box-shadow: 0 0 12px color-mix(in srgb, var(--accent-color) 20%, transparent);
}

:deep(.el-button--primary) {
  align-self: flex-start;
  margin-top: 4px;
}

@media (max-width: 767px) {
  .tuning-panel {
    padding: 16px;
    gap: 14px;
    border-radius: 12px;
  }

  .tuning-panel h3 {
    font-size: 15px;
  }

  .skill-textarea :deep(.el-textarea__inner) {
    font-size: 13px;
  }
}
</style>
