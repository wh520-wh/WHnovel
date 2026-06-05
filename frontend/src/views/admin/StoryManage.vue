<template>
  <div class="table-scroll-mobile">
    <div class="page-header">
      <h2>故事管理</h2>
      <div class="header-actions">
        <el-button
          class="desktop-bulk-delete"
          type="danger"
          plain
          :disabled="selectedIds.length === 0"
          @click="handleBulkDelete"
        >
          批量删除
        </el-button>
        <el-button type="primary" @click="openDialog()">新建故事</el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      class="story-table"
      :data="stories"
      stripe
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="48" />
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="封面" width="96">
        <template #default="{ row }">
          <div
            class="cover-thumb"
            :style="row.cover_image ? { backgroundImage: `url(${row.cover_image})` } : {}"
            aria-label="封面缩略图"
          />
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" width="180" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="tags" label="标签" width="220">
        <template #default="{ row }">
          <el-tag v-for="tag in row.tags" :key="tag" size="small" class="tag-item">{{
            tag
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="简介" min-width="260">
        <template #default="{ row }">
          <div class="description-cell">{{ row.description || '暂无简介' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <div class="action-buttons">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="primary" @click.stop="toggleMore(row.id, $event)">
              更多
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </el-button>
            <Teleport to="body">
              <Transition name="dropdown-fade">
                <div
                  v-if="activeMoreId === row.id"
                  class="more-menu-overlay"
                  @click="activeMoreId = null"
                >
                  <div class="more-menu-card" :style="getMenuStyle()" @click.stop>
                    <button
                      type="button"
                      class="more-menu-btn"
                      @click="handleMoreCommand('characters', row)"
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                      角色管理
                    </button>
                    <button
                      type="button"
                      class="more-menu-btn"
                      @click="handleMoreCommand('prompt', row)"
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      提示词
                    </button>
                    <button
                      type="button"
                      class="more-menu-btn"
                      @click="handleMoreCommand('state-config', row)"
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <circle cx="12" cy="12" r="3" />
                        <path
                          d="M12 1v6m0 6v6m5.2-13.2l-4.2 4.2m0 6l4.2 4.2M23 12h-6m-6 0H1m18.2 5.2l-4.2-4.2m0-6l-4.2-4.2"
                        />
                      </svg>
                      状态配置
                    </button>
                  </div>
                </div>
              </Transition>
            </Teleport>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="mobile-story-list" aria-label="移动端故事管理列表">
      <article v-for="story in stories" :key="story.id" class="mobile-story-card">
        <div
          class="mobile-story-cover"
          :style="story.cover_image ? { backgroundImage: `url(${story.cover_image})` } : {}"
          aria-label="封面缩略图"
        />
        <div class="mobile-story-main">
          <div class="mobile-story-meta">
            <span>#{{ story.id }}</span>
            <span>{{ story.category || '其他' }}</span>
          </div>
          <h3>{{ story.title || '未命名故事' }}</h3>
          <p>{{ story.description || '暂无简介' }}</p>
          <div class="mobile-story-tags">
            <span v-for="tag in story.tags || []" :key="tag">{{ tag }}</span>
            <span v-if="!story.tags || story.tags.length === 0" class="muted">暂无标签</span>
          </div>
          <div class="mobile-story-actions">
            <button type="button" @click="openDialog(story)">编辑</button>
            <button type="button" @click="handleMoreCommand('characters', story)">角色</button>
            <button type="button" @click="handleMoreCommand('prompt', story)">提示词</button>
            <button type="button" @click="handleMoreCommand('state-config', story)">
              状态配置
            </button>
            <button type="button" class="danger" @click="handleDelete(story.id)">删除</button>
          </div>
        </div>
      </article>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑故事' : '新建故事'"
      width="600px"
      class="story-edit-dialog"
      @closed="editingId = null"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="选择分类">
            <el-option
              v-for="category in STORY_CATEGORIES"
              :key="category"
              :label="category"
              :value="category"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="tagsInput" placeholder="使用英文逗号分隔，如：恋爱,校园" />
        </el-form-item>
        <el-form-item label="封面图">
          <div style="display: flex; align-items: center; gap: 10px">
            <div
              v-if="form.cover_image"
              style="
                width: 80px;
                height: 50px;
                border-radius: 4px;
                background-size: cover;
                background-position: center;
              "
              :style="{ backgroundImage: `url(${form.cover_image})` }"
            ></div>
            <div
              v-else
              style="
                width: 80px;
                height: 50px;
                border-radius: 4px;
                border: 1px dashed var(--el-border-color);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                color: #999;
              "
            >
              未设置
            </div>
            <el-button size="small" @click="handleUploadCover">上传</el-button>
          </div>
        </el-form-item>
        <el-form-item label="背景图">
          <div style="display: flex; align-items: center; gap: 10px">
            <div
              v-if="form.background_image"
              style="
                width: 80px;
                height: 50px;
                border-radius: 4px;
                background-size: cover;
                background-position: center;
              "
              :style="{ backgroundImage: `url(${form.background_image})` }"
            ></div>
            <div
              v-else
              style="
                width: 80px;
                height: 50px;
                border-radius: 4px;
                border: 1px dashed var(--el-border-color);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                color: #999;
              "
            >
              未设置
            </div>
            <el-button size="small" @click="handleUploadBackground">上传</el-button>
          </div>
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="默认开场提示词">
          <el-input
            v-model="form.opening_requirement"
            type="textarea"
            :rows="3"
            placeholder="故事开场时用户看到的引导文本，将作为开场消息发送给AI"
          />
        </el-form-item>
        <el-form-item label="世界观">
          <el-input v-model="form.world_setting" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="图片风格">
          <el-input
            v-model="form.image_style"
            type="textarea"
            :rows="2"
            placeholder="如：漫画分格，简洁有力的对话气泡风格。留空则 AI 自动生成"
          />
        </el-form-item>
      </el-form>
      <div class="story-preview">
        <div class="preview-title">卡片预览</div>
        <div class="preview-card">
          <div
            class="preview-cover"
            :style="form.cover_image ? { backgroundImage: `url(${form.cover_image})` } : {}"
            aria-label="故事封面预览"
          />
          <div class="preview-content">
            <div class="preview-header">
              <h3>{{ form.title || '未命名故事' }}</h3>
              <span class="preview-category">{{ form.category || '其他' }}</span>
            </div>
            <p>{{ form.description || '暂无简介' }}</p>
            <div class="preview-tags">
              <span v-for="tag in previewTags" :key="tag" class="preview-tag">{{ tag }}</span>
              <span v-if="previewTags.length === 0" class="preview-tag muted">暂无标签</span>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="story-dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="info" :loading="generating" @click="handleOpenModelSelect"
            >一键AI生成</el-button
          >
          <el-button type="warning" @click="handleStandaloneGenerateCover"
            >一键AI生成封面</el-button
          >
          <el-button type="warning" @click="handleStandaloneGenerateBackground"
            >一键AI生成背景</el-button
          >
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 模型选择弹窗 -->
    <el-dialog v-model="modelSelectVisible" title="选择模型" width="400px" destroy-on-close>
      <p style="margin-bottom: 12px; color: var(--text-secondary); font-size: 13px">
        请选择用于生成故事内容的模型
      </p>
      <ModelSelect v-model="selectedModelId" :options="availableModels" placeholder="选择模型" />
      <div style="margin-top: 12px">
        <el-input
          v-model="form.preference"
          type="textarea"
          :rows="2"
          placeholder="写下你的偏好，如：我想成为一个世界首富"
        />
      </div>
      <div
        style="
          margin-top: 16px;
          border-top: 1px solid var(--el-border-color-lighter);
          padding-top: 16px;
        "
      >
        <div
          style="
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
          "
        >
          <span>生成封面图</span>
          <el-switch v-model="generateCover" />
        </div>
        <ModelSelect
          v-if="generateCover"
          v-model="coverImageModelId"
          :options="imageModels"
          placeholder="选择图片模型"
          style="margin-bottom: 12px"
        />
        <div
          style="
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
          "
        >
          <span>生成背景图</span>
          <el-switch v-model="generateBackground" />
        </div>
        <ModelSelect
          v-if="generateBackground"
          v-model="backgroundImageModelId"
          :options="imageModels"
          placeholder="选择图片模型"
        />
      </div>
      <template #footer>
        <el-button @click="modelSelectVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!selectedModelId"
          @click="
            confirmGenerate({
              category: form.category || dialogCategory,
              title_hint: form.title,
              tags_hint: tagsInput,
              image_style: form.image_style,
              preference: form.preference || '',
            })
          "
        >
          开始生成
        </el-button>
      </template>
    </el-dialog>

    <!-- 独立图片生成模型选择弹窗 -->
    <el-dialog
      v-model="imageModelSelectVisible"
      :title="imageModelDialogTitle"
      width="400px"
      destroy-on-close
    >
      <div v-if="standaloneGenerating" class="generating-steps">
        <div
          v-for="(step, idx) in standaloneGeneratingSteps"
          :key="idx"
          class="generating-step"
          :class="{
            'step-active': standaloneGeneratingStep === idx,
            'step-done': standaloneGeneratingStep > idx,
            'step-pending': standaloneGeneratingStep < idx,
          }"
        >
          <span class="step-icon">
            <template v-if="standaloneGeneratingStep > idx">✓</template>
            <template v-else-if="standaloneGeneratingStep === idx">✦</template>
            <template v-else>○</template>
          </span>
          <span :class="{ 'flow-text': standaloneGeneratingStep === idx }">{{ step }}</span>
        </div>
      </div>
      <ModelSelect
        v-model="selectedImageModelId"
        :options="imageModels"
        placeholder="选择图片模型"
        :disabled="standaloneGenerating"
      />
      <template #footer>
        <el-button v-if="!standaloneGenerating" @click="imageModelSelectVisible = false"
          >取消</el-button
        >
        <el-button
          type="primary"
          :disabled="!selectedImageModelId || standaloneGenerating"
          :loading="standaloneGenerating"
          @click="confirmStandaloneImageGenerate"
          >确认生成</el-button
        >
      </template>
    </el-dialog>

    <!-- 生成结果预览弹窗 -->
    <el-dialog
      v-model="previewVisible"
      title="生成结果预览"
      width="640px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div v-if="previewData" class="preview-result">
        <div class="preview-field">
          <div class="preview-label">标题</div>
          <div class="preview-value">{{ previewData.title }}</div>
        </div>
        <div class="preview-field">
          <div class="preview-label">简介</div>
          <div class="preview-value">{{ previewData.description }}</div>
        </div>
        <div class="preview-field">
          <div class="preview-label">标签</div>
          <div class="preview-value">{{ previewData.tags?.join(', ') }}</div>
        </div>
        <div class="preview-field">
          <div class="preview-label">世界观</div>
          <div class="preview-value world-setting-preview">{{ previewData.world_setting }}</div>
        </div>
        <div class="preview-field">
          <div class="preview-label">开场提示词</div>
          <div class="preview-value world-setting-preview">
            {{ previewData.opening_requirement || '(AI自动生成)' }}
          </div>
        </div>
        <div class="preview-field">
          <div class="preview-label">图片风格</div>
          <div class="preview-value">{{ previewData.image_style || '(AI自动生成)' }}</div>
        </div>
        <div v-if="previewData.cover_url" class="preview-field">
          <div class="preview-label">封面图</div>
          <img :src="previewData.cover_url" alt="封面预览" class="cover-preview-img" />
        </div>
      </div>
      <template #footer>
        <el-button @click="handleCancelPreview">取消</el-button>
        <el-button
          :loading="generating"
          @click="
            () =>
              confirmGenerate({
                category: form.category || dialogCategory,
                title_hint: form.title,
                tags_hint: tagsInput,
                image_style: form.image_style,
                preference: form.preference || '',
              })
          "
        >
          重新生成
        </el-button>
        <el-button type="primary" @click="applyPreview">确认填入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createStory,
  deleteStory,
  getStories,
  updateStory,
  standaloneGenerateCover,
  standaloneGenerateBackground,
  uploadStoryImage,
  getModels,
} from '../../api'
import { useStoryGenerate } from '../../composables/useStoryGenerate'
import { useStoryStore } from '../../stores/story'
import ModelSelect from '../../components/ModelSelect.vue'
import type { Story } from '../../stores/story'
import { STORY_CATEGORIES } from '../../constants/categories'
import { MODEL_TYPE_IMAGE } from '../../constants/modelTypes'

const route = useRoute()
const router = useRouter()

const stories = ref<any[]>([])
const selectedIds = ref<number[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const tagsInput = ref('')
const activeMoreId = ref<number | null>(null)
const storyStore = useStoryStore()
const {
  generating,
  generateCover,
  coverImageModelId,
  generateBackground,
  backgroundImageModelId,
  previewData,
  previewVisible,
  modelSelectVisible,
  selectedModelId,
  availableModels,
  openModelSelect,
  confirmGenerate,
  confirmFill,
  cancelPreview,
} = useStoryGenerate()

function handleOpenModelSelect() {
  loadAllModels()
  openModelSelect()
}

// ---- 独立图片生成 ----
const imageModelSelectVisible = ref(false)
const selectedImageModelId = ref<number | null>(null)
const imageModelDialogTitle = ref('')
const imageGeneratePurpose = ref<'cover' | 'background'>('cover')
const standaloneGenerating = ref(false)
const standaloneGeneratingStep = ref(-1)
const allModels = ref<any[]>([])

const standaloneGeneratingSteps = computed(() => [
  imageGeneratePurpose.value === 'background' ? '正在生成背景图...' : '正在生成封面图...',
])

const imageModels = computed(() =>
  allModels.value.filter((m: any) => m.model_type === MODEL_TYPE_IMAGE && !!m.enabled),
)

async function loadAllModels() {
  try {
    const resp = await getModels()
    allModels.value = resp.data || []
  } catch {
    allModels.value = []
  }
}

function handleStandaloneGenerateCover() {
  imageGeneratePurpose.value = 'cover'
  imageModelDialogTitle.value = '选择图片模型 — 生成封面'
  selectedImageModelId.value = null
  loadAllModels()
  imageModelSelectVisible.value = true
}

function handleStandaloneGenerateBackground() {
  imageGeneratePurpose.value = 'background'
  imageModelDialogTitle.value = '选择图片模型 — 生成背景'
  selectedImageModelId.value = null
  loadAllModels()
  imageModelSelectVisible.value = true
}

async function confirmStandaloneImageGenerate() {
  if (!selectedImageModelId.value || !editingId.value || standaloneGenerating.value) return
  standaloneGenerating.value = true
  standaloneGeneratingStep.value = 0
  try {
    if (imageGeneratePurpose.value === 'cover') {
      const { data } = await standaloneGenerateCover(editingId.value, selectedImageModelId.value)
      form.cover_image = data.cover_image
    } else {
      const { data } = await standaloneGenerateBackground(
        editingId.value,
        selectedImageModelId.value,
      )
      form.background_image = data.background_image
    }
    imageModelSelectVisible.value = false
    ElMessage.success('图片生成成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '图片生成失败')
  } finally {
    standaloneGenerating.value = false
    standaloneGeneratingStep.value = -1
  }
}

async function handleUploadCover() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file || !editingId.value) return
    try {
      const { data } = await uploadStoryImage(editingId.value, file, 'cover')
      form.cover_image = data.cover_image
      ElMessage.success('封面图上传成功')
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '上传失败')
    }
  }
  input.click()
}

async function handleUploadBackground() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file || !editingId.value) return
    try {
      const { data } = await uploadStoryImage(editingId.value, file, 'background')
      form.background_image = data.background_image
      ElMessage.success('背景图上传成功')
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '上传失败')
    }
  }
  input.click()
}
const previewTags = computed(() =>
  tagsInput.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean),
)

const form = reactive({
  title: '',
  category: STORY_CATEGORIES[STORY_CATEGORIES.length - 1] as string,
  cover_image: '',
  background_image: '',
  description: '',
  tags: [] as string[],
  world_setting: '',
  opening_requirement: '',
  image_style: '',
  preference: '',
})

const dialogCategory = ref('')

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getStories()
    stories.value = data
  } finally {
    loading.value = false
  }
}

function handleSelectionChange(rows: any[]) {
  selectedIds.value = rows.map((row) => row.id)
}

function openDialog(row?: any) {
  if (row) {
    editingId.value = row.id
    form.title = row.title || ''
    form.category = row.category || STORY_CATEGORIES[STORY_CATEGORIES.length - 1]
    form.cover_image = row.cover_image || ''
    form.background_image = row.background_image || ''
    form.description = row.description || ''
    form.tags = [...(row.tags || [])]
    form.world_setting = row.world_setting || ''
    form.opening_requirement = row.opening_requirement || ''
    form.image_style = row.image_style || ''
    form.preference = row.preference || ''
    tagsInput.value = (row.tags || []).join(',')
  } else {
    editingId.value = null
    form.title = ''
    form.category = STORY_CATEGORIES[STORY_CATEGORIES.length - 1] as string
    form.cover_image = ''
    form.background_image = ''
    form.description = ''
    form.tags = []
    form.world_setting = ''
    form.opening_requirement = ''
    form.image_style = ''
    form.preference = ''
    tagsInput.value = ''
  }
  dialogCategory.value = form.category
  dialogVisible.value = true
}

async function handleSave() {
  form.tags = tagsInput.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  saving.value = true
  try {
    if (editingId.value) {
      await updateStory(editingId.value, form)
    } else {
      await createStory(form)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await fetchList()
    await storyStore.refreshStories()
    storyStore.broadcastStories()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function toggleMore(id: number, event?: MouseEvent) {
  if (activeMoreId.value === id) {
    activeMoreId.value = null
  } else {
    activeMoreId.value = id
    if (event) {
      menuPosition.value = { x: event.clientX, y: event.clientY }
    }
  }
}

const menuPosition = ref({ x: 0, y: 0 })

function getMenuStyle(): Record<string, string> {
  return {
    top: `${menuPosition.value.y + 10}px`,
    left: `${menuPosition.value.x - 80}px`,
  }
}

function handleMoreCommand(cmd: string, row: Story) {
  const routes: Record<string, string> = {
    characters: `/admin/stories/${row.id}/characters`,
    prompt: `/admin/stories/${row.id}/prompt`,
    'state-config': `/admin/stories/${row.id}/state-config`,
  }
  if (routes[cmd]) {
    router.push(routes[cmd])
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该故事？', '确认', { type: 'warning' })
    await deleteStory(id)
    ElMessage.success('已删除')
    await fetchList()
    await storyStore.refreshStories()
    storyStore.broadcastStories()
  } catch {
    // user cancelled confirmation dialog
  }
}

async function handleBulkDelete() {
  if (selectedIds.value.length === 0) return

  try {
    await ElMessageBox.confirm(`确定批量删除 ${selectedIds.value.length} 个故事？`, '确认', {
      type: 'warning',
    })
    const results = await Promise.allSettled(selectedIds.value.map((id) => deleteStory(id)))
    const failed = results.filter((result) => result.status === 'rejected')
    selectedIds.value = []
    await fetchList()
    await storyStore.refreshStories()
    storyStore.broadcastStories()
    if (failed.length === 0) {
      ElMessage.success(`批量删除完成，共删除 ${results.length} 项`)
    } else {
      ElMessage.warning(
        `批量删除完成，成功 ${results.length - failed.length} 项，失败 ${failed.length} 项`,
      )
    }
  } catch {
    // user cancelled confirmation dialog
  }
}

function handleCancelPreview() {
  ElMessageBox.confirm('确定放弃生成的內容吗？', '确认', {
    confirmButtonText: '确定放弃',
    cancelButtonText: '继续编辑',
    type: 'warning',
  })
    .then(() => {
      cancelPreview()
    })
    .catch(() => {
      // 继续编辑
    })
}

function applyPreview() {
  const data = confirmFill()
  if (!data) return
  form.title = data.title
  form.description = data.description
  form.world_setting = data.world_setting
  form.cover_image = data.cover_url || ''
  form.background_image = data.background_url || ''
  form.image_style = data.image_style || ''
  form.opening_requirement = data.opening_requirement || ''
  tagsInput.value = (data.tags || []).join(', ')
}

onMounted(async () => {
  await fetchList()
  const editId = route.query.editId
  if (editId) {
    const story = stories.value.find((s) => s.id === Number(editId))
    if (story) openDialog(story)
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 20px;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: 10px;
}

.tag-item {
  margin-right: 4px;
}

.description-cell {
  display: -webkit-box;
  overflow: hidden;
  color: var(--text-secondary);
  line-height: 1.5;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.cover-thumb {
  width: 64px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  background-color: var(--bg-input);
  background-image: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent-color) 22%, var(--bg-elevated)),
    var(--bg-elevated)
  );
  background-size: cover;
  background-position: center;
}

.story-preview {
  margin-top: 12px;
  border-top: 1px dashed var(--border-color);
  padding-top: 12px;
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.preview-card {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 12px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 10px;
  background: var(--bg-input);
}

.preview-cover {
  width: 100%;
  min-height: 96px;
  border-radius: 8px;
  background-color: var(--bg-secondary);
  background-image: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent-color) 22%, var(--bg-elevated)),
    var(--bg-elevated)
  );
  background-size: cover;
  background-position: center;
}

.preview-content h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 15px;
}

.preview-content p {
  margin: 8px 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.preview-category {
  font-size: 12px;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 2px 8px;
  background: color-mix(in srgb, var(--accent-color) 18%, transparent);
}

.preview-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.preview-tag {
  font-size: 12px;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 2px 8px;
}

.preview-tag.muted {
  color: var(--text-muted);
}

:deep(.story-table .el-table__inner-wrapper::before) {
  background-color: var(--border-color);
}

:deep(.story-table .el-table__empty-block) {
  background: var(--bg-secondary);
}

.mobile-story-list {
  display: none;
}

.mobile-story-card {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 12px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 18%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.035),
      color-mix(in srgb, var(--accent-color) 4.5%, transparent)
    ),
    var(--admin-card-bg);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16);
}

.mobile-story-cover {
  width: 88px;
  min-height: 116px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 10px;
  background-color: var(--bg-input);
  background-image: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent-color) 22%, var(--bg-elevated)),
    var(--bg-elevated)
  );
  background-size: cover;
  background-position: center;
}

.mobile-story-main {
  min-width: 0;
}

.mobile-story-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  color: var(--text-muted);
  font-size: 12px;
}

.mobile-story-meta span {
  border: 1px solid color-mix(in srgb, var(--accent-color) 18%, transparent);
  border-radius: 999px;
  padding: 2px 8px;
  background: color-mix(in srgb, var(--accent-color) 8%, transparent);
}

.mobile-story-main h3 {
  margin: 8px 0 0;
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.mobile-story-main p {
  display: -webkit-box;
  margin: 8px 0 0;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.mobile-story-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.mobile-story-tags span {
  max-width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--text-primary);
  font-size: 12px;
}

.mobile-story-tags .muted {
  color: var(--text-muted);
}

.mobile-story-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.mobile-story-actions button {
  min-height: 44px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 24%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--accent-color) 10%, transparent);
  color: var(--text-primary);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.mobile-story-actions button:active {
  background: color-mix(in srgb, var(--accent-color) 18%, transparent);
}

.mobile-story-actions .danger {
  border-color: rgba(248, 113, 113, 0.3);
  background: rgba(248, 113, 113, 0.12);
  color: #fecaca;
}

/* ---- 操作按钮容器 ---- */
.action-buttons {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.action-buttons .el-button--small {
  border-radius: 6px;
  padding: 5px 9px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  min-height: 32px;
}

/* 更多按钮箭头 */
.action-buttons .el-button--small svg {
  margin-left: 2px;
}

/* 下拉菜单遮罩层 */
.more-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
}

/* 下拉菜单卡片 - 圆润设计 */
.more-menu-card {
  position: fixed;
  min-width: 150px;
  padding: 8px;
  background: var(--bg-elevated, var(--bg-card));
  border: 1px solid var(--border-color);
  border-radius: 16px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
  z-index: 10000;
}

.more-menu-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-smooth);
}

.more-menu-btn:hover {
  background: var(--bg-hover);
}

.more-menu-btn svg {
  flex-shrink: 0;
  color: var(--accent-color);
}

/* 下拉菜单过渡动画 */
.dropdown-fade-enter-active {
  transition:
    opacity 120ms ease,
    transform 120ms ease;
}
.dropdown-fade-leave-active {
  transition:
    opacity 80ms ease,
    transform 80ms ease;
}
.dropdown-fade-enter-from {
  opacity: 0;
  transform: scale(0.95);
}
.dropdown-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

.preview-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.preview-field {
  display: flex;
  gap: 12px;
}
.preview-label {
  width: 60px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 600;
}
.preview-value {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}
.world-setting-preview {
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  background: var(--bg-input);
  border-radius: 8px;
  padding: 8px 12px;
}
.cover-preview-img {
  max-width: 240px;
  max-height: 180px;
  border-radius: 8px;
  object-fit: cover;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  margin-top: 8px;
}

/* Glass el-table */
:deep(.el-table) {
  background: transparent;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: color-mix(in srgb, var(--accent-color) 8%, transparent);
  border-radius: 12px;
  overflow: hidden;
}

:deep(.el-table th.el-table__cell) {
  background: color-mix(in srgb, var(--accent-color) 10%, transparent) !important;
  color: var(--text-primary);
  font-weight: 600;
  border-bottom: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid color-mix(in srgb, var(--accent-color) 10%, transparent);
}

:deep(.el-table__body tr:hover > td.el-table__cell) {
  background: color-mix(in srgb, var(--accent-color) 6%, transparent) !important;
}

:deep(.el-table--stripe .el-table__body tr.el-table__row--striped > td.el-table__cell) {
  background: color-mix(in srgb, var(--accent-color) 3%, transparent);
}

/* Glass el-dialog */
:deep(.el-dialog) {
  background: var(--admin-card-bg);
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

.story-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.generating-steps {
  margin-bottom: 12px;
  padding: 12px;
  background: color-mix(in srgb, var(--accent-color) 6%, transparent);
  border: 1px dashed color-mix(in srgb, var(--accent-color) 30%, transparent);
  border-radius: 10px;
}
.generating-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  line-height: 1.8;
  font-family: var(--font-sans);
}
.step-icon {
  width: 14px;
  text-align: center;
  flex-shrink: 0;
}
.step-active {
  color: var(--accent-color);
}
.step-done {
  color: var(--success-color);
}
.step-pending {
  color: var(--text-muted);
}
.flow-text {
  color: var(--accent-color);
}

/* Glass el-form */
:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: var(--admin-input-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 10px;
}

:deep(.el-input__wrapper:hover),
:deep(.el-textarea__inner:hover) {
  border-color: color-mix(in srgb, var(--accent-color) 40%, transparent);
}

:deep(.el-input__wrapper.is-focus),
:deep(.el-textarea__inner:focus) {
  border-color: var(--accent-color);
  box-shadow: 0 0 12px color-mix(in srgb, var(--accent-color) 20%, transparent);
}

@media (prefers-reduced-motion: reduce) {
  :deep(.el-dialog),
  :deep(.el-table) {
    transition: none;
  }
}

@media (max-width: 767px) {
  .table-scroll-mobile {
    overflow-x: hidden;
  }

  .page-header {
    align-items: flex-start;
    gap: 12px;
  }

  .page-header h2 {
    font-size: 18px;
  }

  .header-actions {
    flex-shrink: 0;
  }

  .desktop-bulk-delete {
    display: none;
  }

  :deep(.story-table) {
    display: none;
  }

  .mobile-story-list {
    display: grid;
    gap: 12px;
  }

  .mobile-story-card {
    grid-template-columns: 76px 1fr;
    padding: 10px;
  }

  .mobile-story-cover {
    width: 76px;
    min-height: 104px;
  }

  .story-dialog-footer {
    display: grid;
    grid-template-columns: 1fr;
  }

  .story-dialog-footer :deep(.el-button) {
    width: 100%;
    min-height: 44px;
    margin-left: 0 !important;
  }

  .preview-card {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.story-edit-dialog {
  --el-dialog-margin-top: 24px;
  width: min(600px, calc(100vw - 32px)) !important;
  max-height: calc(100dvh - 48px);
  display: flex;
  flex-direction: column;
  margin-top: 24px !important;
  margin-bottom: 24px;
}

.story-edit-dialog .el-dialog__body {
  min-height: 0;
  overflow-y: auto;
  max-height: calc(100dvh - 190px);
}

.story-edit-dialog .el-dialog__footer {
  flex-shrink: 0;
  border-top: 1px solid color-mix(in srgb, var(--accent-color) 16%, transparent);
  padding: 12px 20px 16px;
}

@media (max-width: 767px) {
  .story-edit-dialog {
    --el-dialog-margin-top: 12px;
    position: fixed;
    top: 12px;
    right: 10px;
    left: 10px;
    width: auto !important;
    max-height: calc(100dvh - 108px);
    margin: 0 !important;
    border-radius: 16px;
  }

  .story-edit-dialog .el-dialog__body {
    max-height: calc(100dvh - 252px);
    padding: 14px 16px;
  }

  .story-edit-dialog .el-dialog__footer {
    padding: 12px 16px 14px;
  }
}
</style>
