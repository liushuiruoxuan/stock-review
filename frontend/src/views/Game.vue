<template>
  <div v-loading="loading">
    <!-- 多空对比概览 -->
    <div class="stat-grid">
      <StatCard label="席位买入总额" :value="fmtYuan(g.battle?.buy_total)" tone="up" />
      <StatCard label="席位卖出总额" :value="fmtYuan(g.battle?.sell_total)" tone="down" />
      <StatCard
        label="席位净买"
        :value="fmtYuan((g.battle?.buy_total || 0) - (g.battle?.sell_total || 0))"
        :tone="(g.battle?.buy_total || 0) >= (g.battle?.sell_total || 0) ? 'up' : 'down'" />
      <StatCard label="席位覆盖个股" :value="g.battle?.stock_cnt ?? '--'" />
      <StatCard label="涨停家数" :value="g.ladder?.count ?? '--'" tone="up" />
      <StatCard label="最高连板" :value="(g.ladder?.max_limit ?? 0) + ' 板'" tone="up" />
    </div>

    <div class="two-col">
      <!-- 多空博弈图 -->
      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-h">多空博弈（{{ g.battle?.date || '--' }} 席位口径）</div>
        </template>
        <BaseChart v-if="battleOption" :option="battleOption" height="300px" />
        <el-empty v-else description="暂无席位数据（需 MySQL + 龙虎榜席位抓取）" :image-size="60" />
      </el-card>

      <!-- 连板梯队 -->
      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-h">连板梯队（{{ g.ladder?.date || '--' }}）<span v-if="g.ladder?.broken_rate != null" class="sub">炸板率 {{ g.ladder.broken_rate }}%</span></div>
        </template>
        <div v-if="g.ladder" class="ladder-wrap">
          <div class="dist-tags">
            <span v-for="(cnt, tag) in g.ladder.limit_dist" :key="tag" class="dist-tag">
              {{ tag }} <b>{{ cnt }}</b>
            </span>
          </div>
          <div class="theme-tags">
            <span v-for="t in g.ladder.theme_top.slice(0, 10)" :key="t.theme" class="theme-tag">
              {{ t.theme }} <b>{{ t.count }}</b>
            </span>
          </div>
          <div class="lu-list">
            <div v-for="r in g.ladder.top.slice(0, 8)" :key="r.code" class="lu-row" @click="goStock(r.code)">
              <span class="lu-tag">{{ r.limit_tag }}</span>
              <span class="lu-name">{{ r.name }}</span>
              <span class="lu-reason">{{ r.reason }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无涨停数据" :image-size="60" />
      </el-card>
    </div>

    <div class="two-col">
      <!-- 席位攻击榜 -->
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">席位攻击榜（净买 Top15）</div></template>
        <el-table v-if="seatRows.length" :data="seatRows" size="small" height="340">
          <el-table-column type="index" label="#" width="46" />
          <el-table-column prop="seat_name" label="席位" min-width="220" show-overflow-tooltip />
          <el-table-column prop="net_wan" label="净买(万)" width="110" align="right" sortable>
            <template #default="{ row }">
              <span :class="trendClass(row.net_wan)">{{ fmtNum(row.net_wan, 0) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无席位数据" :image-size="60" />
      </el-card>

      <!-- 抱团监控 -->
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">游资抱团监控（同票 ≥3 席位）</div></template>
        <el-table v-if="g.syndicate?.stocks?.length" :data="g.syndicate.stocks" size="small" height="340">
          <el-table-column prop="code" label="代码" width="90" />
          <el-table-column prop="name" label="名称" width="90" />
          <el-table-column prop="seat_cnt" label="席位数" width="70" align="center" />
          <el-table-column label="席位" min-width="260">
            <template #default="{ row }">
              <span class="synd-seats">{{ row.seats.slice(0, 4).join(' / ') }}{{ row.seats.length > 4 ? ' …' : '' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="60">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="goStock(row.code)">画像</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="当日无抱团信号" :image-size="60" />
      </el-card>
    </div>

    <!-- 热点股（博弈核心池） -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">热点重合榜（龙虎榜 ∩ 涨停 = 博弈核心池）<router-link to="/hot-billboard" class="more">查看全部 ›</router-link></div></template>
      <DataTable v-if="dragonRows.length" :rows="dragonRows" :columns="dragonCols" height="320px" />
      <el-empty v-else description="暂无数据" :image-size="60" />
    </el-card>

    <!-- 连续净卖预警 -->
    <el-card v-if="(g.continuous_sell || []).length" shadow="never" class="card">
      <template #header><div class="card-h">机构连续净卖预警（≥3 日）</div></template>
      <el-table :data="g.continuous_sell" size="small" height="260">
        <el-table-column prop="code" label="代码" width="90" />
        <el-table-column prop="name" label="名称" width="110" />
        <el-table-column prop="streak" label="连续天数" width="90" align="center" />
        <el-table-column prop="end_date" label="最近日期" width="110" />
        <el-table-column prop="latest_net_wan" label="最新净额(万)" width="120" align="right">
          <template #default="{ row }">
            <span :class="trendClass(row.latest_net_wan)">{{ fmtNum(row.latest_net_wan, 0) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import StatCard from '../components/StatCard.vue'
import BaseChart from '../components/BaseChart.vue'
import DataTable from '../components/DataTable.vue'
import { api, ui } from '../api'
import { fmtYuan, fmtPct, fmtNum, trendClass } from '../utils/format'

const router = useRouter()
const loading = ref(true)
const g = ref({})

const goStock = (code) => router.push('/game/stock/' + code)

const battleOption = computed(() => {
  const bt = g.value.battle
  if (!bt || !bt.date || !Object.keys(bt.by_type || {}).length) return null
  const cats = ['机构专用', '沪深股通', '游资/营业部']
  const keys = ['inst', 'hk', 'youzi']
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (p) => p.map(x => `${x.seriesName}<br/>${x.name}: ${fmtYuan(x.value)}`).join('<br/>') },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    grid: { left: 8, right: 18, top: 34, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: cats },
    yAxis: { type: 'value', axisLabel: { formatter: (v) => fmtYuan(v) } },
    series: [
      { name: '买入', type: 'bar', barWidth: '28%', itemStyle: { color: '#f5222d' },
        data: keys.map(k => (bt.by_type[k] || {}).buy || 0) },
      { name: '卖出', type: 'bar', barWidth: '28%', itemStyle: { color: '#16a34a' },
        data: keys.map(k => (bt.by_type[k] || {}).sell || 0) }
    ]
  }
})

const seatRows = computed(() => (g.value.seat_heat?.net || []).slice(0, 15))
const dragonRows = computed(() => g.value.dragon || [])
const dragonCols = [
  { prop: 'name', label: '名称', width: 100, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'limit_tag', label: '梯队', width: 80, align: 'center' },
  { prop: 'change_pct', label: '涨幅', width: 90, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'net_amt', label: '龙虎榜净买', width: 120, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'inst_buy_cnt', label: '机构买(家)', width: 100, align: 'center' },
  { prop: 'themes', label: '题材', minWidth: 160 },
  { prop: 'reason', label: '涨停原因', minWidth: 200 }
]

async function loadAll() {
  loading.value = true
  try {
    g.value = await api.gameOverview()
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
watch(() => ui.selectedDate, loadAll)
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; margin-bottom: 14px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
.card { border-radius: 10px; margin-bottom: 0; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
.sub { font-size: 12px; font-weight: 400; color: #d48806; }
.more { margin-left: auto; font-size: 13px; color: #409eff; text-decoration: none; font-weight: 400; }
.ladder-wrap { display: flex; flex-direction: column; gap: 10px; }
.dist-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.dist-tag { background: #fef0f0; color: #f5222d; border: 1px solid #fdd; border-radius: 4px; padding: 2px 8px; font-size: 12px; }
.dist-tag b { font-size: 13px; }
.theme-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.theme-tag { background: #f0f7ff; color: #337ecc; border: 1px solid #d9ecff; border-radius: 4px; padding: 2px 8px; font-size: 12px; }
.lu-list { display: flex; flex-direction: column; }
.lu-row { display: flex; align-items: center; gap: 10px; padding: 6px 2px; border-bottom: 1px dashed #eee; cursor: pointer; font-size: 13px; }
.lu-row:hover { background: #f7f9fc; }
.lu-tag { background: #fef0f0; color: #f5222d; border-radius: 4px; padding: 1px 6px; font-size: 11px; flex-shrink: 0; }
.lu-name { font-weight: 700; width: 80px; flex-shrink: 0; }
.lu-reason { color: #8a93a6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.synd-seats { font-size: 12px; color: #6b7488; }
@media (max-width: 1100px) {
  .stat-grid { grid-template-columns: repeat(3, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
@media (max-width: 768px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
