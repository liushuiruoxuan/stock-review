"""量化回测 / 选股端点（v2 新增）。回测为后台任务，前端轮询进度。"""
import threading

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import db
import marketdb
from datasvc import tasks as tasksvc
from quant import engine as qe
from quant import metrics as qm
from quant import screener as qscr
from quant import strategies as qstrat

router = APIRouter()

_EQUITY_MAX_POINTS = 600   # 净值曲线最大采样点数（存 JSON）


@router.get("/api/quant/strategies")
def quant_strategies():
    return {"strategies": qstrat.list_strategies()}


@router.get("/api/quant/runs")
def quant_runs(limit: int = 20):
    return {"runs": marketdb.list_runs(limit=max(1, min(100, limit)))}


@router.get("/api/quant/runs/{run_id}")
def quant_run(run_id: int):
    run = marketdb.get_run(run_id)
    if not run:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return run


def _load_close_df(codes, start, end):
    """行情库 → close 矩阵（pivot）。"""
    rows = marketdb.load_bars(codes=codes, start=start, end=end, limit=2000000)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    pivot = df.pivot(index="trade_date", columns="code", values="close")
    pivot = pivot.sort_index()
    # 剔除数据过少的列（新股/长期停牌）
    pivot = pivot.dropna(axis=1, thresh=max(30, int(len(pivot) * 0.3)))
    return pivot


def _load_hot_signals(start, end):
    """龙虎榜跟随策略信号：hot_billboard 历史按日提取。"""
    signals = {}
    dates = db.list_dates() or []
    for d in dates:
        if d < start or d > end:
            continue
        hb = db.load_section(d, "hot_billboard") or legacy_fallback(d)
        if hb:
            signals[d] = [{"code": x.get("code"), "net_amt": x.get("net_amt")}
                          for x in hb if x.get("code")]
    return signals


def legacy_fallback(d):
    import server as legacy_server
    return legacy_server.load_data("hot_billboard", d) or []


def _run_backtest_thread(run_id, strategy, params, universe, start, end):
    """后台线程：加载行情 → 策略权重 → 引擎 → 指标 → 落库。"""
    try:
        marketdb.update_run(run_id, progress=10)
        # 股票池
        if universe == "liquid500":
            codes = marketdb.liquid_universe(top_n=500)
        elif universe == "liquid200":
            codes = marketdb.liquid_universe(top_n=200)
        else:
            codes = None  # 全部
        marketdb.update_run(run_id, progress=25)

        close_df = _load_close_df(codes, start, end)
        if close_df is None or close_df.empty:
            marketdb.update_run(run_id, status="failed",
                                error="行情库为空或无数据，请先执行行情同步")
            return
        marketdb.update_run(run_id, progress=45)

        extra = {}
        if strategy == "dragon_follow":
            extra["signals"] = _load_hot_signals(start, end)
        weights = qstrat.run_strategy(strategy, close_df, params, extra)
        marketdb.update_run(run_id, progress=65)

        # 基准：上证指数
        bench_rows = marketdb.load_bars(codes=["1.000001"],
                                        table=marketdb.T_INDEX_BARS,
                                        start=start, end=end)
        bench = None
        if bench_rows:
            b = pd.Series({r["trade_date"]: float(r["close"] or 0) for r in bench_rows})
            b = b.sort_index()
            bench = (1.0 + b.pct_change().fillna(0.0)).cumprod()

        result = qe.run(close_df, weights, benchmark=None)
        metrics = qm.compute(result["equity"], result["net"], result["trades"])
        marketdb.update_run(run_id, progress=85)

        # 净值曲线降采样
        eq = result["equity"]
        step = max(1, len(eq) // _EQUITY_MAX_POINTS)
        equity_pts = [{"date": str(dt)[:10], "nav": round(float(v), 6)}
                      for dt, v in eq.iloc[::step].items()]
        if equity_pts and str(eq.index[-1])[:10] != equity_pts[-1]["date"]:
            equity_pts.append({"date": str(eq.index[-1])[:10],
                               "nav": round(float(eq.iloc[-1]), 6)})
        if bench is not None:
            bpts = []
            bstep = max(1, len(bench) // _EQUITY_MAX_POINTS)
            for dt, v in bench.iloc[::bstep].items():
                bpts.append({"date": str(dt)[:10], "nav": round(float(v), 6)})
            equity_pts = [{"strategy": e["nav"],
                           "benchmark": next((b["nav"] for b in bpts
                                              if b["date"] == e["date"]), None),
                           "date": e["date"]} for e in equity_pts]

        trades = sorted(result["trades"], key=lambda t: t["entry"], reverse=True)[:500]
        marketdb.update_run(run_id, status="done", progress=100,
                            metrics=metrics, trades=trades, equity=equity_pts)
    except Exception as e:
        import traceback
        traceback.print_exc()
        marketdb.update_run(run_id, status="failed", error=str(e))


@router.post("/api/quant/backtest")
async def quant_backtest(request: Request):
    """提交回测任务。body: {strategy, params, universe, start, end}"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "请求体需为 JSON"}, status_code=400)
    strategy = body.get("strategy") or "ma_cross"
    if strategy not in qstrat.STRATEGIES:
        return JSONResponse({"error": "未知策略：%s" % strategy}, status_code=400)
    params = body.get("params") or {}
    universe = body.get("universe") or "liquid500"
    start = body.get("start") or "2019-01-01"
    end = body.get("end") or "2099-01-01"

    run_id = marketdb.create_run(strategy, params, universe, start, end)
    if run_id is None:
        return JSONResponse({"error": "MySQL 不可用，暂不支持回测"}, status_code=503)

    th = threading.Thread(target=_run_backtest_thread,
                          args=(run_id, strategy, params, universe, start, end),
                          daemon=True)
    th.start()
    return {"ok": True, "run_id": run_id}


@router.post("/api/quant/screener")
async def quant_screener(request: Request):
    """条件选股。body: 条件字典（见 quant.screener.DEFAULT_CONDITIONS）。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    return qscr.screen(body or {})
