<template>
  <div v-loading="loading">
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          条件选股
          <span class="sub">行情快照 {{ res.bar_date || '--' }} × 涨停 {{ res.limitup_date || '--' }} × 席位净买</span>
          <el-button size="small" type="primary" style="margin-left: auto" @click="load">执行筛选</el-button>
        </div>
      </template>
      <el-form inline>
        <el-form-item label="涨幅(%)">
          <div class="range-box">
            <el-input-number v-model="c.pct_min" :controls="false" placeholder="min" style="width: 84px" />
            <span class="sep">~</span>
            <el-input-number v-model="c.pct_max" :controls="false" placeholder="max" style="width: 84px" />
          </div>
        </el-form-item>
        <el-form-item label="换手(%)">
          <div class="range-box">
            <el-input-number v-model="c.turnover_min" :controls="false" placeholder="min" style="width: 84px" />
            <span class="sep">~</span>
            <el-input-number v-model="c.turnover_max" :controls="false" placeholder="max" style="width: 84px" />
          </div>
        </el-form-item>
        <el-form-item label="成交额≥(亿)">
          <el-input-number v-model="c.amount_min" :controls="false" style="width: 100px" :step="1e8" />
        </el-form-item>
        <el-form-item label="连板≥">
          <el-input-number v-model="c.limit_count_min" :min="1" :max="20" style="width: 90px" />
        </el-form-item>
        <el-form-item label="机构净买≥(万)">
          <el-input-number v-model="c.inst_net_min" :controls="false" style="width: 110px" :step="1e4" />
        </el-form-item>
        <el-form-item label="游资净买≥(万)">
          <el-input-number v-model="c.youzi_net_min" :controls="false" style="width: 110px" :step="1e4" />
        </el-form-item>
        <el-form-item label="排序">
          <el-select v-model="c.sort" style="width: 130px">
            <el-option label="涨跌幅" value="pct_chg" />
            <el-option label="成交额" value="amount" />
            <el-option label="换手率" value="turnover" />
            <el-option label="连板数" value="limit_count" />
            <el-option label="机构净买" value="inst_net" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="c.limit" :min="10" :max="500" style="width: 100px" />
        </el-form-item>
      </el-form>
      <el-alert v-if="res.hint" type="warning" :closable="false" show-icon :title="res.hint" class="hint" />
    </el-card>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">筛选结果（{{ res.count ?? 0 }}）<router-link to="/quant" class="more">量化回测 ›</router-link></div>
      </template>
      <DataTable :rows="res.rows || []" :columns="cols" height="560px" :empty-text="res.bar_date ? '无满足条件的个股' : '先执行筛选'" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DataTable from '../components/DataTable.vue'
import { api } from '../api'
import { fmtYuan, fmtPct, fmtNum, trendClass } from '../utils/format'

const loading = ref(false)
const res = ref({})
const c = ref({
  pct_min: null, pct_max: null, turnover_min: null, turnover_max: null,
  amount_min: null, limit_count_min: null, inst_net_min: null, youzi_net_min: null,
  sort: 'pct_chg', limit: 100
})

const cols = [
  { prop: 'name', label: '名称', width: 100, fixed: 'left' },
  { prop: 'code', label: '代码', width: 90 },
  { prop: 'close', label: '收盘', width: 80, align: 'right', render: (r) => fmtNum(r.close) },
  { prop: 'pct_chg', label: '涨幅', width: 88, align: 'right', sortable: true, render: (r) => fmtPct(r.pct_chg), cellClass: (r) => trendClass(r.pct_chg) },
  { prop: 'turnover', label: '换手%', width: 88, align: 'right', sortable: true, render: (r) => fmtNum(r.turnover) },
  { prop: 'amount', label: '成交额', width: 110, align: 'right', sortable: true, render: (r) => fmtYuan(r.amount) },
  { prop: 'limit_count', label: '连板', width: 70, align: 'center', sortable: true },
  { prop: 'limit_tag', label: '梯队', width: 80, align: 'center' },
  { prop: 'inst_net', label: '机构净买', width: 110, align: 'right', sortable: true, render: (r) => fmtYuan(r.inst_net), cellClass: (r) => trendClass(r.inst_net) },
  { prop: 'youzi_net', label: '游资净买', width: 110, align: 'right', sortable: true, render: (r) => fmtYuan(r.youzi_net), cellClass: (r) => trendClass(r.youzi_net) },
  { prop: 'themes', label: '题材', minWidth: 180 }
]

async function load() {
  loading.value = true
  try {
    const cond = {}
    for (const [k, v] of Object.entries(c.value)) {
      if (v !== null && v !== '' && v !== undefined) cond[k] = v
    }
    res.value = await api.quantScreener(cond)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card { border-radius: 10px; margin-bottom: 14px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
.sub { font-size: 12px; font-weight: 400; color: #8a93a6; }
.more { margin-left: auto; font-size: 13px; color: #409eff; text-decoration: none; font-weight: 400; }
.range-box { display: flex; align-items: center; gap: 4px; }
.sep { color: #8a93a6; }
.hint { border-radius: 8px; }
</style>
