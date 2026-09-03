<template>
  <div ref="el" :style="{ width: '100%', height: height }"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '320px' }
})

const el = ref(null)
let chart = null
let lastSig = ''

/**
 * option 指纹（忽略函数字段，如 tooltip.formatter）。
 * 大屏每 30s 轮询会整体替换 data，option 对象引用必变但内容常常一模一样，
 * 用它跳过「引用变、内容没变」的重绘。
 */
function sig(o) {
  try {
    return JSON.stringify(o)
  } catch {
    return ''
  }
}

function render() {
  if (!el.value) return
  // 复用实例：不再 dispose + init，否则每次数据刷新画布都会清空重建（表现为闪烁）
  if (!chart || chart.isDisposed()) {
    chart = echarts.init(el.value)
    lastSig = ''
  }
  const s = sig(props.option)
  if (s === lastSig) return
  lastSig = s
  chart.setOption(props.option, true)
}

function resize() {
  chart && chart.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})

watch(() => props.option, () => render(), { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
})
</script>
