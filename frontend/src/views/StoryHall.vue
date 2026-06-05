<template>
  <div class="story-hall">
    <div class="hall-header">
      <div class="header-row">
        <div>
          <h1>故事大厅</h1>
          <p class="hall-subtitle">选择一个故事，开始你的冒险</p>
        </div>

        <div class="hall-actions">
          <button class="hall-action-btn create-btn" type="button" @click="openCreateDialog">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            创建故事
          </button>
          <button
            v-if="isAdmin"
            class="hall-action-btn admin-entry"
            type="button"
            @click="router.push('/admin')"
          >
            管理
          </button>
        </div>
      </div>
    </div>

    <!-- 分类筛选 -->
    <div class="category-filter">
      <button
        v-for="cat in categories"
        :key="cat"
        class="filter-pill"
        :class="{ active: selectedCategory === cat }"
        @click="selectedCategory = cat"
      >
        {{ cat }}
      </button>
    </div>

    <!-- 搜索框 - 可折叠设计 -->
    <div class="story-search" :class="{ expanded: searchExpanded }">
      <button
        class="story-search-trigger"
        type="button"
        :aria-label="searchExpanded ? '聚焦搜索' : '展开搜索'"
        :aria-expanded="searchExpanded"
        @click="handleSearchButtonClick"
      >
        <svg
          class="search-icon"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      </button>
      <input
        ref="searchInputRef"
        v-model="searchQuery"
        :tabindex="searchExpanded ? 0 : -1"
        class="story-search-input"
        placeholder="搜索故事标题、简介、标签..."
        @keydown.esc="handleSearchEsc"
        @blur="handleSearchBlur"
      />
      <button
        v-if="searchExpanded && searchQuery"
        class="story-search-clear"
        @mousedown.prevent="clearSearch"
      >
        ×
      </button>
    </div>

    <!-- 故事卡片网格 -->
    <div class="story-grid">
      <!-- 骨架屏：加载中时显示 -->
      <template v-if="storyStore.loading">
        <div v-for="i in 6" :key="'skeleton-' + i" class="story-card-skeleton">
          <SkeletonBlock height="160px" border-radius="16px" />
          <SkeletonText :lines="2" style="margin-top: 12px" />
        </div>
      </template>
      <!-- 真实内容 -->
      <template v-else>
        <StoryCard
          v-for="story in filteredStories"
          :key="story.id"
          :story="story"
          @click="enterStory(story.id)"
          @duplicate="openCreateDialogAsCopy(story.id)"
        />
        <div v-if="storyStore.fetchError" class="empty-tip">
          <svg
            class="empty-icon"
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="32" cy="32" r="24" stroke="currentColor" stroke-width="2" />
            <line
              x1="22"
              y1="22"
              x2="42"
              y2="42"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
            <line
              x1="42"
              y1="22"
              x2="22"
              y2="42"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
          <p class="empty-text">加载失败：{{ storyStore.fetchError }}</p>
          <el-button type="primary" style="margin-top: 16px" @click="storyStore.fetchStories()"
            >重试</el-button
          >
        </div>
        <div v-else-if="filteredStories.length === 0" class="empty-tip">
          <svg
            class="empty-icon"
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect
              x="8"
              y="12"
              width="48"
              height="40"
              rx="4"
              stroke="currentColor"
              stroke-width="2"
            />
            <line x1="8" y1="24" x2="56" y2="24" stroke="currentColor" stroke-width="2" />
            <line x1="20" y1="12" x2="20" y2="24" stroke="currentColor" stroke-width="2" />
            <line x1="44" y1="12" x2="44" y2="24" stroke="currentColor" stroke-width="2" />
            <rect x="16" y="32" width="12" height="2" rx="1" fill="currentColor" opacity="0.4" />
            <rect x="16" y="38" width="24" height="2" rx="1" fill="currentColor" opacity="0.4" />
            <rect x="16" y="44" width="16" height="2" rx="1" fill="currentColor" opacity="0.4" />
          </svg>
          <p class="empty-text">暂无故事</p>
          <p class="empty-hint">快去创作第一个故事吧</p>
          <button
            class="hall-action-btn create-btn"
            style="margin-top: 16px"
            @click="openCreateDialog"
          >
            创建第一个故事
          </button>
        </div>
      </template>
    </div>

    <!-- 创建/复制故事弹窗 -->
    <el-dialog
      v-model="createDialogVisible"
      :title="createTab === 'new' ? '新建故事' : '基于已有故事创建'"
      width="600px"
    >
      <el-tabs v-model="createTab" class="create-tabs">
        <el-tab-pane label="新建故事" name="new" />
        <el-tab-pane label="基于已有故事" name="copy" />
      </el-tabs>

      <!-- 新建表单 -->
      <el-form
        v-if="createTab === 'new'"
        :model="createForm"
        label-width="80px"
        class="create-form"
      >
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" placeholder="给你的故事起个名字" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="createForm.category" style="width: 100%">
            <el-option v-for="cat in STORY_CATEGORIES" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="createTagsInput" placeholder="使用英文逗号分隔，如：恋爱,校园" />
        </el-form-item>
        <el-form-item label="封面图">
          <div style="display: flex; align-items: center; gap: 10px">
            <div
              v-if="createForm.cover_image"
              style="
                width: 80px;
                height: 50px;
                border-radius: 4px;
                background-size: cover;
                background-position: center;
              "
              :style="{ backgroundImage: `url(${createForm.cover_image})` }"
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
              v-if="createForm.background_image"
              style="
                width: 80px;
                height: 50px;
                border-radius: 4px;
                background-size: cover;
                background-position: center;
              "
              :style="{ backgroundImage: `url(${createForm.background_image})` }"
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
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="2"
            placeholder="简短介绍故事背景"
          />
        </el-form-item>
        <el-form-item label="世界观">
          <el-input
            v-model="createForm.world_setting"
            type="textarea"
            :rows="isMobile ? 2 : 3"
            placeholder="描述故事的世界观、设定等"
          />
        </el-form-item>
        <el-form-item label="默认开场提示词">
          <el-input
            v-model="createForm.opening_requirement"
            type="textarea"
            :rows="isMobile ? 2 : 3"
            placeholder="故事开场时用户看到的引导文本，将作为开场消息发送给AI"
          />
        </el-form-item>
        <el-form-item label="图片风格">
          <el-input
            v-model="createForm.image_style"
            type="textarea"
            :rows="2"
            placeholder="如：漫画分格，简洁有力的对话气泡风格。留空则 AI 自动生成"
          />
        </el-form-item>
      </el-form>

      <!-- 复制选择列表 -->
      <div v-if="createTab === 'copy'" class="copy-list">
        <p class="copy-hint">选择一个故事作为模板：</p>
        <div class="copy-story-list">
          <div
            v-for="story in storyStore.stories"
            :key="story.id"
            class="copy-story-item"
            :class="{ selected: selectedCopyId === story.id }"
            @click="selectedCopyId = story.id"
          >
            <div class="copy-story-info">
              <span class="copy-story-title">{{ story.title }}</span>
              <span class="copy-story-category">{{ story.category }}</span>
            </div>
            <span v-if="selectedCopyId === story.id" class="copy-check">✓</span>
          </div>
        </div>
        <p v-if="selectedCopyId" class="copy-confirm">
          将复制「{{ selectedStoryForCopy?.title }}」并创建新故事
        </p>
      </div>

      <template #footer>
        <el-button :disabled="creating" @click="createDialogVisible = false">取消</el-button>
        <el-button
          :loading="generating"
          type="info"
          @click="
            () => {
              if (!createForm.category) {
                ElMessage.warning('请先选择分类')
                return
              }
              handleOpenModelSelect()
            }
          "
        >
          一键AI生成
        </el-button>
        <el-button v-if="editingStoryId" type="warning" @click="handleStandaloneGenerateCover"
          >一键AI生成封面</el-button
        >
        <el-button v-if="editingStoryId" type="warning" @click="handleStandaloneGenerateBackground"
          >一键AI生成背景</el-button
        >
        <el-button type="primary" :loading="creating" @click="handleCreate">
          {{ createTab === 'new' ? '创建' : '复制并创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 模型选择弹窗 -->
    <el-dialog v-model="modelSelectVisible" title="选择模型" width="400px" destroy-on-close>
      <p style="margin-bottom: 12px; color: var(--text-secondary); font-size: 13px">
        请选择用于生成故事内容的模型
      </p>
      <div v-if="generating" class="generating-steps">
        <div
          v-for="(step, idx) in generatingSteps"
          :key="idx"
          class="generating-step"
          :class="{
            'step-active': generatingStep === idx,
            'step-done': generatingStep > idx,
            'step-pending': generatingStep < idx,
          }"
        >
          <span class="step-icon">
            <template v-if="generatingStep > idx">✓</template>
            <template v-else-if="generatingStep === idx">✦</template>
            <template v-else>○</template>
          </span>
          <span :class="{ 'flow-text': generatingStep === idx }">{{ step }}</span>
        </div>
      </div>
      <el-select
        v-model="selectedModelId"
        placeholder="选择模型"
        style="width: 100%"
        :disabled="generating"
      >
        <el-option v-for="m in availableModels" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <div style="margin-top: 12px">
        <el-input
          v-model="createForm.preference"
          type="textarea"
          :rows="2"
          placeholder="写下你的偏好，如：我想成为一个世界首富"
          :disabled="generating"
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
          <el-switch v-model="generateCover" :disabled="generating" />
        </div>
        <ModelSelect
          v-if="generateCover"
          v-model="coverImageModelId"
          :options="imageModels"
          placeholder="选择图片模型"
          style="margin-bottom: 12px"
          :disabled="generating"
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
          <el-switch v-model="generateBackground" :disabled="generating" />
        </div>
        <ModelSelect
          v-if="generateBackground"
          v-model="backgroundImageModelId"
          :options="imageModels"
          placeholder="选择图片模型"
          :disabled="generating"
        />
      </div>
      <template #footer>
        <el-button v-if="!generating" @click="modelSelectVisible = false">取消</el-button>
        <el-button
          v-if="!generating"
          type="primary"
          :disabled="!selectedModelId || generating"
          @click="
            confirmGenerate({
              category: createForm.category,
              title_hint: createForm.title,
              tags_hint: createTagsInput,
              image_style: createForm.image_style,
              preference: createForm.preference,
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
          <div class="preview-label">图片风格</div>
          <div class="preview-value">{{ previewData.image_style || '(AI自动生成)' }}</div>
        </div>
        <div class="preview-field">
          <div class="preview-label">开场提示词</div>
          <div class="preview-value world-setting-preview">
            {{ previewData.opening_requirement || '(AI自动生成)' }}
          </div>
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
                category: createForm.category,
                title_hint: createForm.title,
                tags_hint: createTagsInput,
                image_style: createForm.image_style,
                preference: createForm.preference,
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
import { ref, computed, onMounted, onBeforeUnmount, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useStoryStore } from '../stores/story'
import {
  createStory,
  standaloneGenerateCover,
  standaloneGenerateBackground,
  uploadStoryImage,
  getModels,
} from '../api'
import { STORY_CATEGORIES } from '../constants/categories'
import { MODEL_TYPE_IMAGE } from '../constants/modelTypes'
import StoryCard from '../components/StoryCard.vue'
import SkeletonBlock from '../components/ui/SkeletonBlock.vue'
import SkeletonText from '../components/ui/SkeletonText.vue'
import ModelSelect from '../components/ModelSelect.vue'
import { useStoryGenerate } from '../composables/useStoryGenerate'

const router = useRouter()

const storyStore = useStoryStore()

const {
  generating,
  generatingStep,
  generatingSteps,
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
      // 继续编辑，什么都不做
    })
}

function readAdminMode() {
  return localStorage.getItem('admin_mode') === '1'
}

const isAdmin = ref(readAdminMode())

// 移动端检测
const isMobile = ref(window.innerWidth <= 480)
function handleResize() {
  isMobile.value = window.innerWidth <= 480
}
window.addEventListener('resize', handleResize)

function syncAdminMode() {
  isAdmin.value = readAdminMode()
}

function handleAdminModeChanged() {
  syncAdminMode()
}

function handleAdminModeStorage(e: StorageEvent) {
  if (e.key === 'admin_mode') {
    syncAdminMode()
  }
}
const selectedCategory = ref('全部')
const searchQuery = ref('')
const searchExpanded = ref(false)
const searchInputRef = ref<HTMLInputElement | null>(null)

function expandSearch() {
  if (!searchExpanded.value) {
    searchExpanded.value = true
    nextTick(() => {
      searchInputRef.value?.focus()
    })
  }
}

function clearSearch() {
  searchQuery.value = ''
  searchInputRef.value?.focus()
}

function handleSearchButtonClick() {
  if (!searchExpanded.value) {
    expandSearch()
    return
  }
  searchInputRef.value?.focus()
}

function handleSearchEsc() {
  if (searchQuery.value) {
    searchQuery.value = ''
  } else {
    searchExpanded.value = false
  }
}

function handleSearchBlur() {
  if (!searchQuery.value) {
    searchExpanded.value = false
  }
}

const categories = computed(() => ['全部', ...new Set(storyStore.stories.map((s) => s.category))])

const filteredStories = computed(() => {
  let list = storyStore.stories
  if (selectedCategory.value !== '全部') {
    list = list.filter((s) => s.category === selectedCategory.value)
  }
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.tags.some((t) => t.toLowerCase().includes(q)),
    )
  }
  return list
})

function enterStory(storyId: number) {
  router.push(`/play/${storyId}`)
}

// ---- 创建/复制故事弹窗 ----
const createDialogVisible = ref(false)
const createTab = ref<'new' | 'copy'>('new')
const selectedCopyId = ref<number | null>(null)
const creating = ref(false)
const createTagsInput = ref('')
const createCategory = ref('')
const createForm = reactive({
  title: '',
  category: '其他',
  preference: '',
  cover_image: '',
  background_image: '',
  description: '',
  world_setting: '',
  opening_requirement: '',
  image_style: '',
})

const selectedStoryForCopy = computed(() =>
  storyStore.stories.find((s) => s.id === selectedCopyId.value),
)

function openCreateDialog() {
  createTab.value = 'new'
  selectedCopyId.value = null
  Object.assign(createForm, {
    title: '',
    category: '其他',
    preference: '',
    cover_image: '',
    background_image: '',
    description: '',
    world_setting: '',
    opening_requirement: '',
    image_style: '',
  })
  createTagsInput.value = ''
  createCategory.value = createForm.category
  createDialogVisible.value = true
}

function openCreateDialogAsCopy(storyId: number) {
  createTab.value = 'copy'
  selectedCopyId.value = storyId
  // 预填表单数据
  const src = storyStore.stories.find((s) => s.id === storyId)
  if (src) {
    Object.assign(createForm, {
      title: src.title + '（副本）',
      category: src.category,
      preference: src.preference || '',
      cover_image: src.cover_image || '',
      background_image: src.background_image || '',
      description: src.description || '',
      world_setting: src.world_setting || '',
      opening_requirement: src.opening_requirement || '',
      image_style: src.image_style || '',
    })
    createTagsInput.value = (src.tags || []).join(', ')
  }
  createDialogVisible.value = true
}

async function handleCreate() {
  createCategory.value = createForm.category
  creating.value = true
  try {
    if (createTab.value === 'copy' && !selectedCopyId.value) {
      ElMessage.warning('请先选择一个故事')
      return
    }

    if (!createForm.title?.trim() && createTab.value !== 'copy') {
      ElMessage.warning('请填写故事标题')
      return
    }

    const formData = {
      title: createForm.title,
      category: createForm.category,
      cover_image: createForm.cover_image,
      background_image: createForm.background_image,
      description: createForm.description,
      world_setting: createForm.world_setting,
      opening_requirement: createForm.opening_requirement,
      image_style: createForm.image_style,
      tags: createTagsInput.value
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    }

    if (createTab.value === 'copy') {
      const src = selectedStoryForCopy.value
      if (src) {
        // 直接从模板故事取数据填充
        formData.title = src.title + '（副本）'
        formData.category = src.category || '其他'
        formData.cover_image = src.cover_image || ''
        formData.background_image = src.background_image || ''
        formData.description = src.description || ''
        formData.world_setting = src.world_setting || ''
        formData.opening_requirement = src.opening_requirement || ''
        formData.image_style = src.image_style || ''
        formData.tags = Array.isArray(src.tags) ? src.tags : []
      }
    }

    const { data } = await createStory(formData)
    createDialogVisible.value = false
    router.push(`/admin/stories?editId=${data.id}`)
  } catch {
    ElMessage.error('创建失败，请重试')
  } finally {
    creating.value = false
  }
}

let unsubscribe: () => void

function applyPreview() {
  const data = confirmFill()
  if (!data) return
  createForm.title = data.title
  createForm.description = data.description
  createForm.world_setting = data.world_setting
  createForm.cover_image = data.cover_url || ''
  createForm.background_image = data.background_url || ''
  createForm.image_style = data.image_style || ''
  createForm.opening_requirement = data.opening_requirement || ''
  createTagsInput.value = (data.tags || []).join(', ')
}

// ---- 独立图片生成 & 上传 ----
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
// 记录已创建故事的 ID，用于上传/独立生成（创建后才有 story_id）
const editingStoryId = ref<number | null>(null)

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
  if (!editingStoryId.value) return
  imageGeneratePurpose.value = 'cover'
  imageModelDialogTitle.value = '选择图片模型 — 生成封面'
  selectedImageModelId.value = null
  loadAllModels()
  imageModelSelectVisible.value = true
}

function handleStandaloneGenerateBackground() {
  if (!editingStoryId.value) return
  imageGeneratePurpose.value = 'background'
  imageModelDialogTitle.value = '选择图片模型 — 生成背景'
  selectedImageModelId.value = null
  loadAllModels()
  imageModelSelectVisible.value = true
}

async function confirmStandaloneImageGenerate() {
  if (!selectedImageModelId.value || !editingStoryId.value || standaloneGenerating.value) return
  standaloneGenerating.value = true
  standaloneGeneratingStep.value = 0
  try {
    if (imageGeneratePurpose.value === 'cover') {
      const { data } = await standaloneGenerateCover(
        editingStoryId.value,
        selectedImageModelId.value,
      )
      createForm.cover_image = data.cover_image
    } else {
      const { data } = await standaloneGenerateBackground(
        editingStoryId.value,
        selectedImageModelId.value,
      )
      createForm.background_image = data.background_image
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
  if (!editingStoryId.value) {
    ElMessage.warning('请先创建故事后再上传封面图')
    return
  }
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    try {
      const { data } = await uploadStoryImage(editingStoryId.value!, file, 'cover')
      createForm.cover_image = data.cover_image
      ElMessage.success('封面图上传成功')
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '上传失败')
    }
  }
  input.click()
}

async function handleUploadBackground() {
  if (!editingStoryId.value) {
    ElMessage.warning('请先创建故事后再上传背景图')
    return
  }
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    try {
      const { data } = await uploadStoryImage(editingStoryId.value!, file, 'background')
      createForm.background_image = data.background_image
      ElMessage.success('背景图上传成功')
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '上传失败')
    }
  }
  input.click()
}

onMounted(() => {
  storyStore.fetchStories()
  // Subscribe to same-tab story updates
  unsubscribe = storyStore.subscribe(() => {
    storyStore.fetchStories()
  })
  window.addEventListener('admin-mode-changed', handleAdminModeChanged)
  window.addEventListener('storage', handleAdminModeStorage)
})

onBeforeUnmount(() => {
  unsubscribe?.()
  window.removeEventListener('admin-mode-changed', handleAdminModeChanged)
  window.removeEventListener('storage', handleAdminModeStorage)
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.story-hall {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
}

/* ---- 头部区域 ---- */
.hall-header {
  margin-bottom: 28px;
  padding: 28px 32px;
  background:
    radial-gradient(ellipse at 30% 0%, rgba(20, 184, 166, 0.15) 0%, transparent 50%),
    linear-gradient(135deg, rgba(20, 184, 166, 0.08) 0%, transparent 60%);
  border-radius: 16px;
  border: 1px solid var(--border-color);
  box-shadow:
    var(--shadow-md),
    inset 0 0 60px rgba(20, 184, 166, 0.05);
  animation: header-in 400ms var(--ease-out) both;
}

@keyframes header-in {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.hall-actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  min-width: 148px;
}

.hall-header h1 {
  position: relative;
  display: inline-block;
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  font-family: var(--heading);
}

/* 主色签名点缀（纯装饰，绝对定位不占布局流） */
.hall-header h1::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -6px;
  width: 44px;
  height: 3px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent-color), transparent);
}

.hall-subtitle {
  color: var(--text-muted);
  margin-top: 6px;
  font-size: 14px;
}

.hall-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  padding: 8px 18px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-smooth),
    box-shadow var(--duration-fast) var(--ease-smooth),
    background-color var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth);
  box-shadow: var(--shadow-sm);
  background: var(--user-bubble);
  color: #fff;
}

.hall-action-btn:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  background: var(--accent-hover);
}

.create-btn,
.admin-entry {
  width: 100%;
}

/* ---- 分类筛选 ---- */
.category-filter {
  display: flex;
  gap: 8px;
  margin-bottom: 28px;
  flex-wrap: wrap;
  animation: fade-in 300ms var(--ease-out) 100ms both;
}

.filter-pill {
  padding: 6px 16px;
  min-height: 44px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-smooth);
}

.filter-pill:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
  color: var(--text-primary);
  border-color: color-mix(in srgb, var(--accent-color) 40%, transparent);
  background: var(--bg-hover);
}

.filter-pill.active {
  background: var(--user-bubble);
  color: #fff;
  border-color: transparent;
  box-shadow:
    var(--shadow-md),
    0 0 16px color-mix(in srgb, var(--accent-color) 30%, transparent);
}

.filter-pill.active:hover {
  background: var(--accent-hover);
  border-color: transparent;
  transform: translateY(-2px);
}

/* ---- 故事卡片网格 ---- */
.story-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
}

/* ---- 空状态 ---- */
.empty-tip {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--text-muted);
  padding: 80px 0;
  opacity: 0;
  animation: empty-fade-in 300ms ease-out 100ms forwards;
}

@keyframes empty-fade-in {
  to {
    opacity: 1;
  }
}

.empty-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  color: var(--border-color);
}

.empty-text {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.empty-hint {
  font-size: 13px;
  color: var(--text-muted);
}

/* ---- 头部操作按钮 ---- */
/* ---- 创建弹窗表单 ---- */
.create-tabs {
  margin-bottom: 16px;
}
.create-form :deep(.el-form-item__label) {
  font-size: 13px;
}
.copy-list {
  min-height: 120px;
}
.copy-hint {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;
}
.copy-story-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
}
.copy-story-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-smooth),
    box-shadow var(--duration-fast) var(--ease-smooth),
    background-color var(--duration-fast) var(--ease-smooth),
    border-color var(--duration-fast) var(--ease-smooth),
    color var(--duration-fast) var(--ease-smooth);
}
.copy-story-item:hover {
  border-color: var(--accent-color);
  background: var(--bg-hover);
}
.copy-story-item.selected {
  border-color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 10%, transparent);
}
.copy-story-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.copy-story-title {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}
.copy-story-category {
  font-size: 12px;
  color: var(--text-muted);
}
.copy-check {
  color: var(--accent-color);
  font-size: 16px;
}
.copy-confirm {
  margin-top: 10px;
  font-size: 13px;
  color: var(--accent-color);
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

.story-hall :deep(.el-dialog__header) {
  padding: 16px 20px;
  margin-right: 0;
}

.story-hall :deep(.el-dialog__headerbtn) {
  width: 28px;
  height: 28px;
  background: rgba(20, 184, 166, 0.1);
  border: 1px solid rgba(20, 184, 166, 0.2);
  border-radius: 50%;
  top: 12px;
  right: 16px;
}

.story-hall :deep(.el-dialog__headerbtn:hover) {
  background: rgba(20, 184, 166, 0.2);
}

.story-hall :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: var(--text-secondary);
}

@media (max-width: 767px) {
  .story-hall {
    padding: 16px;
  }

  .hall-header {
    padding: 18px 16px;
    margin-bottom: 16px;
  }

  .hall-header h1 {
    font-size: 26px;
  }

  .hall-subtitle {
    font-size: 13px;
  }

  .header-row {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .hall-actions {
    width: 100%;
    min-width: 0;
  }

  .hall-action-btn {
    width: 100%;
    min-height: 44px;
    padding: 10px 16px;
  }
}

@media (max-width: 600px) {
  .story-hall :deep(.el-dialog) {
    max-width: calc(100vw - 32px);
    width: 100% !important;
  }
}

@media (max-width: 480px) {
  .story-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .filter-pill {
    padding: 8px 14px;
    font-size: 13px;
    min-height: 44px;
  }

  .create-form :deep(.el-form-item__label) {
    font-size: 12px;
  }

  .create-form :deep(.el-textarea__inner) {
    min-height: 44px;
  }

  /* el-dialog 移动端全宽 */
  .story-hall :deep(.el-dialog) {
    max-width: calc(100vw - 32px);
    width: 100% !important;
  }
}

@media (max-width: 380px) {
  .story-grid {
    grid-template-columns: 1fr;
  }
}

/* ---- 搜索框 - 可折叠设计 ---- */
.story-search {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
  border: 1.5px solid var(--accent-color);
  border-radius: 50%;
  background: rgba(20, 184, 166, 0.12);
  box-sizing: border-box;
  cursor: pointer;
  overflow: hidden;
  transition:
    width 420ms cubic-bezier(0.26, 0.88, 0.16, 1),
    border-radius 420ms cubic-bezier(0.26, 0.88, 0.16, 1),
    background 420ms cubic-bezier(0.26, 0.88, 0.16, 1),
    box-shadow 420ms cubic-bezier(0.26, 0.88, 0.16, 1);
}

.story-search.expanded {
  width: 100%;
  max-width: 480px;
  border-radius: 22px;
  background: var(--bg-input);
  box-shadow: 0 0 22px var(--accent-glow);
  cursor: auto;
}

.story-search-trigger {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border: none;
  background: transparent;
  color: var(--accent-color);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  transition:
    color 180ms var(--ease-smooth),
    transform 180ms var(--ease-smooth);
}

.story-search-trigger:hover,
.story-search-trigger:focus-visible {
  color: var(--text-primary);
}

.story-search-trigger:active {
  transform: scale(0.96);
}

.search-icon {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  color: var(--accent-color);
  margin: 0;
  transition: margin 420ms cubic-bezier(0.26, 0.88, 0.16, 1);
  cursor: pointer;
}

.story-search.expanded .story-search-trigger {
  width: 40px;
}

.story-search.expanded .search-icon {
  cursor: default;
}

.story-search-input {
  flex: 1;
  min-width: 0;
  max-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--text-sm);
  padding: 0;
  opacity: 0;
  transition:
    max-width 420ms cubic-bezier(0.26, 0.88, 0.16, 1),
    opacity 220ms ease;
}

.story-search.expanded .story-search-input {
  max-width: 480px;
  opacity: 1;
  transition-delay: 0ms, 200ms;
}

.story-search-input::placeholder {
  color: var(--text-muted);
}

.story-search-clear {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  margin-right: 10px;
  border: none;
  background: var(--bg-tertiary);
  border-radius: 50%;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  line-height: 1;
  transition:
    background 150ms,
    color 150ms;
}

.story-search-clear:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

@media (max-width: 480px) {
  .story-search.expanded {
    width: calc(100vw - 80px);
  }
}

/* AI 生成步骤骨架屏 */
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

/* ---- 骨架屏 ---- */
.story-card-skeleton {
  background: var(--bg-card);
  border-radius: 16px;
  padding: 12px;
  overflow: hidden;
}
</style>
