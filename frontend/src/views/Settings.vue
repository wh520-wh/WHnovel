<template>
  <div class="settings-layout">
    <!-- 移动端顶部导航（替代侧边栏） -->
    <div class="mobile-nav" v-if="sidebarMode === 'hidden'">
      <button
        v-for="item in navItems"
        :key="item.key"
        class="mobile-nav-item"
        :class="{ active: currentSection === item.key }"
        @click="currentSection = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <!-- 侧边导航 -->
    <aside class="settings-sidebar" :class="{ collapsed: sidebarMode === 'collapsed' }" v-if="sidebarMode !== 'hidden'">
      <!-- Logo 区域 -->
      <div class="sidebar-logo">
        <div class="logo-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#5eead4"/>
                <stop offset="100%" stop-color="#0f766e"/>
              </linearGradient>
            </defs>
            <path d="M12 2L2 7l10 5 10-5-10-5z" fill="url(#logoGrad)" opacity="0.9"/>
            <path d="M2 17l10 5 10-5" stroke="url(#logoGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            <path d="M2 12l10 5 10-5" stroke="url(#logoGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </svg>
        </div>
        <span class="logo-text" v-show="sidebarMode === 'expanded'">AI 故事</span>
      </div>

      <!-- 导航列表 -->
      <nav class="sidebar-nav">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: currentSection === item.key }"
          @click="currentSection = item.key"
          :title="sidebarMode !== 'expanded' ? item.label : undefined"
        >
          <span class="nav-icon" v-html="item.icon"></span>
          <span class="nav-label" v-show="sidebarMode === 'expanded'">{{ item.label }}</span>
          <span class="nav-indicator" v-if="currentSection === item.key"></span>
        </button>
      </nav>

      <!-- 底部帮助入口 -->
      <div class="sidebar-footer">
        <button class="help-btn" :class="{ collapsed: sidebarMode === 'collapsed' }" @click="openHelp" :title="sidebarMode !== 'expanded' ? '帮助与反馈' : undefined">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span v-show="sidebarMode === 'expanded'">帮助与反馈</span>
        </button>

        <!-- 响应式折叠按钮 -->
        <button class="collapse-btn" @click="sidebarMode = sidebarMode === 'expanded' ? 'collapsed' : 'expanded'" :title="sidebarMode === 'expanded' ? '收起侧边栏' : '展开侧边栏'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :style="{ transform: sidebarMode === 'collapsed' ? 'rotate(180deg)' : 'none', transition: 'transform 0.3s ease' }">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="settings-main">
      <!-- 内容头部 -->
      <div class="main-header">
        <div class="main-header-left">
          <button
            v-if="returnStoryId"
            class="back-play-btn"
            type="button"
            @click="goBackToPlay"
            :title="`返回故事 #${returnStoryId}${route.query.archiveId ? ` / 会话 #${route.query.archiveId}` : ''}`"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            返回进行中的故事
          </button>
          <h1 class="main-title">{{ sectionTitle }}</h1>
        </div>
        <button class="reset-btn" @click="handleReset" :disabled="saving">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="1 4 1 10 7 10"/>
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
          </svg>
          恢复默认
        </button>
      </div>

      <!-- 内容区（5个设置分组） -->
      <div class="main-content">
        <Transition name="fade-slide" mode="out-in">

          <!-- ===== 模型配置 ===== -->
          <section v-if="currentSection === 'model'" class="settings-content" key="model">
            <div class="settings-group">
              <div class="group-header">
                <div class="group-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/></svg>
                </div>
                <div class="group-title">模型选择</div>
                <button class="group-manage-btn" @click="router.push('/admin/models')" title="管理模型配置">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  管理模型
                </button>
              </div>
              <div class="settings-card">
                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">主用模型</div>
                    <div class="setting-hint">优先调用的模型</div>
                  </div>
                  <div class="setting-control" style="width: 100%; max-width: 340px;">
                    <ModelSelect
                      v-model="form.primary_model_id"
                      :options="enabledModels"
                      placeholder="请选择主用模型"
                    />
                  </div>
                </div>

                <div class="setting-row setting-row--block">
                  <div class="setting-info">
                    <div class="setting-label">备用模型</div>
                    <div class="setting-hint">主模型失败时自动切换</div>
                  </div>
                  <div class="backup-list-wrap">
                    <TransitionGroup v-if="form.backup_model_ids.length > 0" name="backup-item" tag="div" class="backup-list">
                      <div class="backup-item" v-for="(id, idx) in form.backup_model_ids" :key="id"
                        draggable="true"
                        @dragstart="onBackupDragStart(idx, $event)"
                        @dragover.prevent="onBackupDragOver(idx)"
                        @drop.prevent="onBackupDrop(idx)"
                        @dragend="onBackupDragEnd"
                        :class="{ 'is-dragging': dragIdx === idx, 'is-drag-over': dragOverIdx === idx }"
                      >
                        <span class="backup-drag-handle" title="拖拽排序">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="6" r="1.2"/><circle cx="15" cy="6" r="1.2"/><circle cx="9" cy="12" r="1.2"/><circle cx="15" cy="12" r="1.2"/><circle cx="9" cy="18" r="1.2"/><circle cx="15" cy="18" r="1.2"/></svg>
                        </span>
                        <span class="backup-rank">{{ idx + 1 }}</span>
                        <span class="backup-name">{{ modelNameById(id) }}</span>
                        <div class="backup-ops">
                          <button class="icon-btn" @click="moveBackupUp(idx)" :disabled="idx === 0" title="上移">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"/></svg>
                          </button>
                          <button class="icon-btn" @click="moveBackupDown(idx)" :disabled="idx === form.backup_model_ids.length - 1" title="下移">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
                          </button>
                          <button class="icon-btn icon-btn--danger" @click="removeBackup(idx)" title="删除">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                          </button>
                        </div>
                      </div>
                    </TransitionGroup>
                    <div v-else class="backup-empty">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                      暂无备用模型
                    </div>
                    <div class="backup-add-row">
                      <ModelSelect
                        v-model="backupCandidateId"
                        :options="backupCandidates"
                        placeholder="选择模型"
                        :disabled="backupCandidates.length === 0"
                        style="flex:1"
                      />
                      <button class="btn-add" @click="addBackup" :disabled="!backupCandidateId">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        添加
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- ===== 互动与图片设置 ===== -->
          <section v-else-if="currentSection === 'interaction'" class="settings-content" key="interaction">
            <div class="settings-group">
              <div class="group-header">
                <div class="group-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </div>
                <div class="group-title">互动设置</div>
              </div>
              <div class="settings-notice">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <span>保存后对新一轮对话生效；正在输出中的回复不受影响</span>
              </div>
              <div class="settings-card">
                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">上下文长度</div>
                    <div class="setting-hint">{{ form.context_length }} 轮对话记忆</div>
                  </div>
                  <div class="setting-control slider-wrap">
                    <el-slider v-model="form.context_length" :min="2" :max="30" :step="1" :show-tooltip="false" />
                  </div>
                </div>

                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">回复长度</div>
                  </div>
                  <div class="setting-control style-pills">
                    <button v-for="style in replyStyles" :key="style.value" class="style-pill" :class="{ active: form.reply_style === style.value }" @click="form.reply_style = style.value">{{ style.label }}</button>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">自动生成选项</div>
                    <div class="setting-hint">AI 回复后自动生成剧情选项</div>
                  </div>
                  <div class="setting-control">
                    <el-switch v-model="form.auto_generate_options" />
                  </div>
                </div>

                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">复制图片格式</div>
                    <div class="setting-hint">URL 为链接文本，图片为二进制</div>
                  </div>
                  <div class="setting-control style-pills">
                    <button class="style-pill" :class="{ active: form.copy_image_format === 'url' }" @click="form.copy_image_format = 'url'">URL</button>
                    <button class="style-pill" :class="{ active: form.copy_image_format === 'binary' }" @click="form.copy_image_format = 'binary'">图片</button>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">关闭聊天气泡弹性效果</div>
                    <div class="setting-hint">关闭后禁用聊天气泡入场、悬停和点击弹性反馈</div>
                  </div>
                  <div class="setting-control">
                    <el-switch v-model="form.disable_chat_bubble_elastic" />
                  </div>
                </div>

                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">管理员模式</div>
                    <div class="setting-hint">开启后显示管理后台入口，无需控制台命令</div>
                  </div>
                  <div class="setting-control">
                    <el-switch v-model="adminModeEnabled" @change="handleAdminModeToggle" />
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- ===== 图片设置 ===== -->
          <section v-else-if="currentSection === 'image'" class="settings-content" key="image">
            <div class="settings-group">
              <div class="group-header">
                <div class="group-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                </div>
                <div class="group-title">图片设置</div>
              </div>
              <div class="settings-card">
                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">使用模型</div>
                    <div class="setting-hint">聊天中生成图片所使用的模型</div>
                  </div>
                  <div class="setting-control" style="width: 100%; max-width: 340px;">
                    <ModelSelect
                      v-model="form.default_image_model_id"
                      :options="imageModels"
                      placeholder="选择图片模型"
                    />
                  </div>
                </div>

                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">图片尺寸</div>
                  </div>
                  <div class="setting-control radio-group">
                    <button class="radio" :class="{ active: form.image_size === '1K' }" @click="form.image_size = '1K'">1K</button>
                    <button class="radio" :class="{ active: form.image_size === '2K' }" @click="form.image_size = '2K'">2K</button>
                    <button class="radio" :class="{ active: form.image_size === '3K' }" @click="form.image_size = '3K'">3K</button>
                  </div>
                </div>

                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">添加水印</div>
                  </div>
                  <div class="setting-control">
                    <el-switch v-model="form.image_watermark" />
                  </div>
                </div>

                <div class="setting-row setting-row--block">
                  <div class="setting-info">
                    <div class="setting-label">全局风格</div>
                    <div class="setting-hint">用于未配置风格的故事</div>
                  </div>
                  <div class="textarea-wrap">
                    <el-input
                      type="textarea"
                      v-model="form.default_image_style"
                      :rows="2"
                      placeholder="如：漫画分格，简洁有力的对话气泡风格"
                      resize="none"
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- ===== 应用设置 ===== -->
          <section v-else-if="currentSection === 'app'" class="settings-content" key="app">
            <div class="settings-group">
              <div class="group-header">
                <div class="group-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                </div>
                <div class="group-title">应用设置</div>
              </div>
              <div class="settings-card">
                <!-- Group 1: 系统提示词 -->
                <div class="setting-row setting-row--block">
                  <div class="setting-info">
                    <div class="setting-label">全局默认系统提示词</div>
                    <div class="setting-hint">所有故事的默认系统提示词，可被故事级设置覆盖</div>
                  </div>
                  <div class="textarea-wrap">
                    <el-input
                      type="textarea"
                      v-model="form.default_system_prompt"
                      :rows="4"
                      placeholder="请输入全局默认系统提示词..."
                      resize="none"
                    />
                  </div>
                </div>

                <div class="setting-row setting-row--block">
                  <div class="setting-info">
                    <div class="setting-label">状态播报提示词</div>
                    <div class="setting-hint">AI 生成状态播报时的额外提示词规则</div>
                  </div>
                  <div class="textarea-wrap">
                    <el-input
                      type="textarea"
                      v-model="form.state_broadcast_prompt"
                      :rows="3"
                      placeholder="请输入状态播报提示词..."
                      resize="none"
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- ===== 剧情选项 ===== -->
          <section v-else-if="currentSection === 'plot'" class="settings-content" key="plot">
            <div class="settings-group">
              <div class="group-header">
                <div class="group-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                </div>
                <div class="group-title">剧情选项</div>
              </div>
              <div class="settings-card">
                <div class="setting-row setting-row--block">
                  <div class="setting-info">
                    <div class="setting-label">自定义提示词</div>
                    <div class="setting-hint">控制 AI 生成选项的格式，不填使用默认</div>
                  </div>
                  <div class="textarea-wrap">
                    <el-input type="textarea" v-model="form.options_prompt" :rows="4" placeholder="请仅根据当前剧情生成 N 个后续可选行动。要求：1.第二人称描述主角行动，禁止第一人称；2.单一确定性动作，禁止或/等不确定词；3.选项间有明显差异；4.简洁明确。不填则使用系统默认。" resize="none" />
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- ===== 外观 ===== -->
          <section v-else-if="currentSection === 'appearance'" class="settings-content" key="appearance">
            <div class="settings-group">
              <div class="group-header">
                <div class="group-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/></svg>
                </div>
                <div class="group-title">外观</div>
              </div>
              <div class="settings-card">
                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">主题</div>
                  </div>
                  <div class="setting-control theme-pills">
                    <button class="theme-pill" :class="{ active: themeStore.theme === 'dark' }" @click="themeStore.setTheme('dark')">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
                      暗色
                    </button>
                    <button class="theme-pill" :class="{ active: themeStore.theme === 'light' }" @click="themeStore.setTheme('light')">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/></svg>
                      亮色
                    </button>
                    <button class="theme-pill" :class="{ active: themeStore.theme === 'enigma' }" @click="themeStore.setTheme('enigma')">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                      Enigma
                    </button>
                    <button class="theme-pill" :class="{ active: themeStore.theme === 'claude' }" @click="themeStore.setTheme('claude')">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/></svg>
                      Claude
                    </button>
                  </div>
                </div>
                <div class="setting-row">
                  <div class="setting-info">
                    <div class="setting-label">聊天背景图</div>
                    <div class="setting-hint">关闭后所有故事不再显示聊天背景图（包括移动端）</div>
                  </div>
                  <div class="setting-control">
                    <el-switch v-model="form.show_background_image" />
                  </div>
                </div>
              </div>
            </div>
          </section>

        </Transition>
      </div>

      <!-- 底部保存按钮 -->
      <div class="main-footer">
        <button class="save-btn" @click="handleSave" :disabled="saving">
          <svg v-if="!saving" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
          </svg>
          <span class="save-spinner" v-if="saving"></span>
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useThemeStore } from '../stores/theme'
import ModelSelect from '../components/ModelSelect.vue'
import {
  ALLOWED_SETTINGS_SECTIONS,
  SETTINGS_SECTION_TITLES,
  useSettingsForm,
} from '../composables/useSettingsForm'

// ============== 导航状态 ==============
type SectionKey = typeof ALLOWED_SETTINGS_SECTIONS[number]

const currentSection = ref<SectionKey>('model')
const sidebarMode = ref<'expanded' | 'collapsed' | 'hidden'>('expanded')

const navItems: Array<{ key: SectionKey; label: string; icon: string }> = [
  {
    key: 'model',
    label: '模型配置',
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  },
  {
    key: 'interaction',
    label: '互动设置',
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  },
  {
    key: 'image',
    label: '图片设置',
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
  },
  {
    key: 'app',
    label: '全局设置',
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>`,
  },
  {
    key: 'plot',
    label: '剧情选项',
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  },
  {
    key: 'appearance',
    label: '外观',
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
  },
]

const sectionTitle = computed(() => SETTINGS_SECTION_TITLES[currentSection.value])

// ============== 表单数据 ==============
const themeStore = useThemeStore()
const route = useRoute()
const router = useRouter()

const {
  form,
  models,
  saving,
  backupCandidateId,
  adminModeEnabled,
  enabledModels,
  backupCandidates,
  imageModels,
  loadSettings,
  saveSettings,
  resetSettings,
  addBackup,
  removeBackup,
  moveBackupUp,
  moveBackupDown,
} = useSettingsForm()

const replyStyles = [
  { value: 'concise', label: '简短' },
  { value: 'detailed', label: '标准' },
  { value: 'creative', label: '丰富' },
]

const returnStoryId = computed(() => {
  const fromQuery = route.query.from
  const queryStoryId = Number(route.query.storyId)
  if (fromQuery === 'play' && Number.isFinite(queryStoryId) && queryStoryId > 0) {
    return queryStoryId
  }

  if (route.name === 'Settings') {
    return null
  }

  return null
})

// ============== 拖拽排序 ==============
const dragIdx = ref<number | null>(null)
const dragOverIdx = ref<number | null>(null)

function onBackupDragStart(idx: number, e: DragEvent) {
  dragIdx.value = idx
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function onBackupDragOver(idx: number) {
  if (dragIdx.value === null) return
  dragOverIdx.value = idx
}


function onBackupDrop(targetIdx: number) {
  if (dragIdx.value === null || dragIdx.value === targetIdx) return
  const arr = form.backup_model_ids
  const [item] = arr.splice(dragIdx.value, 1)
  arr.splice(targetIdx, 0, item)
  dragIdx.value = null
  dragOverIdx.value = null
}

function onBackupDragEnd() {
  dragIdx.value = null
  dragOverIdx.value = null
}

// ============== 响应式侧边栏 ==============
function handleResize() {
  if (window.innerWidth <= 768) {
    sidebarMode.value = 'hidden'
  } else if (window.innerWidth <= 900) {
    sidebarMode.value = 'collapsed'
  } else {
    sidebarMode.value = 'expanded'
  }
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

// ============== 生命周期 ==============
onMounted(loadSettings)

// ============== 方法 ==============
function modelNameById(id: number) {
  const m = models.value.find((x) => x.id === id)
  return m ? `${m.name} (${m.model_id})` : `模型 #${id}`
}

function openHelp() {
  ElMessage.info('帮助与反馈功能开发中...')
}

function handleAdminModeToggle(value: boolean) {
  if (value) {
    localStorage.setItem('admin_mode', '1')
  } else {
    localStorage.removeItem('admin_mode')
  }
  window.dispatchEvent(new Event('admin-mode-changed'))
}

function goBackToPlay() {
  if (!returnStoryId.value) return

  const query: Record<string, string> = {}
  const fromArchiveId = Number(route.query.archiveId)
  if (Number.isFinite(fromArchiveId) && fromArchiveId > 0) {
    query.archiveId = String(fromArchiveId)
  }

  const go = route.query.from === 'play' ? router.replace : router.push
  go({
    path: `/play/${returnStoryId.value}`,
    query,
  })
}

async function handleSave() {
  await saveSettings()
}

async function handleReset() {
  await resetSettings()
}
</script>

<style scoped>
/* ============== 布局 ============== */
.settings-layout {
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
  font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ============== 侧边栏 ============== */
.settings-sidebar {
  width: 220px;
  min-width: 220px;
  height: 100%;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width var(--duration-slow) var(--ease-smooth), min-width var(--duration-slow) var(--ease-smooth);
  overflow: hidden;
  position: relative;
  z-index: 10;
}

.settings-sidebar.collapsed {
  width: 64px;
  min-width: 64px;
}

/* Logo */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px;
  border-bottom: 1px solid var(--border-color);
  min-height: 64px;
  overflow: hidden;
}

.logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(94, 234, 212, 0.15), rgba(15, 118, 110, 0.1));
  border: 1px solid rgba(94, 234, 212, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  letter-spacing: -0.01em;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  padding: 12px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 16px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  position: relative;
  white-space: nowrap;
  text-align: left;
  font-family: inherit;
}

.nav-item:hover {
  color: var(--text-secondary);
  background: var(--settings-accent-subtle);
}

.nav-item.active {
  color: var(--accent-color);
  background: var(--settings-accent-subtle);
}

.nav-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-icon :deep(svg) {
  width: 18px;
  height: 18px;
}

.nav-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--accent-color);
  border-radius: 0 2px 2px 0;
  box-shadow: 0 0 8px var(--accent-glow);
}

/* 底部 */
.sidebar-footer {
  padding: 12px 8px;
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.help-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 8px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  white-space: nowrap;
  text-align: left;
  font-family: inherit;
}

.help-btn:hover {
  color: var(--text-secondary);
  background: var(--settings-accent-subtle);
}

.help-btn span {
  flex: 1;
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 8px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  font-family: inherit;
}

.collapse-btn:hover {
  color: var(--text-secondary);
  border-color: var(--border-color);
  background: var(--settings-accent-subtle);
}

/* ============== 主内容区 ============== */
.settings-main {
  flex: 1;
  height: 100%;
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* 头部 */
.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
  min-height: 64px;
  flex-shrink: 0;
}

.main-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.01em;
}

.reset-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  font-family: inherit;
}

.reset-btn:hover:not(:disabled) {
  border-color: var(--accent-color);
  color: var(--accent-color);
  background: var(--settings-accent-subtle);
}

.reset-btn:active:not(:disabled) {
  transform: scale(0.97);
}

.reset-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 内容区 */
.main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 18px 24px;
  scrollbar-width: thin;
  scrollbar-color: var(--border-color) transparent;
}

.main-content::-webkit-scrollbar {
  width: 6px;
}

.main-content::-webkit-scrollbar-track {
  background: transparent;
}

.main-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

/* 底部保存 */
.main-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

.save-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 160px;
  padding: 12px 28px;
  border-radius: 20px;
  border: 1px solid rgba(20, 184, 166, 0.4);
  background: linear-gradient(135deg, var(--accent-color), var(--accent-hover));
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s var(--ease-smooth), box-shadow 0.2s var(--ease-smooth), background-color 0.2s var(--ease-smooth), border-color 0.2s var(--ease-smooth), color 0.2s var(--ease-smooth);
  font-family: inherit;
  box-shadow: 0 0 20px rgba(20, 184, 166, 0.35), 0 4px 16px var(--accent-glow);
}

.save-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 0 30px rgba(20, 184, 166, 0.5), 0 6px 24px var(--accent-glow);
}

.save-btn:active:not(:disabled) {
  transform: translateY(0);
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.save-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

/* ============== 过渡动画 ============== */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity var(--duration-fast, 120ms) ease-out, transform var(--duration-fast, 120ms) ease-out;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(12px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

/* ============== 响应式 ============== */
.main-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.back-play-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  font-family: inherit;
  white-space: nowrap;
}

.back-play-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  background: var(--settings-accent-subtle);
}

@media (max-width: 900px) {
  .settings-sidebar.collapsed {
    width: 64px;
    min-width: 64px;
  }

  .settings-sidebar.collapsed .logo-text,
  .settings-sidebar.collapsed .nav-label,
  .settings-sidebar.collapsed .help-btn span {
    display: none;
  }

  .settings-sidebar.collapsed .sidebar-logo {
    padding: 20px 16px;
    justify-content: center;
  }

  .settings-sidebar.collapsed .nav-item {
    padding: 10px;
    justify-content: center;
  }

  .settings-sidebar.collapsed .nav-indicator {
    display: none;
  }

  .settings-sidebar.collapsed .help-btn {
    padding: 10px;
    justify-content: center;
  }
}

/* ============== 内容区样式 ============== */
.settings-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 2px;
}

.group-icon {
  width: 26px;
  height: 26px;
  background: var(--settings-accent-subtle);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-color);
  flex-shrink: 0;
}

.group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.settings-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin-bottom: 10px;
  background: color-mix(in srgb, var(--accent-color) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.settings-notice svg {
  flex-shrink: 0;
  color: var(--accent-color);
}

.settings-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-color);
  gap: 16px;
  transition: background 0.15s;
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-row:hover {
  background: var(--settings-accent-subtle);
}

.setting-row--block {
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.setting-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.setting-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.setting-control {
  flex-shrink: 0;
  margin-left: 12px;
}

/* 滑块 */
.slider-wrap {
  min-width: 180px;
  width: 180px;
}

/* 回复风格 pills */
.style-pills {
  display: flex;
  gap: 6px;
}

.style-pill {
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  font-family: inherit;
}

.style-pill:hover {
  border-color: var(--accent-color);
  color: var(--text-secondary);
}

.style-pill.active {
  background: var(--settings-accent-subtle);
  border-color: var(--accent-color);
  color: var(--accent-color);
  box-shadow: 0 0 0 1px var(--accent-color);
}

/* 主题 pills */
.theme-pills {
  display: flex;
  gap: 6px;
}

.theme-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  font-family: inherit;
}

.theme-pill:hover {
  border-color: var(--accent-color);
  color: var(--text-secondary);
}

.theme-pill.active {
  background: var(--settings-accent-subtle);
  border-color: var(--accent-color);
  color: var(--accent-color);
  box-shadow: 0 0 0 1px var(--accent-color);
}

/* 单选组 */
.radio-group {
  display: flex;
  gap: 4px;
}

.radio {
  padding: 4px 12px;
  border-radius: 5px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, background-color 0.15s, border-color 0.15s, color 0.15s;
  font-family: inherit;
}

.radio:hover {
  border-color: var(--accent-color);
  color: var(--text-secondary);
}

.radio.active {
  background: var(--settings-accent-subtle);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

/* 备用模型列表 */
.backup-list-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
  width: 100%;
}

.backup-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.backup-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 7px;
  border-left: 3px solid var(--accent-color);
  transition: transform 0.15s, box-shadow 0.15s, background-color 0.15s, border-color 0.15s, color 0.15s;
}

.backup-item:hover {
  border-color: var(--accent-color);
  background: var(--settings-accent-subtle);
}

.backup-item.is-dragging {
  opacity: 0.4;
  border-color: var(--accent-color);
}

.backup-list.is-dragging-over {
  outline: 2px dashed var(--accent-color);
  outline-offset: 4px;
  border-radius: 8px;
}

.backup-drag-handle {
  cursor: grab;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  padding: 2px;
  border-radius: 3px;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}

.backup-drag-handle:hover {
  color: var(--text-secondary);
  background: var(--border-color);
}

.backup-drag-handle:active {
  cursor: grabbing;
}

.backup-rank {
  width: 20px;
  height: 20px;
  background: var(--settings-accent-subtle);
  color: var(--accent-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

.backup-name {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.backup-ops {
  display: flex;
  gap: 3px;
}

.backup-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.05);
  border: 1px dashed rgba(239, 68, 68, 0.2);
  border-radius: 7px;
  color: var(--color-danger, #f87171);
  font-size: 11px;
}

.backup-add-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.btn-add {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 7px;
  border: 1px solid var(--border-color);
  background: var(--settings-accent-subtle);
  color: var(--accent-color);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, background-color 0.15s, border-color 0.15s, color 0.15s;
  font-family: inherit;
  white-space: nowrap;
}

.btn-add:hover:not(:disabled) {
  border-color: var(--accent-color);
  background: color-mix(in srgb, var(--accent-color) 12%, transparent);
}

.btn-add:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 操作按钮 */
.icon-btn {
  width: 26px;
  height: 26px;
  border-radius: 5px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, background-color 0.15s, border-color 0.15s, color 0.15s;
  flex-shrink: 0;
}

.icon-btn:hover:not(:disabled) {
  background: var(--border-color);
  color: var(--text-primary);
}

.icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.icon-btn--danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
}

/* 文本域 */
.textarea-wrap {
  margin-top: 4px;
}

.style-textarea {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #3a3a4a);
  background: var(--bg-secondary, #1e1e2e);
  color: var(--text-primary, #e0e0e0);
  font-size: 14px;
  resize: vertical;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}

.style-textarea:focus {
  border-color: var(--accent-color, #0f766e);
}

/* 列表动画 */
.backup-item-enter-active {
  animation: item-in 0.2s var(--ease-spring) both;
}

.backup-item-leave-active {
  animation: item-out 0.15s var(--ease-smooth) both;
}

.backup-item-move {
  transition: transform 0.2s var(--ease-spring);
}

@keyframes item-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes item-out {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-4px); }
}

.group-manage-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 3px 10px;
  border-radius: 5px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s var(--ease-smooth), box-shadow 0.15s var(--ease-smooth), background-color 0.15s var(--ease-smooth), border-color 0.15s var(--ease-smooth), color 0.15s var(--ease-smooth);
  font-family: inherit;
  white-space: nowrap;
}

.group-manage-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  background: var(--settings-accent-subtle);
}

@media (max-width: 767px) {
  .group-header {
    flex-wrap: wrap;
  }
  .group-manage-btn {
    margin-left: 0;
  }
}

@media (max-width: 767px) {
  .main-header-left {
    gap: 6px;
    flex-wrap: wrap;
  }

  .main-title {
    font-size: 16px;
  }

  .back-play-btn {
    padding: 8px 10px;
    min-height: 40px;
    font-size: 12px;
  }

  .reset-btn {
    padding: 8px 10px;
    min-height: 40px;
    font-size: 12px;
  }

  .settings-sidebar {
    display: none !important;
  }

  .settings-layout {
    flex-direction: column;
  }

  .settings-main {
    margin-left: 0 !important;
    width: 100% !important;
    flex: 1;
    min-height: 0;
  }

  /* 移动端隐藏备用模型拖拽手柄 */
  .backup-drag-handle {
    display: none;
  }

  /* 移动端放大备用模型操作按钮触摸区域 */
  .backup-ops .icon-btn {
    min-width: 44px;
    min-height: 44px;
  }

  /* 移动端顶部导航标签（替代侧边栏） */
  .mobile-nav {
    display: flex;
    overflow-x: auto;
    gap: 4px;
    padding: 8px 12px;
    background: var(--bg-elevated);
    border-bottom: 1px solid var(--border-color);
    scrollbar-width: none;
    -ms-overflow-style: none;
  }
  .mobile-nav::-webkit-scrollbar {
    display: none;
  }
  .mobile-nav-item {
    flex-shrink: 0;
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: transform 0.15s, box-shadow 0.15s, background-color 0.15s, border-color 0.15s, color 0.15s;
    font-family: inherit;
  }
  .mobile-nav-item.active {
    background: var(--settings-accent-subtle);
    color: var(--accent-color);
    border-color: var(--accent-color);
  }
}
</style>

<style>
/* ============== CSS 变量定义（使用设计系统变量，适配三主题） ============== */
/* accent-subtle 用 color-mix 实现，可随主题自适应 */
:root {
  --settings-accent-subtle: color-mix(in srgb, var(--accent-color) 8%, transparent);
}
[data-theme="light"] {
  --settings-accent-subtle: color-mix(in srgb, var(--accent-color) 6%, transparent);
}
</style>
