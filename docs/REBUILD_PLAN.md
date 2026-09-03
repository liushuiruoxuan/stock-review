# stock-review 全面升级重构方案（v2）

- **日期**：2026-09-02
- **状态**：待评审（§10 决策项拍板后开工）
- **目标**：在现有「每日复盘看板」基础上，新增 **大屏看板**、**资金博弈看板**、**量化回测/选股** 三大能力，并偿还关键技术债

---

## 1. 现状盘点

### 1.1 代码资产

| 模块 | 文件 | 规模 | 现状评价 |
|---|---|---|---|
| 路由/API | `backend/server.py` | 879 行 | if 链手工分发约 23 个端点，零依赖模式有启动即崩 bug（TD-8） |
| 数据抓取 | `backend/eastmoney.py` | ~900 行 | 东财（龙虎榜/席位/涨停/板块/资金流）+ 新浪（极速拉升），仅当日快照，**无历史 K 线** |
| 存储 | `backend/db.py` | ~280 行 | MySQL 3 表，section 表 JSON blob 反模式，无连接池 |
| 因子计算 | `backend/monitor.py` | 413 行 | ⭐ 纯函数实现席位分类/胜率/连卖/抱团信号，质量高，**直接复用** |
| 前端 | `frontend/src/` | 2803 行 | Vue3.5 + ElementPlus + ECharts，11 个页面，4 个可复用基础组件 |
| 部署 | `Dockerfile` / `docker-compose.yml` / `deploy.py` | - | 多阶段构建，镜像内无 volume，热更靠 docker cp 补丁 |

### 1.2 数据库现状（MySQL `stock_review`）

| 表 | 内容 | 结构 |
|---|---|---|
| section | 各板块数据（billboard/stocks_flow/sectors_hot…） | JSON blob 整存整取 |
| seats | 龙虎榜席位明细 | 列式 ✅ |
| limit_up | 每日涨停梯队 | 列式 ✅ |

**核心缺口：全库无 OHLCV 历史行情、无交易日历、无标的主数据、无指数基准。** 这是量化能力的唯一硬阻塞，必须新建一条独立数据管线（§4）。

### 1.3 技术债清单

| 编号 | 问题 | 影响 | 处理 |
|---|---|---|---|
| TD-1 | server.py if 链路由，新端点要改 3 处 | 开发效率 | Phase 1 重写为路由表 |
| TD-2 | 依赖模式下 `ensure_built()` 每请求打外网 | 线上延迟 | Phase 1 改为定时预构建 |
| TD-3 | section 表 JSON blob，无法 SQL 查询/建索引 | 分析能力 | 保留（快照数据）+ 新表走列式 |
| TD-4 | 每次查询新建 MySQL 连接 | 性能 | 引入连接池 |
| TD-5 | `/api/refresh` 同步阻塞，无长任务模型 | 全量初始化必挂 | 引入后台任务 + 进度查询 |
| TD-6 | 前端无状态管理，`api/index.js` 里全局 reactive | 可维护性 | 沿用轻量方案即可（见 §7） |
| TD-7 | 前后端零测试 | 回归风险 | 关键路径补测试 |
| TD-8 | **bug**：零依赖模式下 `server.py:181-202` `hb_bb` 未定义 NameError，启动即崩 | 线上稳定性 | **Phase 0 立即修** |
| TD-9 | 镜像无 volume，改代码需 docker cp 或重建镜像 | 迭代速度 | 保留热更通道 + 每阶段打镜像 tag |

### 1.4 可直接复用的资产

- `monitor.py` 全部因子函数 → 资金博弈看板与「龙虎榜跟随策略」的核心 alpha
- `seats` + `limit_up` 两张列式表 → 资金博弈看板数据底座
- 前端 `BaseChart / DataTable / StatCard / SourceTag` 四件套 → 所有新页面
- `eastmoney.py` 各 fetch 函数 → 挂到新任务调度器即可
- Docker 多阶段构建 + nas.xingtux.cn 部署链路 → 原样沿用

---

## 2. 目标架构

```
E:\ai\stock-review
├── backend/
│   ├── app/                    # 新：FastAPI 应用壳
│   │   ├── main.py             # 入口，路由表自动注册
│   │   ├── routers/
│   │   │   ├── legacy.py       # 现有 23 个端点等价迁移
│   │   │   ├── market.py       # 指数/行情/日历
│   │   │   ├── bigscreen.py    # 大屏聚合端点
│   │   │   ├── game.py         # 资金博弈端点
│   │   │   └── quant.py        # 回测/选股端点
│   │   └── deps.py             # 连接池、任务队列依赖注入
│   ├── core/
│   │   ├── eastmoney.py        # 保留，原样迁移
│   │   ├── monitor.py          # 保留，原样迁移 ⭐
│   │   └── db.py               # 重写：连接池 + 新表 DAO
│   ├── datasvc/                # 新：行情数据管线
│   │   ├── calendar.py         # 交易日历
│   │   ├── bars_fetcher.py     # OHLCV 增量抓取（东财 kline API）
│   │   └── jobs.py             # 盘后定时任务（APScheduler）
│   ├── quant/                  # 新：量化模块
│   │   ├── engine.py           # 向量化回测引擎（pandas/numpy）
│   │   ├── metrics.py          # 年化/回撤/夏普/胜率
│   │   ├── strategies/         # 策略目录（每策略一个 py）
│   │   └── screener.py         # 条件选股器
│   └── server.py               # 旧入口，Phase 1 后退役
├── frontend/src/
│   ├── views/
│   │   ├── BigScreen.vue       # 新：大屏（暗色，独立布局）
│   │   ├── Game.vue            # 新：资金博弈总览
│   │   ├── StockGame.vue       # 新：个股博弈画像
│   │   ├── QuantBacktest.vue   # 新：回测工作台
│   │   └── QuantScreener.vue   # 新：选股器
│   ├── theme/bigscreen.css     # 大屏暗色主题
│   └── （现有 11 页面原样保留）
└── deploy.py                   # 沿用，增加镜像 tag 参数
```

**分层原则**：抓取层（datasvc）→ 存储层（db）→ 计算层（monitor/quant）→ 展示层（routers + frontend），单向依赖，量化引擎只读行情库。

---

## 3. 关键决策项（推荐已标注，见 §10）

| # | 决策 | 推荐 | 备选 |
|---|---|---|---|
| D1 | 量化范围 | **策略回测 + 因子选股**（纯研究，不碰真实资金） | 回测+模拟盘（二期）；券商实盘（暂缓，QMT 等对个人门槛高且涉及真实资金风险） |
| D2 | 重构方式 | **分层重构**：保留抓取层/monitor.py/seats 表，重写路由+存储+新增模块 | 增量演进（最快但 TD-1/2/5 持续拖累）；推倒重来（战线过长） |
| D3 | 技术栈 | **放开依赖**：FastAPI + numpy/pandas + APScheduler | 保留零依赖（回测性能差 10~100 倍，不可行） |
| D4 | 大屏定位 | **独立投屏页** `/bigscreen`，暗色 1920×1080 | 整体暗色工作台（11 页全改，成本高） |
| D5 | 行情存储 | **沿用现有 MySQL 实例**，新增列式行情表 | SQLite（省一个依赖，但与现有部署割裂） |

---

## 4. 数据层重构（Phase 1 核心）

### 4.1 新增表

```sql
-- 标的主数据
CREATE TABLE instruments (
  code     VARCHAR(12) PRIMARY KEY,   -- '600519.SH'
  name     VARCHAR(32) NOT NULL,
  industry VARCHAR(32),
  list_date DATE,
  is_active TINYINT DEFAULT 1
);

-- 交易日历（含是否交易日、涨停幅规则）
CREATE TABLE trade_calendar (
  trade_date DATE PRIMARY KEY,
  is_open    TINYINT NOT NULL
);

-- 日线行情（核心表，列式）
CREATE TABLE daily_bars (
  code       VARCHAR(12) NOT NULL,
  trade_date DATE NOT NULL,
  open DECIMAL(12,3), high DECIMAL(12,3),
  low  DECIMAL(12,3), close DECIMAL(12,3),
  volume  BIGINT,        -- 手
  amount  DECIMAL(18,2), -- 元
  turnover DECIMAL(8,4), -- 换手率%
  pct_chg  DECIMAL(8,4), -- 涨跌幅%
  PRIMARY KEY (code, trade_date),
  KEY idx_date (trade_date)
);

-- 指数基准（上证/深成/创业板/万得全A替代：用国证A指）
CREATE TABLE index_bars ( LIKE daily_bars 结构 );

-- 回测任务与结果
CREATE TABLE backtest_runs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  strategy VARCHAR(64), params JSON,
  universe JSON, date_range JSON,
  status VARCHAR(16),          -- running/done/failed
  metrics JSON, trades JSON, equity_curve JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

容量估算：全市场 ~5400 只 × 10 年 × 250 日 ≈ **1350 万行，约 1.5 GB**，MySQL 单表可承受；查询走 `(code, trade_date)` 主键 + `idx_date`。

### 4.2 行情抓取管线

- **数据源**：东方财富 kline 接口（`push2his.eastmoney.com`，免费无 key，与现有 eastmoney.py 同源、同反爬策略），逐标的拉日 K。
- **全量初始化**：5400 只 × ~0.15s/只 ≈ **15~20 分钟**，走后台任务（TD-5），前端显示进度条，可断点续传（按 code 游标）。
- **每日增量**：收盘后 17:00 定时任务，只拉当日 + 补昨日缺失；停牌自动跳过（依赖 trade_calendar）。
- **风控**：请求间隔 + 重试 + UA 池，失败落 `fetch_errors` 表供人工重跑。

### 4.3 与现有数据的关系

- section/seats/limit_up 三表**原样保留**，旧端点继续可用；
- 新行情库独立命名空间，不迁移旧数据；
- `instruments` 初次构建时可从现有 seats/limit_up/billboard 历史数据 + 东财列表接口合成。

---

## 5. 三大新功能设计

### 5.1 大屏看板 `/bigscreen`（D4：独立投屏页）

- **布局**（1920×1080 基准，`transform: scale()` 等比适配任意分辨率，F11 全屏）：

```
┌──────────────────────────────────────────────────────┐
│  每日复盘 · 资金大屏          2026-09-02  18:00:00 ●LIVE│
├──────────┬────────────────────────────┬──────────────┤
│ 指数卡片  │        涨停梯队热度         │  龙虎榜净买    │
│ 上证/深成 │   （高度分布+炸板率）        │   Top10 柱图  │
│ /创业板   │                            │              │
├──────────┼────────────────────────────┼──────────────┤
│ 席位进攻  │     主力资金流向地图          │  游资/机构    │
│ 热力条    │   （板块净流入环形+排行）      │  活跃榜轮播   │
├──────────┴────────────────────────────┴──────────────┤
│              底部跑马灯：席位动态 / 涨停原因滚动          │
└──────────────────────────────────────────────────────┘
```

- **技术**：复用 `BaseChart` + ECharts dark 主题；数据走新增聚合端点 `GET /api/bigscreen/overview`（一次请求全屏数据，30s 轮询 + 手动刷新）；
- **复用率 ~80%**：所有图表逻辑来自现有 `utils/charts.js`。

### 5.2 资金博弈看板 `/game`

把现有 seats + limit_up + billboard 三路数据**融合成博弈视角**，核心逻辑全部复用 `monitor.py`：

1. **博弈总览页**：当日多空力量对比（席位买额 vs 卖额瀑布图）、游资/机构/量化三类席位进攻热度、抱团席位监控（复用 `detect_crowding`）、连板梯队 + 炸板率。
2. **个股博弈画像页**（点击任意个股进入）：
   - 席位进出明细 + 每个席位的**历史胜率**（复用 `seat_win_rate`）；
   - 该股历史信号时间线（席位抱团/连卖/涨停日叠加 K 线 ← 依赖 §4 行情库，这是新旧数据的交汇点）；
   - 结论标签：「游资接力」「机构锁仓」「量化对倒」等。
3. **新增端点**：`GET /api/game/overview`、`GET /api/game/stock/{code}`。

### 5.3 量化模块 `/quant`（D1：回测 + 选股，不接实盘）

- **回测引擎**：pandas 向量化（非事件驱动），支持 T+1、双边手续费、滑点、涨跌停不可成交约束（复用 limit_up 表）；
- **内置策略**（每个都是可编辑的 py 文件，热加载）：
  1. 双均线基准策略（教学用）
  2. 动量轮动（行业 ETF）
  3. **龙虎榜席位跟随策略**——用 monitor.py 的胜率/抱团因子生成信号，这是本项目独有的 alpha 来源
- **指标输出**：总收益/年化/最大回撤/夏普/胜率/盈亏比 + 逐笔交易明细 + 资金曲线（与基准叠加）；
- **选股器**：多条件筛选（行情字段 + 席位因子 + 涨停因子），保存筛选方案；
- **长任务**：回测提交后进任务队列，前端轮询进度（解决 TD-5 的同一套机制）；
- **安全边界**：quant 模块对数据库**只读**，无任何下单接口。

---

## 6. 后端改造要点

| 项 | 方案 |
|---|---|
| 框架 | FastAPI + uvicorn（Docker 镜像内 pip 安装，不污染宿主） |
| 旧端点 | `routers/legacy.py` 等价迁移，路径与响应结构**完全不变**（前端零改动），迁移后用脚本逐端点 diff 验证 |
| 连接池 | `dbutils`/原生连接池，进程级单例 |
| 定时任务 | APScheduler：17:00 行情增量、18:30 龙虎榜/席位构建（替代 TD-2 的请求时构建） |
| 长任务 | 线程池 + `backtest_runs.status` 状态机，前端轮询 |

## 7. 前端改造要点

- 新增 5 个页面（§2），现有 11 页**一行不改**；
- 状态管理沿用现有 `reactive` 全局 `ui`（项目规模下不必引入 Pinia）；
- 大屏页独立入口路由，暗色 CSS 变量作用域隔离，不影响亮色主题；
- `package.json` 仅按需增加依赖，ECharts/ElementPlus 版本不动。

## 8. 实施路线图（每阶段独立可部署、可回滚）

| 阶段 | 内容 | 交付物 | 预估 |
|---|---|---|---|
| **P0** | 修 TD-8 bug；git tag `v1-baseline`；MySQL 建新表 | 线上零依赖模式不再崩 | 0.5 天 |
| **P1** | FastAPI 壳 + legacy 端点等价迁移 + 连接池 + 行情管线（全量初始化 + 每日增量） | 新后端上线，行情库有数据 | 2~3 天 |
| **P2** | 大屏看板（前端 + 聚合端点） | `/bigscreen` 可投屏 | 1~2 天 |
| **P3** | 资金博弈看板（总览 + 个股画像） | `/game` 上线 | 2 天 |
| **P4** | 量化回测 + 选股器 + 内置 3 策略 | `/quant` 上线 | 3~5 天 |
| **P5**（可选） | 模拟盘（虚拟持仓记账） | 二期再议 | - |

每阶段结束：git tag + docker 镜像 tag（如 `stock-review:p1`），出问题 `docker tag` 秒级回滚。

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 东财 kline 接口限流/改版 | 请求间隔 + 指数退避重试；抓取层已抽象，可切新浪/腾讯备用源 |
| 全量初始化 15~20 分钟被中断 | 按 code 游标断点续传，任务表记录进度 |
| MySQL 容量（~1.5GB/10 年） | 现有服务器可承受；daily_bars 按年分区预留 |
| 新旧端点行为不一致 | legacy 迁移后脚本化 diff（请求 → 响应 JSON 对比） |
| 你对 UI 反复调优需要回滚 | 每阶段 git tag；建议前端改动日结提交 |

## 10. 请你拍板的决策清单

- [ ] **D1 量化范围**：推荐「回测+选股」，实盘暂缓 —— 是否同意？
- [ ] **D2 重构方式**：推荐「分层重构」 —— 是否同意？
- [ ] **D3 技术栈**：推荐「FastAPI + numpy/pandas」（镜像内安装，不影响零依赖哲学的线上兜底） —— 是否同意？
- [ ] **D4 大屏定位**：推荐「独立投屏页」 —— 是否同意？
- [ ] **D5 行情存储**：推荐「沿用现有 MySQL」 —— 是否同意？
- [ ] 行情历史深度：**10 年**还是 5 年（全量初始化时间减半）？
- [ ] 大屏是否需要**自动轮播**（板块自动切换，每 15s）？
