<template>
  <div class="metrics-page table-scroll-mobile">
    <div class="page-header">
      <h2>调用统计</h2>
      <div class="tools">
        <el-button :loading="loading" @click="fetchAll">刷新</el-button>
        <el-button type="danger" plain @click="handleReset">清零统计日志</el-button>
      </div>
    </div>

    <el-alert
      v-for="item in errorList"
      :key="item.key"
      class="section-error"
      type="warning"
      show-icon
      :closable="false"
      :title="item.title"
      :description="item.description"
    />

    <el-row :gutter="12" class="kpis">
      <el-col :span="6" :xs="12"
        ><el-card
          ><div class="kpi">
            <div class="label">总调用</div>
            <div class="value">{{ summaryLoaded ? summary.total_calls : '--' }}</div>
          </div></el-card
        ></el-col
      >
      <el-col :span="6" :xs="12"
        ><el-card
          ><div class="kpi">
            <div class="label">成功率</div>
            <div class="value">
              {{ summaryLoaded ? `${summary.success_rate.toFixed(2)}%` : '--' }}
            </div>
          </div></el-card
        ></el-col
      >
      <el-col :span="6" :xs="12"
        ><el-card
          ><div class="kpi">
            <div class="label">平均耗时</div>
            <div class="value">
              {{ summaryLoaded ? `${summary.avg_latency_ms.toFixed(0)} ms` : '--' }}
            </div>
          </div></el-card
        ></el-col
      >
      <el-col :span="6" :xs="12"
        ><el-card
          ><div class="kpi">
            <div class="label">总费用</div>
            <div class="value">
              {{ summaryLoaded ? `¥ ${summary.total_cost.toFixed(4)}` : '--' }}
            </div>
          </div></el-card
        ></el-col
      >
    </el-row>

    <el-card class="section">
      <template #header><span>按模型统计</span></template>
      <el-table :data="byModel" stripe>
        <el-table-column prop="model_name" label="模型" min-width="160" />
        <el-table-column prop="total_calls" label="调用数" width="90" />
        <el-table-column prop="success_rate" label="成功率" width="100">
          <template #default="{ row }">{{ Number(row.success_rate).toFixed(2) }}%</template>
        </el-table-column>
        <el-table-column prop="avg_latency_ms" label="平均耗时(ms)" width="120">
          <template #default="{ row }">{{ Number(row.avg_latency_ms).toFixed(0) }}</template>
        </el-table-column>
        <el-table-column prop="total_tokens" label="Tokens" width="110" />
        <el-table-column prop="total_cost" label="费用" width="120">
          <template #default="{ row }">¥ {{ Number(row.total_cost).toFixed(4) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="section">
      <template #header><span>按天趋势</span></template>
      <div v-if="recentData.length > 0" class="trend-chart">
        <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="bar-chart">
          <!-- Y轴网格线 -->
          <line
            v-for="i in 4"
            :key="'grid' + i"
            :x1="paddingL"
            :y1="paddingT + (chartH / 4) * (i - 1)"
            :x2="chartWidth - paddingR"
            :y2="paddingT + (chartH / 4) * (i - 1)"
            stroke="color-mix(in srgb, var(--accent-color) 12%, transparent)"
            stroke-width="1"
            stroke-dasharray="4,4"
          />
          <!-- Y轴标签 -->
          <text
            v-for="(label, i) in yLabels"
            :key="'y' + i"
            :x="paddingL - 6"
            :y="paddingT + (chartH / 4) * i + 4"
            text-anchor="end"
            font-size="10"
            fill="var(--text-muted)"
          >
            {{ label }}
          </text>
          <!-- X轴标签 -->
          <text
            v-for="(item, i) in recentData"
            :key="'x' + i"
            :x="barX(i)"
            :y="chartHeight - 4"
            text-anchor="middle"
            font-size="9"
            fill="var(--text-muted)"
          >
            {{ item.day.slice(5) }}
          </text>
          <!-- 柱形 -->
          <rect
            v-for="(item, i) in recentData"
            :key="'bar' + i"
            :x="barX(i) - barW / 2"
            :y="barY(item.total_calls)"
            :width="barW"
            :height="chartH - (barY(item.total_calls) - paddingT)"
            rx="3"
            ry="3"
            :fill="
              item.total_calls > 0
                ? 'url(#barGrad)'
                : 'color-mix(in srgb, var(--accent-color) 10%, transparent)'
            "
            :stroke="
              item.total_calls > 0
                ? 'color-mix(in srgb, var(--accent-color) 40%, transparent)'
                : 'transparent'
            "
            stroke-width="1"
          />
          <!-- 柱形顶部的数字 -->
          <template v-for="(item, i) in recentData" :key="'num' + i">
            <text
              v-if="item.total_calls > 0"
              :x="barX(i)"
              :y="barY(item.total_calls) - 4"
              text-anchor="middle"
              font-size="9"
              fill="var(--accent-color)"
            >
              {{ item.total_calls }}
            </text>
          </template>
          <defs>
            <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--accent-hover)" />
              <stop offset="100%" stop-color="var(--accent-color)" />
            </linearGradient>
          </defs>
        </svg>
        <div class="chart-legend">
          <span class="legend-item"><span class="dot teal"></span>日调用量（近14天）</span>
          <span class="legend-sep">|</span>
          <span class="legend-item"
            >最高 <b>{{ maxCalls }}</b></span
          >
          <span class="legend-item"
            >平均 <b>{{ avgCalls }}</b></span
          >
        </div>
      </div>
      <el-table v-else :data="[]" stripe>
        <el-table-column prop="day" label="日期" width="140" />
        <el-table-column prop="total_calls" label="调用数" width="90" />
        <el-table-column prop="success_rate" label="成功率" width="110">
          <template #default="{ row }">{{ Number(row.success_rate).toFixed(2) }}%</template>
        </el-table-column>
        <el-table-column prop="total_tokens" label="Tokens" width="120" />
        <el-table-column prop="total_cost" label="费用" width="140">
          <template #default="{ row }">¥ {{ Number(row.total_cost).toFixed(4) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="section">
      <template #header><span>流式请求明细（排障）</span></template>
      <el-table :data="streamRequests" stripe class="stream-detail-table">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) || '-' }}</template>
        </el-table-column>
        <el-table-column
          v-if="!isMobile"
          prop="request_id"
          label="请求ID"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column prop="model_name" label="模型" width="160" show-overflow-tooltip />
        <el-table-column v-if="!isMobile" prop="story_id" label="故事ID" width="80" />
        <el-table-column v-if="!isMobile" prop="archive_id" label="会话ID" width="80" />
        <el-table-column v-if="!isMobile" prop="stream_emitted_delta" label="发delta" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.stream_emitted_delta ? 'success' : 'info'">
              {{ row.stream_emitted_delta ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ttfb_ms" label="TTFB(ms)" width="95" />
        <el-table-column v-if="!isMobile" prop="fallback_used" label="切备模" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.fallback_used ? 'warning' : 'info'">
              {{ row.fallback_used ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!isMobile" prop="tail_valid" label="尾包有效" width="95">
          <template #default="{ row }">
            <el-tag size="small" :type="row.tail_valid ? 'success' : 'danger'">
              {{ row.tail_valid ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_stage" label="错误阶段" width="120">
          <template #default="{ row }">{{ row.error_stage || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="!isMobile" prop="error_code" label="错误码" width="150">
          <template #default="{ row }">{{ row.error_code || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="!isMobile" prop="latency_ms" label="总耗时(ms)" width="110" />
        <el-table-column prop="success" label="结果" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.success ? 'success' : 'danger'">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '../../utils/time'
import {
  getErrorMessage,
  getMetricsSummary,
  getMetricsByModel,
  getMetricsTimeseries,
  getMetricsStreamRequests,
  resetMetrics,
} from '../../api'

const RESET_CONFIRM_TEXT = 'RESET_METRICS'

const isMobile = ref(window.innerWidth <= 767)
function handleResize() {
  isMobile.value = window.innerWidth <= 767
}
onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => window.removeEventListener('resize', handleResize))

const loading = ref(false)
const summaryLoaded = ref(false)
const summary = reactive({
  total_calls: 0,
  success_calls: 0,
  success_rate: 0,
  avg_latency_ms: 0,
  total_prompt_tokens: 0,
  total_completion_tokens: 0,
  total_tokens: 0,
  total_cost: 0,
})
const byModel = ref<any[]>([])
const timeseries = ref<any[]>([])
const streamRequests = ref<any[]>([])
const sectionErrors = reactive({
  summary: '',
  byModel: '',
  timeseries: '',
  streamRequests: '',
})

type SectionErrorItem = {
  key: string
  title: string
  description: string
}

const errorList = computed(() => {
  const items: SectionErrorItem[] = []
  if (sectionErrors.summary) {
    items.push({ key: 'summary', title: '汇总加载失败', description: sectionErrors.summary })
  }
  if (sectionErrors.byModel) {
    items.push({ key: 'byModel', title: '按模型统计加载失败', description: sectionErrors.byModel })
  }
  if (sectionErrors.timeseries) {
    items.push({
      key: 'timeseries',
      title: '按天趋势加载失败',
      description: sectionErrors.timeseries,
    })
  }
  if (sectionErrors.streamRequests) {
    items.push({
      key: 'streamRequests',
      title: '流式请求明细加载失败',
      description: sectionErrors.streamRequests,
    })
  }
  return items
})

async function fetchAll() {
  loading.value = true
  try {
    sectionErrors.summary = ''
    sectionErrors.byModel = ''
    sectionErrors.timeseries = ''
    sectionErrors.streamRequests = ''

    const [s, m, t, stream] = await Promise.allSettled([
      getMetricsSummary(),
      getMetricsByModel(),
      getMetricsTimeseries(),
      getMetricsStreamRequests({ limit: 120 }),
    ])

    if (s.status === 'fulfilled') {
      Object.assign(summary, s.value.data)
      summaryLoaded.value = true
    } else {
      summaryLoaded.value = false
      sectionErrors.summary = getErrorMessage(s.reason, '汇总接口请求失败')
    }

    if (m.status === 'fulfilled') {
      byModel.value = m.value.data
    } else {
      byModel.value = []
      sectionErrors.byModel = getErrorMessage(m.reason, '按模型统计接口请求失败')
    }

    if (t.status === 'fulfilled') {
      timeseries.value = t.value.data
    } else {
      timeseries.value = []
      sectionErrors.timeseries = getErrorMessage(t.reason, '按天趋势接口请求失败')
    }

    if (stream.status === 'fulfilled') {
      streamRequests.value = stream.value.data
    } else {
      streamRequests.value = []
      sectionErrors.streamRequests = getErrorMessage(stream.reason, '流式请求明细接口请求失败')
    }

    if (errorList.value.length > 0) {
      ElMessage.warning('部分统计区块加载失败，请查看页面提示')
    }
  } finally {
    loading.value = false
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('此操作不可恢复，确定要清空所有调用统计日志吗？', '清空统计日志', {
      type: 'warning',
      confirmButtonText: '确认清空',
      cancelButtonText: '取消',
    })
    await resetMetrics(RESET_CONFIRM_TEXT)
    ElMessage.success('统计日志已清空')
    await fetchAll()
  } catch {
    // 用户取消
  }
}

onMounted(fetchAll)

// ---- 简单SVG柱状图 ----
const chartWidth = 600
const chartHeight = 140
const paddingL = 36
const paddingR = 12
const paddingT = 12
const paddingB = 28
const chartW = computed(() => chartWidth - paddingL - paddingR)
const chartH = computed(() => chartHeight - paddingT - paddingB)

const recentData = computed(() => timeseries.value.slice(-14))
const callsMax = computed(() => {
  const r = recentData.value
  return r.length ? Math.max(...r.map((d) => d.total_calls), 1) : 1
})

const barSlot = computed(() => chartW.value / Math.max(recentData.value.length, 1))

function barX(i: number) {
  return paddingL + barSlot.value * i + barSlot.value / 2
}
const barW = 16

function barY(calls: number) {
  const h = (calls / callsMax.value) * chartH.value
  return paddingT + chartH.value - h
}

const maxCalls = computed(() => recentData.value.reduce((m, d) => Math.max(m, d.total_calls), 0))
const avgCalls = computed(() => {
  const r = recentData.value
  if (!r.length) return 0
  return Math.round(r.reduce((s, d) => s + d.total_calls, 0) / r.length)
})
const yLabels = computed(() => {
  const max = callsMax.value
  return [0, 0.25, 0.5, 0.75].map((p) => Math.round(max * (1 - p)).toString())
})
</script>

<style scoped>
.metrics-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.page-header h2 {
  font-size: 20px;
  color: var(--text-primary);
}
.tools {
  display: flex;
  gap: 8px;
}
.kpis .kpi .label {
  color: var(--text-secondary);
  font-size: 12px;
}
.kpis .kpi .value {
  color: var(--text-primary);
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
}
.section {
  margin-top: 2px;
}
.section-error {
  margin-bottom: 2px;
}

/* Glass el-card for section */
:deep(.el-card) {
  background: var(--admin-card-bg);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 16px;
  box-shadow: 0 0 20px color-mix(in srgb, var(--accent-color) 8%, transparent);
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

/* Glass el-card header */
:deep(.el-card__header) {
  border-bottom: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  color: var(--text-primary);
  font-weight: 600;
}

/* Glass alert */
:deep(.el-alert) {
  background: color-mix(in srgb, var(--accent-color) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 12px;
}

/* KPI card glass */
.kpis :deep(.el-card) {
  background: var(--bg-card);
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, transparent);
  border-radius: 14px;
  box-shadow: 0 0 16px color-mix(in srgb, var(--accent-color) 10%, transparent);
}

.kpis .kpi .value {
  color: var(--accent-color);
  text-shadow: 0 0 12px color-mix(in srgb, var(--accent-color) 40%, transparent);
}

@media (prefers-reduced-motion: reduce) {
  :deep(.el-card),
  :deep(.el-table) {
    transition: none;
  }
}

.trend-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bar-chart {
  width: 100%;
  height: auto;
  overflow: visible;
}
.chart-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: var(--text-muted);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend-item b {
  color: var(--accent-color);
  font-weight: 600;
}
.legend-sep {
  color: var(--border-color);
}
.dot.teal {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-hover), var(--accent-color));
  display: inline-block;
}

@media (max-width: 767px) {
  .metrics-page :deep(.el-table) {
    font-size: 12px;
  }
}
</style>
