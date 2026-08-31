import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import Billboard from '../views/Billboard.vue'
import CapitalFlow from '../views/CapitalFlow.vue'
import Sectors from '../views/Sectors.vue'
import RapidRise from '../views/RapidRise.vue'
import CapitalAttention from '../views/CapitalAttention.vue'
import InstitutionYouzi from '../views/InstitutionYouzi.vue'
import Monitor from '../views/Monitor.vue'
import Seats from '../views/Seats.vue'
import LimitUp from '../views/LimitUp.vue'
import HotBillboard from '../views/HotBillboard.vue'

const routes = [
  { path: '/', name: 'dashboard', component: Dashboard, meta: { title: '总览', icon: 'DataLine' } },
  { path: '/billboard', name: 'billboard', component: Billboard, meta: { title: '龙虎榜', icon: 'Trophy', section: 'billboard' } },
  { path: '/capital-flow', name: 'capital-flow', component: CapitalFlow, meta: { title: '资金流向', icon: 'Money', section: 'stocks_flow' } },
  { path: '/sectors', name: 'sectors', component: Sectors, meta: { title: '热点 / 流出板块', icon: 'PieChart', section: 'sectors_hot' } },
  { path: '/rapid-rise', name: 'rapid-rise', component: RapidRise, meta: { title: '极速拉升', icon: 'Top', section: 'rapid_rise' } },
  { path: '/capital-attention', name: 'capital-attention', component: CapitalAttention, meta: { title: '资金关注', icon: 'View', section: 'capital_attention' } },
  { path: '/institution-youzi', name: 'institution-youzi', component: InstitutionYouzi, meta: { title: '机构 / 游资', icon: 'User', section: 'institution' } },
  { path: '/monitor', name: 'monitor', component: Monitor, meta: { title: '资金监控', icon: 'Bell', section: 'monitor' } },
  { path: '/seats', name: 'seats', component: Seats, meta: { title: '席位监控', icon: 'OfficeBuilding', section: 'seats' } },
  { path: '/limit-up', name: 'limit-up', component: LimitUp, meta: { title: '涨停排行', icon: 'Top', section: 'limit_up' } },
  { path: '/hot-billboard', name: 'hot-billboard', component: HotBillboard, meta: { title: '热点重合榜', icon: 'TrendCharts', section: 'hot_billboard' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
