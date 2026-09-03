<template>
  <div v-loading="loading">
    <!-- 头部 -->
    <div class="profile-head">
      <div class="ph-left">
        <span class="ph-name">{{ d.name }}</span>
        <span class="ph-code">{{ d.code }}</span>
        <el-tag v-for="t in d.tags || []" :key="t" size="small" :type="tagType(t)" effect="dark">{{ t }}</el-tag>
      </div>
      <el-button size="small" @click="$router.back()">返回</el-button>
    </div>

    <div class="two-col">
      <!-- K线收盘价 -->
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">近 120 日走势（行情库）<span v-if="!d.kline?.length" class="sub">未同步，先在量化页触发行情同步</span></div></template>
        <BaseChart v-if="d.kline?.length" :option="klineOption" height="280px" />
        <el-empty v-else description="暂无K线" :image-size="60" />
      </el-card>

      <!-- 席位胜率 -->
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">参与席位画像（净额 Top15）</div></template>
        <el-table v-if="(d.seat_win || []).length" :data="d.seat_win" size="small" height="280">
          <el-table-column prop="seat_name" label="席位" min-width="200" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="70" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.type === 'inst' || row.type === 'hk' ? 'primary' : 'warning'" effect="plain">
                {{ row.type === 'inst' ? '机构' : row.type === 'hk' ? '北向' : '游资' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="cnt" label="次数" width="60" align="center" />
          <el-table-column prop="net_wan" label="累计净额(万)" width="110" align="right" sortable>
            <template #default="{ row }">
              <span :class="trendClass(row.net_wan)">{{ fmtNum(row.net_wan, 0) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="avg_rise_3d" label="3日胜率%" width="90" align="right">
            <template #default="{ row }">
              <span :class="trendClass(row.avg_rise_3d)">{{ row.avg_rise_3d ?? '--' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="该股暂无席位记录" :image-size="60" />
      </el-card>
    </div>

    <div class="two-col">
      <!-- 龙虎榜上榜历史 -->
      <el-card shadow="never" class="card">
        <template #header><div class="card-h">龙虎榜上榜历史（近 20 次）</div></template>
        <el-table v-if="(d.billboard_history || []).length" :data="d.billboard_history.slice(0, 20)" size="small" height="320">
          <el-table-column prop="date" label="日期" width="105" />
          <el-table-column prop="category" label="类别" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="catType(row.category)" effect="plain">{{ catLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="net_amt" label="净买" width="100" align="right">
            <template #default="{ row }">
              <span :class="trendClass(row.net_amt)">{{ fmtYuan(row.net_amt) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="d1" label="次日%" width="76" align="right">
            <template #default="{ row }"><span :class="trendClass(row.d1)">{{ fmtPct(row.d1) }}</span></template>
          </el-table-column>
          <el-table-column prop="d5" label="后5日%" width="76" align="right">
            <template #default="{ row }"><span :class="trendClass(row.d5)">{{ fmtPct(row.d5) }}</span></template>
          </el-table-column>
          <el-table-column prop="reason" label="上榜原因" min-width="170" show-overflow-tooltip />
        </el-table>
        <el-empty v-else description="该股未上过龙虎榜" :image-size="60" />
      </el-card>

      <!-- 涨停历史 + 席位进出 -->
      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-h">
            涨停历史
            <span class="sub">（{{ (d.limitup_history || []).length }} 次）</span>
          </div>
        </template>
        <el-timeline v-if="(d.limitup_history || []).length" style="padding-left: 4px; max-height: 320px; overflow-y: auto">
          <el-timeline-item v-for="r in d.limitup_history" :key="r.date" :timestamp="r.date" placement="top" type="danger">
            <b>{{ r.limit_tag }}</b> 封单 {{ fmtYuan(r.seal_money) }}
            <div class="lu-reason">{{ r.reason }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="该股近期无涨停记录" :image-size="60" />
      </el-card>
    </div>

    <!-- 席位进出明细 -->
    <el-card shadow="never" class="card">
      <template #header><div class="card-h">席位进出明细（近 50 笔）</div></template>
      <el-table v-if="(d.seats_all || []).length" :data="d.seats_all.slice(0, 50)" size="small" height="340">
        <el-table-column prop="date" label="日期" width="105" />
        <el-table-column prop="seat_name" label="席位" min-width="220" show-overflow-tooltip />
        <el-table-column prop="side" label="方向" width="60" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.side === 'BUY' ? 'danger' : 'success'" effect="plain">{{ row.side === 'BUY' ? '买' : '卖' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="buy_amt" label="买入" width="100" align="right">
          <template #default="{ row }">{{ fmtYuan(row.buy_amt) }}</template>
        </el-table-column>
        <el-table-column prop="sell_amt" label="卖出" width="100" align="right">
          <template #default="{ row }">{{ fmtYuan(row.sell_amt) }}</template>
        </el-table-column>
        <el-table-column prop="net_amt" label="净额" width="100" align="right">
          <template #default="{ row }"><span :class="trendClass(row.net_amt)">{{ fmtYuan(row.net_amt) }}</span></template>
        </el-table-column>
        <el-table-column prop="rise_prob_3d" label="3日胜率%" width="86" align="right" />
      </el-table>
      <el-empty v-else description="暂无席位明细" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import BaseChart from '../components/BaseChart.vue'
import { api } from '../api'
import { fmtYuan, fmtPct, fmtNum, trendClass } from '../utils/format'

const route = useRoute()
const loading = ref(true)
const d = ref({})

const klineOption = computed(() => {
  const bars = d.value.kline || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 8, right: 14, top: 20, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: bars.map(b => b.date) },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'line', data: bars.map(b => b.close), symbol: 'none',
      areaStyle: { opacity: 0.08 }, lineStyle: { width: 2 }
    }]
  }
})

const catLabel = (c) => ({ inst_buy: '机构买', inst_sell: '机构卖', inst_split: '分歧', youzi: '游资' }[c] || c)
const catType = (c) => ({ inst_buy: 'primary', inst_sell: 'success', inst_split: 'info', youzi: 'warning' }[c] || 'info')
const tagType = (t) => ({ '机构主导': 'primary', '游资进攻': 'danger', '机构撤退': 'success', '游资抱团': 'warning', '高位连板': 'danger', '频繁上榜': 'info' }[t] || 'info')

onMounted(async () => {
  loading.value = true
  try {
    d.value = await api.gameStock(route.params.code)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.profile-head {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border: 1px solid #eef0f4; border-radius: 10px;
  padding: 12px 18px; margin-bottom: 14px;
}
.ph-left { display: flex; align-items: center; gap: 10px; }
.ph-name { font-size: 20px; font-weight: 800; color: #1f2733; }
.ph-code { font-size: 14px; color: #8a93a6; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
.card { border-radius: 10px; }
.card-h { display: flex; align-items: center; gap: 10px; font-weight: 600; color: #1f2733; font-size: 15px; }
.sub { font-size: 12px; font-weight: 400; color: #8a93a6; }
.lu-reason { font-size: 12px; color: #8a93a6; margin-top: 2px; }
@media (max-width: 1100px) { .two-col { grid-template-columns: 1fr; } }
</style>
