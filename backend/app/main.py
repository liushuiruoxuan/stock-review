"""
FastAPI 主入口（v2）。

启动：  uvicorn app.main:app --host 0.0.0.0 --port 8000
        （或 python run.py —— 自动降级到旧 server.py）

职责：
  - 挂载全部路由（legacy 等价迁移 + market/bigscreen/game/quant 新模块）
  - 托管 frontend/dist（SPA 回退）
  - 启动时初始化 MySQL（旧三表 + 行情库五表）与定时调度
  - 初始数据构建放后台线程，不阻塞服务启动
"""
import os
import sys
import threading

# backend/ 加入 sys.path（app 包内引用 eastmoney/db/server 等平铺模块）
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402

from app.routers import bigscreen, game, legacy, market, quant  # noqa: E402

DIST_DIR = os.path.normpath(os.path.join(BACKEND_DIR, "..", "frontend", "dist"))

app = FastAPI(title="stock-review", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(legacy.router)
app.include_router(market.router)
app.include_router(bigscreen.router)
app.include_router(game.router)
app.include_router(quant.router)


@app.get("/api/{rest:path}")
def api_404(rest: str):
    """未匹配到的 /api 路径统一 404（与旧行为一致）。"""
    return JSONResponse({"error": "unknown api: /api/%s" % rest}, status_code=404)


@app.get("/{full_path:path}")
def spa(full_path: str):
    """静态资源 + SPA 回退（/bigscreen /game /quant 等前端路由）。"""
    if not os.path.isdir(DIST_DIR):
        return JSONResponse({
            "hint": "前端未构建。请先 cd frontend && npm install && npm run build，"
                    "或开发模式 npm run dev (默认代理到本服务)。",
            "api": "try GET /api/status",
        })
    if full_path:
        fp = os.path.normpath(os.path.join(DIST_DIR, full_path))
        if fp.startswith(DIST_DIR) and os.path.isfile(fp):
            return FileResponse(fp)
    index = os.path.join(DIST_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return JSONResponse({"error": "not found"}, status_code=404)


def _startup_init():
    """后台线程：MySQL 初始化 → 初始构建 → 补齐历史 → 启动调度。"""
    import time
    try:
        import db
        ok = db.init_db()
        for _ in range(15):
            if ok:
                break
            print("[startup] 等待 MySQL 就绪...")
            time.sleep(3)
            ok = db.init_db()
        if ok:
            print("[startup] MySQL 初始化成功。")
        else:
            print("[startup] MySQL 未就绪，回退 JSON 缓存（运行中自动重试）。")
    except Exception as e:
        print("[startup] MySQL 初始化异常：", e)

    try:
        import marketdb
        marketdb.init_tables()
    except Exception as e:
        print("[startup] 行情库初始化异常：", e)

    try:
        import server as legacy_server
        legacy_server.ensure_built(force=False)
        try:
            legacy_server.backfill_recent()
        except Exception as e:
            print("[startup] backfill 异常：", e)
    except Exception as e:
        print("[startup] 初始构建异常：", e)

    try:
        from datasvc import jobs
        jobs.start()
    except Exception as e:
        print("[startup] 调度器启动异常：", e)
    print("[startup] 初始化完成")


@app.on_event("startup")
def on_startup():
    threading.Thread(target=_startup_init, daemon=True).start()
    print("=" * 60)
    print("stock-review v2 (FastAPI)  |  http://localhost:%s"
          % os.environ.get("PORT", "8000"))
    print("=" * 60)
