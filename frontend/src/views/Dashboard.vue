<template>
  <div v-loading="loading" element-loading-text="加载复盘数据...">
    <div class="stat-grid">
      <StatCard label="龙虎榜上榜数" :value="summary.billboard_count || 0" tone="" />
      <StatCard label="龙虎榜净买入合计" :value="fmtYuan(summary.billboard_net_total)" :tone="(summary.billboard_net_total||0) >= 0 ? 'up' : 'down'" />
      <StatCard label="机构参与标的" :value="summary.inst_count || 0" tone="" />
      <StatCard label="游资活跃标的" :value="summary.youzi_count || 0" tone="" />
      <StatCard label="资金流入板块" :value="summary.sectors_hot_count || 0" tone="up" />
      <StatCard label="资金流出板块" :value="summary.sectors_outflow_count || 0" tone="down" />
    </div>

    <div class="chart-grid">
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">龙虎榜净买入 Top10 <SourceTag section="billboard" /></div></template>
        <BaseChart :option="bbOption" height="360px" />
      </el-card>
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">热点板块资金流入 Top10 <SourceTag section="sectors_hot" /></div></template>
        <BaseChart :option="sectorOption" height="360px" />
      </el-card>
    </div>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          龙虎榜净买入榜
          <SourceTag section="billboard" />
          <router-link to="/billboard" class="more">查看全部 ›</router-link>
        </div>
      </template>
      <DataTable :rows="bbRows" :columns="bbCols" :height="'420px'" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import StatCard from '../components/StatCard.vue'
import BaseChart from '../components/BaseChart.vue'
import DataTable from '../components/DataTable.vue'
import SourceTag from '../components/SourceTag.vue'
import { api } from '../api'
import { fmtYuan, fmtPct, trendClass } from '../utils/format'
import { netBarOption } from '../utils/charts'

const loading = ref(true)
const summary = ref({})
const billboard = ref([])
const sectorsHot = ref([])

const bbRows = computed(() => (billboard.value || []).slice(0, 12))
const bbCols = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'change_pct', label: '涨幅', width: 90, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'net_amt', label: '龙虎榜净买', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'reason', label: '上榜原因', minWidth: 200 },
  { prop: 'explain', label: '席位说明', minWidth: 160 }
]

const bbOption = computed(() => {
  const top = (billboard.value || []).slice(0, 10).reverse()
  return netBarOption(top.map((r) => r.name), top.map((r) => r.net_amt))
})
const sectorOption = computed(() => {
  const top = (sectorsHot.value || []).slice(0, 10).reverse()
  return netBarOption(top.map((r) => r.name), top.map((r) => r.main_net))
})

onMounted(async () => {
  try {
    const [s, b, h] = await Promise.all([api.summary(), api.billboard(), api.sectorsHot(10)])
    summary.value = s || {}
    billboard.value = b || []
    sectorsHot.value = h || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; margin-bottom: 14px; }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
.card { border-radius: 10px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
.more { margin-left: auto; font-size: 13px; color: #409eff; text-decoration: none; font-weight: 400; }
@media (max-width: 1100px) {
  .stat-grid { grid-template-columns: repeat(3, 1fr); }
  .chart-grid { grid-template-columns: 1fr; }
}
</style>
