<template>
  <div v-loading="loading">
    <el-alert type="success" :closable="false" show-icon class="tip">
      <template #title>
        席位监控（Tier B）：逐席位（营业部 / 机构 / 沪深股通）买卖明细、席位画像、抱团（共振）与连续净卖预警。
        数据来自东方财富龙虎榜席位接口，免费、逐日历史可回看，支持席位名 / 方向 / 类型 / 净额多维筛选与导出。
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
            <el-option label="机构专用" value="inst" />
            <el-option label="沪深股通" value="hk" />
            <el-option label="游资/营业部" value="youzi" />
          </el-select>
        </div>
        <div class="f-item">
          <span class="f-label">方向</span>
          <el-select v-model="selSide" size="small" style="width: 100px" @change="reload">
            <el-option label="全部" value="" />
            <el-option label="买入" value="BUY" />
            <el-option label="卖出" value="SELL" />
          </el-select>
        </div>
        <div class="f-item">
          <span class="f-label">席位名</span>
          <el-input v-model="selSeat" size="small" style="width: 150px" placeholder="如 拉萨" @keyup.enter="reload" />
        </div>
        <div class="f-item">
          <span class="f-label">净买≥(万)</span>
          <el-input v-model="selMinNet" size="small" style="width: 110px" placeholder="0" @keyup.enter="reload" />
        </div>
        <el-button size="small" type="primary" :icon="Search" :loading="loading" @click="reload">查询</el-button>
        <el-button size="small" :icon="Download" @click="doExport">导出 CSV</el-button>
        <span class="f-hint">共 {{ seats.length }} 条席位记录</span>
      </div>
    </el-card>

    <!-- 当日统计 -->
    <div class="stat-row">
      <div class="stat"><div class="stat-v">{{ stats.count }}</div><div class="stat-l">席位记录</div></div>
      <div class="stat"><div class="stat-v" :class="yuanClass(stats.net_total_wan * 1e4)">{{ fmtYuan(stats.net_total_wan * 1e4) }}</div><div class="stat-l">净额合计</div></div>
      <div class="stat up"><div class="stat-v">{{ fmtYuan(stats.buy_total_wan * 1e4) }}</div><div class="stat-l">买入合计</div></div>
      <div class="stat down"><div class="stat-v">{{ fmtYuan(stats.sell_total_wan * 1e4) }}</div><div class="stat-l">卖出合计</div></div>
      <div class="stat"><div class="stat-v">{{ stats.youzi }}</div><div class="stat-l">游资席位</div></div>
      <div class="stat"><div class="stat-v">{{ stats.inst }}</div><div class="stat-l">机构席位</div></div>
    </div>

    <!-- 席位画像 -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">席位画像（跨历史聚合）</div>
      </template>
      <div class="profile-bar">
        <el-input v-model="profileSeat" size="small" style="width: 280px" placeholder="输入营业部/席位名，如 中国银河证券大连黄河路" @keyup.enter="loadProfile" />
        <el-button size="small" type="primary" :icon="Search" :loading="profileLoading" @click="loadProfile">查询画像</el-button>
      </div>
      <div v-if="profile" class="profile-body">
        <div class="pf-grid">
          <div class="pf"><div class="pf-v">{{ profile.appearances }}</div><div class="pf-l">上榜次数</div></div>
          <div class="pf"><div class="pf-v" :class="yuanClass(profile.total_net_wan * 1e4)">{{ fmtYuan(profile.total_net_wan * 1e4) }}</div><div class="pf-l">累计净额</div></div>
          <div class="pf"><div class="pf-v">{{ profile.avg_rise_3d == null ? '--' : profile.avg_rise_3d + '%' }}</div><div class="pf-l">平均3日胜率</div></div>
          <div class="pf"><div class="pf-v">{{ profile.stock_cnt }}</div><div class="pf-l">涉及个股</div></div>
          <div class="pf"><div class="pf-v">{{ profile.first_date }} ~ {{ profile.last_date }}</div><div class="pf-l">活跃区间</div></div>
        </div>
        <div v-if="profile.latest" class="pf-latest">
          最近一次：{{ profile.latest.date }} · {{ profile.latest.name }}({{ profile.latest.code }}) ·
          <b :class="profile.latest.side === 'BUY' ? 'up' : 'down'">{{ profile.latest.side === 'BUY' ? '买入' : '卖出' }}</b> ·
          净额 {{ fmtYuan(profile.latest.net_amt) }}
          <span class="pf-reason">{{ profile.latest.explanation }}</span>
        </div>
        <div class="pf-stocks">
          <el-tag v-for="s in profile.stocks" :key="s.code" size="small" effect="plain" class="pf-chip">{{ s.name }}</el-tag>
        </div>
      </div>
      <div v-else-if="profileTried" class="empty">未找到该席位的的历史记录。</div>
    </el-card>

    <!-- 抱团（共振）信号 -->
    <el-card shadow="never" class="card" v-if="syndicate.stocks && syndicate.stocks.length">
      <template #header>
        <div class="card-h">
          抱团（共振）信号：{{ syndicate.date }} 共 {{ syndicate.stocks.length }} 只个股同日出现 ≥{{ syndicate.threshold }} 个游资/营业部席位
        </div>
      </template>
      <div class="syn-list">
        <div v-for="s in syndicate.stocks" :key="s.code" class="syn-item">
          <span class="syn-name">{{ s.name }}</span>
          <span class="syn-code">{{ s.code }}</span>
          <el-tag size="small" type="warning" effect="plain">{{ s.seat_cnt }}席</el-tag>
          <span class="syn-seats">{{ s.seats.join('、') }}</span>
        </div>
      </div>
    </el-card>

    <!-- 席位排行 -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">席位排行 · {{ selDate }}</div></template>
      <div class="rank-grid">
        <div class="rank-block">
          <div class="rank-title">净额排行（万）</div>
          <table class="rank-table">
            <thead><tr><th>席位</th><th>净额(万)</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in rankings.net" :key="r.seat_name">
                <td>{{ i + 1 }}. {{ r.seat_name }}</td>
                <td :class="yuanClass(r.net_wan * 1e4)">{{ fmtYuan(r.net_wan * 1e4) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="rank-block">
          <div class="rank-title">活跃度排行（出现次数）</div>
          <table class="rank-table">
            <thead><tr><th>席位</th><th>次数</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in rankings.active" :key="r.seat_name">
                <td>{{ i + 1 }}. {{ r.seat_name }}</td>
                <td>{{ r.cnt }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </el-card>

    <!-- 席位明细表 -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">席位明细 · {{ selDate }} <SourceTag section="billboard" /></div></template>
      <DataTable :rows="seats" :columns="cols" :height="'580px'" />
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
const selSide = ref('')
const selSeat = ref('')
const selMinNet = ref('')
const seats = ref([])
const stats = ref({ count: 0, net_total_wan: 0, buy_total_wan: 0, sell_total_wan: 0, inst: 0, hk: 0, youzi: 0 })
const syndicate = ref({ date: '', threshold: 3, stocks: [] })
const rankings = ref({ net: [], active: [] })

const profileSeat = ref('')
const profile = ref(null)
const profileLoading = ref(false)
const profileTried = ref(false)

function seatTypeOf(name) {
  if (!name) return 'other'
  if (name.includes('机构专用')) return 'inst'
  if (name.includes('沪股通') || name.includes('深股通') || name.includes('陆股通')) return 'hk'
  return 'youzi'
}
const SEAT_TYPE_LABELS = { inst: '机构专用', hk: '沪深股通', youzi: '游资/营业部', other: '其他' }

const cols = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'seat_name', label: '席位', minWidth: 160, render: (r) => r.seat_name },
  { prop: 'type', label: '类型', width: 100, render: (r) => SEAT_TYPE_LABELS[seatTypeOf(r.seat_name)], cellClass: (r) => seatTypeOf(r.seat_name) === 'inst' ? 'up' : (seatTypeOf(r.seat_name) === 'hk' ? 'down' : '') },
  { prop: 'side', label: '方向', width: 70, render: (r) => r.side === 'BUY' ? '买入' : '卖出', cellClass: (r) => r.side === 'BUY' ? 'up' : 'down' },
  { prop: 'buy_amt', label: '买入', width: 120, align: 'right', sortable: true, render: (r) => fmtYuan(r.buy_amt), cellClass: (r) => trendClass(r.buy_amt) },
  { prop: 'sell_amt', label: '卖出', width: 120, align: 'right', sortable: true, render: (r) => fmtYuan(r.sell_amt) },
  { prop: 'net_amt', label: '净额', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'rise_prob_3d', label: '3日胜率', width: 92, align: 'right', sortable: true, render: (r) => (r.rise_prob_3d == null ? '--' : r.rise_prob_3d.toFixed(1) + '%'), cellClass: (r) => (r.rise_prob_3d != null && r.rise_prob_3d >= 50 ? 'up' : 'down') },
  { prop: 'explanation', label: '上榜原因', minWidth: 160 }
]

async function reload() {
  loading.value = true
  try {
    const p = {
      date: selDate.value,
      type: selType.value === 'all' ? '' : selType.value,
      side: selSide.value,
      seat: selSeat.value,
      min_net: (selMinNet.value || 0) * 10000,
    }
    const data = await api.seatsDaily(p)
    dates.value = data.available_dates || []
    if (!selDate.value && dates.value.length) selDate.value = dates.value[0]
    selDate.value = data.date
    stats.value = data.stats || stats.value
    seats.value = data.seats || []
    syndicate.value = data.syndicate || syndicate.value
    rankings.value = data.rankings || rankings.value
  } finally {
    loading.value = false
  }
}

async function loadProfile() {
  if (!profileSeat.value) return
  profileLoading.value = true
  profileTried.value = true
  try {
    const data = await api.seatsProfile({ seat: profileSeat.value })
    profile.value = data.profile || null
  } finally {
    profileLoading.value = false
  }
}

function doExport() {
  const p = {
    date: selDate.value,
    type: selType.value === 'all' ? '' : selType.value,
    side: selSide.value,
    seat: selSeat.value,
    min_net: (selMinNet.value || 0) * 10000,
  }
  const url = api.seatsExportUrl(p)
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
.stat-v { font-size: 20px; font-weight: 700; color: #1f2733; }
.stat-l { font-size: 12px; color: #8a93a6; margin-top: 2px; }
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
.empty { color: #8a93a6; font-size: 13px; padding: 10px 0; }

.profile-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.pf-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.pf { background: #fafbfc; border-radius: 8px; padding: 12px; text-align: center; }
.pf-v { font-size: 18px; font-weight: 700; color: #1f2733; }
.pf-l { font-size: 12px; color: #8a93a6; margin-top: 3px; }
.pf-latest { font-size: 13px; color: #6b7488; margin: 12px 0 8px; }
.pf-reason { color: #8a93a6; margin-left: 6px; }
.pf-stocks { display: flex; flex-wrap: wrap; gap: 6px; }
.pf-chip { cursor: default; }

.syn-list { display: flex; flex-direction: column; gap: 8px; max-height: 260px; overflow-y: auto; }
.syn-item { display: flex; align-items: center; gap: 10px; font-size: 13px; padding: 6px 8px; background: #fff8ec; border-radius: 6px; }
.syn-name { font-weight: 600; color: #b76e00; }
.syn-code { color: #8a93a6; }
.syn-seats { color: #6b7488; font-size: 12px; }

.rank-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.rank-block { background: #fafbfc; border-radius: 8px; padding: 10px 12px; }
.rank-title { font-size: 13px; font-weight: 600; color: #1f2733; margin-bottom: 8px; }
.rank-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.rank-table th, .rank-table td { text-align: left; padding: 5px 6px; border-bottom: 1px solid #eef0f4; }
.rank-table th { color: #8a93a6; font-weight: 500; }
.rank-table td:last-child { text-align: right; font-weight: 600; }
@media (max-width: 1100px) {
  .stat-row { grid-template-columns: repeat(3, 1fr); }
  .rank-grid { grid-template-columns: 1fr; }
}
</style>
