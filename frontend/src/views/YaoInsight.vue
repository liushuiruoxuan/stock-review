<template>
  <div v-loading="loading">
    <!-- ====== 妖股榜 ====== -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-h">
          妖股洞察
          <span class="sub">
            近 60 个交易日 · 截止 {{ res.bar_date || '--' }}（窗口 {{ res.win_start || '--' }} 起）·
            妖气指数 = 涨幅40 + 连板25 + 换手15 + 量能10 + 游资10
          </span>
          <el-select v-model="cutoff" size="small" style="width: 132px; margin-left: auto" @change="load">
            <el-option label="最新交易日" value="" />
            <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button size="small" type="primary" style="margin-left: 8px" @click="load">
            重新扫描
          </el-button>
        </div>
      </template>

      <el-table
        :data="res.rows || []"
        stripe
        size="small"
        row-key="code"
        height="480px"
        empty-text="暂无妖股候选（等待行情同步或提高窗口）"
        class="yao-table"
        @row-click="openProfile"
      >
        <el-table-column type="index" label="#" width="50" align="center" fixed />
        <el-table-column prop="name" label="名称" width="96" fixed>
          <template #default="s">
            <span class="stk-name">{{ s.row.name || s.row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="代码" width="84" />
        <el-table-column prop="score" label="妖气指数" width="96" align="center" sortable>
          <template #default="s">
            <span class="score">{{ s.row.score }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="stage" label="阶段" width="88" align="center">
          <template #default="s">
            <el-tag :type="stageTag(s.row.stage)" size="small" effect="plain">
              {{ s.row.stage }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="gain" label="区间涨幅" width="92" align="right" sortable>
          <template #default="s">
            <span :class="s.row.gain >= 0 ? 'up' : 'down'">{{ fmtPct(s.row.gain) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="max_streak" label="连板高度" width="86" align="center" sortable>
          <template #default="s">
            <span :class="s.row.max_streak >= 3 ? 'up' : ''">{{ s.row.max_streak }}板</span>
          </template>
        </el-table-column>
        <el-table-column prop="lim_days" label="涨停次数" width="86" align="center" sortable />
        <el-table-column prop="avg_turn10" label="10日均换手" width="100" align="right" sortable>
          <template #default="s">{{ s.row.avg_turn10 }}%</template>
        </el-table-column>
        <el-table-column prop="vol_ratio" label="量能倍数" width="86" align="right" sortable>
          <template #default="s">{{ s.row.vol_ratio }}x</template>
        </el-table-column>
        <el-table-column prop="bias" label="MA20乖离" width="92" align="right">
          <template #default="s">
            <span :class="(s.row.bias || 0) > 40 ? 'up' : ''">{{ s.row.bias }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="lb_days" label="上榜天数" width="86" align="center" />
        <el-table-column prop="youzi_cnt" label="游资家数" width="86" align="center" />
        <el-table-column prop="risks" label="风险信号" min-width="140">
          <template #default="s">
            <el-tooltip
              v-if="(s.row.risks || []).length"
              :content="(s.row.risks || []).join('；')"
              placement="top"
            >
              <span class="risk-chip">⚠ {{ s.row.risks.length }}</span>
            </el-tooltip>
            <span v-else class="muted">--</span>
          </template>
        </el-table-column>
        <el-table-column prop="close" label="收盘" width="80" align="right">
          <template #default="s">{{ fmtNum(s.row.close) }}</template>
        </el-table-column>
        <el-table-column prop="pct_chg" label="当日" width="76" align="right">
          <template #default="s">
            <span :class="trendClass(s.row.pct_chg)">{{ fmtPct(s.row.pct_chg) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="data_end" label="行情日" width="96" align="center">
          <template #default="s">
            <template v-if="s.row.data_end && s.row.data_end !== s.row.bar_date">
              <el-tooltip
                :content="'行情库仅覆盖至 ' + s.row.data_end + '（回填中或缺尾），非所选截止日数据'"
                placement="top"
              >
                <span class="lag">{{ s.row.data_end }}</span>
              </el-tooltip>
            </template>
            <span v-else class="muted">{{ s.row.data_end || '--' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="disclaimer">
        妖股识别为启发式评分（涨幅/连板/换手/量能/游资加权），仅供研究参考，非投资建议；妖股波动极大，追高需谨慎。
      </div>
    </el-card>

    <!-- ====== 个股画像 ====== -->
    <el-card v-if="prof && prof.code" shadow="never" class="card">
      <template #header>
        <div class="card-h">
          <span class="stk-name">{{ prof.name || prof.code }}</span>
          <span class="sub">{{ prof.code }} · 近 60 个交易日画像</span>
          <el-tag :type="stageTag(prof.stage)" size="small" style="margin-left: 10px">
            {{ prof.stage }}
          </el-tag>
          <el-tag type="danger" size="small" effect="dark" style="margin-left: 6px">
            妖气 {{ prof.score }}
          </el-tag>
          <el-button size="small" text style="margin-left: auto" @click="prof = {}">收起</el-button>
        </div>
      </template>

      <!-- 风险信号 -->
      <el-alert
        v-for="(r, i) in prof.risks || []"
        :key="i"
        type="warning"
        :closable="false"
        show-icon
        :title="r"
        class="risk-alert"
      />

      <!-- 评分明细 -->
      <div class="score-row">
        <div v-for="d in scoreBars" :key="d.label" class="score-item">
          <div class="score-label">{{ d.label }} <b>{{ d.val }}</b></div>
          <el-progress :percentage="d.pct" :stroke-width="8" :show-text="false" />
        </div>
      </div>

      <!-- K 线 + 均线 + 成交额 -->
      <BaseChart :option="klineOption" height="360px" />

      <!-- 席位 / 涨停明细 -->
      <div class="prof-grid">
        <div class="prof-box">
          <div class="box-title">游资席位净买 Top5</div>
          <div v-for="(y, i) in prof.youzi_top || []" :key="i" class="mini-row">
            <span class="rank" :class="'top' + (i + 1)">{{ i + 1 }}</span>
            <span class="seat-name" :title="y.seat_name">{{ y.seat_name }}</span>
            <span :class="y.net_wan >= 0 ? 'up' : 'down'">{{ fmtYuan(y.net_wan * 1e4) }}</span>
          </div>
          <div v-if="!(prof.youzi_top || []).length" class="muted" style="padding: 10px 0">
            窗口内无游资上榜记录
          </div>
          <div class="box-title" style="margin-top: 12px">最近上榜明细</div>
          <div v-for="(s, i) in (prof.seat_rows || []).slice(0, 8)" :key="'s' + i" class="mini-row">
            <span class="mini-date">{{ s.date }}</span>
            <span class="seat-name" :title="s.seat_name">{{ s.seat_name }}</span>
            <span :class="s.net_amt >= 0 ? 'up' : 'down'">{{ fmtYuan(s.net_amt) }}</span>
          </div>
        </div>
        <div class="prof-box">
          <div class="box-title">涨停明细（窗口内）</div>
          <div v-for="(l, i) in prof.limitup || []" :key="i" class="mini-row">
            <span class="mini-date">{{ l.date }}</span>
            <el-tag size="small" type="danger" effect="plain">{{ l.limit_tag }}</el-tag>
            <span class="seat-name" :title="l.reason">{{ l.reason || '--' }}</span>
          </div>
          <div v-if="!(prof.limitup || []).length" class="muted" style="padding: 10px 0">
            窗口内无涨停记录（涨幅由连续大阳推动）
          </div>
          <div class="box-title" style="margin-top: 12px">关键指标</div>
          <div class="kv-grid">
            <div class="kv"><span>区间涨幅</span><b :class="trendClass(prof.gain)">{{ fmtPct(prof.gain) }}</b></div>
            <div class="kv"><span>最高连板</span><b>{{ prof.max_streak }}板</b></div>
            <div class="kv"><span>涨停次数</span><b>{{ prof.lim_days }}</b></div>
            <div class="kv"><span>10日均换手</span><b>{{ prof.avg_turn10 }}%</b></div>
            <div class="kv"><span>量能倍数</span><b>{{ prof.vol_ratio }}x</b></div>
            <div class="kv"><span>MA20乖离</span><b>{{ prof.bias }}%</b></div>
            <div class="kv"><span>上榜天数</span><b>{{ prof.lb_days }}</b></div>
            <div class="kv"><span>游资家数</span><b>{{ prof.youzi_cnt }}</b></div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import BaseChart from '../components/BaseChart.vue'
import { api } from '../api'
import { fmtYuan, fmtPct, fmtNum, trendClass } from '../utils/format'

const loading = ref(false)
const res = ref({})
const prof = ref({})
const cutoff = ref('')       // 截止交易日；'' = 最新
const dates = ref([])        // 可选交易日（倒序）

const UP = '#f5222d', DOWN = '#16a34a'

async function load() {
  loading.value = true
  try {
    res.value = await api.yaoList({ days: 60, top: 20, date: cutoff.value })
  } finally {
    loading.value = false
  }
}

async function openProfile(row) {
  prof.value = await api.yaoProfile(row.code, 60, cutoff.value)
}

function stageTag(s) {
  if (s === '加速') return 'danger'
  if (s === '主升') return 'warning'
  if (s === '启动') return 'primary'
  return 'info'   // 分歧/退潮
}

const scoreBars = computed(() => {
  const d = prof.value.score_detail || {}
  const items = [
    { label: '涨幅', val: d.gain, max: 40 },
    { label: '连板', val: d.board, max: 25 },
    { label: '换手', val: d.turn, max: 15 },
    { label: '量能', val: d.vol, max: 10 },
    { label: '游资', val: d.seat, max: 10 }
  ]
  return items.map((x) => ({ ...x, pct: Math.round((x.val / x.max) * 100) }))
})

const klineOption = computed(() => {
  const p = prof.value
  if (!p.kline || !p.kline.length) return {}
  const dates = p.kline.map((k) => k.date)
  return {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['MA5', 'MA10', 'MA20'], top: 0, textStyle: { color: '#666' } },
    grid: [
      { left: 56, right: 16, top: 30, height: '56%' },
      { left: 56, right: 16, top: '74%', height: '18%' }
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLabel: { color: '#888' } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } }
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { color: '#f0f0f0' } } },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 40, end: 100 }],
    series: [
      {
        name: 'K线', type: 'candlestick',
        data: p.kline.map((k) => [k.open, k.close, k.low, k.high]),
        itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN }
      },
      { name: 'MA5', type: 'line', data: p.ma5, symbol: 'none', lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'MA10', type: 'line', data: p.ma10, symbol: 'none', lineStyle: { width: 1, color: '#3b82f6' } },
      { name: 'MA20', type: 'line', data: p.ma20, symbol: 'none', lineStyle: { width: 1, color: '#8b5cf6' } },
      {
        name: '成交额', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: p.kline.map((k) => ({
          value: k.amount,
          itemStyle: { color: k.pct_chg >= 0 ? UP : DOWN, opacity: 0.7 }
        }))
      }
    ]
  }
})

onMounted(async () => {
  load()
  try {
    const r = await api.yaoDates(40)
    dates.value = (r && r.dates) || []
  } catch (e) {
    dates.value = []
  }
})
</script>

<style scoped>
.card { margin-bottom: 14px; }
.card-h {
  display: flex; align-items: center; gap: 10px;
  font-size: 15px; font-weight: 700; color: #1f2733;
}
.card-h .sub { font-size: 12px; font-weight: 400; color: #8a93a6; }
.yao-table :deep(tbody tr) { cursor: pointer; }
.stk-name { font-weight: 700; color: #1f2733; }
.score { font-weight: 800; color: #f5222d; font-size: 15px; }
.risk-chip { color: #d48806; font-weight: 600; cursor: default; }
.muted { color: #b0b8c5; }
.lag { color: #d48806; font-weight: 600; cursor: default; }
.disclaimer {
  margin-top: 10px; font-size: 12px; color: #a0a8b5;
  border-top: 1px dashed #eef0f4; padding-top: 8px;
}
.risk-alert { margin-bottom: 8px; }
.score-row { display: flex; gap: 18px; margin: 6px 0 14px; }
.score-item { flex: 1; }
.score-label { font-size: 12px; color: #8a93a6; margin-bottom: 4px; }
.score-label b { color: #1f2733; }
.prof-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 14px; }
.prof-box {
  background: #f8f9fb; border: 1px solid #eef0f4; border-radius: 8px; padding: 12px;
}
.box-title { font-size: 13px; font-weight: 700; color: #1f2733; margin-bottom: 6px; }
.mini-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 0; border-bottom: 1px dashed #eef0f4; font-size: 13px;
}
.mini-row:last-child { border-bottom: none; }
.rank {
  width: 20px; height: 20px; border-radius: 4px; background: #eef0f4; color: #8a93a6;
  font-size: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.rank.top1 { background: #f5222d; color: #fff; }
.rank.top2 { background: #ff7a45; color: #fff; }
.rank.top3 { background: #d48806; color: #fff; }
.seat-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #4a5468;
}
.mini-date { color: #8a93a6; font-size: 12px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
.kv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 14px; }
.kv {
  display: flex; justify-content: space-between; font-size: 13px;
  background: #fff; border-radius: 6px; padding: 6px 10px; border: 1px solid #eef0f4;
}
.kv span { color: #8a93a6; }
.kv b { font-weight: 700; }
</style>
