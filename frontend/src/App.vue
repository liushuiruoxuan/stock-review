<template>
  <el-container class="app-root">
    <el-aside width="212px" class="aside">
      <div class="brand">
        <div class="brand-logo">盘</div>
        <div class="brand-text">
          <div class="brand-title">每日复盘</div>
          <div class="brand-sub">股票资金看板</div>
        </div>
      </div>
      <el-menu :default-active="activePath" router class="menu" background-color="transparent">
        <el-menu-item v-for="r in menus" :key="r.path" :index="r.path">
          <el-icon><component :is="r.icon" /></el-icon>
          <span>{{ r.title }}</span>
        </el-menu-item>
      </el-menu>
      <div class="aside-foot">
        <div class="foot-line">数据：东方财富</div>
        <div class="foot-line">仅供研究，非投资建议</div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span class="page-title">{{ currentTitle }}</span>
          <el-tag v-if="ui.tradeDate" size="small" type="info" effect="plain">
            交易日 {{ ui.tradeDate }}
          </el-tag>
        </div>
        <div class="header-right">
          <span class="src-mini">
            龙虎榜
            <b :class="srcClass('billboard')">{{ srcText('billboard') }}</b>
          </span>
          <span class="src-mini">
            个股
            <b :class="srcClass('stocks')">{{ srcText('stocks') }}</b>
          </span>
          <span class="src-mini">
            板块
            <b :class="srcClass('sectors')">{{ srcText('sectors') }}</b>
          </span>
          <el-button size="small" :icon="Refresh" :loading="refreshing" @click="doRefresh">
            刷新数据
          </el-button>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ui, loadStatus, api } from './api'

const route = useRoute()
const refreshing = ref(false)

const menus = [
  { path: '/', title: '总览', icon: 'DataLine' },
  { path: '/billboard', title: '龙虎榜', icon: 'Trophy' },
  { path: '/capital-flow', title: '资金流向', icon: 'Money' },
  { path: '/sectors', title: '热点 / 流出板块', icon: 'PieChart' },
  { path: '/rapid-rise', title: '极速拉升', icon: 'Top' },
  { path: '/capital-attention', title: '资金关注', icon: 'View' },
  { path: '/institution-youzi', title: '机构 / 游资', icon: 'User' },
  { path: '/monitor', title: '资金监控', icon: 'Bell' },
  { path: '/seats', title: '席位监控', icon: 'OfficeBuilding' }
]

const activePath = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '总览')

function srcText(k) {
  return ui.sources[k] === 'demo' ? '示例' : '实时'
}
function srcClass(k) {
  return ui.sources[k] === 'demo' ? 't-demo' : 't-live'
}

async function doRefresh() {
  refreshing.value = true
  try {
    await api.refresh()
    await loadStatus()
    window.location.reload()
  } finally {
    refreshing.value = false
  }
}

onMounted(() => {
  loadStatus()
})
</script>

<style>
:root {
  --up: #f5222d;
  --down: #16a34a;
}
.up { color: var(--up) !important; font-weight: 600; }
.down { color: var(--down) !important; font-weight: 600; }
</style>

<style scoped>
.app-root { height: 100vh; }
.aside {
  background: #0f1830;
  color: #cdd5e5;
  display: flex;
  flex-direction: column;
  border-right: none;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 18px 14px;
}
.brand-logo {
  width: 38px; height: 38px; border-radius: 9px;
  background: linear-gradient(135deg, #f5222d, #ff7a45);
  color: #fff; font-weight: 800; font-size: 20px;
  display: flex; align-items: center; justify-content: center;
}
.brand-title { font-size: 17px; font-weight: 700; color: #fff; }
.brand-sub { font-size: 12px; color: #8a93a6; }
.menu { border-right: none; background: transparent !important; flex: 1; }
.menu :deep(.el-menu-item) {
  color: #b9c2d6; border-radius: 8px; margin: 4px 10px; height: 44px;
}
.menu :deep(.el-menu-item.is-active) {
  background: #1f2d4d !important; color: #fff; font-weight: 600;
}
.menu :deep(.el-menu-item:hover) { background: #16213c; color: #fff; }
.aside-foot { padding: 14px 18px; font-size: 11px; color: #6b7488; line-height: 1.7; }

.header {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-bottom: 1px solid #eef0f4; height: 60px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.page-title { font-size: 18px; font-weight: 700; color: #1f2733; }
.header-right { display: flex; align-items: center; gap: 14px; }
.src-mini { font-size: 12px; color: #8a93a6; }
.src-mini b { margin-left: 4px; font-weight: 600; }
.t-live { color: #16a34a; }
.t-demo { color: #d48806; }
.main { background: #f5f7fa; padding: 18px; overflow-y: auto; }
</style>
