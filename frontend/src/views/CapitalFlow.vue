<template>
  <div v-loading="loading">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>个股资金流向（主力 / 超大单 / 大单 / 中单 / 小单净流入，单位元）</template>
    </el-alert>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          主力资金净流入 Top15
          <SourceTag section="stocks_flow" />
        </div>
      </template>
      <BaseChart :option="option" height="360px" />
    </el-card>

    <div class="two-col">
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">主力净流入榜 <SourceTag section="stocks_flow" /></div></template>
        <DataTable :rows="inflow" :columns="cols" :height="'520px'" />
      </el-card>
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">主力净流出榜 <SourceTag section="stocks_flow" /></div></template>
        <DataTable :rows="outflow" :columns="cols" :height="'520px'" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import BaseChart from '../components/BaseChart.vue'
import DataTable from '../components/DataTable.vue'
import SourceTag from '../components/SourceTag.vue'
import { api } from '../api'
import { fmtYuan, fmtPct, trendClass } from '../utils/format'
import { netBarOption } from '../utils/charts'

const loading = ref(true)
const inflow = ref([])
const outflow = ref([])

const cols = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'price', label: '现价', width: 80, align: 'right' },
  { prop: 'change_pct', label: '涨幅', width: 90, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'main_net', label: '主力净流入', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.main_net), cellClass: (r) => trendClass(r.main_net) },
  { prop: 'main_net_pct', label: '主力净占%', width: 110, align: 'right', sortable: true, render: (r) => fmtPct(r.main_net_pct), cellClass: (r) => trendClass(r.main_net_pct) },
  { prop: 'super_net', label: '超大单', width: 120, align: 'right', render: (r) => fmtYuan(r.super_net), cellClass: (r) => trendClass(r.super_net) },
  { prop: 'big_net', label: '大单', width: 120, align: 'right', render: (r) => fmtYuan(r.big_net), cellClass: (r) => trendClass(r.big_net) },
  { prop: 'mid_net', label: '中单', width: 110, align: 'right', render: (r) => fmtYuan(r.mid_net), cellClass: (r) => trendClass(r.mid_net) },
  { prop: 'small_net', label: '小单', width: 110, align: 'right', render: (r) => fmtYuan(r.small_net), cellClass: (r) => trendClass(r.small_net) }
]

const option = computed(() => {
  const top = inflow.value.slice(0, 15).reverse()
  return netBarOption(top.map((r) => r.name), top.map((r) => r.main_net))
})

onMounted(async () => {
  try {
    const d = (await api.stocksFlow(60)) || {}
    inflow.value = d.inflow || []
    outflow.value = d.outflow || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.tip { margin-bottom: 14px; border-radius: 8px; }
.card { border-radius: 10px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 1100px) { .two-col { grid-template-columns: 1fr; } }
</style>
