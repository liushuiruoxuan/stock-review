<template>
  <div v-loading="loading">
    <el-tabs v-model="tab" class="tabs">
      <el-tab-pane label="今日热点板块（资金流入）" name="hot">
        <el-card shadow="never" class="card">
          <template #header>
            <div class="card-h">热点板块资金流入 Top15 <SourceTag section="sectors_hot" /></div>
          </template>
          <BaseChart :option="hotOption" height="360px" />
        </el-card>
        <el-card shadow="never" class="card">
          <template #header><div class="card-h">热点板块明细 <SourceTag section="sectors_hot" /></div></template>
          <div class="table-scroll">
            <DataTable :rows="hot" :columns="cols" :height="'500px'" />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="资金流出板块" name="out">
        <el-card shadow="never" class="card">
          <template #header>
            <div class="card-h">资金净流出板块 Top15 <SourceTag section="sectors_outflow" /></div>
          </template>
          <BaseChart :option="outOption" height="360px" />
        </el-card>
        <el-card shadow="never" class="card">
          <template #header><div class="card-h">资金流出板块明细 <SourceTag section="sectors_outflow" /></div></template>
          <div class="table-scroll">
            <DataTable :rows="out" :columns="cols" :height="'500px'" />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
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
const tab = ref('hot')
const hot = ref([])
const out = ref([])

const COL_DESKTOP = [
  { prop: 'name', label: '板块', minWidth: 110, fixed: 'left' },
  { prop: 'change_pct', label: '涨幅', width: 100, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'main_net', label: '主力净流入', width: 140, align: 'right', sortable: true, render: (r) => fmtYuan(r.main_net), cellClass: (r) => trendClass(r.main_net) },
  { prop: 'main_net_pct', label: '主力净占%', width: 120, align: 'right', sortable: true, render: (r) => fmtPct(r.main_net_pct), cellClass: (r) => trendClass(r.main_net_pct) },
  { prop: 'leader_name', label: '领涨股', minWidth: 100, render: (r) => r.leader_name || '--' }
]
const COL_MOBILE = [
  { prop: 'name', label: '板块', minWidth: 80, fixed: 'left' },
  { prop: 'change_pct', label: '涨幅', width: 72, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'main_net', label: '主力净流入', width: 110, align: 'right', sortable: true, render: (r) => fmtYuan(r.main_net), cellClass: (r) => trendClass(r.main_net) },
  { prop: 'leader_name', label: '领涨股', minWidth: 80, render: (r) => r.leader_name || '--' }
]
const cols = computed(() => isMobile.value ? COL_MOBILE : COL_DESKTOP)

const hotOption = computed(() => {
  const t = hot.value.slice(0, 15).reverse()
  return netBarOption(t.map((r) => r.name), t.map((r) => r.main_net))
})
const outOption = computed(() => {
  const t = out.value.slice(0, 15).reverse()
  return netBarOption(t.map((r) => r.name), t.map((r) => r.main_net))
})

onMounted(async () => {
  try {
    const [h, o] = await Promise.all([api.sectorsHot(30), api.sectorsOutflow(30)])
    hot.value = h || []
    out.value = o || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.tabs :deep(.el-tabs__header) { margin-bottom: 14px; }
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
</style>
