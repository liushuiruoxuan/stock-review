<template>
  <div v-loading="loading">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>
        资金监控（汇总级）：机构/游资动向基于龙虎榜席位说明（机构买入/卖出家数）派生，支持金额阈值、类型、时间段筛选与按交易日导出。
        逐席位游资/机构明细（抱团、席位频率）受免费接口限制暂不可用，将在接入席位级数据源后自动增强（Tier B）。
      </template>
    </el-alert>

    <!-- 筛选条 -->
    <el-card shadow="never" class="filter-card">
      <div class="filters">
        <div class="f-item">
          <span class="f-label">交易日</span>
          <el-select v-model="selDate" size="small" style="width: 150px" @change="reload">
            <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
          </el-select>
        </div>
        <div class="f-item">
          <span class="f-label">类型</span>
          <el-select v-model="selType" size="small" style="width: 120px" @change="reload">
            <el-option label="全部" value="all" />
            <el-option label="机构买入" value="inst_buy" />
            <el-option label="机构卖出" value="inst_sell" />
            <el-option label="机构分歧" value="inst_split" />
            <el-option label="游资" value="youzi" />
          </el-select>
        </div>
        <div class="f-item">
          <span class="f-label">净买≥(万)</span>
          <el-input v-model="selMinNet" size="small" style="width: 110px" placeholder="0" @keyup.enter="reload" />
        </div>
        <el-button size="small" type="primary" :icon="Search" :loading="loading" @click="reload">查询</el-button>
        <el-button size="small" :icon="Download" @click="doExport">导出 CSV</el-button>
        <span class="f-hint">共 {{ ranking.length }} 条</span>
      </div>
    </el-card>

    <!-- 当日统计 -->
    <div class="stat-row">
      <div class="stat"><div class="stat-v">{{ stats.count }}</div><div class="stat-l">上榜数</div></div>
      <div class="stat"><div class="stat-v" :class="yuanClass(stats.net_total_wan * 1e4)">{{ fmtYuan(stats.net_total_wan * 1e4) }}</div><div class="stat-l">净买合计</div></div>
      <div class="stat up"><div class="stat-v">{{ stats.inst_buy }}</div><div class="stat-l">机构买入</div></div>
      <div class="stat down"><div class="stat-v">{{ stats.inst_sell }}</div><div class="stat-l">机构卖出</div></div>
      <div class="stat"><div class="stat-v">{{ stats.inst_split }}</div><div class="stat-l">机构分歧</div></div>
      <div class="stat"><div class="stat-v">{{ stats.youzi }}</div><div class="stat-l">游资</div></div>
    </div>

    <!-- 机构共振信号 -->
    <el-alert
      v-if="resonance.is_resonance"
      type="warning" :closable="false" show-icon class="sig-alert"
      :title="`机构共振信号：${resonance.date} 共 ${resonance.count} 只个股被机构净买入（阈值 ${resonance.threshold}）`"
    >
      <template #default>
        <span class="res-names">{{ resonance.stocks.slice(0, 12).map(s => s.name).join('、') }}<template v-if="resonance.stocks.length > 12"> 等</template></span>
      </template>
    </el-alert>

    <!-- 机构连续净卖预警 -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          机构连续净卖出预警（≥{{ signalsMinStreak }}日）
          <el-tag size="small" :type="signals.length ? 'danger' : 'success'" effect="dark">{{ signals.length }} 条</el-tag>
        </div>
      </template>
      <div v-if="!signals.length" class="empty">近阶段暂无机构连续净卖出预警标的。</div>
      <div v-else class="sig-list">
        <div v-for="s in signals" :key="s.code" class="sig-item">
          <el-tag type="danger" effect="plain" size="small">{{ s.streak }}日</el-tag>
          <span class="sig-name">{{ s.name }}</span>
          <span class="sig-code">{{ s.code }}</span>
          <span class="sig-meta">区间 {{ s.start_date }} ~ {{ s.end_date }}</span>
          <span class="sig-meta">最新净额 {{ fmtYuan(s.latest_net_amt) }}</span>
          <span class="sig-meta">机构卖 {{ s.inst_sell_cnt }} / 买 {{ s.inst_buy_cnt }}</span>
        </div>
      </div>
    </el-card>

    <!-- 历史胜率 -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">历史胜率（基于后续表现，样本越多越可信）</div></template>
      <div class="wr-grid">
        <div v-for="g in wrGroups" :key="g.key" class="wr-block">
          <div class="wr-title">{{ g.title }}</div>
          <table class="wr-table">
            <thead><tr><th>周期</th><th>上涨概率</th><th>样本</th></tr></thead>
            <tbody>
              <tr v-for="k in ['d1','d2','d5','d10']" :key="k">
                <td>{{ winrate[g.key][k].label }}</td>
                <td :class="winrate[g.key][k].rate != null && winrate[g.key][k].rate >= 50 ? 'up' : 'down'">
                  {{ winrate[g.key][k].rate == null ? '--' : winrate[g.key][k].rate + '%' }}
                </td>
                <td>{{ winrate[g.key][k].total }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </el-card>

    <!-- 监控排行 -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">监控排行 · {{ selDate }} <SourceTag section="billboard" /></div></template>
      <DataTable :rows="ranking" :columns="cols" :height="'560px'" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search, Download } from '@element-plus/icons-vue'
import DataTable from '../components/DataTable.vue'
import SourceTag from '../components/SourceTag.vue'
import { api } from '../api'
import { fmtYuan, fmtPct, trendClass, yuanClass } from '../utils/format'

const loading = ref(true)
const dates = ref([])
const selDate = ref('')
const selType = ref('all')
const selMinNet = ref('')
const ranking = ref([])
const stats = ref({ count: 0, net_total_wan: 0, inst_buy: 0, inst_sell: 0, inst_split: 0, youzi: 0 })
const resonance = ref({ date: '', count: 0, is_resonance: false, threshold: 3, stocks: [] })
const winrate = ref({ all: {}, inst_buy: {}, youzi: {} })
const wrGroups = [
  { key: 'all', title: '全部标的' },
  { key: 'inst_buy', title: '机构买入' },
  { key: 'youzi', title: '游资' }
]
const signals = ref([])
const signalsMinStreak = ref(3)

const cols = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'category', label: '类别', width: 96, render: (r) => catLabel(r.category), cellClass: (r) => catClass(r.category) },
  { prop: 'net_amt', label: '龙虎榜净买', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'inst_buy_cnt', label: '机构买', width: 78, align: 'right', sortable: true },
  { prop: 'inst_sell_cnt', label: '机构卖', width: 78, align: 'right', sortable: true },
  { prop: 'list_times', label: '上榜次数', width: 92, align: 'right', sortable: true },
  { prop: 'd1', label: '次日%', width: 88, align: 'right', sortable: true, render: (r) => (r.d1 == null ? '--' : fmtPct(r.d1)), cellClass: (r) => trendClass(r.d1) },
  { prop: 'd2', label: '后2日%', width: 90, align: 'right', sortable: true, render: (r) => (r.d2 == null ? '--' : fmtPct(r.d2)), cellClass: (r) => trendClass(r.d2) },
  { prop: 'd5', label: '后5日%', width: 90, align: 'right', sortable: true, render: (r) => (r.d5 == null ? '--' : fmtPct(r.d5)), cellClass: (r) => trendClass(r.d5) },
  { prop: 'change_pct', label: '涨幅%', width: 90, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'reason', label: '上榜原因', minWidth: 170 },
  { prop: 'explain', label: '席位说明', minWidth: 160, render: (r) => r.explain || '--' }
]

const CAT_LABELS = { inst_buy: '机构买入', inst_sell: '机构卖出', inst_split: '机构分歧', youzi: '游资' }
function catLabel(c) { return CAT_LABELS[c] || c }
function catClass(c) {
  if (c === 'inst_buy') return 'up'
  if (c === 'inst_sell') return 'down'
  return ''
}

async function reload() {
  loading.value = true
  try {
    const [daily, sig] = await Promise.all([
      api.monitorDaily({ date: selDate.value, type: selType.value, min_net: selMinNet.value || 0 }),
      api.monitorSignals({ min_streak: signalsMinStreak.value })
    ])
    dates.value = daily.available_dates || []
    if (!selDate.value && dates.value.length) selDate.value = dates.value[0]
    selDate.value = daily.date
    stats.value = daily.stats || stats.value
    ranking.value = daily.ranking || []
    resonance.value = daily.resonance || resonance.value
    winrate.value = daily.winrate || winrate.value
    signals.value = sig.signals || []
    signalsMinStreak.value = sig.min_streak || 3
  } finally {
    loading.value = false
  }
}

function doExport() {
  const url = api.monitorExportUrl({ date: selDate.value, type: selType.value, min_net: selMinNet.value || 0 })
  window.open(url, '_blank')
}

onMounted(reload)
</script>

<style scoped>
.tip { margin-bottom: 12px; border-radius: 8px; }
.filter-card { border-radius: 10px; margin-bottom: 12px; }
.filters { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.f-item { display: flex; align-items: center; gap: 6px; }
.f-label { font-size: 13px; color: #6b7488; }
.f-hint { font-size: 12px; color: #8a93a6; margin-left: auto; }
.stat-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 12px; }
.stat { background: #fff; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.stat-v { font-size: 22px; font-weight: 700; color: #1f2733; }
.stat-l { font-size: 12px; color: #8a93a6; margin-top: 2px; }
.sig-alert { margin-bottom: 12px; border-radius: 8px; }
.res-names { font-size: 13px; color: #8a4b00; }
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
.empty { color: #8a93a6; font-size: 13px; padding: 10px 0; }
.sig-list { display: flex; flex-direction: column; gap: 8px; max-height: 280px; overflow-y: auto; }
.sig-item { display: flex; align-items: center; gap: 12px; font-size: 13px; padding: 6px 8px; background: #fff5f5; border-radius: 6px; }
.sig-name { font-weight: 600; color: #c0392b; }
.sig-code { color: #8a93a6; }
.sig-meta { color: #6b7488; font-size: 12px; }
.wr-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.wr-block { background: #fafbfc; border-radius: 8px; padding: 10px 12px; }
.wr-title { font-size: 13px; font-weight: 600; color: #1f2733; margin-bottom: 8px; }
.wr-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.wr-table th, .wr-table td { text-align: center; padding: 5px 4px; border-bottom: 1px solid #eef0f4; }
.wr-table th { color: #8a93a6; font-weight: 500; }
@media (max-width: 1100px) {
  .stat-row { grid-template-columns: repeat(3, 1fr); }
  .wr-grid { grid-template-columns: 1fr; }
}
</style>
