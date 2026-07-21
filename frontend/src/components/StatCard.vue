<template>
  <div class="stat-card" :style="cardStyle">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-value" :class="valueClass">{{ value }}</div>
    <div v-if="sub" class="stat-sub" :class="subClass">{{ sub }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { trendClass } from '../utils/format'

const props = defineProps({
  label: String,
  value: [String, Number],
  sub: String,
  tone: { type: String, default: '' } // '', 'up', 'down'
})

const valueClass = computed(() => {
  if (props.tone === 'up') return 'up'
  if (props.tone === 'down') return 'down'
  return ''
})
const subClass = computed(() => {
  if (props.sub == null) return ''
  // 子类由调用方通过 :class 控制，这里仅占位
  return ''
})
const cardStyle = computed(() => ({}))
void trendClass
void valueClass
</script>

<style scoped>
.stat-card {
  background: #fff;
  border: 1px solid #eef0f4;
  border-radius: 10px;
  padding: 16px 18px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.stat-label {
  font-size: 13px;
  color: #8a93a6;
  margin-bottom: 8px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1f2733;
  line-height: 1.2;
}
.stat-sub {
  font-size: 12px;
  color: #a0a8b8;
  margin-top: 6px;
}
</style>
