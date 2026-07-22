<template>
  <div class="limitup-page">
    <div class="page-head">
      <div>
        <h2 class="view-title">昨日涨停股票排行榜</h2>
        <p class="view-sub">
          数据来源：开盘红历史涨停池（含连板数 / 涨停原因 / 题材 / 封单 / 净流入），并关联龙虎榜与机构席位。
        </p>
      </div>
      <div class="head-tools">
        <el-select v-model="selDate" placeholder="交易日" style="width: 160px" @change="load">
          <el-option v-for="d in availableDates" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="stat-row" v-if="stats">
      <div class="stat-card">
        <div class="stat-label">涨停总数</div>
        <div class="stat-value up">{{ stats.count }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">最高连板</div>
        <div class="stat-value warn">{{ stats.max_limit }} 板</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">封板总金额</div>
        <div class="stat-value">{{ fmtYuan(stats.seal_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">涨停净流入合计</div>
        <div class="stat-value" :class="yuanClass(stats.net_inflow_total)">{{ fmtYuan(stats.net_inflow_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">登上龙虎榜</div>
        <div class="stat-value">{{ stats.with_billboard }} 家</div>
      </div>
    </div>

    <el-card class="theme-card" shadow="never" v-if="stats && stats.theme_top.length">
      <template #header><span class="card-h">题材热度（涨停股涉及）</span></template>
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
        <el-input v-model="kw" placeholder="搜索代码 / 名称" clearable style="width: 200px" />
        <el-select v-model="minLimit" placeholder="连板数≥" style="width: 130px" @change="applyFilter">
          <el-option label="全部" :value="0" />
          <el-option label="2 板及以上" :value="2" />
          <el-option label="3 板及以上" :value="3" />
          <el-option label="4 板及以上" :value="4" />
        </el-select>
        <el-checkbox v-model="onlyBillboard" @change="applyFilter">仅看登上龙虎榜</el-checkbox>
        <span class="filter-count">共 {{ filtered.length }} 只</span>
      </div>

      <el-table :data="paged" stripe border height="560" v-loading="loading" :default-sort="{ prop: 'limit_count', order: 'descending' }">
        <el-table-column type="index" label="#" width="48" />
        <el-table-column label="代码 / 名称" min-width="140">
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
        <el-table-column label="涨停原因" prop="reason" min-width="130" show-overflow-tooltip />
        <el-table-column label="题材" prop="themes" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="themes">{{ row.themes || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="封单金额" width="110" prop="seal_money" sortable align="right">
          <template #default="{ row }"><span :class="yuanClass(row.seal_money)">{{ fmtYuan(row.seal_money) }}</span></template>
        </el-table-column>
        <el-table-column label="主力净流入" width="120" prop="net_inflow" sortable align="right">
          <template #default="{ row }"><span :class="yuanClass(row.net_inflow)">{{ fmtYuan(row.net_inflow) }}</span></template>
        </el-table-column>
        <el-table-column label="流通市值" width="110" prop="market_cap" sortable align="right">
          <template #default="{ row }">{{ fmtYuan(row.market_cap) }}</template>
        </el-table-column>
        <el-table-column label="换手率" width="86" prop="turnover_rate" sortable align="right">
          <template #default="{ row }">{{ row.turnover_rate != null ? row.turnover_rate + '%' : '--' }}</template>
        </el-table-column>
        <el-table-column label="同行业涨停" width="92" prop="industry_zt" sortable align="center">
          <template #default="{ row }">
            <span v-if="row.industry_zt">{{ row.industry_zt }} 家</span><span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="龙虎榜" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.billboard" type="warning" size="small" effect="dark">有</el-tag>
            <el-tag v-else size="small" effect="plain" type="info">无</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pager"
        layout="prev, pager, next"
        :total="filtered.length"
        :page-size="pageSize"
        v-model:current-page="page"
      />
    </el-card>

    <el-drawer v-model="drawer" :title="cur.name + '（' + cur.code + '）'" size="46%" direction="rtl">
      <div v-loading="detailLoading">
        <el-divider content-position="left">涨停催化</el-divider>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="连板数">
            <span class="limit-badge" :class="limitClass(cur.limit_count)">{{ cur.limit_tag || '首板' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="涨停原因">{{ cur.reason || '--' }}</el-descriptions-item>
          <el-descriptions-item label="题材">{{ cur.themes || '--' }}</el-descriptions-item>
          <el-descriptions-item label="同行业涨停">{{ cur.industry_zt ? cur.industry_zt + ' 家' : '--' }}</el-descriptions-item>
          <el-descriptions-item label="封单金额"><span :class="yuanClass(cur.seal_money)">{{ fmtYuan(cur.seal_money) }}</span></el-descriptions-item>
          <el-descriptions-item label="主力净流入"><span :class="yuanClass(cur.net_inflow)">{{ fmtYuan(cur.net_inflow) }}</span></el-descriptions-item>
          <el-descriptions-item label="成交额">{{ fmtYuan(cur.turnover) }}</el-descriptions-item>
          <el-descriptions-item label="换手率">{{ cur.turnover_rate != null ? cur.turnover_rate + '%' : '--' }}</el-descriptions-item>
          <el-descriptions-item label="流通市值">{{ fmtYuan(cur.market_cap) }}</el-descriptions-item>
          <el-descriptions-item label="最后涨停">{{ fmtTime(cur.limit_time) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">机构 / 龙虎榜动向</el-divider>
        <template v-if="cur.billboard">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="龙虎榜净买">
              <span :class="yuanClass(cur.billboard.net_amt)">{{ fmtYuan(cur.billboard.net_amt) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="机构买入 / 卖出家数">
              {{ cur.billboard.inst_buy_cnt || 0 }} / {{ cur.billboard.inst_sell_cnt || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="上榜原因" :span="2">{{ cur.billboard.explain || cur.billboard.reason || '--' }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="cur.seat_summary" class="seat-summary">
            <el-tag type="danger" effect="plain">机构净 {{ fmtYuan(cur.seat_summary.inst_net) }}</el-tag>
            <el-tag type="warning" effect="plain">游资净 {{ fmtYuan(cur.seat_summary.youzi_net) }}</el-tag>
            <el-tag effect="plain">席位 {{ cur.seat_summary.seat_cnt }} 笔</el-tag>
          </div>
          <el-table v-if="cur.seats && cur.seats.length" :data="cur.seats" size="small" border class="seat-tbl">
            <el-table-column label="席位" prop="seat_name" min-width="150" show-overflow-tooltip />
            <el-table-column label="类别" width="80">
              <template #default="{ row }">
                <el-tag :type="row.type === '机构' ? 'danger' : 'warning'" size="small" effect="plain">{{ row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="方向" width="64">
              <template #default="{ row }">
                <el-tag :type="row.side === 'BUY' ? 'danger' : 'success'" size="small">{{ row.side === 'BUY' ? '买' : '卖' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="净额" width="110" align="right">
              <template #default="{ row }"><span :class="yuanClass(row.net_amt)">{{ fmtYuan(row.net_amt) }}</span></template>
            </el-table-column>
            <el-table-column label="买入额" width="110" align="right">
              <template #default="{ row }">{{ fmtYuan(row.buy_amt) }}</template>
            </el-table-column>
            <el-table-column label="卖出额" width="110" align="right">
              <template #default="{ row }">{{ fmtYuan(row.sell_amt) }}</template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="当日未登上龙虎榜（无机构/游资席位数据）" :image-size="80" />

        <el-divider content-position="left">近期公告 / 新闻</el-divider>
        <div v-if="newsLoading" class="news-loading">加载中…</div>
        <template v-else>
          <el-timeline v-if="news.length" class="news-tl">
            <el-timeline-item v-for="(n, i) in news" :key="i" :timestamp="n.time" placement="top">
              <div class="news-item">
                <span class="news-title">{{ n.title }}</span>
                <div class="news-types">
                  <el-tag v-for="t in n.types" :key="t" size="small" effect="plain" type="info">{{ t }}</el-tag>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="近 150 条公告中未匹配到该公司（免费源无按股新闻接口）" :image-size="80" />
          <p class="news-note">注：公告按股票名称尽力匹配，仅为复盘参考，非投资建议。</p>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { api } from '../api'
import { fmtYuan, yuanClass } from '../utils/format'

const loading = ref(false)
const selDate = ref('')
const availableDates = ref([])
const stats = ref(null)
const ranking = ref([])

const kw = ref('')
const minLimit = ref(0)
const onlyBillboard = ref(false)
const page = ref(1)
const pageSize = 30

const drawer = ref(false)
const cur = ref({})
const detailLoading = ref(false)
const news = ref([])
const newsLoading = ref(false)

function limitClass(n) {
  n = n || 1
  if (n >= 4) return 'lb-4'
  if (n === 3) return 'lb-3'
  if (n === 2) return 'lb-2'
  return 'lb-1'
}
function fmtTime(ts) {
  if (!ts) return '--'
  try {
    const d = new Date(ts * 1000)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch (e) { return '--' }
}

const filtered = computed(() => {
  let list = ranking.value
  if (kw.value) {
    const k = kw.value.trim().toLowerCase()
    list = list.filter(r => (r.code || '').toLowerCase().includes(k) || (r.name || '').includes(kw.value.trim()))
  }
  if (minLimit.value > 0) list = list.filter(r => (r.limit_count || 1) >= minLimit.value)
  if (onlyBillboard.value) list = list.filter(r => r.billboard)
  return list
})
const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return filtered.value.slice(start, start + pageSize)
})

function applyFilter() { page.value = 1 }

async function load() {
  loading.value = true
  try {
    const res = await api.limitupDaily({ date: selDate.value })
    selDate.value = res.date
    availableDates.value = res.available_dates || []
    stats.value = res.stats
    ranking.value = res.ranking || []
    page.value = 1
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  cur.value = row
  drawer.value = true
  news.value = []
  newsLoading.value = true
  try {
    const res = await api.limitupNews(row.code, row.name)
    news.value = res.news || []
  } catch (e) {
    news.value = []
  } finally {
    newsLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.limitup-page { padding: 4px 2px; }
.page-head { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 14px; }
.view-title { margin: 0; font-size: 20px; }
.view-sub { margin: 4px 0 0; color: #8a8f99; font-size: 12px; }
.head-tools { display: flex; gap: 8px; align-items: center; }
.stat-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 12px; }
.stat-card { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 14px; }
.stat-label { color: #8a8f99; font-size: 12px; }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.stat-value.up { color: #f5483b; }
.stat-value.warn { color: #fa8c16; }
.theme-card { margin-bottom: 12px; }
.card-h { font-weight: 600; }
.theme-tag { margin: 0 8px 8px 0; }
.table-card { margin-bottom: 12px; }
.filter-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.filter-count { color: #8a8f99; font-size: 13px; }
.pager { margin-top: 10px; justify-content: center; }
.name-cell { display: flex; flex-direction: column; line-height: 1.35; }
.code { color: #8a8f99; font-size: 12px; }
.sname { font-weight: 600; }
.themes { color: #5a5f6a; font-size: 12px; }
.limit-badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; font-weight: 700; color: #fff; }
.lb-1 { background: #f5483b; }
.lb-2 { background: #fa541c; }
.lb-3 { background: #fa8c16; }
.lb-4 { background: #d4380d; }
.seat-summary { display: flex; gap: 8px; margin: 10px 0; }
.seat-tbl { margin-top: 6px; }
.news-tl { padding-left: 4px; }
.news-item { font-size: 13px; }
.news-title { font-weight: 600; }
.news-types { margin-top: 4px; display: flex; gap: 6px; flex-wrap: wrap; }
.news-note { color: #b0b4bc; font-size: 11px; margin-top: 8px; }
.news-loading { color: #8a8f99; padding: 12px 0; }
.up { color: #f5483b; }
</style>
