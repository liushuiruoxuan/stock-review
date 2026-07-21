import { fmtYuan } from './format'

const UP = '#f5222d'
const DOWN = '#16a34a'

// 资金净流向柱状图：正值红、负值绿（A股习惯）
export function netBarOption(categories, values, opts = {}) {
  const horizontal = opts.horizontal !== false
  const data = values.map((v) => ({
    value: v,
    itemStyle: { color: (v ?? 0) >= 0 ? UP : DOWN }
  }))
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (p) => `${p[0].name}<br/>${fmtYuan(p[0].value)}`
    },
    grid: { left: 6, right: 18, top: 16, bottom: 6, containLabel: true },
    xAxis: horizontal
      ? { type: 'value', axisLabel: { formatter: (v) => fmtYuan(v) }, splitLine: { lineStyle: { color: '#f0f2f5' } } }
      : { type: 'category', data: categories, axisLabel: { interval: 0, rotate: opts.rotate || 0 } },
    yAxis: horizontal
      ? { type: 'category', data: categories, axisLabel: { fontSize: 12 } }
      : { type: 'value', axisLabel: { formatter: (v) => fmtYuan(v) }, splitLine: { lineStyle: { color: '#f0f2f5' } } },
    series: [{ type: 'bar', data, barWidth: '58%' }]
  }
}

export function pieFlowOption(items) {
  return {
    tooltip: { trigger: 'item', formatter: (p) => `${p.name}<br/>${fmtYuan(p.value)} (${p.percent}%)` },
    legend: { type: 'scroll', bottom: 0, textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '70%'],
        center: ['50%', '44%'],
        data: items.map((it) => ({
          name: it.name,
          value: it.value,
          itemStyle: { color: it.value >= 0 ? UP : DOWN }
        })),
        label: { show: false }
      }
    ]
  }
}
