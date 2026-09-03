import { reactive } from 'vue'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(url + ' -> ' + r.status)
  return r.json()
}

function qs(params) {
  const p = new URLSearchParams()
  for (const k in params) {
    const v = params[k]
    if (v !== undefined && v !== null && v !== '') p.set(k, v)
  }
  return p.toString()
}

// 历史回看日期线程：selectedDate 为空(undefined/null/空串)时取最新交易日
function dq() {
  const d = ui.selectedDate
  return d ? `&date=${encodeURIComponent(d)}` : ''
}

export const api = {
  status: () => getJSON('/api/status'),
  summary: () => getJSON('/api/summary' + (ui.selectedDate ? '?date=' + ui.selectedDate : '')),
  billboard: () => getJSON('/api/billboard' + (ui.selectedDate ? '?date=' + ui.selectedDate : '')),
  stocksFlow: (limit = 50) => getJSON(`/api/stocks/flow?limit=${limit}${dq()}`),
  rapidRise: (limit = 50) => getJSON(`/api/rapid-rise?limit=${limit}${dq()}`),
  capitalAttention: (limit = 50) => getJSON(`/api/capital-attention?limit=${limit}${dq()}`),
  sectorsHot: (limit = 30) => getJSON(`/api/sectors/hot?limit=${limit}${dq()}`),
  sectorsOutflow: (limit = 30) => getJSON(`/api/sectors/outflow?limit=${limit}${dq()}`),
  institution: () => getJSON('/api/institution' + (ui.selectedDate ? '?date=' + ui.selectedDate : '')),
  youzi: (limit = 50) => getJSON(`/api/youzi?limit=${limit}${dq()}`),
  monitorDaily: (params = {}) => getJSON('/api/monitor/daily?' + qs(params)),
  monitorSignals: (params = {}) => getJSON('/api/monitor/signals?' + qs(params)),
  monitorExportUrl: (params = {}) => '/api/monitor/export?' + qs(params),
  seatsDaily: (params = {}) => getJSON('/api/seats/daily?' + qs(params)),
  seatsProfile: (params = {}) => getJSON('/api/seats/profile?' + qs(params)),
  seatsSignals: (params = {}) => getJSON('/api/seats/signals?' + qs(params)),
  seatsExportUrl: (params = {}) => '/api/seats/export?' + qs(params),
  limitupDaily: (params = {}) => getJSON('/api/limitup/daily?' + qs(params)),
  limitupNews: (code, name) => getJSON('/api/limitup/news?' + qs({ code, name })),
  hotBillboard: (limit = 200) => getJSON(`/api/hot-billboard?limit=${limit}${dq()}`),
  historyDates: () => getJSON('/api/history/dates'),
  refresh: () => fetch('/api/refresh', { method: 'POST' }).then((r) => r.json()),

  // ===== v2：大屏 / 博弈 / 行情 / 量化 =====
  bigscreen: () => getJSON('/api/bigscreen/overview' + (ui.selectedDate ? '?date=' + ui.selectedDate : '')),
  gameOverview: () => getJSON('/api/game/overview' + (ui.selectedDate ? '?date=' + ui.selectedDate : '')),
  gameStock: (code) => getJSON('/api/game/stock/' + code + (ui.selectedDate ? '?date=' + ui.selectedDate : '')),
  marketOverview: () => getJSON('/api/market/overview'),
  marketSync: (scope) => fetch('/api/market/sync?scope=' + scope, { method: 'POST' }).then((r) => r.json()),
  marketSyncStatus: () => getJSON('/api/market/sync/status'),
  quantStrategies: () => getJSON('/api/quant/strategies'),
  quantBacktest: (body) => fetch('/api/quant/backtest', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then((r) => r.json()),
  quantRun: (id) => getJSON('/api/quant/runs/' + id),
  quantRuns: () => getJSON('/api/quant/runs'),
  quantScreener: (conds) => fetch('/api/quant/screener', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(conds)
  }).then((r) => r.json()),

  // ===== 妖股洞察 =====
  yaoList: (params = {}) => getJSON('/api/yao/list?' + qs(params)),
  yaoProfile: (code, days = 60) => getJSON(`/api/yao/profile/${code}?days=${days}`)
}

// 全局 UI 状态：数据源(live/demo)、交易日、历史回看日期等
export const ui = reactive({
  sources: {},
  tradeDate: '',        // 最新已构建交易日
  serverTime: '',
  loaded: false,
  selectedDate: '',      // 用户选择的历史回看日期；'' / null = 最新
  availableDates: []    // 可回看的历史交易日列表（来自 /api/history/dates）
})

export async function loadDates() {
  try {
    const r = await api.historyDates()
    ui.availableDates = (r && r.dates) || []
  } catch (e) {
    ui.availableDates = []
  }
  return ui.availableDates
}

const SECTION_SOURCE = {
  billboard: 'billboard',
  institution: 'billboard',
  youzi: 'billboard',
  stocks_flow: 'stocks',
  rapid_rise: 'stocks',
  capital_attention: 'stocks',
  sectors_hot: 'sectors',
  sectors_outflow: 'sectors'
}

export function isDemo(section) {
  const key = SECTION_SOURCE[section]
  return ui.sources[key] === 'demo'
}

export async function loadStatus() {
  try {
    const s = await api.status()
    ui.sources = s.sources || {}
    ui.tradeDate = s.trade_date
    ui.serverTime = s.server_time
    ui.loaded = true
    return s
  } catch (e) {
    return null
  }
}
