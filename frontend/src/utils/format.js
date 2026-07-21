// 数值格式化工具（A股习惯：涨红跌绿）

export function fmtYuan(v) {
  if (v === null || v === undefined || isNaN(v)) return '--'
  const a = Math.abs(v)
  if (a >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (a >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return v.toFixed(0)
}

export function fmtPct(v) {
  if (v === null || v === undefined || isNaN(v)) return '--'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

export function fmtNum(v, d = 2) {
  if (v === null || v === undefined || isNaN(v)) return '--'
  return Number(v).toFixed(d)
}

// 红涨绿跌
export function trendClass(v) {
  if (v === null || v === undefined || isNaN(v)) return ''
  return v >= 0 ? 'up' : 'down'
}

export function yuanClass(v) {
  if (v === null || v === undefined || isNaN(v)) return ''
  return v >= 0 ? 'up' : 'down'
}
