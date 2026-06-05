<template>
  <div class="table-scroll-mobile">
    <div class="page-header">
      <div>
        <el-button text @click="$router.push('/admin/stories')">← 返回故事列表</el-button>
        <h2>角色管理</h2>
      </div>
      <el-button type="primary" @click="openDialog()">添加角色</el-button>
    </div>

    <el-table v-loading="loading" :data="characters" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" width="120" />
      <el-table-column prop="personality" label="性格" show-overflow-tooltip />
      <el-table-column prop="background" label="背景" show-overflow-tooltip />
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" @click="insertIntoWorld(row.id)">插入到世界观</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑角色' : '添加角色'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="性格">
          <el-input v-model="form.personality" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="背景">
          <el-input v-model="form.background" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="头像URL">
          <el-input v-model="form.avatar" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getCharacters,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  getErrorMessage,
} from '../../api'

const route = useRoute()
const storyId = Number(route.params.storyId)

const characters = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({ name: '', personality: '', background: '', avatar: '' })

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getCharacters(storyId)
    characters.value = data
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  if (row) {
    editingId.value = row.id
    Object.assign(form, row)
  } else {
    editingId.value = null
    Object.assign(form, { name: '', personality: '', background: '', avatar: '' })
  }
  dialogVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (editingId.value) {
      await updateCharacter(editingId.value, form)
    } else {
      await createCharacter(storyId, form)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await fetchList()
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该角色？', '确认', { type: 'warning' })
    await deleteCharacter(id)
    ElMessage.success('已删除')
    await fetchList()
  } catch (e: unknown) {
    ElMessage.error(getErrorMessage(e, '删除失败'))
  }
}

function insertIntoWorld(charId: number) {
  try {
    localStorage.setItem('pending_char_ref', String(charId))
    window.open(`/admin/stories/${storyId}/prompt`, '_blank')
  } catch {
    ElMessage.warning('无法打开世界观编辑器')
  }
}

onMounted(fetchList)
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
  margin-top: 4px;
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
}

:deep(.el-dialog__headerbtn:hover) {
  background: color-mix(in srgb, var(--accent-color) 20%, transparent);
}

:deep(.el-dialog__body) {
  padding: 16px 20px;
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
</style>
