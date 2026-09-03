<template>
  <div v-loading="loading">
    <!-- 行情库状态 + 同步 -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          行情库
          <span class="sub">{{ mkt.instruments || 0 }} 标的 · {{ mkt.bars || 0 }} 根K线 · 最新 {{ mkt.latest_bar_date || '未同步' }}</span>
          <div class="sync-btns">
            <el-button size="small" @click="doSync('instruments')">同步标的</el-button>
            <el-button size="small" @click="doSync('calendar')">日历+指数</el-button>
            <el-button size="small" type="warning" @click="doSync('bars_daily')">每日增量</el-button>
            <el-button size="small" type="danger" @click="doSync('bars_full')">全量初始化(约15分钟)</el-button>
          </div>
        </div>
      </template>
      <div v-if="tasks.length" class="task-list">
        <div v-for="t in tasks" :key="t.id" class="task-row">
          <span class="t-name">{{ t.note || t.kind }}</span>
          <el-progress :percentage="t.progress" :status="t.status === 'failed' ? 'exception' : (t.status === 'done' ? 'success' : undefined)" style="width: 260px" />
          <span class="t-detail">{{ t.detail || t.status }} {{ t.error ? '· ' + t.error : '' }}</span>
        </div>
      </div>
    </el-card>

    <!-- 回测表单 -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">策略回测</div></template>
      <el-form inline>
        <el-form-item label="策略">
          <el-select v-model="form.strategy" style="width: 180px" @change="onStrategyChange">
            <el-option v-for="s in strategies" :key="s.name" :label="s.label" :value="s.name" />
          </el-select>
        </el-form-item>
        <el-form-item v-for="p in currentParams" :key="p.key" :label="p.label">
          <el-input-number v-model="form.params[p.key]" :min="p.min" :max="p.max" controls-position="right" style="width: 120px" />
        </el-form-item>
        <el-form-item label="股票池">
          <el-select v-model="form.universe" style="width: 160px">
            <el-option label="流动性前500" value="liquid500" />
            <el-option label="流动性前200" value="liquid200" />
            <el-option label="全部标的" value="all" />
          </el-select>
        </el-form-item>
        <el-form-item label="区间">
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
            start-placeholder="开始" end-placeholder="结束" style="width: 260px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="running" @click="submit">开始回测</el-button>
        </el-form-item>
      </el-form>
      <div class="strat-desc">{{ currentDesc }}</div>
    </el-card>

    <!-- 运行中任务 -->
    <el-card v-if="run && run.status === 'running'" shadow="never" class="card">
      <template #header><div class="card-h">任务 #{{ run.id }} 执行中…</div></template>
      <el-progress :percentage="run.progress" />
    </el-card>

    <!-- 结果 -->
    <template v-if="run && run.status === 'done'">
      <div class="stat-grid">
        <StatCard label="总收益" :value="fmtPct(run.metrics?.total_return)" :tone="run.metrics?.total_return >= 0 ? 'up' : 'down'" />
        <StatCard label="年化收益" :value="fmtPct(run.metrics?.annual_return)" :tone="run.metrics?.annual_return >= 0 ? 'up' : 'down'" />
        <StatCard label="最大回撤" :value="fmtPct(run.metrics?.max_drawdown)" tone="down" />
        <StatCard label="夏普比率" :value="fmtNum(run.metrics?.sharpe)" />
        <StatCard label="交易次数" :value="(run.metrics?.n_trades ?? 0) + ' 笔'" />
        <StatCard label="交易胜率" :value="run.metrics?.trade_win_rate != null ? fmtPct(run.metrics.trade_win_rate) : '--'" tone="up" />
      </div>
      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-h">
            资金曲线（#{{ run.id }} {{ run.strategy }}）
            <span v-if="run.metrics?.excess_return != null" class="sub">超额 {{ fmtPct(run.metrics.excess_return) }}</span>
          </div>
        </template>
        <BaseChart v-if="equityOption" :option="equityOption" height="360px" />
      </el-card>
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">交易明细（前 100 笔）</div></template>
        <el-table :data="(run.trades || []).slice(0, 100)" size="small" height="320">
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="entry" label="开仓日" width="130" />
          <el-table-column prop="exit" label="平仓日" width="130" />
          <el-table-column prop="entry_px" label="开仓价" width="90" align="right">
            <template #default="{ row }">{{ fmtNum(row.entry_px) }}</template>
          </el-table-column>
          <el-table-column prop="exit_px" label="平仓价" width="90" align="right">
            <template #default="{ row }">{{ fmtNum(row.exit_px) }}</template>
          </el-table-column>
          <el-table-column prop="pnl" label="收益" width="100" align="right" sortable>
            <template #default="{ row }">
              <span :class="trendClass(row.pnl)">{{ fmtPct((row.pnl || 0) * 100) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
    <el-alert v-if="run && run.status === 'failed'" type="error" :closable="false" show-icon class="card">
      回测失败：{{ run.error }}
    </el-alert>

    <!-- 历史任务 -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">历史回测<router-link to="/quant/screener" class="more">条件选股 ›</router-link></div></template>
      <el-table :data="runs" size="small" height="260" @row-click="showRun">
        <el-table-column prop="id" label="#" width="60" />
        <el-table-column prop="strategy" label="策略" width="130" />
        <el-table-column prop="universe" label="股票池" width="110" />
        <el-table-column prop="date_start" label="开始" width="105" />
        <el-table-column prop="date_end" label="结束" width="105" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'done' ? 'success' : (row.status === 'failed' ? 'danger' : 'info')">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="总收益" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.metrics" :class="trendClass(row.metrics.total_return)">{{ fmtPct(row.metrics.total_return) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="最大回撤" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.metrics">{{ fmtPct(row.metrics.max_drawdown) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="150" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import StatCard from '../components/StatCard.vue'
import BaseChart from '../components/BaseChart.vue'
import { api } from '../api'
import { fmtPct, fmtNum, trendClass } from '../utils/format'

const loading = ref(true)
const mkt = ref({})
const tasks = ref([])
const strategies = ref([])
const runs = ref([])
const run = ref(null)
const running = ref(false)
const range = ref(['2021-01-01', ''])

const form = ref({ strategy: 'ma_cross', params: {}, universe: 'liquid500' })

const currentParams = computed(() =>
  (strategies.value.find(s => s.name === form.value.strategy) || {}).params || [])
const currentDesc = computed(() =>
  (strategies.value.find(s => s.name === form.value.strategy) || {}).description || '')

function onStrategyChange() {
  const p = {}
  for (const it of currentParams.value) p[it.key] = it.default
  form.value.params = p
}

async function loadMeta() {
  loading.value = true
  try {
    const [m, s, r] = await Promise.all([api.marketOverview(), api.quantStrategies(), api.quantRuns()])
    mkt.value = m
    strategies.value = s.strategies || []
    runs.value = r.runs || []
    onStrategyChange()
    // 恢复最近一次结果
    const lastDone = (r.runs || []).find(x => x.status === 'done')
    if (lastDone) run.value = lastDone
  } finally {
    loading.value = false
  }
}

async function refreshTasks() {
  try {
    const [st, rs] = await Promise.all([api.marketSyncStatus(), api.quantRuns()])
    tasks.value = (st.tasks || []).slice(0, 4)
    runs.value = rs.runs || []
    if (running.value && run.value) {
      const r = await api.quantRun(run.value.id)
      run.value = r
      if (r.status !== 'running') running.value = false
    }
  } catch (e) { /* ignore */ }
}

async function doSync(scope) {
  await api.marketSync(scope)
  refreshTasks()
}

async function submit() {
  const body = {
    strategy: form.value.strategy,
    params: form.value.params,
    universe: form.value.universe,
    start: range.value?.[0] || '2021-01-01',
    end: range.value?.[1] || ''
  }
  const res = await api.quantBacktest(body)
  if (res.run_id) {
    running.value = true
    run.value = { id: res.run_id, status: 'running', progress: 0 }
    refreshTasks()
  }
}

function showRun(row) {
  if (row.status === 'done') run.value = row
}

const equityOption = computed(() => {
  const eq = run.value?.equity
  if (!eq || !eq.length) return null
  const hasBench = eq[0] && eq[0].benchmark != null
  const dates = eq.map(p => p.date)
  const series = [{
    name: '策略', type: 'line', symbol: 'none', lineStyle: { width: 2 },
    data: eq.map(p => hasBench ? p.strategy : p.nav)
  }]
  if (hasBench) {
    series.push({
      name: '上证指数', type: 'line', symbol: 'none', lineStyle: { width: 1.5, type: 'dashed' },
      data: eq.map(p => p.benchmark)
    })
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 8, right: 16, top: 30, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', scale: true },
    series
  }
})

let timer = null
onMounted(() => {
  loadMeta()
  timer = setInterval(refreshTasks, 3000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; flex-wrap: wrap; }
.sub { font-size: 12px; font-weight: 400; color: #8a93a6; }
.more { margin-left: auto; font-size: 13px; color: #409eff; text-decoration: none; font-weight: 400; }
.sync-btns { margin-left: auto; display: flex; gap: 8px; }
.strat-desc { font-size: 12px; color: #8a93a6; margin-top: 4px; }
.stat-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; margin-bottom: 14px; }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-row { display: flex; align-items: center; gap: 14px; }
.t-name { width: 220px; font-size: 13px; color: #1f2733; }
.t-detail { font-size: 12px; color: #8a93a6; }
@media (max-width: 1100px) { .stat-grid { grid-template-columns: repeat(3, 1fr); } }
</style>
