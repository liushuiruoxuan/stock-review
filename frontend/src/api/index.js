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

export const api = {
  status: () => getJSON('/api/status'),
  summary: () => getJSON('/api/summary'),
  billboard: () => getJSON('/api/billboard'),
  stocksFlow: (limit = 50) => getJSON(`/api/stocks/flow?limit=${limit}`),
  rapidRise: (limit = 50) => getJSON(`/api/rapid-rise?limit=${limit}`),
  capitalAttention: (limit = 50) => getJSON(`/api/capital-attention?limit=${limit}`),
  sectorsHot: (limit = 30) => getJSON(`/api/sectors/hot?limit=${limit}`),
  sectorsOutflow: (limit = 30) => getJSON(`/api/sectors/outflow?limit=${limit}`),
  institution: () => getJSON('/api/institution'),
  youzi: (limit = 50) => getJSON(`/api/youzi?limit=${limit}`),
  monitorDaily: (params = {}) => getJSON('/api/monitor/daily?' + qs(params)),
  monitorSignals: (params = {}) => getJSON('/api/monitor/signals?' + qs(params)),
  monitorExportUrl: (params = {}) => '/api/monitor/export?' + qs(params),
  seatsDaily: (params = {}) => getJSON('/api/seats/daily?' + qs(params)),
  seatsProfile: (params = {}) => getJSON('/api/seats/profile?' + qs(params)),
  seatsSignals: (params = {}) => getJSON('/api/seats/signals?' + qs(params)),
  seatsExportUrl: (params = {}) => '/api/seats/export?' + qs(params),
  limitupDaily: (params = {}) => getJSON('/api/limitup/daily?' + qs(params)),
  limitupNews: (code, name) => getJSON('/api/limitup/news?' + qs({ code, name })),
  refresh: () => fetch('/api/refresh', { method: 'POST' }).then((r) => r.json())
}

// 全局 UI 状态：数据源(live/demo)、交易日等
export const ui = reactive({
  sources: {},
  tradeDate: '',
  serverTime: '',
  loaded: false
})

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
