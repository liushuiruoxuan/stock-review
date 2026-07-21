"""
资金监控计算层（Tier A：基于龙虎榜「汇总级」数据，无需席位明细）。

监控维度：
  - 机构 / 游资分类（解析 EXPLAIN 中的机构买入/卖出家数）
  - 单日净买入/净卖出金额、金额阈值筛选
  - 个股上榜次数（历史聚合）
  - 机构连续净卖出预警（跨交易日，>=N 日触发）
  - 同日多股机构净买入「机构共振」信号（席位级抱团的汇总级替代）
  - 历史胜率（利用 D1/D2/D5/D10 后续表现计算上涨概率）
输出：按交易日生成监控报告，支持 CSV 导出。

说明：本层完全从已有的龙虎榜日数据派生，零新增数据源。
席位级明细（逐席位游资/机构）受免费接口限制无法获取，相关维度标记为 Tier B 待增强。
"""
import csv
import io

WIN_FIELDS = ["d1", "d2", "d5", "d10"]
WIN_LABELS = {"d1": "次日", "d2": "后2日", "d5": "后5日", "d10": "后10日"}

CATEGORY_LABELS = {
    "inst_buy": "机构买入",
    "inst_sell": "机构卖出",
    "inst_split": "机构分歧",
    "youzi": "游资",
}


def classify(rec):
    """将一条龙虎榜记录归类到 机构买入/机构卖出/机构分歧/游资。"""
    b = rec.get("inst_buy_cnt") or 0
    s = rec.get("inst_sell_cnt") or 0
    if b > 0 and s == 0:
        return "inst_buy"
    if s > 0 and b == 0:
        return "inst_sell"
    if b > 0 and s > 0:
        return "inst_split"
    return "youzi"


def inst_net_sell(rec):
    """机构是否当日净卖出（席位家数口径：卖出家数 > 买入家数）。"""
    b = rec.get("inst_buy_cnt") or 0
    s = rec.get("inst_sell_cnt") or 0
    return s > b


def gather(load_data, dates):
    """加载所有交易日龙虎榜并标注 category，返回按日期升序的 {td: [recs]}。"""
    by_date = {}
    for td in dates:
        bb = load_data("billboard", td)
        if bb:
            for r in bb:
                r["category"] = classify(r)
            by_date[td] = bb
    return dict(sorted(by_date.items()))


def build_list_times(by_date):
    """code -> {code, name, dates:[...]} 个股上榜次数/日期序列。"""
    m = {}
    for td, recs in by_date.items():
        for r in recs:
            c = r.get("code")
            if not c:
                continue
            e = m.setdefault(c, {"code": c, "name": r.get("name"), "dates": []})
            e["dates"].append(td)
    return m


def _net_wan(rec):
    v = rec.get("net_amt")
    return (v / 1e4) if isinstance(v, (int, float)) else None


def daily_ranking(by_date, list_times, date, min_net_wan=0, type_filter="all", limit=200):
    """单日监控排行：补充 net_wan/上榜次数，按金额阈值与类型筛选，按净买降序。"""
    recs = by_date.get(date, [])
    out = []
    for r in recs:
        row = dict(r)
        row["net_wan"] = _net_wan(r)
        row["list_times"] = len(list_times.get(r.get("code"), {}).get("dates", []))
        out.append(row)
    if min_net_wan:
        out = [x for x in out if x["net_wan"] is not None and x["net_wan"] >= min_net_wan]
    if type_filter and type_filter != "all":
        out = [x for x in out if x.get("category") == type_filter]
    out.sort(key=lambda x: (x["net_wan"] if x["net_wan"] is not None else -1e18), reverse=True)
    return out[:limit]


def resonance(by_date, date, threshold=3):
    """同日多股被机构净买入 → 机构共振信号（席位级抱团的汇总替代）。"""
    recs = by_date.get(date, [])
    inst_buy_stocks = [
        r for r in recs
        if (r.get("inst_buy_cnt") or 0) > 0 and (r.get("net_amt") or 0) > 0
    ]
    inst_buy_stocks.sort(key=lambda x: x.get("net_amt") or -1e18, reverse=True)
    return {
        "date": date,
        "count": len(inst_buy_stocks),
        "is_resonance": len(inst_buy_stocks) >= threshold,
        "threshold": threshold,
        "stocks": inst_buy_stocks,
    }


def compute_winrate(recs):
    agg = {k: {"win": 0, "total": 0} for k in WIN_FIELDS}
    for r in recs:
        for k in WIN_FIELDS:
            v = r.get(k)
            if isinstance(v, (int, float)):
                agg[k]["total"] += 1
                if v > 0:
                    agg[k]["win"] += 1
    out = {}
    for k in WIN_FIELDS:
        t = agg[k]["total"]
        out[k] = {
            "label": WIN_LABELS[k],
            "total": t,
            "win": agg[k]["win"],
            "rate": round(agg[k]["win"] / t * 100, 1) if t else None,
        }
    return out


def winrate(by_date):
    """历史胜率：整体 / 机构买入 / 游资 三类。"""
    all_recs = [r for recs in by_date.values() for r in recs]
    inst_recs = [r for r in all_recs if r.get("category") == "inst_buy"]
    youzi_recs = [r for r in all_recs if r.get("category") == "youzi"]
    return {
        "all": compute_winrate(all_recs),
        "inst_buy": compute_winrate(inst_recs),
        "youzi": compute_winrate(youzi_recs),
    }


def continuous_sell_signals(by_date, min_streak=3, until_date=None):
    """机构连续净卖出预警：按 code 聚合时间序列，找连续 inst_net_sell 的 run。"""
    code_seq = {}
    for td, recs in by_date.items():
        if until_date and td > until_date:
            continue
        for r in recs:
            c = r.get("code")
            if not c:
                continue
            code_seq.setdefault(c, []).append((td, r))
    signals = []
    for code, seq in code_seq.items():
        seq.sort(key=lambda x: x[0])
        best_run, cur = [], []
        for td, r in seq:
            if inst_net_sell(r):
                cur.append((td, r))
            else:
                if len(cur) > len(best_run):
                    best_run = cur
                cur = []
        if len(cur) > len(best_run):
            best_run = cur
        if len(best_run) >= min_streak:
            first_td, first_r = best_run[0]
            last_td, last_r = best_run[-1]
            signals.append({
                "code": code,
                "name": last_r.get("name") or first_r.get("name"),
                "streak": len(best_run),
                "start_date": first_td,
                "end_date": last_td,
                "dates": [t for t, _ in best_run],
                "latest_net_amt": last_r.get("net_amt"),
                "latest_net_wan": _net_wan(last_r),
                "latest_close": last_r.get("close"),
                "inst_sell_cnt": last_r.get("inst_sell_cnt"),
                "inst_buy_cnt": last_r.get("inst_buy_cnt"),
            })
    signals.sort(key=lambda x: (x["streak"], -(x["latest_net_amt"] or 0)), reverse=True)
    return signals


def _fmt(v):
    if v is None or v == "":
        return ""
    if isinstance(v, float):
        return "%.2f" % v
    return str(v)


def to_csv(by_date, list_times, date, min_net_wan=0, type_filter="all"):
    """按交易日导出监控报告 CSV（带 BOM 便于 Excel 打开）。"""
    rows = daily_ranking(by_date, list_times, date, min_net_wan, type_filter, limit=100000)
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["交易日", "代码", "名称", "类别", "龙虎榜净买(万)", "机构买入家数",
                 "机构卖出家数", "上榜次数", "次日%", "后2日%", "后5日%", "涨幅%",
                 "上榜原因", "席位说明"])
    for r in rows:
        wr.writerow([
            date, r.get("code"), r.get("name"),
            CATEGORY_LABELS.get(r.get("category"), r.get("category")),
            _fmt(r.get("net_wan")), r.get("inst_buy_cnt"), r.get("inst_sell_cnt"),
            r.get("list_times"), _fmt(r.get("d1")), _fmt(r.get("d2")), _fmt(r.get("d5")),
            _fmt(r.get("change_pct")), r.get("reason"), r.get("explain"),
        ])
    return buf.getvalue()


# ----------------------- 席位级（Tier B） -----------------------
# 席位类型：机构专用 / 沪深股通 / 游资(营业部)
def seat_type_of(seat_name):
    if not seat_name:
        return "other"
    if "机构专用" in seat_name:
        return "inst"
    if "沪股通" in seat_name or "深股通" in seat_name or "陆股通" in seat_name:
        return "hk"
    return "youzi"


def seat_type_label(t):
    return {"inst": "机构专用", "hk": "沪深股通", "youzi": "游资/营业部"}.get(t, "其他")


def compute_seat_stats(seats):
    stats = {"count": len(seats), "net_total_wan": 0.0,
             "buy_total_wan": 0.0, "sell_total_wan": 0.0,
             "inst": 0, "hk": 0, "youzi": 0, "seats": 0}
    names = set()
    for s in seats:
        b = _to_float(s.get("buy_amt")) or 0
        sl = _to_float(s.get("sell_amt")) or 0
        n = _to_float(s.get("net_amt")) or 0
        stats["buy_total_wan"] += b / 1e4
        stats["sell_total_wan"] += sl / 1e4
        stats["net_total_wan"] += n / 1e4
        t = seat_type_of(s.get("seat_name"))
        if t == "inst":
            stats["inst"] += 1
        elif t == "hk":
            stats["hk"] += 1
        else:
            stats["youzi"] += 1
        if s.get("seat_name"):
            names.add(s.get("seat_name"))
    stats["seats"] = len(names)
    return stats


def seat_profile(by_date_seats, seat_name):
    """席位画像：跨所有交易日聚合某席位（上榜次数/累计净额/平均3日胜率/偏好个股）。"""
    if not seat_name:
        return None
    total = 0.0
    cnt = 0
    rise = []
    stocks = {}
    dates = []
    latest = None
    for td, rows in by_date_seats.items():
        for s in rows:
            if s.get("seat_name") != seat_name:
                continue
            cnt += 1
            n = _to_float(s.get("net_amt")) or 0
            total += n
            rp = _to_float(s.get("rise_prob_3d"))
            if rp is not None:
                rise.append(rp)
            if s.get("code"):
                stocks[s.get("code")] = s.get("name")
            dates.append(td)
            if latest is None or td > latest.get("date"):
                latest = {"date": td, "code": s.get("code"), "name": s.get("name"),
                          "side": s.get("side"), "net_amt": n,
                          "buy_amt": _to_float(s.get("buy_amt")),
                          "sell_amt": _to_float(s.get("sell_amt")),
                          "explanation": s.get("explanation")}
    if cnt == 0:
        return None
    avg_rise = round(sum(rise) / len(rise), 1) if rise else None
    top_stocks = list(stocks.items())[:20]
    return {
        "seat_name": seat_name,
        "appearances": cnt,
        "total_net_wan": round(total / 1e4, 1),
        "avg_rise_3d": avg_rise,
        "stock_cnt": len(stocks),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "latest": latest,
        "stocks": [{"code": c, "name": n} for c, n in top_stocks],
    }


def seat_continuous_sell(by_date_seats, min_streak=3, until_date=None):
    """席位连续净卖预警：按席位聚合每日净买(多票合计)，找连续净卖 run。"""
    seat_day = {}
    for td, rows in by_date_seats.items():
        if until_date and td > until_date:
            continue
        for s in rows:
            name = s.get("seat_name")
            if not name:
                continue
            n = _to_float(s.get("net_amt")) or 0
            seat_day.setdefault(name, []).append((td, n))
    signals = []
    for name, seq in seat_day.items():
        day_net = {}
        for td, n in seq:
            day_net[td] = day_net.get(td, 0) + n
        best_run, cur = [], []
        for td in sorted(day_net.keys()):
            if day_net[td] < 0:
                cur.append((td, day_net[td]))
            else:
                if len(cur) > len(best_run):
                    best_run = cur
                cur = []
        if len(cur) > len(best_run):
            best_run = cur
        if len(best_run) >= min_streak:
            first_td, first_net = best_run[0]
            last_td, last_net = best_run[-1]
            signals.append({
                "seat_name": name,
                "streak": len(best_run),
                "start_date": first_td,
                "end_date": last_td,
                "dates": [t for t, _ in best_run],
                "latest_net_amt": last_net,
                "latest_net_wan": round(last_net / 1e4, 1),
            })
    signals.sort(key=lambda x: (x["streak"], -(x["latest_net_amt"] or 0)), reverse=True)
    return signals


def seat_syndicate(by_date_seats, date, threshold=3):
    """抱团（共振）：同一交易日、同一只票出现 >= threshold 个游资/营业部席位。"""
    rows = by_date_seats.get(date, [])
    by_stock = {}
    for s in rows:
        c = s.get("code")
        if not c:
            continue
        if seat_type_of(s.get("seat_name")) == "youzi":
            by_stock.setdefault(c, {"name": s.get("name"), "seats": []})
            by_stock[c]["seats"].append(s.get("seat_name"))
    out = []
    for c, info in by_stock.items():
        distinct = list(dict.fromkeys(info["seats"]))
        if len(distinct) >= threshold:
            out.append({"code": c, "name": info["name"],
                        "seat_cnt": len(distinct), "seats": distinct})
    out.sort(key=lambda x: x["seat_cnt"], reverse=True)
    return {"date": date, "threshold": threshold, "stocks": out}


def seat_rankings(by_date_seats, date, limit=30):
    """席位净值排行 + 活跃度排行（按当日出现席位去重计数）。"""
    rows = by_date_seats.get(date, [])
    net_by_seat = {}
    appear = {}
    for s in rows:
        name = s.get("seat_name")
        if not name:
            continue
        n = _to_float(s.get("net_amt")) or 0
        net_by_seat[name] = net_by_seat.get(name, 0) + n
        appear[name] = appear.get(name, 0) + 1
    net_rank = sorted(net_by_seat.items(), key=lambda x: x[1], reverse=True)[:limit]
    act_rank = sorted(appear.items(), key=lambda x: x[1], reverse=True)[:limit]
    return {
        "net": [{"seat_name": k, "net_wan": round(v / 1e4, 1)} for k, v in net_rank],
        "active": [{"seat_name": k, "cnt": v} for k, v in act_rank],
    }


def seats_to_csv(seats):
    """按交易日导出席位明细 CSV（带 BOM 便于 Excel 打开）。"""
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["交易日", "代码", "名称", "席位", "方向", "买入(元)", "卖出(元)",
                 "净额(元)", "3日上涨概率%", "3日买卖次数", "上榜原因"])
    for s in seats:
        wr.writerow([
            s.get("trade_date"), s.get("code"), s.get("name"), s.get("seat_name"),
            "买入" if s.get("side") == "BUY" else "卖出",
            _fmt(s.get("buy_amt")), _fmt(s.get("sell_amt")), _fmt(s.get("net_amt")),
            _fmt(s.get("rise_prob_3d")), _fmt(s.get("trade_times_3d")),
            s.get("explanation") or "",
        ])
    return buf.getvalue()
