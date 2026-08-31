<template>
  <div v-loading="loading">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>全市场实时涨幅排行（数据：新浪财经，仅供参考）</template>
    </el-alert>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          涨幅榜 Top15
          <SourceTag section="rapid_rise" />
        </div>
      </template>
      <BaseChart :option="option" height="360px" />
    </el-card>

    <el-card shadow="never" class="card">
      <template #header><div class="card-h">极速拉升个股 <SourceTag section="rapid_rise" /></div></template>
      <div class="table-scroll">
        <DataTable :rows="rows" :columns="cols" :height="'540px'" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import BaseChart from '../components/BaseChart.vue'
import DataTable from '../components/DataTable.vue'
import SourceTag from '../components/SourceTag.vue'
import { api, ui } from '../api'
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
  { prop: 'volume', label: '成交量(股)', width: 120, align: 'right', sortable: true, render: (r) => (r.volume != null ? r.volume.toLocaleString() : '--') },
  { prop: 'turnover', label: '成交额', width: 120, align: 'right', sortable: true, render: (r) => fmtYuan(r.turnover) },
  { prop: 'turnover_rate', label: '换手%', width: 90, align: 'right', render: (r) => (r.turnover_rate == null ? '--' : r.turnover_rate.toFixed(2)) }
]
const COL_MOBILE = [
  { prop: 'name', label: '名称', minWidth: 80, fixed: 'left' },
  { prop: 'code', label: '代码', width: 72 },
  { prop: 'change_pct', label: '涨幅', width: 72, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'price', label: '现价', width: 64, align: 'right' },
  { prop: 'turnover_rate', label: '换手%', width: 60, align: 'right', render: (r) => (r.turnover_rate == null ? '--' : r.turnover_rate.toFixed(2)) }
]
const cols = computed(() => isMobile.value ? COL_MOBILE : COL_DESKTOP)

const option = computed(() => {
  const t = rows.value.slice(0, 15).reverse()
  return netBarOption(t.map((r) => r.name), t.map((r) => r.change_pct))
})

async function loadAll() {
  loading.value = true
  try {
    rows.value = (await api.rapidRise(60)) || []
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
// 历史回看日期切换时自动重新加载
watch(() => ui.selectedDate, loadAll)
</script>

<style scoped>
.tip { margin-bottom: 14px; border-radius: 8px; }
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
</style>
