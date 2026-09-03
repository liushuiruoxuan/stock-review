"""行情库 / 数据同步端点（v2 新增）。"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import marketdb
from datasvc import bars, tasks as tasksvc

router = APIRouter()


@router.get("/api/market/overview")
def market_overview():
    """行情库概况（大屏/量化页顶部状态）。"""
    return {
        "instruments": marketdb.count_instruments(),
        "calendar": marketdb.calendar_count(),
        "bars": marketdb.bars_count(),
        "latest_bar_date": marketdb.latest_bar_date(),
        "indexes": [{"code": i["code"], "name": i["name"]} for i in marketdb.INDEXES],
        "sync_tasks": tasksvc.snapshot()[:5],
    }


@router.get("/api/market/kline")
def market_kline(code: str, days: int = 120):
    """个股日K（优先行情库；库缺失时现场抓取不入库）。"""
    rows = marketdb.load_bars(codes=[code])
    if not rows:
        live = bars.fetch_daily_bars(code) or []
        rows = live[-days:] if live else []
    else:
        rows = rows[-days:]
    out = []
    for r in rows:
        out.append({
            "date": r["trade_date"],
            "open": float(r["open"]) if r.get("open") is not None else None,
            "close": float(r["close"]) if r.get("close") is not None else None,
            "high": float(r["high"]) if r.get("high") is not None else None,
            "low": float(r["low"]) if r.get("low") is not None else None,
            "pct_chg": float(r["pct_chg"]) if r.get("pct_chg") is not None else None,
        })
    return {"code": code, "count": len(out), "bars": out}


@router.get("/api/market/instruments")
def market_instruments(q: str = None, limit: int = 50, offset: int = 0):
    limit = max(1, min(200, int(limit)))
    return {"rows": marketdb.list_instruments(q=q, limit=limit, offset=offset),
            "total": marketdb.count_instruments()}


@router.get("/api/market/index")
def market_index(code: str = "1.000001", days: int = 120):
    """指数日K（近 N 日）。"""
    rows = marketdb.load_bars(codes=[code], table=marketdb.T_INDEX_BARS)
    rows = (rows or [])[-days:]
    out = [{"date": r["trade_date"], "close": float(r["close"] or 0),
            "pct_chg": float(r["pct_chg"]) if r.get("pct_chg") is not None else None}
           for r in rows]
    return {"code": code, "count": len(out), "bars": out}


@router.post("/api/market/sync")
def market_sync(scope: str = "bars_daily"):
    """触发数据同步后台任务。scope: instruments | calendar | bars_full | bars_daily"""
    if scope == "instruments":
        tid = tasksvc.run_task("sync_instruments", lambda t: bars.sync_instruments(),
                               note="同步标的主数据")
    elif scope == "calendar":
        tid = tasksvc.run_task("sync_calendar",
                               lambda t: bars.sync_calendar_and_index(),
                               note="同步交易日历+指数")
    elif scope == "bars_full":
        tid = tasksvc.run_task("sync_bars_full", bars.sync_bars_full,
                               note="日线全量同步（约12-20分钟，支持断点续传）")
    elif scope == "bars_daily":
        tid = tasksvc.run_task("sync_bars_daily", lambda t: bars.sync_bars_daily(),
                               note="日线增量同步")
    else:
        return JSONResponse({"error": "未知 scope: %s" % scope}, status_code=400)
    return {"ok": True, "task_id": tid}


@router.get("/api/market/sync/status")
def market_sync_status():
    return {"tasks": tasksvc.snapshot()}
