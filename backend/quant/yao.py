"""
妖股洞察（v2）：全市场妖股识别 + 妖气指数 + 生命周期阶段 + 个股画像。

口径（默认近 60 个交易日，均基于 sr_daily_bars 收盘数据）：
  妖气指数 0-100 加权：
    区间涨幅 40%（200% 封顶归一）
    连板高度 25%（6 板封顶；涨停判定 pct_chg>=阈值-0.3，主板 9.8 / 创业科创 19.8）
    换手热度 15%（近 10 日均换手，25% 封顶）
    量能放大 10%（近 10 日均额 / 窗口均额，5 倍封顶）
    游资介入 10%（上榜天数 6 分 + 游资席位家数 4 分）
  候选门槛：区间涨幅>=50% 或 最高连板>=3；且最近一日有成交（额>=3000 万），
           剔除 ST/退市与长期停牌（窗口不足 10 根 K 线）。

  生命周期（启发式，按优先级）：
    分歧/退潮：乖离>=25% 且（近 3 日累计<-5% 或 单日<=-5% 或 高位放量滞涨）
    加速：区间涨幅>=100% 或 乖离>=30%
    主升：区间涨幅>=30%
    启动：其余

风险信号：
  高位放量滞涨 / 龙虎榜净卖转向 / 乖离率过高(>40%) / 天量长上影

对外接口：
  scan(days=60, top=20)          妖股榜
  profile(code, days=60)         个股画像（走势+阶段+席位+涨停明细+风险）
"""
import datetime
import time

import db
import marketdb
import monitor

# ---------------- 缓存 ----------------
_LIST_TTL = 300          # 妖股榜缓存 5 分钟
_SEAT_TTL = 600          # 席位聚合缓存 10 分钟
_LIMITUP_TTL = 600       # 涨停明细缓存 10 分钟
_CACHE = {"list": {}, "seat": {"ts": 0.0, "data": None},
          "limitup": {"ts": 0.0, "data": None}}


def _limit_threshold(code):
    """收盘涨停判定阈值（%）。创业 300/301 与科创 688/689 为 20cm。"""
    return 19.8 if str(code).startswith(("300", "301", "688", "689")) else 9.8


def _window_start(end, days):
    """end 往前约 days 个交易日对应的日历起点（1.8 倍冗余，覆盖节假日）。"""
    return (datetime.date.fromisoformat(end)
            - datetime.timedelta(days=int(days * 1.8) + 5)).isoformat()


# ---------------- 席位 / 涨停聚合（带缓存） ----------------

def _seat_stats(win_dates):
    """近窗口席位聚合：
    {code: {lb_days, youzi_names:set, youzi_cnt, net_sum, last_net, last_date}}"""
    c = _CACHE["seat"]
    if c["data"] and time.time() - c["ts"] < _SEAT_TTL:
        return c["data"]
    out = {}
    seen = set()                      # (code, date) 上榜天数去重
    for d in (win_dates or [])[:45]:
        for s in (db.load_seats(d) or []):
            code = s.get("code") or s.get("security_code")
            if not code:
                continue
            name = s.get("seat_name") or ""
            net = float(s.get("net_amt") or 0)
            e = out.setdefault(code, {"lb_days": 0, "youzi_names": set(),
                                      "net_sum": 0.0, "last_net": None,
                                      "last_date": None})
            e["net_sum"] += net
            if monitor.seat_type_of(name) == "youzi":
                e["youzi_names"].add(name)
            key = (code, d)
            if key not in seen:
                seen.add(key)
                e["lb_days"] += 1
            if e["last_date"] is None or d > e["last_date"]:
                e["last_date"] = d
                e["last_net"] = net
    for e in out.values():
        e["youzi_cnt"] = len(e["youzi_names"])
    if out:
        c["data"] = out
        c["ts"] = time.time()
    return out


def _limitup_map(win_dates):
    """近窗口涨停明细 {code: [{date,limit_count,limit_tag,reason,seal_money}]}。"""
    c = _CACHE["limitup"]
    if c["data"] and time.time() - c["ts"] < _LIMITUP_TTL:
        return c["data"]
    out = {}
    for d in (win_dates or [])[:45]:
        for r in (db.load_limit_up(d) or []):
            code = r.get("code")
            if not code:
                continue
            out.setdefault(code, []).append({
                "date": str(r.get("trade_date") or d),
                "limit_count": r.get("limit_count"),
                "limit_tag": r.get("limit_tag"),
                "reason": r.get("reason"),
                "seal_money": r.get("seal_money"),
            })
    if out:
        c["data"] = out
        c["ts"] = time.time()
    return out


def _window_dates(end, days):
    """截至 end 的最近 days 个交易日（优先交易日历；日历为空返回 None 由调用方退化）。"""
    cal = marketdb.load_calendar(start=_window_start(end, days), end=end)
    return cal[-int(days):] if cal else None


def available_dates(n=40):
    """妖股页「截止日期」下拉可选交易日（倒序，最新在前）。"""
    cal = marketdb.load_calendar()
    return (cal or [])[::-1][: int(n)]


# ---------------- 评分共用 ----------------

def _score_of(gain, max_streak, avg_turn10, vol_ratio, lb_days, youzi_cnt):
    return (min(max(gain, 0) / 2.0, 1) * 40
            + min(max_streak / 6, 1) * 25
            + min(avg_turn10 / 25, 1) * 15
            + min(vol_ratio / 5, 1) * 10
            + min(lb_days / 5, 1) * 6 + min(youzi_cnt / 3, 1) * 4)


def _stage_and_risks(bars, gain, bias, seat_e):
    """返回 (stage, risks)。bars 升序窗口 K 线（dict）。"""
    risks = []
    closes = [float(b["close"]) for b in bars]
    chgs = [float(b.get("pct_chg") or 0) for b in bars]
    amts = [float(b.get("amount") or 0) for b in bars]
    lows = [float(b["low"]) for b in bars]
    n = len(bars)

    g3 = (closes[-1] / closes[-4] - 1) if n >= 4 else 0.0
    a5 = sum(amts[-5:]) / max(min(5, n), 1)
    a_prev = (sum(amts[:-5]) / (n - 5)) if n > 5 else a5
    heavy_vol = (a_prev > 0 and a5 >= 2 * a_prev)

    if bias is not None and bias > 0.40:
        risks.append("乖离率过高（MA20 乖离 %.0f%%）" % (bias * 100))
    if heavy_vol and g3 < 0.03 and (bias or 0) > 0.20:
        risks.append("高位放量滞涨（近5日量能为前期2倍+，3日累计<3%）")
    if seat_e and seat_e.get("last_net") is not None and seat_e["last_net"] < 0:
        risks.append("龙虎榜净卖转向（最近上榜净卖出 %.0f 万）"
                     % (seat_e["last_net"] / 1e4))
    if n >= 2 and closes[-2]:
        amp = (max(float(b["high"]) for b in bars[-1:]) - lows[-1]) / closes[-2]
        if amp >= 0.10 and chgs[-1] < 3 and amts[-1] >= max(amts):
            risks.append("天量长上影（振幅 %.0f%% 且创窗口天量）" % (amp * 100))

    if (bias or 0) >= 0.25 and (g3 < -0.05 or chgs[-1] <= -5
                                or (heavy_vol and g3 < 0.03)):
        stage = "分歧/退潮"
    elif gain >= 1.0 or (bias or 0) >= 0.30:
        stage = "加速"
    elif gain >= 0.30:
        stage = "主升"
    else:
        stage = "启动"
    return stage, risks


# ---------------- 妖股榜 ----------------

def scan(days=60, top=20, end=None):
    """妖股榜。end: 截止交易日 'YYYY-MM-DD'（None=最新行情日）。
    返回每只股票的实际行情截止日 data_end —— 回填未完成或停牌时可能早于 end。"""
    end = end or marketdb.latest_bar_date()
    key = "%s-%s-%s" % (days, top, end)
    c = _CACHE["list"].get(key)
    if c and time.time() - c["ts"] < _LIST_TTL:
        return c["data"]

    if not end:
        return {"bar_date": None, "count": 0, "rows": [],
                "hint": "行情库为空，请先同步日线数据"}
    start = _window_start(end, days)
    rows_raw = marketdb.load_bars(start=start, end=end, limit=600000)
    if not rows_raw:
        return {"bar_date": end, "count": 0, "rows": [],
                "hint": "截止 %s 无行情数据" % end}

    # 窗口：截至 end 的最近 days 个交易日（优先交易日历，退化由 bars 推导）
    win_dates = _window_dates(end, days)
    if win_dates:
        win = set(win_dates)
        win_start = win_dates[0]
    else:
        dates = sorted({r["trade_date"] for r in rows_raw})
        win = set(dates[-int(days):])
        win_start = dates[-int(days)] if len(dates) >= int(days) else dates[0]
    by_code = {}
    for r in rows_raw:
        if r["trade_date"] in win:
            by_code.setdefault(r["code"], []).append(r)

    seat_dates = db.list_seat_dates() or []
    seats = _seat_stats(seat_dates)
    names = {i["code"]: i["name"] for i in marketdb.list_instruments(limit=100000)}

    out = []
    for code, bars in by_code.items():
        bars.sort(key=lambda r: r["trade_date"])
        if len(bars) < 10:
            continue
        name = names.get(code) or ""
        if "ST" in name.upper() or "退" in name:
            continue
        if float(bars[-1].get("amount") or 0) < 3e7:   # 流动性门槛
            continue

        closes = [float(b["close"]) for b in bars]
        chgs = [float(b.get("pct_chg") or 0) for b in bars]
        turns = [float(b.get("turnover") or 0) for b in bars]
        amts = [float(b.get("amount") or 0) for b in bars]

        if closes[0] <= 0:
            continue
        gain = closes[-1] / closes[0] - 1
        thr = _limit_threshold(code) - 0.3
        lim_days = sum(1 for x in chgs if x >= thr)
        max_streak = streak = 0
        for x in chgs:
            if x >= thr:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        t10 = turns[-10:]
        avg_turn10 = sum(t10) / max(len(t10), 1)
        a10 = sum(amts[-10:]) / max(len(amts[-10:]), 1)
        a_all = sum(amts) / max(len(amts), 1)
        vol_ratio = (a10 / a_all) if a_all else 0
        ma20 = sum(closes[-20:]) / min(20, len(closes))
        bias = closes[-1] / ma20 - 1 if ma20 else None

        if gain < 0.5 and max_streak < 3:               # 候选门槛
            continue

        seat_e = seats.get(code) or {}
        lb_days = int(seat_e.get("lb_days") or 0)
        youzi_cnt = int(seat_e.get("youzi_cnt") or 0)
        score = _score_of(gain, max_streak, avg_turn10, vol_ratio,
                          lb_days, youzi_cnt)
        stage, risks = _stage_and_risks(bars, gain, bias, seat_e)

        out.append({
            "code": code, "name": name,
            "score": round(score, 1),
            "gain": round(gain * 100, 1),
            "max_streak": max_streak,
            "lim_days": lim_days,
            "avg_turn10": round(avg_turn10, 1),
            "vol_ratio": round(vol_ratio, 2),
            "bias": round(bias * 100, 1) if bias is not None else None,
            "lb_days": lb_days,
            "youzi_cnt": youzi_cnt,
            "stage": stage,
            "risks": risks,
            "close": closes[-1],
            "pct_chg": chgs[-1],
            "amount": amts[-1],
            "bar_date": bars[-1]["trade_date"],
            "data_end": bars[-1]["trade_date"],
        })

    out.sort(key=lambda r: r["score"], reverse=True)
    out = out[: int(top)]
    # 数据完整度：有多少只标的的行情已覆盖到截止日 end（供前端提示回填进度）
    covered = sum(1 for _c, _b in by_code.items()
                  if _b and _b[-1]["trade_date"] == end)
    data = {"bar_date": end, "win_start": win_start,
            "count": len(out), "rows": out,
            "coverage": {"covered": covered,
                         "total": marketdb.count_instruments()}}
    _CACHE["list"][key] = {"ts": time.time(), "data": data}
    return data


# ---------------- 个股画像 ----------------

def profile(code, days=60, end=None):
    """个股画像：走势 + 阶段 + 评分明细 + 席位 + 涨停明细 + 风险信号。
    end: 截止交易日（None=最新行情日）。"""
    end = end or marketdb.latest_bar_date()
    if not end:
        return {"code": code, "hint": "行情库为空"}
    start = _window_start(end, days)
    rows = marketdb.load_bars(codes=[code], start=start, end=end, limit=500) or []
    rows.sort(key=lambda r: r["trade_date"])
    if len(rows) < 5:
        return {"code": code, "hint": "窗口内K线不足"}

    win_dates = _window_dates(end, days)
    if win_dates:
        win = set(win_dates)
        bars = [r for r in rows if r["trade_date"] in win] or rows[-int(days):]
    else:
        bars = rows[-int(days):]
    bars.sort(key=lambda r: r["trade_date"])

    closes = [float(b["close"]) for b in bars]
    chgs = [float(b.get("pct_chg") or 0) for b in bars]
    amts = [float(b.get("amount") or 0) for b in bars]
    turns = [float(b.get("turnover") or 0) for b in bars]

    thr = _limit_threshold(code) - 0.3
    lim_days = sum(1 for x in chgs if x >= thr)
    max_streak = streak = 0
    streaks = []
    for x in chgs:
        if x >= thr:
            streak += 1
            max_streak = max(max_streak, streak)
            streaks.append(streak)
        else:
            streak = 0
            streaks.append(0)

    gain = closes[-1] / closes[0] - 1 if closes[0] else 0
    t10 = turns[-10:]
    avg_turn10 = sum(t10) / max(len(t10), 1)
    a10 = sum(amts[-10:]) / max(len(amts[-10:]), 1)
    a_all = sum(amts) / max(len(amts), 1)
    vol_ratio = (a10 / a_all) if a_all else 0
    ma20 = sum(closes[-20:]) / min(20, len(closes))
    bias = closes[-1] / ma20 - 1 if ma20 else None

    seat_dates = db.list_seat_dates() or []
    seat_e = (_seat_stats(seat_dates).get(code) or {})
    lb_days = int(seat_e.get("lb_days") or 0)
    youzi_cnt = int(seat_e.get("youzi_cnt") or 0)
    score = _score_of(gain, max_streak, avg_turn10, vol_ratio,
                      lb_days, youzi_cnt)
    stage, risks = _stage_and_risks(bars, gain, bias, seat_e)

    def _ma(k):
        return [round(sum(closes[max(0, i - k + 1): i + 1]) / min(k, i + 1), 3)
                for i in range(len(closes))]

    # 该股席位上榜明细（窗口内，按日期倒序）
    seat_rows = []
    for d in seat_dates[:45]:
        for s in (db.load_seats(d) or []):
            if (s.get("code") or s.get("security_code")) != code:
                continue
            seat_rows.append({
                "date": str(d), "seat_name": s.get("seat_name"),
                "side": s.get("side"), "net_amt": float(s.get("net_amt") or 0),
                "buy_amt": float(s.get("buy_amt") or 0),
                "type": monitor.seat_type_of(s.get("seat_name") or ""),
            })
    seat_rows.sort(key=lambda r: r["date"], reverse=True)
    agg = {}
    for s in seat_rows:
        e = agg.setdefault(s["seat_name"], {"seat_name": s["seat_name"],
                                            "net": 0.0, "type": s["type"]})
        e["net"] += s["net_amt"]
    youzi_top = sorted([e for e in agg.values() if e["type"] == "youzi"],
                       key=lambda x: x["net"], reverse=True)[:5]
    for e in youzi_top:
        e["net_wan"] = round(e["net"] / 1e4, 1)

    lu_map = _limitup_map(db.list_limitup_dates() or [])
    lu_detail = (lu_map.get(code) or [])[:15]

    name = ""
    for i in marketdb.list_instruments(limit=100000):
        if i["code"] == code:
            name = i["name"]
            break

    return {
        "code": code, "name": name,
        "bar_date": end,
        "data_end": bars[-1]["trade_date"] if bars else None,
        "stage": stage, "score": round(score, 1),
        "score_detail": {
            "gain": round(min(max(gain, 0) / 2.0, 1) * 40, 1),
            "board": round(min(max_streak / 6, 1) * 25, 1),
            "turn": round(min(avg_turn10 / 25, 1) * 15, 1),
            "vol": round(min(vol_ratio / 5, 1) * 10, 1),
            "seat": round(min(lb_days / 5, 1) * 6 + min(youzi_cnt / 3, 1) * 4, 1),
        },
        "gain": round(gain * 100, 1), "max_streak": max_streak,
        "lim_days": lim_days, "streaks": streaks,
        "avg_turn10": round(avg_turn10, 1), "vol_ratio": round(vol_ratio, 2),
        "bias": round(bias * 100, 1) if bias is not None else None,
        "lb_days": lb_days, "youzi_cnt": youzi_cnt,
        "risks": risks,
        "kline": [{"date": b["trade_date"], "open": float(b["open"]),
                   "high": float(b["high"]), "low": float(b["low"]),
                   "close": float(b["close"]), "pct_chg": chgs[i],
                   "amount": amts[i]} for i, b in enumerate(bars)],
        "ma5": _ma(5), "ma10": _ma(10), "ma20": _ma(20),
        "youzi_top": youzi_top,
        "seat_rows": seat_rows[:30],
        "limitup": lu_detail,
    }
