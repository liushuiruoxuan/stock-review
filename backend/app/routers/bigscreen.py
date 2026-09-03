"""大屏聚合端点（v2 新增）：一次请求返回整块大屏数据，前端 30s 轮询。"""
import datetime

from fastapi import APIRouter

import db
import marketdb
import monitor
import server as legacy_server
from datasvc import globfin
from .legacy import _monitor_ctx, _seats_ctx, _td_or_state

router = APIRouter()


@router.get("/api/bigscreen/overview")
def bigscreen_overview(date: str = None):
    legacy_server.ensure_built()
    td = _td_or_state(date)

    out = {
        "trade_date": td,
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "indexes": marketdb.index_snapshot(days=60),
    }

    # 汇总 + 热点重合榜 Top10
    out["summary"] = legacy_server.load_data("summary", td) or {}
    hb = legacy_server.load_data("hot_billboard", td) or []
    if not hb and not date:
        fb = db.list_limitup_dates() or []
        if fb:
            hb = legacy_server.load_data("hot_billboard", fb[0]) or []
    out["hot_billboard"] = hb[:10]

    # 板块 / 极速拉升
    out["sectors_hot"] = (legacy_server.load_data("sectors_hot", td) or [])[:8]
    out["rapid_rise"] = (legacy_server.load_data("rapid_rise", td) or [])[:8]

    # 涨停梯队
    lu_dates = db.list_limitup_dates() or []
    out["limitup"] = {"available": bool(lu_dates), "date": lu_dates[0] if lu_dates else None,
                      "stats": None, "top": []}
    if lu_dates:
        rows = db.load_limit_up(lu_dates[0]) or []
        limit_dist = {}
        for r in rows:
            tag = r.get("limit_tag") or ("%d连板" % (r.get("limit_count") or 1))
            limit_dist[tag] = limit_dist.get(tag, 0) + 1
        top = sorted(rows, key=lambda r: ((r.get("limit_count") or 1),
                                          r.get("seal_money") or 0), reverse=True)[:8]
        out["limitup"] = {
            "available": True, "date": lu_dates[0],
            "stats": {"count": len(rows),
                      "max_limit": max([(r.get("limit_count") or 1) for r in rows] or [0]),
                      "limit_dist": limit_dist},
            "top": [{"code": r.get("code"), "name": r.get("name"),
                     "limit_count": r.get("limit_count"), "limit_tag": r.get("limit_tag"),
                     "reason": r.get("reason"), "seal_money": r.get("seal_money")}
                    for r in top],
        }

    # 席位攻击力（游资净买 Top + 机构净买 Top）
    try:
        by_date_seats = _seats_ctx()
        if by_date_seats:
            seat_date = td if td in by_date_seats else max(by_date_seats.keys())
            rows = by_date_seats.get(seat_date, [])
            agg = {}
            for s in rows:
                name = s.get("seat_name") or ""
                if not name:
                    continue
                e = agg.setdefault(name, {"seat_name": name, "net": 0.0, "cnt": 0,
                                          "type": monitor.seat_type_of(name)})
                e["net"] += float(s.get("net_amt") or 0)
                e["cnt"] += 1
            youzi = [a for a in agg.values() if a["type"] == "youzi"]
            inst = [a for a in agg.values() if a["type"] in ("inst", "hk")]
            youzi.sort(key=lambda x: x["net"], reverse=True)
            inst.sort(key=lambda x: x["net"], reverse=True)
            out["seats"] = {
                "date": seat_date,
                "youzi_top": [{"seat_name": a["seat_name"],
                               "net_wan": round(a["net"] / 1e4, 1)} for a in youzi[:8]],
                "inst_top": [{"seat_name": a["seat_name"],
                              "net_wan": round(a["net"] / 1e4, 1)} for a in inst[:8]],
            }
        else:
            out["seats"] = None
    except Exception:
        out["seats"] = None

    # 跑马灯：席位动态 + 涨停原因
    ticker = []
    try:
        if out.get("seats"):
            for a in out["seats"]["youzi_top"][:5]:
                ticker.append({"text": "游资 %s 净买 %.0f 万" % (a["seat_name"][:16], a["net_wan"]),
                               "tone": "up"})
        for r in out["limitup"].get("top", [])[:6]:
            if r.get("reason"):
                ticker.append({"text": "%s（%s）：%s" % (r.get("name"), r.get("limit_tag"),
                                                        (r.get("reason") or "")[:30]),
                               "tone": "neutral"})
        for r in (out.get("hot_billboard") or [])[:5]:
            if r.get("net_amt") is not None:
                ticker.append({"text": "%s 龙虎榜净买 %.0f 万" % (
                    r.get("name"), (r.get("net_amt") or 0) / 1e4), "tone": "up"})
    except Exception:
        pass
    out["ticker"] = ticker[:18]

    # 全球财经：行情（美股/港股/亚太/欧洲 + 商品 + 外汇）+ 财经要闻
    try:
        out["global"] = globfin.snapshot(limit=12)
    except Exception as e:
        print("[bigscreen] 全球财经抓取异常：", e)
        out["global"] = {"quotes": {"updated_at": None, "quotes": []}, "news": []}

    return out
