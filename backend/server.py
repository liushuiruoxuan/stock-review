"""
股票每日复盘 - 本地后端服务（Python 标准库，零第三方依赖）。

功能：
  - 代理抓取东方财富接口，解决浏览器跨域问题。
  - 按交易日把各看板数据落盘缓存到 cache/<交易日>/，避免重复请求被限流。
  - 同时（可选）双写到 MySQL，支持历史回看；MySQL 不可用时自动回退 JSON 缓存。
  - 交易日收盘后(15:35 起)自动抓取并刷新缓存。
  - 提供 /api/* 接口给前端；若 frontend/dist 存在则一并托管前端静态资源。

启动：  python server.py   (默认 http://localhost:8000)
MySQL： 见 db_config.py（环境变量或默认值）。不装 PyMySQL 也能跑，仅用 JSON 缓存。
"""
import http.server
import socketserver
import json
import os
import sys
import threading
import time
import datetime
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eastmoney as em
import demo
import db
import monitor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
DIST_DIR = os.path.join(BASE_DIR, "..", "frontend", "dist")
PORT = int(os.environ.get("PORT", "8000"))

# 运行期状态
STATE = {
    "trade_date": None,
    "generated_at": None,
    "sources": {},          # name -> "live" / "demo"
    "last_refresh_at": None,
}

SECTIONS = [
    "billboard", "stocks_flow", "rapid_rise", "capital_attention",
    "sectors_hot", "sectors_outflow", "institution", "youzi", "summary",
]


# ----------------------- 缓存 -----------------------
def cache_path(name, trade_date):
    d = os.path.join(CACHE_DIR, trade_date)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name + ".json")


def load_cache(name, trade_date):
    p = cache_path(name, trade_date)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_cache(name, trade_date, payload):
    p = cache_path(name, trade_date)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def load_data(section, td):
    """优先 MySQL，缺失/失败回退本地 JSON 缓存。"""
    data = db.load_section(td, section)
    if data is not None:
        return data
    return load_cache(section, td)


# ----------------------- 数据构建 -----------------------
def _derive_stocks(stocks):
    inflow = sorted([s for s in stocks if s["main_net"] is not None],
                    key=lambda x: x["main_net"], reverse=True)
    return inflow


def build_all(trade_date=None, force=False):
    """抓取并构建所有看板数据，写入缓存（及 MySQL）。返回 STATE 摘要。"""
    trade_date = trade_date or em.resolve_trade_date()
    sources = {}

    # 1) 龙虎榜
    bb_raw = em.fetch_billboard_raw(trade_date)
    if bb_raw:
        billboard = [em.normalize_billboard(r) for r in bb_raw]
        sources["billboard"] = "live"
    else:
        billboard = demo.gen_billboard(trade_date)
        sources["billboard"] = "demo"

    # 1.5) 席位明细（Tier B）：逐席位买卖（限流抓取，失败自动跳过）
    try:
        seats = em.fetch_billboard_seats(trade_date, billboard)
    except Exception as e:
        print("[build] 席位抓取异常：", e)
        seats = []
    if seats:
        db.save_seats(seats)
        sources["seats"] = "live"
    else:
        sources["seats"] = "demo"

    # 2) 个股池（资金流/涨幅/关注共用）
    raw = em.fetch_clist(em.STOCK_FS, "f62", 400, em.FIELD_STOCK)
    stocks = [em.norm_stock(r) for r in raw]
    if not stocks:
        stocks = demo.gen_stocks(trade_date, n=80)
        sources["stocks"] = "demo"
    else:
        sources["stocks"] = "live"

    # 3) 行业 + 概念板块
    ind = em.fetch_clist(em.INDUSTRY_FS, "f62", 150, em.FIELD_SECTOR)
    con = em.fetch_clist(em.CONCEPT_FS, "f62", 300, em.FIELD_SECTOR)
    sectors = [em.norm_sector(r) for r in (ind + con)]
    if not sectors:
        sectors = [s for s in demo.gen_sectors(trade_date) if s["change_pct"] >= 0]
        sources["sectors"] = "demo"
    else:
        sources["sectors"] = "live"

    # 4) 衍生看板
    stocks_flow = _derive_stocks(stocks)
    rapid_rise = sorted([s for s in stocks if s["change_pct"] is not None],
                        key=lambda x: x["change_pct"], reverse=True)
    capital_attention = sorted(
        [s for s in stocks if (s["main_net"] or 0) > 0 and (s["change_pct"] or 0) > 0],
        key=lambda x: x["main_net"], reverse=True)

    sectors_hot = sorted([s for s in sectors if s["main_net"] is not None],
                         key=lambda x: x["main_net"], reverse=True)
    sectors_outflow = sorted([s for s in sectors if s["main_net"] is not None],
                             key=lambda x: x["main_net"])

    # 机构动向：龙虎榜中机构参与(买入)个股，按净买入排序
    inst = sorted(
        [b for b in billboard if (b.get("inst_buy_cnt") or 0) > 0 or "机构买入" in (b.get("explain") or "")],
        key=lambda x: x["net_amt"] if x["net_amt"] is not None else -1e18, reverse=True)
    inst_sell = sorted(
        [b for b in billboard if (b.get("inst_sell_cnt") or 0) > 0 or "机构卖出" in (b.get("explain") or "")],
        key=lambda x: x["net_amt"] if x["net_amt"] is not None else 1e18)

    # 游资/营业部活跃：龙虎榜中机构未主导(或无机构)且净买入居前
    youzi = sorted(
        [b for b in billboard if (b.get("inst_buy_cnt") or 0) == 0],
        key=lambda x: x["net_amt"] if x["net_amt"] is not None else -1e18, reverse=True)

    # 汇总
    bb_net_total = sum((b["net_amt"] or 0) for b in billboard)
    summary = {
        "trade_date": trade_date,
        "billboard_count": len(billboard),
        "billboard_net_total": bb_net_total,
        "top_hot_sector": sectors_hot[0] if sectors_hot else None,
        "top_institution_stock": inst[0] if inst else None,
        "top_youzi_stock": youzi[0] if youzi else None,
        "top_rise_stock": rapid_rise[0] if rapid_rise else None,
        "top_attention_stock": capital_attention[0] if capital_attention else None,
        "inst_count": len(inst),
        "youzi_count": len(youzi),
        "sectors_hot_count": len([s for s in sectors if (s["main_net"] or 0) > 0]),
        "sectors_outflow_count": len([s for s in sectors if (s["main_net"] or 0) < 0]),
    }

    payloads = {
        "billboard": billboard,
        "stocks_flow": stocks_flow,
        "rapid_rise": rapid_rise,
        "capital_attention": capital_attention,
        "sectors_hot": sectors_hot,
        "sectors_outflow": sectors_outflow,
        "institution": {"buy": inst, "sell": inst_sell},
        "youzi": youzi,
        "summary": summary,
    }

    for name, data in payloads.items():
        save_cache(name, trade_date, data)
    # 双写 MySQL（失败自动回退 JSON，不阻塞）
    db.save_all(trade_date, payloads)

    STATE["trade_date"] = trade_date
    STATE["generated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STATE["sources"] = sources
    STATE["last_refresh_at"] = STATE["generated_at"]
    print("[build] trade_date=%s sources=%s mysql=%s" % (trade_date, sources, db.is_available()))
    return STATE


def ensure_built(force=False):
    td = em.resolve_trade_date()
    # 若缓存存在且为当日，直接复用
    if not force and STATE.get("trade_date") == td:
        return STATE
    cached = load_cache("summary", td)
    if cached and not force:
        STATE["trade_date"] = td
        STATE["generated_at"] = "cached"
        STATE["sources"] = {}
        STATE["last_refresh_at"] = "cached"
        return STATE
    return build_all(td, force=force)


# ----------------------- 定时调度 -----------------------
def scheduler_loop():
    """交易日 15:35 起尝试刷新；之后 16:30/18:00/20:00 再补抓。"""
    tried = {}
    while True:
        try:
            now = datetime.datetime.now()
            td = em.resolve_trade_date()
            if not em.is_trading_day(now.date()):
                time.sleep(300)
                continue
            # 刷新窗口
            window = [(15, 35), (16, 30), (18, 0), (20, 0)]
            for (h, m) in window:
                key = "%s-%02d%02d" % (td, h, m)
                if key in tried:
                    continue
                if now.hour > h or (now.hour == h and now.minute >= m):
                    build_all(td, force=True)
                    tried[key] = True
            # 清理昨天的 tried key
            tried = {k: v for k, v in tried.items() if k.startswith(td)}
        except Exception as e:
            print("[scheduler] err:", e)
        time.sleep(120)


# ----------------------- HTTP 服务 -----------------------
def _json_default(o):
    """json.dumps 兜底：date/datetime -> 字符串，其余 -> str。"""
    import datetime as _dt
    if isinstance(o, (_dt.date, _dt.datetime, _dt.time)):
        return o.isoformat()
    return str(o)


class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except Exception:
            self._send_json({"error": "not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({}, 204)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        if path.startswith("/api/"):
            self.route_api(path, qs)
            return
        self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/refresh":
            td = em.resolve_trade_date()
            build_all(td, force=True)
            self._send_json({"ok": True, "state": STATE})
            return
        self._send_json({"error": "not found"}, 404)

    def route_api(self, path, qs):
        def lim(default=50):
            try:
                return max(1, min(300, int(qs.get("limit", [default])[0])))
            except Exception:
                return default

        ensure_built()
        td = STATE.get("trade_date") or em.resolve_trade_date()

        if path == "/api/status":
            self._send_json({
                "trade_date": td, "generated_at": STATE.get("generated_at"),
                "sources": STATE.get("sources"), "last_refresh_at": STATE.get("last_refresh_at"),
                "mysql": db.is_available(),
                "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            return
        if path == "/api/summary":
            self._send_json(load_data("summary", td) or {})
            return
        if path == "/api/billboard":
            self._send_json(load_data("billboard", td) or [])
            return
        if path == "/api/stocks/flow":
            data = load_data("stocks_flow", td) or []
            self._send_json({"inflow": data[:lim(50)], "outflow": list(reversed(data[-lim(50):]))})
            return
        if path == "/api/rapid-rise":
            data = load_data("rapid_rise", td) or []
            self._send_json(data[:lim(50)])
            return
        if path == "/api/capital-attention":
            data = load_data("capital_attention", td) or []
            self._send_json(data[:lim(50)])
            return
        if path == "/api/sectors/hot":
            data = load_data("sectors_hot", td) or []
            self._send_json(data[:lim(30)])
            return
        if path == "/api/sectors/outflow":
            data = load_data("sectors_outflow", td) or []
            self._send_json(data[:lim(30)])
            return
        if path == "/api/institution":
            data = load_data("institution", td) or {"buy": [], "sell": []}
            self._send_json(data)
            return
        if path == "/api/youzi":
            data = load_data("youzi", td) or []
            self._send_json(data[:lim(50)])
            return
        if path == "/api/history/dates":
            self._send_json({"dates": db.list_dates(), "source": "mysql" if db.is_available() else "json"})
            return
        if path == "/api/history":
            date = qs.get("date", [None])[0] or td
            hist = db.load_history(date)
            fallback = {k: (v if v is not None else load_cache(k, date)) for k, v in hist.items()}
            self._send_json({
                "trade_date": date, "data": fallback,
                "source": "mysql" if db.is_available() else "json",
            })
            return
        if path.startswith("/api/monitor/"):
            self.route_monitor(path, qs, td)
            return
        if path.startswith("/api/seats/"):
            self.route_seats(path, qs, td)
            return
        self._send_json({"error": "unknown api: %s" % path}, 404)

    # ----------------------- 资金监控（Tier A） -----------------------
    def route_monitor(self, path, qs, td):
        def q(name, default=None):
            v = qs.get(name, [default])[0]
            return v

        def _to_int(v, default=0):
            try:
                return int(v)
            except Exception:
                return default

        dates = db.list_dates()
        if not dates:
            self._send_json({"error": "暂无数据，请先刷新"}, 404)
            return
        by_date = monitor.gather(load_data, dates)
        list_times = monitor.build_list_times(by_date)
        if not by_date:
            self._send_json({"error": "龙虎榜数据为空"}, 404)
            return

        if path == "/api/monitor/daily":
            date = q("date") or td
            if date not in by_date:
                date = max(by_date.keys())
            min_net = max(0, _to_int(q("min_net", "0"), 0))
            type_filter = q("type", "all") or "all"
            limit = max(1, min(500, _to_int(q("limit", "200"), 200)))
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
            self._send_json({
                "date": date,
                "available_dates": list(reversed(list(by_date.keys()))),
                "stats": stats,
                "ranking": ranking,
                "resonance": res,
                "winrate": wr,
                "filters": {"min_net": min_net, "type": type_filter},
            })
            return

        if path == "/api/monitor/signals":
            min_streak = max(2, _to_int(q("min_streak", "3"), 3))
            sigs = monitor.continuous_sell_signals(by_date, min_streak=min_streak, until_date=td)
            self._send_json({"date": td, "min_streak": min_streak, "signals": sigs})
            return

        if path == "/api/monitor/export":
            date = q("date") or td
            if date not in by_date:
                date = max(by_date.keys())
            min_net = max(0, _to_int(q("min_net", "0"), 0))
            type_filter = q("type", "all") or "all"
            csv_text = monitor.to_csv(by_date, list_times, date, min_net, type_filter)
            body = csv_text.encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition",
                             'attachment; filename="monitor_%s.csv"' % date)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        self._send_json({"error": "unknown monitor api: %s" % path}, 404)

    # ----------------------- 席位监控（Tier B） -----------------------
    def route_seats(self, path, qs, td):
        def q(name, default=None):
            return qs.get(name, [default])[0]

        def _to_int(v, default=0):
            try:
                return int(v)
            except Exception:
                return default

        dates = db.list_seat_dates()
        if not dates:
            self._send_json({"error": "暂无席位数据，请先抓取龙虎榜席位"}, 404)
            return

        # 载入全部交易日的席位明细（内存中聚合，体量可控）
        by_date_seats = {}
        for d in dates:
            rows = db.load_seats(d)
            if rows:
                by_date_seats[d] = rows
        by_date_seats = dict(sorted(by_date_seats.items()))

        if path == "/api/seats/daily":
            date = q("date") or td
            if date not in by_date_seats:
                date = max(by_date_seats.keys())
            seat = q("seat")
            side = q("side")
            stype = q("type")
            min_net = _to_int(q("min_net", "0"), 0)   # 单位：元
            limit = max(1, min(5000, _to_int(q("limit", "2000"), 2000)))
            seats = db.load_seats(date, seat=seat, side=side, seat_type=stype,
                                  min_net=min_net, limit=limit)
            if seats is None:
                seats = []
            stats = monitor.compute_seat_stats(seats)
            synd = monitor.seat_syndicate(
                by_date_seats, date, threshold=max(2, _to_int(q("synd", "3"), 3)))
            ranks = monitor.seat_rankings(by_date_seats, date)
            self._send_json({
                "date": date,
                "available_dates": list(reversed(list(by_date_seats.keys()))),
                "stats": stats,
                "seats": seats,
                "syndicate": synd,
                "rankings": ranks,
                "filters": {"seat": seat, "side": side, "type": stype, "min_net": min_net},
            })
            return

        if path == "/api/seats/profile":
            seat = q("seat")
            prof = monitor.seat_profile(by_date_seats, seat) if seat else None
            self._send_json({"seat": seat, "profile": prof})
            return

        if path == "/api/seats/signals":
            min_streak = max(2, _to_int(q("min_streak", "3"), 3))
            sigs = monitor.seat_continuous_sell(by_date_seats, min_streak=min_streak, until_date=td)
            self._send_json({"date": td, "min_streak": min_streak, "signals": sigs})
            return

        if path == "/api/seats/export":
            date = q("date") or td
            if date not in by_date_seats:
                date = max(by_date_seats.keys())
            seat = q("seat")
            side = q("side")
            stype = q("type")
            min_net = _to_int(q("min_net", "0"), 0)
            seats = db.load_seats(date, seat=seat, side=side, seat_type=stype,
                                  min_net=min_net, limit=100000)
            if seats is None:
                seats = []
            csv_text = monitor.seats_to_csv(seats)
            body = csv_text.encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition",
                             'attachment; filename="seats_%s.csv"' % date)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        self._send_json({"error": "unknown seats api: %s" % path}, 404)

    def serve_static(self, path):
        dist = os.path.abspath(DIST_DIR)
        if not os.path.isdir(dist):
            # 前端尚未构建：给出提示页
            self._send_json({
                "hint": "前端未构建。请先 cd frontend && npm install && npm run build，"
                        "或开发模式 npm run dev (默认代理到本服务)。",
                "api": "try GET /api/status"
            })
            return
        if path in ("/", ""):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(dist, path.lstrip("/")))
        if not fp.startswith(dist):
            self._send_json({"error": "forbidden"}, 403)
            return
        if os.path.isfile(fp):
            ct = "text/html; charset=utf-8"
            if fp.endswith(".js"):
                ct = "application/javascript; charset=utf-8"
            elif fp.endswith(".css"):
                ct = "text/css; charset=utf-8"
            elif fp.endswith(".json"):
                ct = "application/json; charset=utf-8"
            elif fp.endswith(".svg"):
                ct = "image/svg+xml"
            elif fp.endswith(".png"):
                ct = "image/png"
            self._send_file(fp, ct)
            return
        # SPA 回退
        self._send_file(os.path.join(dist, "index.html"), "text/html; charset=utf-8")

    def log_message(self, fmt, *args):
        pass  # 静默


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    print("=" * 60)
    print("股票每日复盘后端  |  端口 %d" % PORT)
    # MySQL 可能尚未就绪（如 Docker 中 mysql 容器刚起），重试等待。
    ok = db.init_db()
    for attempt in range(15):
        if ok:
            break
        print("[main] 等待 MySQL 就绪... (%d/15)" % (attempt + 1))
        time.sleep(3)
        ok = db.init_db()
    if ok:
        print("[main] MySQL 初始化成功。")
    else:
        print("[main] MySQL 未就绪，已回退 JSON 缓存（运行中会自动重试连接）。")
    print("构建初始数据 ...")
    ensure_built(force=False)
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print("服务已启动: http://localhost:%d" % PORT)
        print("=" * 60)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
