"""
日线行情抓取（v2 数据管线核心）。

主源：东方财富 push2his kline（免费无 key，与 eastmoney.py 同源同反爬策略，前复权）
备源：新浪 CN_MarketDataService.getKLineData（未复权，仅作兜底）
风控：请求间隔 + 指数退避重试；失败记录日志不中断整体同步。
"""
import datetime
import json
import time
import urllib.parse
import urllib.request

import eastmoney as em
import marketdb

KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EM_TOKEN = "fa5fd1943c7b386f172d6893dbfba10b"  # 东财公开 token
SINA_KLINE = ("https://quotes.sina.cn/cn/api/jsonp_v2.php/"
              "var%20t=/CN_MarketDataService.getKLineData")

REQ_INTERVAL = 0.12     # 主源请求间隔（秒），全市场 5900 只 ≈ 12 分钟
RETRY_BACKOFF = (1, 3, 8)


def secid(code):
    """东财 secid：沪市(6/9开头)=1.xxx，其余=0.xxx。"""
    code = str(code)
    if code.startswith(("6", "9")):
        return "1." + code
    return "0." + code


def _kline_params(code, beg, end, fqt=1):
    return {
        "secid": secid(code),
        "ut": EM_TOKEN,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",        # 日K
        "fqt": str(fqt),     # 1=前复权
        "beg": beg.replace("-", ""),
        "end": end.replace("-", ""),
    }


def fetch_kline_em(code, beg="20160101", end="20500101", timeout=15):
    """东财日K。返回 [{trade_date, open, close, high, low, volume, amount,
    pct_chg, turnover}, ...] 或 None（网络失败）。"""
    url = KLINE_URL + "?" + urllib.parse.urlencode(_kline_params(code, beg, end))
    try:
        d = em.http_get_json(url, timeout=timeout)
        data = d.get("data") or {}
        klines = data.get("klines") or []
    except Exception:
        return None
    rows = []
    for line in klines:
        p = line.split(",")
        if len(p) < 11:
            continue
        try:
            rows.append({
                "trade_date": p[0],
                "open": float(p[1]), "close": float(p[2]),
                "high": float(p[3]), "low": float(p[4]),
                "volume": int(float(p[5])), "amount": float(p[6]),
                "pct_chg": float(p[8]),
                "turnover": float(p[10]),
            })
        except (ValueError, IndexError):
            continue
    return rows


def fetch_kline_sina(code, datalen=1023, timeout=15):
    """新浪日K兜底（未复权，仅当东财不可用时）。返回格式同上或 None。"""
    scode = ("sh" if str(code).startswith(("6", "9")) else "sz") + str(code)
    url = "%s?symbol=%s&scale=240&ma=no&datalen=%d" % (SINA_KLINE, scode, datalen)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": em.UA,
            "Referer": "https://finance.sina.com.cn/",
        })
        with urllib.request.urlopen(req, timeout=timeout, context=em._ctx) as r:
            raw = r.read().decode("utf-8", "ignore")
        # jsonp: var t=[...];
        i = raw.find("[")
        j = raw.rfind("]")
        if i < 0 or j <= i:
            return None
        items = json.loads(raw[i:j + 1])
    except Exception:
        return None
    rows = []
    prev_close = None
    for it in items:
        try:
            close = float(it["close"])
            pct = None
            if prev_close:
                pct = round((close / prev_close - 1) * 100, 4)
            prev_close = close
            rows.append({
                "trade_date": it["day"][:10],
                "open": float(it["open"]), "close": close,
                "high": float(it["high"]), "low": float(it["low"]),
                "volume": int(float(it["volume"])), "amount": None,
                "pct_chg": pct, "turnover": None,
            })
        except (KeyError, ValueError):
            continue
    return rows


def fetch_daily_bars(code, beg="2016-01-01", end="2050-01-01", em_only=False):
    """带重试与备源的日线抓取。返回行列表（可能为空）。

    em_only=True 时东财失败直接返回空（不降级新浪）——用于全量同步，
    避免新浪（仅 ~4 年且无成交额）污染 10 年数据集被误标为“已覆盖”。
    """
    for wait in RETRY_BACKOFF:
        rows = fetch_kline_em(code, beg, end)
        if rows is not None:
            time.sleep(REQ_INTERVAL)
            return rows
        time.sleep(wait)
    if em_only:
        return []
    # 东财彻底失败 → 新浪兜底（仅增量等非全量场景）
    rows = fetch_kline_sina(code)
    if rows:
        lo = beg.replace("-", "")
        rows = [r for r in rows if r["trade_date"].replace("-", "") >= lo]
        time.sleep(REQ_INTERVAL)
    return rows or []


def fetch_index_bars(code, beg="2016-01-01", end="2050-01-01"):
    """指数日K（code 即 secid 形如 '1.000001'）。"""
    url = KLINE_URL + "?" + urllib.parse.urlencode({
        "secid": code, "ut": EM_TOKEN,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1",
        "beg": beg.replace("-", ""), "end": end.replace("-", ""),
    })
    try:
        d = em.http_get_json(url, timeout=15)
        klines = (d.get("data") or {}).get("klines") or []
    except Exception:
        return None
    rows = []
    for line in klines:
        p = line.split(",")
        if len(p) < 11:
            continue
        try:
            rows.append({
                "trade_date": p[0],
                "open": float(p[1]), "close": float(p[2]),
                "high": float(p[3]), "low": float(p[4]),
                "volume": int(float(p[5])), "amount": float(p[6]),
                "pct_chg": float(p[8]), "turnover": float(p[10]),
            })
        except (ValueError, IndexError):
            continue
    return rows


# ------------------------- 标的列表 -------------------------
SINA_PAGE_SIZE = 100  # 新浪该接口每页上限 100（num>100 仍只返回 100）


def _fetch_instruments_sina():
    """新浪市场中心拉全 A 股列表（node=hs_a，按 symbol 升序翻页，每页 100）。
    过滤到 0/3/6 开头的主板/创业板/科创板，排除北交所(4/8/92)、B股(9) 等小众标的。
    返回 [{code, name, market}]。"""
    out = []
    page = 1
    while page <= 60:  # 全 A 约 5400 只 / 100 每页 ≈ 54 页
        url = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               "Market_Center.getHQNodeData?page=%d&num=%d&sort=symbol&asc=1"
               "&node=hs_a&symbol=&_s_r_a=auto" % (page, SINA_PAGE_SIZE))
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": em.UA, "Referer": "https://finance.sina.com.cn/"})
            with urllib.request.urlopen(req, timeout=20, context=em._ctx) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:
            data = None
        if not data or not isinstance(data, list):
            break
        for it in data:
            code = str(it.get("code") or "")
            if not code or code[:1] not in ("0", "3", "6"):
                continue
            out.append({
                "code": code,
                "name": it.get("name") or "",
                "market": "SH" if code.startswith("6") else "SZ",
            })
        if len(data) < SINA_PAGE_SIZE:
            break
        page += 1
        time.sleep(0.15)
    return out


def fetch_instrument_list():
    """全市场 A 股标的列表。主源：新浪（稳定）；备源：东财 clist 翻页。
    返回 [{code, name, market}]。"""
    out = _fetch_instruments_sina()
    if out:
        return out
    # 东财备源
    page = 1
    while page < 80:
        p = {
            "pn": str(page), "pz": "100", "po": "1", "np": "1", "fltt": "2",
            "invt": "2", "fid": "f12", "fs": em.STOCK_FS, "fields": "f12,f14",
        }
        try:
            d = em.http_get_json(em.PUSH2_URL, p)
            rows = em._diff_to_list(d)
        except Exception:
            rows = []
        if not rows:
            break
        for r in rows:
            code = r.get("f12")
            if not code:
                continue
            out.append({
                "code": code,
                "name": r.get("f14") or "",
                "market": "SH" if str(code).startswith(("6", "9")) else "SZ",
            })
        if len(rows) < 100:
            break
        page += 1
        time.sleep(0.1)
    return out


# ------------------------- 同步任务 -------------------------
def _bar_rows_with_code(code, rows):
    out = []
    for r in rows or []:
        r["code"] = code
        out.append(r)
    return out


def sync_instruments():
    """同步标的列表，返回数量。"""
    rows = fetch_instrument_list()
    n = marketdb.upsert_instruments(rows)
    print("[datasvc] 标的同步完成：%d 只" % n)
    return n


def sync_calendar_and_index(beg="2016-01-01"):
    """用上证指数日K推导交易日历，并同步三只指数日线。"""
    total = 0
    for idx in marketdb.INDEXES:
        rows = fetch_index_bars(idx["code"], beg=beg)
        if rows:
            for r in rows:
                r["code"] = idx["code"]
            marketdb.upsert_bars(rows, table=marketdb.T_INDEX_BARS)
            total += len(rows)
            if idx["code"] == "1.000001":
                marketdb.save_calendar([r["trade_date"] for r in rows])
        time.sleep(REQ_INTERVAL)
    print("[datasvc] 日历+指数同步完成：%d 根K线" % total)
    return total


def sync_bars_full(beg="2016-01-01", task_id=None):
    """全量同步全市场日线（断点续传：已有该段数据的标的跳过）。
    供后台任务/手动触发，全市场约 12~20 分钟。"""
    from datasvc import tasks as tasksvc
    insts = marketdb.list_instruments(limit=100000)
    if not insts:
        # 标的列表为空时先同步一次
        sync_instruments()
        insts = marketdb.list_instruments(limit=100000)
    codes = [i["code"] for i in insts]
    coverage = marketdb.bar_coverage()
    end = datetime.date.today().isoformat()
    todo = [c for c in codes if not coverage.get(c) or coverage[c] < end]
    total = len(todo)
    print("[datasvc] 日线全量同步开始：共 %d 只待抓（全市场 %d 只）" % (total, len(codes)))
    for i, code in enumerate(todo):
        rows = fetch_daily_bars(code, beg=beg, em_only=True)
        if rows:
            marketdb.upsert_bars(_bar_rows_with_code(code, rows))
        if task_id and (i % 20 == 0 or i == total - 1):
            tasksvc.set_progress(task_id, i + 1, total, "已抓 %s" % code)
    print("[datasvc] 日线全量同步完成")


def sync_bars_daily():
    """每日增量：只抓最新交易日缺失的标的。"""
    latest = marketdb.latest_bar_date()
    today = datetime.date.today().isoformat()
    if latest and latest >= today:
        print("[datasvc] 日线已是最新（%s），跳过" % latest)
        return 0
    insts = marketdb.list_instruments(limit=100000)
    if not insts:
        sync_instruments()
        insts = marketdb.list_instruments(limit=100000)
    coverage = marketdb.bar_coverage()
    beg = (datetime.date.fromisoformat(latest) if latest
           else datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    n = 0
    for i, inst in enumerate(insts):
        code = inst["code"]
        if coverage.get(code, "") >= beg:
            continue
        rows = fetch_daily_bars(code, beg=beg)
        if rows:
            marketdb.upsert_bars(_bar_rows_with_code(code, rows))
            n += 1
        if i % 500 == 0:
            print("[datasvc] 日线增量进度 %d/%d" % (i, len(insts)))
    # 同步指数与日历
    sync_calendar_and_index()
    print("[datasvc] 日线增量完成：更新 %d 只" % n)
    return n
