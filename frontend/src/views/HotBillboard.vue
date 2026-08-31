<template>
  <div class="hb-page">
    <div class="page-head">
      <div>
        <h2 class="view-title">龙虎榜 x 涨停板：热点重合排行榜</h2>
        <p class="view-sub">
          同时登上龙虎榜且涨停的股票（按龙虎榜净买入额排序），聚焦资金+情绪共振的热点标的。
          <template v-if="ui.selectedDate"> · 回看日期：<b>{{ ui.selectedDate }}</b></template>
          <template v-else-if="hbDate"> · 数据日期：<b>{{ hbDate }}</b></template>
        </p>
      </div>
      <div class="head-tools">
        <el-tag v-if="ui.sources.hot_billboard === 'live'" type="success" effect="plain" size="small">实时数据</el-tag>
        <el-tag v-else-if="ui.sources.hot_billboard === 'demo'" type="warning" effect="plain" size="small">示例数据</el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="stat-row" v-if="stats">
      <div class="stat-card">
        <div class="stat-label">重合热股数</div>
        <div class="stat-value up">{{ stats.count }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">龙虎榜净买入合计</div>
        <div class="stat-value" :class="yuanClass(stats.net_amt_total)">{{ fmtYuan(stats.net_amt_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">封单总额</div>
        <div class="stat-value">{{ fmtYuan(stats.seal_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">涨停净流入合计</div>
        <div class="stat-value" :class="yuanClass(stats.net_inflow_total)">{{ fmtYuan(stats.net_inflow_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">机构参与家数</div>
        <div class="stat-value">{{ stats.inst_count }}</div>
      </div>
    </div>

    <!-- 题材标签云 -->
    <el-card class="theme-card" shadow="never" v-if="stats && stats.theme_top.length">
      <template #header><span class="card-h">重合热股涉及题材</span></template>
      <el-tag
        v-for="t in stats.theme_top"
        :key="t.theme"
        class="theme-tag"
        effect="plain"
        type="danger"
      >{{ t.theme }} · {{ t.count }}</el-tag>
    </el-card>

    <el-card class="table-card" shadow="never">
      <div class="filter-bar">
        <el-input v-model="kw" placeholder="搜索代码 / 名称" clearable style="width: 200px" @input="applyFilter" />
        <el-select v-model="minLimit" placeholder="连板数≥" style="width: 130px" @change="applyFilter">
          <el-option label="全部" :value="0" />
          <el-option label="2 板及以上" :value="2" />
          <el-option label="3 板及以上" :value="3" />
          <el-option label="5 板及以上" :value="5" />
        </el-select>
        <el-select v-model="minNet" placeholder="净买入≥" style="width: 130px" @change="applyFilter">
          <el-option label="全部" :value="0" />
          <el-option label="≥ 1000 万" :value="1e7" />
          <el-option label="≥ 3000 万" :value="3e7" />
          <el-option label="≥ 5000 万" :value="5e7" />
          <el-option label="≥ 1 亿" :value="1e8" />
        </el-select>
        <el-checkbox v-model="onlyInst" @change="applyFilter">仅看机构参与</el-checkbox>
        <span class="filter-count">共 {{ filtered.length }} 只</span>
      </div>

      <!-- 桌面表格 -->
      <template v-if="!isMobile">
        <div class="table-scroll">
          <el-table :data="paged" stripe border height="560" v-loading="loading"
            :default-sort="{ prop: 'net_amt', order: 'descending' }">
            <el-table-column type="index" label="#" width="48" />
            <el-table-column label="代码 / 名称" min-width="140" fixed>
              <template #default="{ row }">
                <div class="name-cell">
                  <span class="code">{{ row.code }}</span>
                  <span class="sname">{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="连板" width="84" prop="limit_count" sortable>
              <template #default="{ row }">
                <span class="limit-badge" :class="limitClass(row.limit_count)">{{ row.limit_tag || '首板' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="涨跌幅" width="86" prop="change_pct" sortable align="right">
              <template #default="{ row }">
                <span :class="trendClass(row.change_pct)">{{ fmtPct(row.change_pct) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="最新价" width="80" prop="close" sortable align="right" />
            <el-table-column label="龙虎榜净买" prop="net_amt" sortable min-width="120" align="right">
              <template #default="{ row }">
                <span :class="yuanClass(row.net_amt)">{{ fmtYuan(row.net_amt) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="买入 / 卖出" min-width="140" align="right">
              <template #default="{ row }">
                <div class="buy-sell">
                  <span class="bs-buy">{{ fmtYuan(row.buy_amt) }}</span>
                  <span class="bs-div">/</span>
                  <span class="bs-sell">{{ fmtYuan(row.sell_amt) }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="机构" width="80" align="center">
              <template #default="{ row }">
                <span v-if="(row.inst_buy_cnt || 0) + (row.inst_sell_cnt || 0) > 0" class="inst-tag">
                  买{{ row.inst_buy_cnt || 0 }} / 卖{{ row.inst_sell_cnt || 0 }}
                </span>
                <span v-else class="no-inst">--</span>
              </template>
            </el-table-column>
            <el-table-column label="涨停原因" prop="lu_reason" min-width="140" show-overflow-tooltip />
            <el-table-column label="题材" prop="themes" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="themes">{{ row.themes || '--' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="封单金额" width="110" prop="seal_money" sortable align="right">
              <template #default="{ row }">{{ fmtYuan(row.seal_money) }}</template>
            </el-table-column>
            <el-table-column label="换手率" width="86" prop="turnover_rate" sortable align="right">
              <template #default="{ row }">{{ row.turnover_rate != null ? row.turnover_rate + '%' : '--' }}</template>
            </el-table-column>
            <el-table-column label="流通市值" width="110" prop="free_cap" sortable align="right">
              <template #default="{ row }">{{ fmtYuan(row.free_cap) }}</template>
            </el-table-column>
            <el-table-column label="同行业涨停" width="92" prop="industry_zt" sortable align="center">
              <template #default="{ row }">
                <span v-if="row.industry_zt">{{ row.industry_zt }} 家</span><span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column label="T+1" width="64" prop="d1" sortable align="right">
              <template #default="{ row }">
                <span :class="trendClass(row.d1)">{{ fmtPct(row.d1) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="T+5" width="64" prop="d5" sortable align="right">
              <template #default="{ row }">
                <span :class="trendClass(row.d5)">{{ fmtPct(row.d5) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-pagination
          class="pager"
          layout="prev, pager, next"
          :total="filtered.length"
          :page-size="pageSize"
          v-model:current-page="page"
        />
      </template>

      <!-- 移动端卡片视图 -->
      <div v-else class="mobile-cards">
        <div v-for="r in paged" :key="r.code" class="mc-item">
          <div class="mc-head">
            <span class="limit-badge" :class="limitClass(r.limit_count)">{{ r.limit_tag || '首板' }}</span>
            <span class="mc-name">{{ r.name }}</span>
            <span class="mc-code">{{ r.code }}</span>
          </div>
          <div class="mc-body">
            <div class="mc-row mc-main-nums">
              <span>净买 <b :class="yuanClass(r.net_amt)">{{ fmtYuan(r.net_amt) }}</b></span>
              <span class="mc-div">|</span>
              <span>涨跌 <b :class="trendClass(r.change_pct)">{{ fmtPct(r.change_pct) }}</b></span>
            </div>
            <div class="mc-row mc-detail">
              <span>买 {{ fmtYuan(r.buy_amt) }} / 卖 {{ fmtYuan(r.sell_amt) }}</span>
            </div>
            <div class="mc-row" v-if="(r.inst_buy_cnt || 0) + (r.inst_sell_cnt || 0) > 0">
              <el-tag size="small" type="danger" effect="plain">机构 买{{ r.inst_buy_cnt }}卖{{ r.inst_sell_cnt }}</el-tag>
            </div>
            <div class="mc-row" v-if="r.lu_reason">{{ r.lu_reason }}</div>
            <div class="mc-row mc-themes" v-if="r.themes">{{ r.themes }}</div>
          </div>
        </div>
        <el-pagination
          class="pager"
          layout="prev, pager, next"
          :total="filtered.length"
          :page-size="pageSize"
          v-model:current-page="page"
          small
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { api, ui } from '../api'
import { fmtYuan, fmtPct, trendClass, yuanClass } from '../utils/format'
import { useResponsive } from '../composables/useResponsive'

const { isMobile } = useResponsive()

const loading = ref(false)
const ranking = ref([])

const kw = ref('')
const minLimit = ref(0)
const minNet = ref(0)
const onlyInst = ref(false)
const page = ref(1)
const pageSize = 30

function limitClass(n) {
  n = n || 1
  if (n >= 5) return 'lb-5'
  if (n >= 4) return 'lb-4'
  if (n === 3) return 'lb-3'
  if (n === 2) return 'lb-2'
  return 'lb-1'
}

const filtered = computed(() => {
  let list = ranking.value
  if (kw.value) {
    const k = kw.value.trim().toLowerCase()
    list = list.filter(r =>
      (r.code || '').toLowerCase().includes(k) ||
      (r.name || '').includes(kw.value.trim())
    )
  }
  if (minLimit.value > 0) list = list.filter(r => (r.limit_count || 1) >= minLimit.value)
  if (minNet.value > 0) list = list.filter(r => (r.net_amt || 0) >= minNet.value)
  if (onlyInst.value) list = list.filter(r => (r.inst_buy_cnt || 0) > 0 || (r.inst_sell_cnt || 0) > 0)
  return list
})

const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return filtered.value.slice(start, start + pageSize)
})

function applyFilter() { page.value = 1 }

const hbDate = computed(() => {
  if (ranking.value.length > 0 && ranking.value[0].hb_date) return ranking.value[0].hb_date
  return null
})

const stats = computed(() => {
  const list = ranking.value
  if (!list.length) return null
  let netAmtTotal = 0, sealTotal = 0, netInflowTotal = 0, instCount = 0
  const themeCnt = {}
  for (const r of list) {
    netAmtTotal += (r.net_amt || 0)
    sealTotal += (r.seal_money || 0)
    netInflowTotal += (r.net_inflow || 0)
    if ((r.inst_buy_cnt || 0) > 0 || (r.inst_sell_cnt || 0) > 0) instCount++
    for (const t of (r.themes || '').replace(/、/g, ',').split(',')) {
      const tt = t.trim()
      if (tt) themeCnt[tt] = (themeCnt[tt] || 0) + 1
    }
  }
  const themeTop = Object.entries(themeCnt)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([theme, count]) => ({ theme, count }))
  return {
    count: list.length,
    net_amt_total: netAmtTotal,
    seal_total: sealTotal,
    net_inflow_total: netInflowTotal,
    inst_count: instCount,
    theme_top: themeTop,
  }
})

async function load() {
  loading.value = true
  try {
    const data = await api.hotBillboard(200)
    ranking.value = data || []
    page.value = 1
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
// 历史回看日期切换时自动重新加载
watch(() => ui.selectedDate, load)
</script>

<style scoped>
.hb-page { padding: 4px 2px; }
.page-head { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 14px; }
.view-title { margin: 0; font-size: 20px; }
.view-sub { margin: 4px 0 0; color: #8a8f99; font-size: 12px; }
.head-tools { display: flex; gap: 8px; align-items: center; }
.stat-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 12px; }
.stat-card { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 14px; }
.stat-label { color: #8a8f99; font-size: 12px; }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.stat-value.up { color: #f5483b; }
.theme-card { margin-bottom: 12px; }
.card-h { font-weight: 600; }
.theme-tag { margin: 0 8px 8px 0; }
.table-card { margin-bottom: 12px; }
.filter-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.filter-count { color: #8a8f99; font-size: 13px; margin-left: auto; }
.pager { margin-top: 10px; justify-content: center; }
.name-cell { display: flex; flex-direction: column; line-height: 1.35; }
.code { color: #8a8f99; font-size: 12px; }
.sname { font-weight: 600; }
.themes { color: #5a5f6a; font-size: 12px; }
.buy-sell { display: flex; gap: 4px; justify-content: flex-end; font-size: 13px; }
.bs-buy { color: #f5483b; }
.bs-div { color: #ccc; }
.bs-sell { color: #16a34a; }
.inst-tag { font-size: 12px; color: #f5483b; font-weight: 600; }
.no-inst { color: #ccc; }
.limit-badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; font-weight: 700; color: #fff; }
.lb-1 { background: #f5483b; }
.lb-2 { background: #fa541c; }
.lb-3 { background: #fa8c16; }
.lb-4 { background: #d4380d; }
.lb-5 { background: #a8071a; }

@media (max-width: 1100px) {
  .stat-row { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 768px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .page-head { flex-direction: column; align-items: flex-start; gap: 8px; }
  .head-tools { align-self: stretch; }
  .filter-bar { flex-direction: column; align-items: stretch; }
  .filter-bar .el-input,
  .filter-bar .el-select { width: 100% !important; }
  .filter-count { margin-left: 0; }
}

/* 移动端卡片 */
.mobile-cards { min-height: 200px; }
.mc-item {
  background: #fff; border: 1px solid #ebeef5; border-radius: 10px;
  padding: 12px 14px; margin-bottom: 8px;
}
.mc-head { display: flex; align-items: center; gap: 8px; }
.mc-name { font-weight: 700; font-size: 15px; color: #1f2733; }
.mc-code { color: #8a8f99; font-size: 12px; }
.mc-body { margin-top: 6px; }
.mc-row { font-size: 12px; color: #5a5f6a; margin-bottom: 3px; }
.mc-main-nums b { font-weight: 700; }
.mc-div { color: #d0d3d8; margin: 0 4px; }
.mc-detail { font-size: 11px; color: #8a8f99; }
.mc-themes { color: #8a8f99; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
