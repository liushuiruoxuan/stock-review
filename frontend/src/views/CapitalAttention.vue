<template>
  <div v-loading="loading">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>资金关注 = 当日主力净流入且收涨的个股，按主力净流入排序，反映资金主动承接力度</template>
    </el-alert>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">资金关注度 Top15（主力净流入）<SourceTag section="capital_attention" /></div>
      </template>
      <BaseChart :option="option" height="360px" />
    </el-card>

    <el-card shadow="never" class="card">
      <template #header><div class="card-h">资金关注榜 <SourceTag section="capital_attention" /></div></template>
      <div class="table-scroll">
        <DataTable :rows="rows" :columns="cols" :height="'540px'" />
      </div>
    </el-card>
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
import { useResponsive } from '../composables/useResponsive'

const { isMobile } = useResponsive()

const loading = ref(true)
const rows = ref([])

const COL_DESKTOP = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'price', label: '现价', width: 80, align: 'right' },
  { prop: 'change_pct', label: '涨幅', width: 100, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'main_net', label: '主力净流入', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.main_net), cellClass: (r) => trendClass(r.main_net) },
  { prop: 'main_net_pct', label: '主力净占%', width: 110, align: 'right', sortable: true, render: (r) => fmtPct(r.main_net_pct), cellClass: (r) => trendClass(r.main_net_pct) },
  { prop: 'super_net', label: '超大单', width: 120, align: 'right', render: (r) => fmtYuan(r.super_net), cellClass: (r) => trendClass(r.super_net) },
  { prop: 'big_net', label: '大单', width: 120, align: 'right', render: (r) => fmtYuan(r.big_net), cellClass: (r) => trendClass(r.big_net) }
]
const COL_MOBILE = [
  { prop: 'name', label: '名称', minWidth: 80, fixed: 'left' },
  { prop: 'code', label: '代码', width: 72 },
  { prop: 'change_pct', label: '涨幅', width: 72, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'main_net', label: '主力净流入', width: 110, align: 'right', sortable: true, render: (r) => fmtYuan(r.main_net), cellClass: (r) => trendClass(r.main_net) }
]
const cols = computed(() => isMobile.value ? COL_MOBILE : COL_DESKTOP)

const option = computed(() => {
  const t = rows.value.slice(0, 15).reverse()
  return netBarOption(t.map((r) => r.name), t.map((r) => r.main_net))
})

onMounted(async () => {
  try {
    rows.value = (await api.capitalAttention(60)) || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.tip { margin-bottom: 14px; border-radius: 8px; }
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
</style>
