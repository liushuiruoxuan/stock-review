<template>
  <div class="bs-viewport" ref="viewport">
    <div class="bs-screen" :style="screenStyle">
      <!-- 顶栏 -->
      <div class="bs-header">
        <div class="bs-title">
          <span class="bs-logo">盘</span>
          每日复盘 · 资金博弈大屏
        </div>
        <div class="bs-sub">{{ data.trade_date || '--' }} 交易日</div>
        <div class="bs-clock">
          <span class="clock">{{ clock }}</span>
          <span class="dot" :class="data.sources ? 'live' : ''">● LIVE</span>
          <span class="countdown">{{ countdown }}s 后刷新</span>
          <button class="bs-btn" @click="load(true)">立即刷新</button>
          <button class="bs-btn" @click="goBack">返回工作台</button>
        </div>
      </div>

      <!-- 主体三栏 -->
      <div class="bs-body">
        <!-- 左列 -->
        <div class="bs-col">
          <div class="bs-card">
            <div class="bs-card-h">指数</div>
            <div class="idx-list">
              <div v-for="ix in data.indexes" :key="ix.code" class="idx-item">
                <div class="idx-name">{{ ix.name }}</div>
                <div class="idx-close">{{ fmtNum(ix.close) }}</div>
                <div class="idx-pct" :class="trendClass(ix.pct_chg)">{{ fmtPct(ix.pct_chg) }}</div>
                <div class="idx-spark"><BaseChart :option="sparkOption(ix)" height="46px" /></div>
              </div>
              <div v-if="!data.indexes?.length" class="idx-empty">行情库未同步<br />（管理页触发「日历+指数」同步）</div>
            </div>
          </div>
          <div class="bs-card grow">
            <div class="bs-card-h">
              <span class="bs-card-title">席位攻击榜</span>
              <div class="seat-tabs">
                <span class="seat-tab" :class="{ active: leftTab === 'youzi' }" @click="leftTab = 'youzi'">游资</span>
                <span class="seat-tab" :class="{ active: leftTab === 'inst' }" @click="leftTab = 'inst'">机构</span>
              </div>
            </div>
            <div class="seat-list">
              <div v-for="(s, i) in rotateSeats" :key="s.seat_name" class="seat-row">
                <span class="seat-rank" :class="i < 3 ? 'top' + (i + 1) : ''">{{ i + 1 }}</span>
                <span class="seat-name" :title="s.seat_name">{{ s.seat_name }}</span>
                <span class="seat-net" :class="trendClass(s.net_wan)">{{ fmtWan(s.net_wan) }}</span>
              </div>
              <div v-if="!rotateSeats.length" class="idx-empty">暂无席位数据</div>
            </div>
          </div>
        </div>

        <!-- 中列 -->
        <div class="bs-col mid">
          <div class="bs-card grow">
            <div class="bs-card-h">涨停梯队 · 最高 {{ data.limitup?.stats?.max_limit || 0 }} 连板</div>
            <BaseChart v-if="ladderOption" :option="ladderOption" height="240px" />
            <div class="lu-top">
              <div v-for="r in data.limitup?.top || []" :key="r.code" class="lu-item">
                <span class="lu-tag">{{ r.limit_tag }}</span>
                <span class="lu-name">{{ r.name }}</span>
                <span class="lu-reason" :title="r.reason">{{ r.reason }}</span>
              </div>
              <div v-if="!(data.limitup?.top || []).length" class="idx-empty">暂无涨停数据</div>
            </div>
          </div>
          <div class="bs-card grow">
            <div class="bs-card-h">{{ rotateRight ? '龙虎榜净买 Top10' : '板块资金流入 Top8' }}</div>
            <BaseChart :option="barOption" height="230px" />
          </div>
        </div>

        <!-- 右列 -->
        <div class="bs-col">
          <div class="bs-card grow">
            <div class="bs-card-h">热点重合榜（龙虎榜 ∩ 涨停）</div>
            <div class="hb-list">
              <div v-for="(r, i) in data.hot_billboard || []" :key="r.code" class="hb-row">
                <span class="seat-rank" :class="i < 3 ? 'top' + (i + 1) : ''">{{ i + 1 }}</span>
                <span class="hb-name">{{ r.name }}</span>
                <span class="hb-net" :class="trendClass(r.net_amt)">{{ fmtYuan(r.net_amt) }}</span>
                <span class="hb-pct" :class="trendClass(r.change_pct)">{{ fmtPct(r.change_pct) }}</span>
              </div>
              <div v-if="!(data.hot_billboard || []).length" class="idx-empty">暂无数据</div>
            </div>
          </div>
          <div class="bs-card">
            <div class="bs-card-h">市场情绪</div>
            <div class="mood-grid">
              <div class="mood-item">
                <div class="mood-v">{{ data.summary?.billboard_count ?? '--' }}</div>
                <div class="mood-l">龙虎榜上榜</div>
              </div>
              <div class="mood-item">
                <div class="mood-v" :class="trendClass(data.summary?.billboard_net_total)">{{ fmtYuan(data.summary?.billboard_net_total) }}</div>
                <div class="mood-l">龙虎榜净买</div>
              </div>
              <div class="mood-item">
                <div class="mood-v up">{{ data.summary?.sectors_hot_count ?? '--' }}</div>
                <div class="mood-l">流入板块</div>
              </div>
              <div class="mood-item">
                <div class="mood-v down">{{ data.summary?.sectors_outflow_count ?? '--' }}</div>
                <div class="mood-l">流出板块</div>
              </div>
              <div class="mood-item">
                <div class="mood-v up">{{ data.limitup?.stats?.count ?? '--' }}</div>
                <div class="mood-l">涨停家数</div>
              </div>
              <div class="mood-item">
                <div class="mood-v">{{ data.summary?.inst_count ?? '--' }}</div>
                <div class="mood-l">机构参与</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部跑马灯 -->
      <div class="bs-ticker">
        <div class="ticker-track" :style="tickerStyle">
          <span v-for="(t, i) in tickerLoop" :key="i" class="ticker-item" :class="t.tone">
            {{ t.text }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import BaseChart from '../components/BaseChart.vue'
import { api } from '../api'
import { fmtYuan, fmtPct, fmtNum, trendClass } from '../utils/format'

const router = useRouter()
const REFRESH_SEC = 30
const ROTATE_SEC = 15

const data = ref({})
const clock = ref('')
const countdown = ref(REFRESH_SEC)
const rotateRight = ref(true)  // 中列下：龙虎榜/板块轮播
const leftTab = ref('youzi')   // 左列下：席位攻击榜标签页（游资/机构，固定不轮播）
const viewport = ref(null)
const screenStyle = ref({})

const fmtWan = (v) => (v >= 0 ? '+' : '') + fmtNum(v, 0) + ' 万'

// ===== 自适应缩放（1920x1080 基准）=====
function fit() {
  const w = window.innerWidth, h = window.innerHeight
  const scale = Math.min(w / 1920, h / 1080)
  screenStyle.value = {
    transform: `scale(${scale})`,
    transformOrigin: 'top left',
    width: '1920px',
    height: '1080px',
    position: 'absolute',
    left: (w - 1920 * scale) / 2 + 'px',
    top: (h - 1080 * scale) / 2 + 'px'
  }
}

// ===== 数据加载与定时器 =====
let timer = null, clockTimer = null, rotTimer = null
async function load(manual) {
  try {
    data.value = await api.bigscreen()
    if (manual) countdown.value = REFRESH_SEC
  } catch (e) {
    console.error(e)
  }
}
function goBack() { router.push('/') }

const tickerLoop = computed(() => {
  const t = data.value.ticker || []
  return t.concat(t)  // 双份实现无缝滚动
})
const tickerStyle = computed(() => ({
  animation: `ticker-scroll ${Math.max(tickerLoop.value.length * 3, 30)}s linear infinite`
}))

// ===== 图表 =====
const UP = '#ff4d4f', DOWN = '#22c55e', AXIS = '#8aa0c8', SPLIT = '#1c2b4a'

function sparkOption(ix) {
  const pts = (ix.spark || []).map(p => p.close)
  const up = (ix.pct_chg || 0) >= 0
  return {
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    xAxis: { type: 'category', show: false, data: pts.map((_, i) => i) },
    yAxis: { type: 'value', show: false },
    series: [{
      type: 'line', data: pts, symbol: 'none',
      lineStyle: { color: up ? UP : DOWN, width: 1.5 }
    }]
  }
}

const ladderOption = computed(() => {
  const dist = data.value.limitup?.stats?.limit_dist || {}
  const keys = Object.keys(dist)
  if (!keys.length) return null
  // 按连板数降序
  const order = { '首板': 1 }
  keys.sort((a, b) => {
    const na = parseInt(a) || order[a] || 0, nb = parseInt(b) || order[b] || 0
    return na - nb
  })
  return {
    grid: { left: 8, right: 14, top: 10, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: keys, axisLabel: { color: AXIS } },
    yAxis: { type: 'value', axisLabel: { color: AXIS }, splitLine: { lineStyle: { color: SPLIT } } },
    series: [{
      type: 'bar', data: keys.map(k => dist[k]), barWidth: '55%',
      itemStyle: { color: '#f0704a', borderRadius: [3, 3, 0, 0] }
    }]
  }
})

const barOption = computed(() => {
  if (rotateRight.value) {
    const top = (data.value.hot_billboard || []).slice(0, 10).reverse()
    return darkBar(top.map(r => r.name), top.map(r => r.net_amt))
  }
  const top = (data.value.sectors_hot || []).slice(0, 8).reverse()
  return darkBar(top.map(r => r.name), top.map(r => r.main_net))
})

function darkBar(cats, vals) {
  return {
    grid: { left: 8, right: 18, top: 8, bottom: 4, containLabel: true },
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: '#13233f', borderColor: '#2a4166', textStyle: { color: '#dde6f5' },
      formatter: (p) => `${p[0].name}<br/>${fmtYuan(p[0].value)}`
    },
    xAxis: { type: 'value', axisLabel: { color: AXIS, formatter: (v) => fmtYuan(v) }, splitLine: { lineStyle: { color: SPLIT } } },
    yAxis: { type: 'category', data: cats, axisLabel: { color: AXIS, fontSize: 12 } },
    series: [{
      type: 'bar', barWidth: '60%',
      data: vals.map(v => ({ value: v, itemStyle: { color: (v ?? 0) >= 0 ? UP : DOWN } }))
    }]
  }
}

const rotateSeats = computed(() => {
  if (!data.value.seats) return []
  return leftTab.value === 'youzi' ? data.value.seats.youzi_top : data.value.seats.inst_top
})

onMounted(() => {
  fit()
  window.addEventListener('resize', fit)
  load()
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) { countdown.value = REFRESH_SEC; load() }
  }, 1000)
  clockTimer = setInterval(() => {
    clock.value = new Date().toLocaleString('zh-CN', { hour12: false })
  }, 1000)
  rotTimer = setInterval(() => {
    rotateRight.value = !rotateRight.value
  }, ROTATE_SEC * 1000)
})

onBeforeUnmount(() => {
  clearInterval(timer)
  clearInterval(clockTimer)
  clearInterval(rotTimer)
  window.removeEventListener('resize', fit)
})
</script>

<style scoped>
.bs-viewport {
  position: fixed; inset: 0; overflow: hidden;
  background: radial-gradient(ellipse at 50% -20%, #14264a 0%, #0a1226 55%, #060b18 100%);
}
.bs-screen { color: #dde6f5; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }

/* 顶栏 */
.bs-header {
  height: 72px; display: flex; align-items: center; gap: 18px;
  padding: 0 28px; border-bottom: 1px solid #1c2b4a;
  background: linear-gradient(180deg, rgba(28, 43, 74, .55), transparent);
}
.bs-title { font-size: 30px; font-weight: 800; letter-spacing: 2px; display: flex; align-items: center; gap: 12px; }
.bs-logo {
  width: 40px; height: 40px; border-radius: 9px; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f5222d, #ff7a45); color: #fff; font-size: 22px;
  box-shadow: 0 0 18px rgba(245, 34, 45, .45);
}
.bs-sub { font-size: 15px; color: #8aa0c8; }
.bs-clock { margin-left: auto; display: flex; align-items: center; gap: 14px; font-size: 15px; color: #8aa0c8; }
.clock { font-size: 20px; color: #dde6f5; font-variant-numeric: tabular-nums; }
.dot { color: #22c55e; font-size: 12px; animation: blink 2s infinite; }
.dot:not(.live) { color: #556; }
@keyframes blink { 50% { opacity: .35; } }
.countdown { font-size: 13px; }
.bs-btn {
  background: #1c2b4a; color: #dde6f5; border: 1px solid #2a4166; border-radius: 6px;
  padding: 6px 14px; font-size: 13px; cursor: pointer;
}
.bs-btn:hover { background: #2a4166; }

/* 主体 */
.bs-body { display: flex; gap: 14px; padding: 14px 28px 0; height: 920px; }
.bs-col { flex: 1; display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.bs-col.mid { flex: 1.25; }
.bs-card {
  background: rgba(16, 28, 52, .82); border: 1px solid #1c2b4a; border-radius: 10px;
  padding: 12px 14px; overflow: hidden;
  box-shadow: inset 0 0 30px rgba(30, 60, 120, .12);
}
.bs-card.grow { flex: 1; min-height: 0; }
.bs-card-h {
  font-size: 16px; font-weight: 700; margin-bottom: 10px; color: #cfe0ff;
  display: flex; align-items: center; gap: 8px;
}
.bs-card-h::before { content: ''; width: 4px; height: 16px; border-radius: 2px; background: #f5222d; }

/* 席位榜标签页 */
.seat-tabs { margin-left: auto; display: flex; gap: 4px; }
.seat-tab {
  font-size: 12px; font-weight: 600; color: #8aa0c8; cursor: pointer;
  padding: 3px 12px; border-radius: 5px; border: 1px solid transparent;
  transition: all .2s; line-height: 1.4;
}
.seat-tab:hover { color: #dde6f5; background: rgba(42, 65, 102, .5); }
.seat-tab.active { color: #fff; background: #f5222d; border-color: #f5222d; }

/* 指数 */
.idx-list { display: flex; gap: 10px; }
.idx-item {
  flex: 1; background: rgba(12, 22, 44, .6); border-radius: 8px; padding: 10px 12px;
  display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; align-items: center;
}
.idx-name { font-size: 13px; color: #8aa0c8; }
.idx-close { font-size: 20px; font-weight: 700; text-align: right; }
.idx-pct { font-size: 15px; font-weight: 600; }
.idx-spark { grid-column: 1 / 3; }
.idx-empty { grid-column: 1 / 3; text-align: center; color: #5b6f96; font-size: 12px; padding: 16px 0; line-height: 1.8; }

/* 席位榜 */
.seat-list { overflow: hidden; display: flex; flex-direction: column; }
.seat-row { display: flex; align-items: center; gap: 10px; padding: 7px 4px; border-bottom: 1px dashed #1c2b4a; }
.seat-rank {
  width: 22px; height: 22px; border-radius: 5px; background: #1c2b4a; color: #8aa0c8;
  font-size: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.seat-rank.top1 { background: #f5222d; color: #fff; }
.seat-rank.top2 { background: #ff7a45; color: #fff; }
.seat-rank.top3 { background: #d48806; color: #fff; }
.seat-name { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.seat-net { font-size: 15px; font-weight: 700; }

/* 涨停 */
.lu-top { margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px 14px; }
.lu-item { display: flex; align-items: center; gap: 8px; font-size: 13px; overflow: hidden; }
.lu-tag {
  flex-shrink: 0; background: rgba(245, 34, 45, .18); color: #ff8f8f; border: 1px solid rgba(245, 34, 45, .4);
  border-radius: 4px; padding: 1px 6px; font-size: 11px;
}
.lu-name { font-weight: 700; flex-shrink: 0; }
.lu-reason { color: #5b6f96; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 热点重合 */
.hb-list { overflow: hidden; display: flex; flex-direction: column; }
.hb-row { display: flex; align-items: center; gap: 10px; padding: 7px 4px; border-bottom: 1px dashed #1c2b4a; }
.hb-name { width: 90px; font-size: 14px; font-weight: 700; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hb-net { flex: 1; text-align: right; font-size: 14px; font-weight: 700; }
.hb-pct { width: 76px; text-align: right; font-size: 14px; }

/* 情绪 */
.mood-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.mood-item { background: rgba(12, 22, 44, .6); border-radius: 8px; padding: 10px; text-align: center; }
.mood-v { font-size: 22px; font-weight: 800; }
.mood-l { font-size: 12px; color: #8aa0c8; margin-top: 4px; }

/* 跑马灯 */
.bs-ticker {
  height: 52px; margin: 14px 28px 0; overflow: hidden; border-radius: 8px;
  background: rgba(16, 28, 52, .82); border: 1px solid #1c2b4a;
  display: flex; align-items: center;
}
.ticker-track {
  display: flex; gap: 42px; white-space: nowrap; padding-left: 100%;
  font-size: 15px; animation: ticker-scroll linear infinite;
}
@keyframes ticker-scroll { to { transform: translateX(-100%); } }
.ticker-item.up { color: #ff8f8f; }
.ticker-item.neutral { color: #8aa0c8; }

/* 涨跌色 */
.up { color: #ff4d4f !important; }
.down { color: #22c55e !important; }
</style>
