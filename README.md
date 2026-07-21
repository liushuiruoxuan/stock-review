# 每日复盘 · 股票资金看板

一个面向**每日复盘**的股票看板网站，聚合龙虎榜、资金流向、热点 / 流出板块、极速拉升、资金关注，以及机构与游资资金动向监控。

> 数据来源：东方财富公开接口（龙虎榜 `datacenter-web`，个股 / 板块资金流 `push2`）。
> 浏览器直连东方财富接口存在跨域限制，因此由本地 Python 后端代理抓取。
> **仅供研究与学习，不构成任何投资建议。**

## 功能模块
| 模块 | 说明 |
| --- | --- |
| 总览 | 当日核心指标 + 龙虎榜净买 / 热点板块图表 |
| 龙虎榜 | 上榜个股、净买入、上榜原因、席位说明、次日表现 |
| 资金流向 | 个股主力 / 超大单 / 大单 / 中单 / 小单净流入（流入榜 + 流出榜） |
| 热点 / 流出板块 | 行业 + 概念板块资金净流入 / 净流出排行 |
| 极速拉升 | 当日涨幅榜前列，结合主力净流入判断抢筹力度 |
| 资金关注 | 主力净流入且收涨的个股（资金主动承接力度） |
| 机构 / 游资 | 龙虎榜机构买入 / 卖出榜、营业部主导活跃榜 |
| 资金监控 | 机构 / 游资分类、金额阈值 / 类型 / 时间段筛选、个股上榜次数、机构连续净卖预警、同日多股机构共振、历史胜率、按交易日导出 CSV |

## 技术架构
- **前端**：Vue 3 + Vite + Element Plus + ECharts（涨红跌绿，A股习惯）
- **后端**：Python 标准库（`http.server` + `urllib` + `threading`），**零第三方依赖**
- **缓存**：按交易日落盘到 `backend/cache/<交易日>/*.json`，避免重复请求被限流
- **定时抓取**：交易日 15:35 起自动刷新缓存（16:30 / 18:00 / 20:00 补抓）
- **降级**：当实时接口暂无可数据（如盘中、或个别网络受限）时，自动回退到内置示例数据，并在界面标注「示例数据」

## 运行方式

### 方式〇：准备 MySQL（可选，但推荐做历史复盘）
后端默认只用本地 JSON 缓存即可运行；若想**持久化 + 历史回看**，请接 MySQL：

1. 在你已有的 MySQL 实例上准备一个库（后端会自动建表，也可手动建）：
   ```sql
   CREATE DATABASE stock_review DEFAULT CHARACTER SET utf8mb4;
   ```
2. 配置连接（二选一，推荐环境变量，避免密码进代码）：
   - 环境变量：`STOCK_DB_HOST` `STOCK_DB_PORT` `STOCK_DB_USER` `STOCK_DB_PASSWORD` `STOCK_DB_NAME`
   - 或直接改 `backend/db_config.py` 里的 `DB_CONFIG` 默认值
3. 安装驱动：
   ```bash
   pip install PyMySQL
   # 若默认源慢，用镜像： pip install -i https://pypi.tuna.tsinghua.edu.cn/simple PyMySQL
   ```
4. 启动后端即会自动建表并按交易日双写；MySQL 不可用时**自动回退 JSON 缓存**，看板不中断。

> 数据存储表：`stock_review_data(trade_date, section, payload JSON)`，按交易日 upsert。
> 历史接口：`GET /api/history/dates` 列出有数据的交易日；`GET /api/history?date=YYYY-MM-DD` 取某日全部看板。

### 方式一：生产模式（最省事，推荐）
```bash
# 1) 构建前端
cd frontend
npm install
npm run build

# 2) 启动后端（会自动托管 frontend/dist）
cd ../backend
python server.py
# 浏览器打开 http://localhost:8000
```

### 方式二：开发模式（热更新）
```bash
# 终端 1：启动后端
cd backend && python server.py

# 终端 2：启动前端（默认 5173，/api 已代理到 8000）
cd frontend && npm install && npm run dev
# 浏览器打开 http://localhost:5173
```

### 手动刷新 / 强制重抓
- 界面右上角「刷新数据」按钮 → `POST /api/refresh`
- 或直接调用：`curl -X POST http://localhost:8000/api/refresh`

## 生产 / 自有服务器部署建议

后端是纯标准库单文件服务，部署极简，无需容器也能长期运行。

### 1) 进程常驻（避免关掉终端就停）
- Windows：用「任务计划程序」开机触发 `python server.py`；或更简单用 `nssm` 把 server.py 注册成服务。
- Linux / macOS：用 systemd 托管（示例见下）。

systemd 示例 `/etc/systemd/system/stock-review.service`：
```
[Unit]
Description=Stock Review Backend
After=network.target

[Service]
WorkingDirectory=/opt/stock-review/backend
ExecStart=/usr/bin/python3 /opt/stock-review/backend/server.py
Environment=PORT=8000
Environment=STOCK_DB_HOST=127.0.0.1
Environment=STOCK_DB_USER=stock
Environment=STOCK_DB_PASSWORD=*****
Environment=STOCK_DB_NAME=stock_review
Restart=always

[Install]
WantedBy=multi-user.target
```
启用：`systemctl enable --now stock-review`

### 2) 反向代理（可选，暴露 80/443）
用 Nginx 反代到 8000 即可用域名访问；HTTPS 由 Nginx 处理。
```
server {
  listen 80; server_name stock.example.com;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

### 3) 数据与调度
- 定时抓取已**内置**（交易日 15:35 / 16:30 / 18:00 / 20:00 自动刷新），无需额外 cron。
- 本地 JSON 缓存在 `backend/cache/`；若启用 MySQL，数据同时落库，可做历史回看。
- 升级代码后重启服务即可，缓存会自动复用当日数据。

## 目录结构
```
stock-review/
├── backend/
│   ├── server.py        # HTTP 服务 + 路由 + 定时调度 + 静态托管
│   ├── eastmoney.py     # 东方财富接口抓取与字段归一化
│   ├── demo.py          # 内置示例数据（接口为空时降级）
│   ├── cache/           # 按交易日缓存的 JSON
│   └── requirements.txt # 零依赖说明
└── frontend/
    ├── src/
    │   ├── api/         # 接口封装 + 全局状态
    │   ├── components/  # DataTable / BaseChart / StatCard / SourceTag
    │   ├── utils/       # 格式化 + 图表 option + useApi
    │   ├── views/       # 各看板页面
    │   ├── router/      # 路由
    │   ├── App.vue      # 布局（侧边栏 + 顶栏）
    │   └── main.js
    ├── index.html
    ├── vite.config.js   # 开发代理 /api -> 8000
    └── package.json
```

## 接口一览（后端）
`/api/status` `/api/summary` `/api/billboard` `/api/stocks/flow`
`/api/rapid-rise` `/api/capital-attention` `/api/sectors/hot`
`/api/sectors/outflow` `/api/institution` `/api/youzi` `POST /api/refresh`

### 资金监控接口（Tier A）
完全由已有的龙虎榜日数据派生，零新增数据源：
- `GET /api/monitor/daily?date=YYYY-MM-DD&type=all|inst_buy|inst_sell|inst_split|youzi&min_net=<万>&limit=200`
  → 当日统计 + 监控排行 + 机构共振信号 + 历史胜率
- `GET /api/monitor/signals?min_streak=3` → 机构连续净卖出预警（跨交易日）
- `GET /api/monitor/export?date=YYYY-MM-DD&type=...&min_net=...` → 当日监控报告 CSV（带 BOM，Excel 直接打开）

## 说明与边界
- 龙虎榜席位级明细依赖东方财富 `datacenter-web` 报表；当该明细不可用时，「机构 / 游资」由龙虎榜汇总中的席位说明文本（如「N 家机构买入」）与净买入额**派生**，并在界面注明。
- 真实席位级接口一旦可用，后端会在 `eastmoney.py` 中自动增强，无需改动前端。
- 所有金额单位为元，前端统一格式化为「亿 / 万」。
