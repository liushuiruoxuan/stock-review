<template>
  <div v-loading="loading">
    <el-alert type="warning" :closable="false" show-icon class="tip">
      <template #title>极速拉升 = 当日涨幅榜前列个股（结合主力净流入判断资金抢筹力度）</template>
    </el-alert>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          涨幅榜 Top15
          <SourceTag section="rapid_rise" />
          <el-switch v-model="onlyMain" active-text="仅看主力净流入为正" inline-prompt style="margin-left: auto;" />
        </div>
      </template>
      <BaseChart :option="option" height="360px" />
    </el-card>

    <el-card shadow="never" class="card">
      <template #header><div class="card-h">极速拉升个股 <SourceTag section="rapid_rise" /></div></template>
      <DataTable :rows="list" :columns="cols" :height="'540px'" />
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

const loading = ref(true)
const rows = ref([])
const onlyMain = ref(false)

const list = computed(() => {
  let r = rows.value
  if (onlyMain.value) r = r.filter((x) => (x.main_net || 0) > 0)
  return r
})

const cols = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'price', label: '现价', width: 80, align: 'right' },
  { prop: 'change_pct', label: '涨幅', width: 100, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'main_net', label: '主力净流入', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.main_net), cellClass: (r) => trendClass(r.main_net) },
  { prop: 'main_net_pct', label: '主力净占%', width: 110, align: 'right', sortable: true, render: (r) => fmtPct(r.main_net_pct), cellClass: (r) => trendClass(r.main_net_pct) },
  { prop: 'turnover', label: '换手%', width: 90, align: 'right', render: (r) => (r.turnover == null ? '--' : r.turnover.toFixed(2)) }
]

const option = computed(() => {
  const t = list.value.slice(0, 15).reverse()
  // 用涨幅画柱状（全为正），颜色统一红
  return netBarOption(t.map((r) => r.name), t.map((r) => r.change_pct))
})

onMounted(async () => {
  try {
    rows.value = (await api.rapidRise(60)) || []
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
