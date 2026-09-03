"""
条件选股器：最新交易日行情快照 × 涨停/席位因子，多条件筛选。

数据源：
  - sr_daily_bars 最新交易日快照（涨跌幅/换手/成交额）
  - stock_review_limitup 当日涨停（连板数/封单/概念）
  - stock_review_seat 当日席位净买（机构/游资分项）
"""
import db
import marketdb


def _latest_bar_date():
    return marketdb.latest_bar_date()


def _snapshot(bd):
    """最新交易日行情快照 {code: row}。"""
    rows = marketdb.load_bars(start=bd)
    out = {}
    for r in rows:
        if r["trade_date"] == bd:
            out[r["code"]] = r
    return out


def _limitup_map(td):
    """当日涨停 {code: row}。td 为涨停交易日（可能与行情日不同，取最近）。"""
    dates = db.list_limitup_dates() or []
    if not dates:
        return {}, None
    use = td if td in dates else dates[0]
    m = {}
    for r in (db.load_limit_up(use) or []):
        m[r.get("code")] = r
    return m, use


def _seat_net_map(td):
    """当日席位净买 {code: {inst_net, youzi_net, net}}。"""
    rows = db.load_seats(td) or []
    out = {}
    for s in rows:
        c = s.get("code") or s.get("security_code")
        if not c:
            continue
        e = out.setdefault(c, {"inst_net": 0.0, "youzi_net": 0.0, "net": 0.0})
        n = float(s.get("net_amt") or 0)
        name = s.get("seat_name") or ""
        if "机构专用" in name:
            e["inst_net"] += n
        elif ("沪股通" in name or "深股通" in name or "陆股通" in name):
            e["inst_net"] += n
        else:
            e["youzi_net"] += n
        e["net"] += n
    return out


DEFAULT_CONDITIONS = {
    "pct_min": None, "pct_max": None,
    "turnover_min": None, "turnover_max": None,
    "amount_min": None,          # 元
    "limit_count_min": None,     # 连板数 >=
    "inst_net_min": None,        # 机构净买 >= (元)
    "youzi_net_min": None,       # 游资净买 >= (元)
    "sort": "pct_chg",           # pct_chg | amount | turnover | limit_count | inst_net
    "limit": 100,
}


def screen(conditions=None):
    """执行筛选，返回 {bar_date, limitup_date, count, rows}。"""
    cond = dict(DEFAULT_CONDITIONS)
    cond.update({k: v for k, v in (conditions or {}).items() if v is not None})

    bd = _latest_bar_date()
    if not bd:
        return {"bar_date": None, "count": 0, "rows": [],
                "hint": "行情库为空，请先在「行情同步」中拉取日线数据"}

    snap = _snapshot(bd)
    lu_map, lu_date = _limitup_map(bd)
    seat_map = _seat_net_map(lu_date or bd)

    inst_names = {i["code"]: i["name"] for i in marketdb.list_instruments(limit=100000)}

    rows = []
    for code, bar in snap.items():
        pct = float(bar.get("pct_chg") or 0)
        turnover = float(bar.get("turnover") or 0)
        amount = float(bar.get("amount") or 0)
        lu = lu_map.get(code) or {}
        seat = seat_map.get(code) or {}

        if cond.get("pct_min") is not None and pct < float(cond["pct_min"]):
            continue
        if cond.get("pct_max") is not None and pct > float(cond["pct_max"]):
            continue
        if cond.get("turnover_min") is not None and turnover < float(cond["turnover_min"]):
            continue
        if cond.get("turnover_max") is not None and turnover > float(cond["turnover_max"]):
            continue
        if cond.get("amount_min") is not None and amount < float(cond["amount_min"]):
            continue
        lc = int(lu.get("limit_count") or 0)
        if cond.get("limit_count_min") is not None and lc < int(cond["limit_count_min"]):
            continue
        if cond.get("inst_net_min") is not None and seat.get("inst_net", 0) < float(cond["inst_net_min"]):
            continue
        if cond.get("youzi_net_min") is not None and seat.get("youzi_net", 0) < float(cond["youzi_net_min"]):
            continue

        rows.append({
            "code": code,
            "name": inst_names.get(code) or lu.get("name") or code,
            "close": float(bar.get("close") or 0),
            "pct_chg": pct,
            "turnover": turnover,
            "amount": amount,
            "limit_count": lc or None,
            "limit_tag": lu.get("limit_tag"),
            "themes": lu.get("themes"),
            "inst_net": seat.get("inst_net"),
            "youzi_net": seat.get("youzi_net"),
        })

    sort_key = cond.get("sort") or "pct_chg"
    def _sk(r):
        v = r.get(sort_key)
        return v if isinstance(v, (int, float)) and v is not None else -1e18
    rows.sort(key=_sk, reverse=True)
    rows = rows[: int(cond.get("limit", 100))]

    return {
        "bar_date": bd,
        "limitup_date": lu_date,
        "count": len(rows),
        "rows": rows,
    }
