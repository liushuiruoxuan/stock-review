<template>
  <div v-loading="loading">
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          龙虎榜净买入 Top15
          <SourceTag section="billboard" />
        </div>
      </template>
      <BaseChart :option="option" height="380px" />
    </el-card>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          龙虎榜全部上榜个股（{{ rows.length }} 只）
          <SourceTag section="billboard" />
          <el-input v-model="kw" placeholder="搜索名称/代码" size="small" clearable style="width: 180px; margin-left: auto;" />
        </div>
      </template>
      <div class="table-scroll">
        <DataTable :rows="filtered" :columns="cols" :height="'560px'" />
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
const kw = ref('')

const filtered = computed(() => {
  const k = kw.value.trim()
  if (!k) return rows.value
  return rows.value.filter((r) => (r.name || '').includes(k) || (r.code || '').includes(k))
})

const COL_DESKTOP = [
  { prop: 'name', label: '名称', minWidth: 90, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'close', label: '收盘', width: 80, align: 'right' },
  { prop: 'change_pct', label: '涨幅', width: 90, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'turnover', label: '换手%', width: 90, align: 'right', sortable: true, render: (r) => (r.turnover == null ? '--' : r.turnover.toFixed(2)) },
  { prop: 'net_amt', label: '龙虎榜净买', width: 130, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'buy_amt', label: '买入额', width: 120, align: 'right', render: (r) => fmtYuan(r.buy_amt) },
  { prop: 'sell_amt', label: '卖出额', width: 120, align: 'right', render: (r) => fmtYuan(r.sell_amt) },
  { prop: 'reason', label: '上榜原因', minWidth: 200 },
  { prop: 'explain', label: '席位说明', minWidth: 160, render: (r) => r.explain || '--' },
  { prop: 'd1', label: '次日%', width: 90, align: 'right', sortable: true, render: (r) => (r.d1 == null ? '--' : fmtPct(r.d1)), cellClass: (r) => trendClass(r.d1) }
]
const COL_MOBILE = [
  { prop: 'name', label: '名称', minWidth: 80, fixed: 'left' },
  { prop: 'code', label: '代码', width: 72 },
  { prop: 'change_pct', label: '涨幅', width: 72, align: 'right', sortable: true, render: (r) => fmtPct(r.change_pct), cellClass: (r) => trendClass(r.change_pct) },
  { prop: 'net_amt', label: '净买', width: 100, align: 'right', sortable: true, render: (r) => fmtYuan(r.net_amt), cellClass: (r) => trendClass(r.net_amt) },
  { prop: 'buy_amt', label: '买入', width: 100, align: 'right', render: (r) => fmtYuan(r.buy_amt) },
  { prop: 'reason', label: '原因', minWidth: 120 }
]
const cols = computed(() => isMobile.value ? COL_MOBILE : COL_DESKTOP)

const option = computed(() => {
  const top = rows.value.slice(0, 15).reverse()
  return netBarOption(top.map((r) => r.name), top.map((r) => r.net_amt))
})

onMounted(async () => {
  try {
    rows.value = (await api.billboard()) || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
</style>
