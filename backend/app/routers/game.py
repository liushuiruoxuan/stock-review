"""资金博弈端点（v2 新增）：席位 × 涨停 × 龙虎榜三路信号融合。"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import db
import marketdb
import monitor
import server as legacy_server
from .legacy import _monitor_ctx, _seats_ctx, _td_or_state

router = APIRouter()


@router.get("/api/game/overview")
def game_overview(date: str = None):
    """博弈总览：多空对比 / 席位热度 / 抱团 / 连板梯队 / 共振 / 热点股。"""
    legacy_server.ensure_built()
    td = _td_or_state(date)

    out = {"date": td}

    # ---- 多空对比（席位口径）----
    by_date_seats = _seats_ctx()
    battle = {"date": None, "buy_total": 0.0, "sell_total": 0.0,
              "by_type": {}, "stock_cnt": 0}
    if by_date_seats:
        seat_date = date or td
        if seat_date not in by_date_seats:
            seat_date = max(by_date_seats.keys())
        rows = by_date_seats.get(seat_date, [])
        codes = set()
        for s in rows:
            t = monitor.seat_type_of(s.get("seat_name"))
            e = battle["by_type"].setdefault(
                t, {"buy": 0.0, "sell": 0.0, "cnt": 0})
            b = float(s.get("buy_amt") or 0)
            sl = float(s.get("sell_amt") or 0)
            e["buy"] += b
            e["sell"] += sl
            e["cnt"] += 1
            battle["buy_total"] += b
            battle["sell_total"] += sl
            if s.get("code"):
                codes.add(s["code"])
        battle["date"] = seat_date
        battle["stock_cnt"] = len(codes)
    out["battle"] = battle

    # ---- 席位热度 / 抱团 ----
    if by_date_seats:
        seat_date = battle["date"]
        ranks = monitor.seat_rankings(by_date_seats, seat_date)
        synd = monitor.seat_syndicate(by_date_seats, seat_date)
        out["seat_heat"] = ranks
        out["syndicate"] = synd
    else:
        out["seat_heat"] = None
        out["syndicate"] = None

    # ---- 连板梯队 + 题材 ----
    lu_dates = db.list_limitup_dates() or []
    out["ladder"] = None
    if lu_dates:
        lu_date = date if date in lu_dates else lu_dates[0]
        rows = db.load_limit_up(lu_date) or []
        limit_dist = {}
        theme_cnt = {}
        broken = 0
        for r in rows:
            tag = r.get("limit_tag") or ("%d连板" % (r.get("limit_count") or 1))
            limit_dist[tag] = limit_dist.get(tag, 0) + 1
            # open_time>0 视为曾开板（炸板）
            if r.get("open_time"):
                broken += 1
            for t in (r.get("themes") or "").replace("、", ",").split(","):
                t = t.strip()
                if t:
                    theme_cnt[t] = theme_cnt.get(t, 0) + 1
        theme_top = sorted(theme_cnt.items(), key=lambda x: x[1], reverse=True)[:10]
        ladder_top = sorted(rows, key=lambda r: ((r.get("limit_count") or 1),
                                                 r.get("seal_money") or 0), reverse=True)[:12]
        out["ladder"] = {
            "date": lu_date,
            "count": len(rows),
            "max_limit": max([(r.get("limit_count") or 1) for r in rows] or [0]),
            "limit_dist": limit_dist,
            "broken_rate": round(broken / len(rows) * 100, 1) if rows else None,
            "theme_top": [{"theme": k, "count": v} for k, v in theme_top],
            "top": [{"code": r.get("code"), "name": r.get("name"),
                     "limit_count": r.get("limit_count"), "limit_tag": r.get("limit_tag"),
                     "reason": r.get("reason"), "themes": r.get("themes"),
                     "seal_money": r.get("seal_money")} for r in ladder_top],
        }

    # ---- 机构共振 / 连续净卖预警 ----
    try:
        _, by_date, _lt = _monitor_ctx()
        if by_date:
            m_date = date or td
            if m_date not in by_date:
                m_date = max(by_date.keys())
            out["resonance"] = monitor.resonance(by_date, m_date)
            sigs = monitor.continuous_sell_signals(by_date, min_streak=3, until_date=td)
            out["continuous_sell"] = sigs[:10]
        else:
            out["resonance"] = None
            out["continuous_sell"] = []
    except Exception:
        out["resonance"] = None
        out["continuous_sell"] = []

    # ---- 热点重合榜（博弈核心标的池）----
    hb = legacy_server.load_data("hot_billboard", td) or []
    if not hb and not date:
        fb = db.list_limitup_dates() or []
        if fb:
            hb = legacy_server.load_data("hot_billboard", fb[0]) or []
    out["dragon"] = hb[:12]

    return out


@router.get("/api/game/stock/{code}")
def game_stock(code: str, date: str = None):
    """个股博弈画像：上榜历史 / 席位进出 / 涨停历史 / K线。"""
    legacy_server.ensure_built()
    td = _td_or_state(date)

    # ---- 龙虎榜上榜历史 ----
    _, by_date, _lt = _monitor_ctx()
    history = []
    if by_date:
        for d in sorted(by_date.keys(), reverse=True):
            for r in by_date[d]:
                if r.get("code") == code:
                    row = dict(r)
                    row["date"] = d
                    history.append(row)
    history = history[:60]

    # ---- 席位进出明细（全部历史，倒序）----
    by_date_seats = _seats_ctx()
    seats_all = []
    seat_names = {}
    for d in sorted(by_date_seats.keys(), reverse=True):
        for s in by_date_seats[d]:
            if (s.get("code") or s.get("security_code")) == code:
                row = dict(s)
                row["date"] = d
                row["type"] = monitor.seat_type_of(s.get("seat_name"))
                seats_all.append(row)
                nm = s.get("seat_name")
                if nm:
                    e = seat_names.setdefault(nm, {"seat_name": nm, "net": 0.0,
                                                   "cnt": 0, "type": monitor.seat_type_of(nm)})
                    e["net"] += float(s.get("net_amt") or 0)
                    e["cnt"] += 1
    seats_all = seats_all[:200]

    # 席位胜率（用东财 rise_prob_3d）
    seat_rank = sorted(seat_names.values(), key=lambda x: x["net"], reverse=True)[:15]
    for d in sorted(by_date_seats.keys(), reverse=True):
        for s in by_date_seats[d]:
            nm = s.get("seat_name")
            if nm in seat_names:
                rp = monitor._to_float(s.get("rise_prob_3d"))
                if rp is not None:
                    seat_names[nm].setdefault("rise_probs", []).append(rp)
    seat_win = []
    for e in seat_rank:
        rps = e.get("rise_probs") or []
        seat_win.append({
            "seat_name": e["seat_name"], "type": e["type"], "cnt": e["cnt"],
            "net_wan": round(e["net"] / 1e4, 1),
            "avg_rise_3d": round(sum(rps) / len(rps), 1) if rps else None,
        })

    # ---- 涨停历史 ----
    limitup_hist = []
    for d in (db.list_limitup_dates() or [])[:120]:
        for r in (db.load_limit_up(d) or []):
            if r.get("code") == code:
                limitup_hist.append({
                    "date": d, "limit_count": r.get("limit_count"),
                    "limit_tag": r.get("limit_tag"), "reason": r.get("reason"),
                    "seal_money": r.get("seal_money"),
                })
    limitup_hist = limitup_hist[:40]

    # ---- K线（行情库，120 日）----
    bars_rows = marketdb.load_bars(codes=[code])
    bars_rows = (bars_rows or [])[-120:]
    kline = [{"date": r["trade_date"], "close": float(r["close"] or 0),
              "pct_chg": float(r["pct_chg"]) if r.get("pct_chg") is not None else None}
             for r in bars_rows]

    # ---- 结论标签（规则推理）----
    tags = []
    try:
        inst_net = sum(float(s.get("net_amt") or 0) for s in seats_all
                       if s.get("type") in ("inst", "hk"))
        youzi_net = sum(float(s.get("net_amt") or 0) for s in seats_all
                        if s.get("type") == "youzi")
        recent_lu = [x for x in limitup_hist[:5]]
        if inst_net > 5e7:
            tags.append("机构主导")
        if youzi_net > 5e7:
            tags.append("游资进攻")
        if inst_net < -3e7:
            tags.append("机构撤退")
        synd_cnt = {}
        for s in seats_all[:40]:
            if s.get("type") == "youzi":
                synd_cnt[s["date"]] = synd_cnt.get(s["date"], 0) + 1
        if synd_cnt and max(synd_cnt.values()) >= 3:
            tags.append("游资抱团")
        if recent_lu and (recent_lu[0].get("limit_count") or 1) >= 3:
            tags.append("高位连板")
        if history and len(history) >= 5:
            tags.append("频繁上榜")
        if not tags:
            tags.append("观望")
    except Exception:
        pass

    return {
        "code": code,
        "name": (history[0].get("name") if history else
                 (seats_all[0].get("name") if seats_all else code)),
        "date": td,
        "billboard_history": history,
        "seats_all": seats_all,
        "seat_win": seat_win,
        "limitup_history": limitup_hist,
        "kline": kline,
        "tags": tags,
    }
