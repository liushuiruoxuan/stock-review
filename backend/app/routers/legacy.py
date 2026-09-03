"""
旧端点等价迁移（与 server.py 的 route_api / route_monitor / route_seats /
route_limitup 逐端点对齐：路径、参数、响应结构完全一致，前端零改动）。

改进（不改行为）：
  - monitor / seats 的重聚合加 5 分钟 TTL 缓存，刷新接口自动失效
  - /api/refresh 改为后台构建，立即返回（旧版为同步阻塞）
"""
import datetime
import threading
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

import db
import monitor
import server as legacy_server

router = APIRouter()

# ----------------------- 聚合缓存 -----------------------
_cache_lock = threading.Lock()
_cache = {"monitor": {"ts": 0, "data": None},
          "seats": {"ts": 0, "data": None}}
_CACHE_TTL = 300  # 秒


def _invalidate_caches():
    with _cache_lock:
        _cache["monitor"]["ts"] = 0
        _cache["monitor"]["data"] = None
        _cache["seats"]["ts"] = 0
        _cache["seats"]["data"] = None


def _monitor_ctx():
    """(dates, by_date, list_times) 聚合，TTL 缓存。"""
    with _cache_lock:
        c = _cache["monitor"]
        if c["data"] and (time.time() - c["ts"]) < _CACHE_TTL:
            return c["data"]
    dates = db.list_dates()
    by_date = monitor.gather(legacy_server.load_data, dates)
    list_times = monitor.build_list_times(by_date)
    data = (dates, by_date, list_times)
    with _cache_lock:
        _cache["monitor"]["ts"] = time.time()
        _cache["monitor"]["data"] = data
    return data


def _seats_ctx():
    """by_date_seats 聚合，TTL 缓存。"""
    with _cache_lock:
        c = _cache["seats"]
        if c["data"] and (time.time() - c["ts"]) < _CACHE_TTL:
            return c["data"]
    dates = db.list_seat_dates() or []
    by_date_seats = {}
    for d in dates:
        rows = db.load_seats(d)
        if rows:
            by_date_seats[d] = rows
    by_date_seats = dict(sorted(by_date_seats.items()))
    with _cache_lock:
        _cache["seats"]["ts"] = time.time()
        _cache["seats"]["data"] = by_date_seats
    return by_date_seats


def _to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _td_or_state(requested):
    return requested or legacy_server.STATE.get("trade_date") or legacy_server.em.resolve_trade_date()


# ----------------------- 基础看板 -----------------------
@router.get("/api/status")
def api_status():
    legacy_server.ensure_built()
    td = legacy_server.STATE.get("trade_date") or legacy_server.em.resolve_trade_date()
    return {
        "trade_date": td,
        "generated_at": legacy_server.STATE.get("generated_at"),
        "sources": legacy_server.STATE.get("sources"),
        "last_refresh_at": legacy_server.STATE.get("last_refresh_at"),
        "mysql": db.is_available(),
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/api/summary")
def api_summary(date: str = None):
    legacy_server.ensure_built()
    td = _td_or_state(date)
    return legacy_server.load_data("summary", td) or {}


@router.get("/api/billboard")
def api_billboard(date: str = None):
    legacy_server.ensure_built()
    return legacy_server.load_data("billboard", _td_or_state(date)) or []


def _lim(v, default=50, cap=300):
    n = _to_int(v, default)
    return max(1, min(cap, n))


@router.get("/api/stocks/flow")
def api_stocks_flow(limit: int = 50, date: str = None):
    legacy_server.ensure_built()
    data = legacy_server.load_data("stocks_flow", _td_or_state(date)) or []
    n = _lim(limit)
    return {"inflow": data[:n], "outflow": list(reversed(data[-n:]))}


@router.get("/api/rapid-rise")
def api_rapid_rise(limit: int = 50, date: str = None):
    legacy_server.ensure_built()
    data = legacy_server.load_data("rapid_rise", _td_or_state(date)) or []
    return data[:_lim(limit)]


@router.get("/api/capital-attention")
def api_capital_attention(limit: int = 50, date: str = None):
    legacy_server.ensure_built()
    data = legacy_server.load_data("capital_attention", _td_or_state(date)) or []
    return data[:_lim(limit)]


@router.get("/api/sectors/hot")
def api_sectors_hot(limit: int = 30, date: str = None):
    legacy_server.ensure_built()
    data = legacy_server.load_data("sectors_hot", _td_or_state(date)) or []
    return data[:_lim(limit, 30)]


@router.get("/api/sectors/outflow")
def api_sectors_outflow(limit: int = 30, date: str = None):
    legacy_server.ensure_built()
    data = legacy_server.load_data("sectors_outflow", _td_or_state(date)) or []
    return data[:_lim(limit, 30)]


@router.get("/api/institution")
def api_institution(date: str = None):
    legacy_server.ensure_built()
    return legacy_server.load_data("institution", _td_or_state(date)) or {"buy": [], "sell": []}


@router.get("/api/youzi")
def api_youzi(limit: int = 50, date: str = None):
    legacy_server.ensure_built()
    data = legacy_server.load_data("youzi", _td_or_state(date)) or []
    return data[:_lim(limit)]


@router.get("/api/hot-billboard")
def api_hot_billboard(limit: int = 200, date: str = None):
    legacy_server.ensure_built()
    td = _td_or_state(date)
    data = legacy_server.load_data("hot_billboard", td) or []
    if not data and not date:
        fb = db.list_limitup_dates() or []
        if fb:
            data = legacy_server.load_data("hot_billboard", fb[0]) or []
    return data[:_lim(limit, 200)]


@router.get("/api/history/dates")
def api_history_dates():
    return {"dates": db.list_dates(), "source": "mysql" if db.is_available() else "json"}


@router.get("/api/history")
def api_history(date: str = None):
    legacy_server.ensure_built()
    d = date or _td_or_state(None)
    hist = db.load_history(d)
    fallback = {k: (v if v is not None else legacy_server.load_cache(k, d))
                for k, v in hist.items()}
    return {
        "trade_date": d, "data": fallback,
        "source": "mysql" if db.is_available() else "json",
    }


# ----------------------- 资金监控（Tier A） -----------------------
@router.get("/api/monitor/daily")
def api_monitor_daily(date: str = None, min_net: int = 0, type: str = "all", limit: int = 200):
    legacy_server.ensure_built()
    td = _td_or_state(None)
    _, by_date, list_times = _monitor_ctx()
    if not by_date:
        return JSONResponse({"error": "暂无数据，请先刷新"}, status_code=404)
    date = date or td
    if date not in by_date:
        date = max(by_date.keys())
    min_net = max(0, _to_int(min_net, 0))
    type_filter = type or "all"
    limit = max(1, min(500, _to_int(limit, 200)))
    ranking = monitor.daily_ranking(by_date, list_times, date, min_net, type_filter, limit)
    res = monitor.resonance(by_date, date)
    wr = monitor.winrate(by_date)
    recs = by_date[date]
    cats = {"inst_buy": 0, "inst_sell": 0, "inst_split": 0, "youzi": 0}
    for r in recs:
        cats[r.get("category")] = cats.get(r.get("category"), 0) + 1
    stats = {
        "count": len(recs),
        "net_total_wan": sum((r.get("net_amt") or 0) for r in recs) / 1e4,
        "inst_buy": cats["inst_buy"], "inst_sell": cats["inst_sell"],
        "inst_split": cats["inst_split"], "youzi": cats["youzi"],
    }
    return {
        "date": date,
        "available_dates": list(reversed(list(by_date.keys()))),
        "stats": stats,
        "ranking": ranking,
        "resonance": res,
        "winrate": wr,
        "filters": {"min_net": min_net, "type": type_filter},
    }


@router.get("/api/monitor/signals")
def api_monitor_signals(min_streak: int = 3):
    legacy_server.ensure_built()
    td = _td_or_state(None)
    _, by_date, _lt = _monitor_ctx()
    min_streak = max(2, _to_int(min_streak, 3))
    sigs = monitor.continuous_sell_signals(by_date, min_streak=min_streak, until_date=td)
    return {"date": td, "min_streak": min_streak, "signals": sigs}


@router.get("/api/monitor/export")
def api_monitor_export(date: str = None, min_net: int = 0, type: str = "all"):
    legacy_server.ensure_built()
    td = _td_or_state(None)
    _, by_date, list_times = _monitor_ctx()
    if not by_date:
        return JSONResponse({"error": "暂无数据"}, status_code=404)
    date = date or td
    if date not in by_date:
        date = max(by_date.keys())
    csv_text = monitor.to_csv(by_date, list_times, date,
                              max(0, _to_int(min_net, 0)), type or "all")
    body = csv_text.encode("utf-8-sig")
    return Response(content=body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="monitor_%s.csv"' % date})


# ----------------------- 席位监控（Tier B） -----------------------
@router.get("/api/seats/daily")
def api_seats_daily(date: str = None, seat: str = None, side: str = None,
                    type: str = None, min_net: int = 0, limit: int = 2000, synd: int = 3):
    legacy_server.ensure_built()
    td = _td_or_state(None)
    by_date_seats = _seats_ctx()
    if not by_date_seats:
        return JSONResponse({"error": "暂无席位数据，请先抓取龙虎榜席位"}, status_code=404)
    date = date or td
    if date not in by_date_seats:
        date = max(by_date_seats.keys())
    min_net = _to_int(min_net, 0)
    limit = max(1, min(5000, _to_int(limit, 2000)))
    seats = db.load_seats(date, seat=seat, side=side, seat_type=type,
                          min_net=min_net, limit=limit)
    if seats is None:
        seats = []
    stats = monitor.compute_seat_stats(seats)
    synd_data = monitor.seat_syndicate(by_date_seats, date,
                                       threshold=max(2, _to_int(synd, 3)))
    ranks = monitor.seat_rankings(by_date_seats, date)
    return {
        "date": date,
        "available_dates": list(reversed(list(by_date_seats.keys()))),
        "stats": stats,
        "seats": seats,
        "syndicate": synd_data,
        "rankings": ranks,
        "filters": {"seat": seat, "side": side, "type": type, "min_net": min_net},
    }


@router.get("/api/seats/profile")
def api_seats_profile(seat: str = None):
    if not seat:
        return {"seat": seat, "profile": None}
    by_date_seats = _seats_ctx()
    return {"seat": seat, "profile": monitor.seat_profile(by_date_seats, seat)}


@router.get("/api/seats/signals")
def api_seats_signals(min_streak: int = 3):
    legacy_server.ensure_built()
    td = _td_or_state(None)
    by_date_seats = _seats_ctx()
    min_streak = max(2, _to_int(min_streak, 3))
    sigs = monitor.seat_continuous_sell(by_date_seats, min_streak=min_streak, until_date=td)
    return {"date": td, "min_streak": min_streak, "signals": sigs}


@router.get("/api/seats/export")
def api_seats_export(date: str = None, seat: str = None, side: str = None,
                     type: str = None, min_net: int = 0):
    legacy_server.ensure_built()
    td = _td_or_state(None)
    by_date_seats = _seats_ctx()
    if not by_date_seats:
        return JSONResponse({"error": "暂无席位数据"}, status_code=404)
    date = date or td
    if date not in by_date_seats:
        date = max(by_date_seats.keys())
    seats = db.load_seats(date, seat=seat, side=side, seat_type=type,
                          min_net=_to_int(min_net, 0), limit=100000)
    if seats is None:
        seats = []
    csv_text = monitor.seats_to_csv(seats)
    body = csv_text.encode("utf-8-sig")
    return Response(content=body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="seats_%s.csv"' % date})


# ----------------------- 涨停板（开盘红） -----------------------
@router.get("/api/limitup/daily")
def api_limitup_daily(date: str = None):
    dates = db.list_limitup_dates()
    if not dates:
        return JSONResponse({"error": "暂无涨停数据，请先刷新或回填历史",
                             "available_dates": []}, status_code=404)
    date = date or dates[0]
    if date not in dates:
        date = dates[0]
    rows = db.load_limit_up(date) or []

    bb = db.load_section(date, "billboard") or []
    bb_map = {b.get("code"): b for b in bb if b.get("code")}
    seats = db.load_seats(date) or []
    seat_by_code = {}
    for s in seats:
        seat_by_code.setdefault(s.get("security_code"), []).append(s)

    def _seat_type(name):
        if name and ("机构专用" in name or "沪股通" in name or "深股通" in name):
            return "机构"
        return "游资"

    enriched = []
    for r in rows:
        code = r.get("code")
        item = dict(r)
        b = bb_map.get(code)
        if b:
            item["billboard"] = {
                "net_amt": b.get("net_amt"),
                "inst_buy_cnt": b.get("inst_buy_cnt"),
                "inst_sell_cnt": b.get("inst_sell_cnt"),
                "explain": b.get("explain"),
                "reason": b.get("reason"),
            }
        ss = seat_by_code.get(code)
        if ss:
            seats_out = [{
                "seat_name": x.get("seat_name"),
                "side": x.get("side"),
                "net_amt": x.get("net_amt"),
                "buy_amt": x.get("buy_amt"),
                "sell_amt": x.get("sell_amt"),
                "type": _seat_type(x.get("seat_name")),
            } for x in ss[:14]]
            inst_net = sum((x.get("net_amt") or 0) for x in ss
                           if _seat_type(x.get("seat_name")) == "机构")
            youzi_net = sum((x.get("net_amt") or 0) for x in ss
                            if _seat_type(x.get("seat_name")) == "游资")
            item["seats"] = seats_out
            item["seat_summary"] = {"inst_net": inst_net, "youzi_net": youzi_net,
                                    "seat_cnt": len(ss)}
        enriched.append(item)

    limit_dist = {}
    seal_total = 0
    net_total = 0
    theme_cnt = {}
    for r in rows:
        tag = r.get("limit_tag") or ("%d连板" % (r.get("limit_count") or 1))
        limit_dist[tag] = limit_dist.get(tag, 0) + 1
        seal_total += (r.get("seal_money") or 0)
        net_total += (r.get("net_inflow") or 0)
        for t in (r.get("themes") or "").replace("、", ",").split(","):
            t = t.strip()
            if t:
                theme_cnt[t] = theme_cnt.get(t, 0) + 1
    theme_top = sorted(theme_cnt.items(), key=lambda x: x[1], reverse=True)[:12]
    stats = {
        "count": len(rows),
        "max_limit": max([(r.get("limit_count") or 1) for r in rows] or [0]),
        "limit_dist": limit_dist,
        "seal_total": seal_total,
        "net_inflow_total": net_total,
        "theme_top": [{"theme": k, "count": v} for k, v in theme_top],
        "with_billboard": sum(1 for r in enriched if r.get("billboard")),
    }
    return {
        "date": date,
        "available_dates": list(reversed(dates)),
        "count": len(enriched),
        "stats": stats,
        "ranking": enriched,
    }


@router.get("/api/limitup/news")
def api_limitup_news(code: str = "", name: str = ""):
    legacy_server.ensure_built()
    news = legacy_server.em.fetch_stock_news(code, name) if name else []
    return {
        "code": code, "name": name, "news": news,
        "note": "近期公告按股票名称尽力匹配（免费源无按股新闻接口，仅供复盘参考）",
    }


# ----------------------- 手动刷新 -----------------------
_refresh_lock = threading.Lock()


@router.post("/api/refresh")
async def api_refresh(request: Request):
    """触发一次完整构建（后台执行，立即返回）。"""
    if _refresh_lock.acquire(blocking=False):

        def _run():
            try:
                td = legacy_server.em.resolve_trade_date()
                legacy_server.build_all(td, force=True)
                _invalidate_caches()
            finally:
                _refresh_lock.release()

        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True, "async": True,
                "state": legacy_server.STATE}
    return {"ok": True, "async": True, "note": "已有构建在进行中",
            "state": legacy_server.STATE}
