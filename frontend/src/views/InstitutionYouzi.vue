<template>
  <div v-loading="loading">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>
        机构动向由龙虎榜中「机构买入/卖出」个股汇总；游资动向为龙虎榜中机构未主导、由营业部主导的活跃标的（净买入排序）。
        数据源为龙虎榜席位说明，真实席位级明细将在可获取时自动增强。
      </template>
    </el-alert>

    <div class="two-col">
      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-h">机构净买入榜（{{ inst.buy.length }}）<SourceTag section="institution" /></div>
        </template>
        <div class="table-scroll">
          <DataTable :rows="inst.buy" :columns="cols" :height="'460px'" />
        </div>
      </el-card>
      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-h">机构净卖出榜（{{ inst.sell.length }}）<SourceTag section="institution" /></div>
        </template>
        <div class="table-scroll">
          <DataTable :rows="inst.sell" :columns="cols" :height="'460px'" />
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">游资 / 营业部活跃榜（{{ youzi.length }}）<SourceTag section="youzi" /></div>
      </template>
      <div class="table-scroll">
        <DataTable :rows="youzi" :columns="youziCols" :height="'520px'" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import DataTable from '../components/DataTable.vue'
import SourceTag from '../components/SourceTag.vue'
import { api, ui } from '../api'
import { fmtYuan, fmtPct, trendClass } from '../utils/format'
import { useResponsive } from '../composables/useResponsive'

const { isMobile } = useResponsive()

const loading = ref(true)
const inst = ref({ buy: [], sell: [] })
const youzi = ref([])

const COL_DESKTOP = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'change_pct', label: '涨幅', width: 90, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'net_amt', label: '龙虎榜净买', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'reason', label: '上榜原因', minWidth: 180 },
  { prop: 'explain', label: '席位说明', minWidth: 160, render: (r) => r.explain || '--' },
  { prop: 'd1', label: '次日%', width: 90, align: 'right', sortable: true, render: (r) => (r.d1 == null ? '--' : fmtPct(r.d1)), cellClass: (r) => trendClass(r.d1) }
]
const COL_MOBILE = [
  { prop: 'name', label: '名称', minWidth: 70, fixed: 'left' },
  { prop: 'code', label: '代码', width: 70 },
  { prop: 'change_pct', label: '涨幅', width: 68, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'net_amt', label: '净买', width: 100, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) }
]
const cols = computed(() => isMobile.value ? COL_MOBILE : COL_DESKTOP)

const YZ_DESKTOP = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'change_pct', label: '涨幅', width: 90, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'net_amt', label: '龙虎榜净买', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'turnover', label: '换手%', width: 90, align: 'right', render: (r) => (r.turnover == null ? '--' : r.turnover.toFixed(2)) },
  { prop: 'reason', label: '上榜原因', minWidth: 180 },
  { prop: 'explain', label: '席位说明', minWidth: 160, render: (r) => r.explain || '--' }
]
const YZ_MOBILE = [
  { prop: 'name', label: '名称', minWidth: 70, fixed: 'left' },
  { prop: 'code', label: '代码', width: 70 },
  { prop: 'change_pct', label: '涨幅', width: 68, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'net_amt', label: '净买', width: 100, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) }
]
const youziCols = computed(() => isMobile.value ? YZ_MOBILE : YZ_DESKTOP)

async function loadAll() {
  loading.value = true
  try {
    const [i, y] = await Promise.all([api.institution(), api.youzi(60)])
    inst.value = i || { buy: [], sell: [] }
    youzi.value = y || []
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
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 1100px) { .two-col { grid-template-columns: 1fr; } }
</style>
