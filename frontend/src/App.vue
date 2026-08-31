<template>
  <div class="app-root" :class="{ 'is-mobile': isMobile }">

    <!-- ====== 桌面侧边栏 ====== -->
    <el-aside v-if="!isMobile" width="212px" class="aside">
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

    <!-- ====== 手机端顶栏 ====== -->
    <div v-if="isMobile" class="mobile-topbar">
      <el-button :icon="Menu" text class="topbar-menu-btn" @click="drawerVisible = true" />
      <div class="topbar-center">
        <span class="topbar-title">{{ currentTitle }}</span>
        <el-select v-model="ui.selectedDate" placeholder="最新" size="small" class="topbar-date-select">
          <el-option label="最新" value="" />
          <el-option v-for="d in ui.availableDates" :key="d" :label="d" :value="d" />
        </el-select>
      </div>
      <el-button :icon="Refresh" text :loading="refreshing" class="topbar-refresh-btn" @click="doRefresh" />
    </div>

    <!-- ====== 右侧内容面板（桌面：header + main；手机：仅 main） ====== -->
    <div class="right-panel">
      <!-- 桌面顶栏 -->
      <div v-if="!isMobile" class="header">
        <div class="header-left">
          <span class="page-title">{{ currentTitle }}</span>
          <el-tag v-if="ui.selectedDate" size="small" type="warning" effect="plain">
            回看 {{ ui.selectedDate }}
          </el-tag>
          <el-tag v-else size="small" type="info" effect="plain">
            交易日 {{ ui.tradeDate }}
          </el-tag>
        </div>
        <div class="header-right">
          <span class="src-mini">
            数据
            <b :class="srcClass('billboard')">{{ srcText('billboard') }}</b>
          </span>
          <el-select v-model="ui.selectedDate" placeholder="最新" size="small" class="date-select">
            <el-option label="最新" value="" />
            <el-option v-for="d in ui.availableDates" :key="d" :label="d" :value="d" />
          </el-select>
          <el-button size="small" :icon="Refresh" :loading="refreshing" @click="doRefresh">
            刷新数据
          </el-button>
        </div>
      </div>
      <!-- 内容区 -->
      <div class="main" :class="{ 'main-mobile': isMobile }">
        <router-view />
      </div>
    </div>

    <!-- ====== 手机端抽屉导航 ====== -->
    <el-drawer
      v-if="isMobile"
      v-model="drawerVisible"
      direction="ltr"
      size="230px"
      :with-header="false"
      :close-on-press-escape="true"
    >
      <div class="drawer-brand">
        <div class="brand-logo">盘</div>
        <div class="brand-text">
          <div class="brand-title">每日复盘</div>
          <div class="brand-sub">股票资金看板</div>
        </div>
      </div>
      <el-menu
        :default-active="activePath"
        router
        class="drawer-menu"
        @select="drawerVisible = false"
      >
        <el-menu-item v-for="r in menus" :key="r.path" :index="r.path">
          <el-icon><component :is="r.icon" /></el-icon>
          <span>{{ r.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh, Menu } from '@element-plus/icons-vue'
import { ui, loadStatus, loadDates, api } from './api'
import { useResponsive } from './composables/useResponsive'

const route = useRoute()
const refreshing = ref(false)
const drawerVisible = ref(false)
const { isMobile } = useResponsive()

const menus = [
  { path: '/', title: '总览', icon: 'DataLine' },
  { path: '/limit-up', title: '涨停排行', icon: 'Top' },
  { path: '/hot-billboard', title: '热点重合榜', icon: 'TrendCharts' },
  { path: '/billboard', title: '龙虎榜', icon: 'Trophy' },
  { path: '/rapid-rise', title: '极速拉升', icon: 'Top' },
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
  loadDates()
})
</script>

<style>
:root {
  --up: #f5222d;
  --down: #16a34a;
}
html, body {
  margin: 0; padding: 0; height: 100%; overflow: hidden;
}
.up { color: var(--up) !important; font-weight: 600; }
.down { color: var(--down) !important; font-weight: 600; }
</style>

<style scoped>
/* ====== 根容器：纯 CSS Flex，不依赖 Element Plus 容器 ====== */
.app-root {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

/* 桌面：row 布局；手机：column 布局 */
.app-root:not(.is-mobile) {
  flex-direction: row;
}
.is-mobile {
  flex-direction: column;
}

/* ====== 桌面侧边栏 ====== */
.aside {
  background: #0f1830;
  color: #cdd5e5;
  display: flex;
  flex-direction: column;
  border-right: none;
  flex-shrink: 0;
  overflow-y: auto;
  height: 100vh;
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
  flex-shrink: 0;
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

/* ====== 右侧内容面板 ====== */
.right-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

/* ====== 手机端顶栏 ====== */
.mobile-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #eef0f4;
  padding: 0 12px;
  height: 48px;
  flex-shrink: 0;
  z-index: 10;
}
.topbar-menu-btn,
.topbar-refresh-btn {
  font-size: 20px; color: #1f2733;
}
.topbar-center {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}
.topbar-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2733;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.topbar-date { flex-shrink: 0; }
.topbar-date-select { width: 116px; flex-shrink: 0; }
.topbar-date-select :deep(.el-input__wrapper) { padding: 0 8px; }

/* ====== 桌面顶栏 ====== */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #eef0f4;
  height: 60px;
  flex-shrink: 0;
  padding: 0 18px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.page-title { font-size: 18px; font-weight: 700; color: #1f2733; }
.header-right { display: flex; align-items: center; gap: 14px; }
.src-mini { font-size: 12px; color: #8a93a6; }
.src-mini b { margin-left: 4px; font-weight: 600; }
.t-live { color: #16a34a; }
.t-demo { color: #d48806; }
.date-select { width: 140px; }

/* ====== 滚动内容区 ====== */
.main {
  flex: 1;
  min-height: 0;
  background: #f5f7fa;
  padding: 18px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.main-mobile { padding: 10px; }

/* ====== 手机端抽屉导航 ====== */
.drawer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px 16px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 6px;
}
.drawer-menu { border-right: none; }
.drawer-menu :deep(.el-menu-item) {
  height: 44px; color: #1f2733; border-radius: 8px; margin: 2px 8px;
}
.drawer-menu :deep(.el-menu-item.is-active) {
  background: #ecf5ff !important; color: #409eff; font-weight: 600;
}
.drawer-menu :deep(.el-menu-item:hover) { background: #f5f7fa; }

/* 移动端表格横向滚动容器 */
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
</style>
