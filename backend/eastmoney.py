"""
东方财富数据抓取与归一化层（仅使用 Python 标准库）。

数据来源：
  - 龙虎榜：datacenter-web.eastmoney.com/api/data/v1/get  (reportName=RPT_DAILYBILLBOARD_DETAILS)
  - 个股 / 板块资金流、涨幅榜：push2.eastmoney.com/api/qt/clist/get

说明：
  - 浏览器直连东方财富接口存在跨域(CORS)限制，故由本后端代理抓取。
  - 个股/板块接口在部分网络环境(如本沙箱)会被限制，此时返回空列表，
    由 server 层回退到内置示例数据(demo.py)，UI 会标注“示例数据”。
"""
import urllib.request
import urllib.parse
import json
import ssl
import datetime
import time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
REF = "https://data.eastmoney.com/"

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

BILLBOARD_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"

# 沪深京 A 股
STOCK_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
# 行业板块
INDUSTRY_FS = "m:90+t:2"
# 概念板块
CONCEPT_FS = "m:90+t:3"

FIELD_STOCK = "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f128"
FIELD_SECTOR = "f12,f14,f2,f3,f62,f184,f104,f105,f128"


def http_get_json(url, params=None, headers=None, timeout=25):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    h = {"User-Agent": UA, "Referer": REF, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw)


def _diff_to_list(data):
    """push2 clist 返回的 data.diff 可能是 dict(索引->行) 或 list。"""
    d = data.get("data") or {}
    diff = d.get("diff") or []
    if isinstance(diff, dict):
        return list(diff.values())
    return diff


# ------------------------- 龙虎榜 -------------------------
def fetch_billboard_raw(trade_date):
    p = {
        "reportName": "RPT_DAILYBILLBOARD_DETAILS",
        "columns": "ALL",
        "filter": "(TRADE_DATE='%s')" % trade_date,
        "pageSize": "300",
        "pageNumber": "1",
        "sortColumns": "BILLBOARD_NET_AMT",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    try:
        d = http_get_json(BILLBOARD_URL, p)
        return (d.get("result") or {}).get("data") or []
    except Exception:
        return []


def normalize_billboard(r):
    explain = r.get("EXPLAIN") or ""
    return {
        "code": r.get("SECURITY_CODE"),
        "name": r.get("SECURITY_NAME_ABBR"),
        "seucode": r.get("SECUCODE"),
        "date": (r.get("TRADE_DATE") or "")[:10],
        "close": r.get("CLOSE_PRICE"),
        "change_pct": r.get("CHANGE_RATE"),
        "turnover": r.get("TURNOVERRATE"),
        "buy_amt": r.get("BILLBOARD_BUY_AMT"),
        "sell_amt": r.get("BILLBOARD_SELL_AMT"),
        "net_amt": r.get("BILLBOARD_NET_AMT"),
        "deal_amt": r.get("BILLBOARD_DEAL_AMT"),
        "reason": r.get("EXPLANATION"),
        "explain": explain,
        "d1": r.get("D1_CLOSE_ADJCHRATE"),
        "d2": r.get("D2_CLOSE_ADJCHRATE"),
        "d5": r.get("D5_CLOSE_ADJCHRATE"),
        "d10": r.get("D10_CLOSE_ADJCHRATE"),
        "free_cap": r.get("FREE_MARKET_CAP"),
        "market": r.get("TRADE_MARKET"),
        # 解析 EXPLAIN 中的机构信息
        "inst_buy_cnt": _parse_inst_cnt(explain, "买入"),
        "inst_sell_cnt": _parse_inst_cnt(explain, "卖出"),
    }


def _parse_inst_cnt(text, direction):
    """从 '2家机构卖出' / '1家机构买入' 中解析机构家数。"""
    import re
    m = re.search(r"(\d+)\s*家机构%s" % direction, text or "")
    return int(m.group(1)) if m else 0


# ------------------------- push2 通用列表 -------------------------
def fetch_clist(fs, fid, pz, fields=FIELD_STOCK):
    p = {
        "pn": "1", "pz": str(pz), "po": "1", "np": "1", "fltt": "2",
        "invt": "2", "fid": fid, "fs": fs, "fields": fields,
    }
    try:
        d = http_get_json(PUSH2_URL, p)
        return _diff_to_list(d)
    except Exception:
        return []


def norm_stock(row):
    return {
        "code": row.get("f12"),
        "name": row.get("f14"),
        "price": _to_float(row.get("f2")),
        "change_pct": _to_float(row.get("f3")),
        "main_net": _to_float(row.get("f62")),          # 主力净流入(元)
        "main_net_pct": _to_float(row.get("f184")),     # 主力净占比(%)
        "main_in": _to_float(row.get("f66")),           # 主力流入(元)
        "super_net": _to_float(row.get("f69")),         # 超大单净流入
        "big_net": _to_float(row.get("f75")),           # 大单净流入
        "mid_net": _to_float(row.get("f78")),           # 中单净流入
        "small_net": _to_float(row.get("f81")),         # 小单净流入
    }


def norm_sector(row):
    return {
        "code": row.get("f12"),
        "name": row.get("f14"),
        "index": _to_float(row.get("f2")),
        "change_pct": _to_float(row.get("f3")),
        "main_net": _to_float(row.get("f62")),          # 主力净流入(元)
        "main_net_pct": _to_float(row.get("f184")),
        "leader_code": row.get("f104"),
        "leader_name": row.get("f105"),
    }


def _to_float(v):
    try:
        if v in (None, "", "-"):
            return None
        return float(v)
    except Exception:
        return None


# ------------------------- 交易日判定 -------------------------
def is_trading_day(d):
    return d.weekday() < 5  # 周一~周五


def latest_billboard_date():
    """返回东方财富有龙虎榜数据的最近交易日 (YYYY-MM-DD)。"""
    start = (datetime.date.today() - datetime.timedelta(days=15)).isoformat()
    p = {
        "reportName": "RPT_DAILYBILLBOARD_DETAILS",
        "columns": "TRADE_DATE",
        "filter": "(TRADE_DATE>='%s')" % start,
        "pageSize": "1", "pageNumber": "1",
        "sortColumns": "TRADE_DATE", "sortTypes": "-1",
        "source": "WEB", "client": "WEB",
    }
    try:
        d = http_get_json(BILLBOARD_URL, p)
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            return (rows[0].get("TRADE_DATE") or "")[:10]
    except Exception:
        pass
    return datetime.date.today().isoformat()


def resolve_trade_date():
    """龙虎榜/复盘以最近一个有数据的交易日为准。"""
    return latest_billboard_date()


# ------------------------- 龙虎榜席位明细（Tier B） -------------------------
# 逐席位（营业部/机构/沪深股通）买卖明细，免费、免鉴权。
# 买入席位：reportName=RPT_BILLBOARD_DAILYDETAILSBUY
# 卖出席位：reportName=RPT_BILLBOARD_DAILYDETAILSSELL
# filter=(TRADE_DATE='YYYY-MM-DD')  按交易日批量返回全部个股席位（翻页）
SEAT_BUY_REPORT = "RPT_BILLBOARD_DAILYDETAILSBUY"
SEAT_SELL_REPORT = "RPT_BILLBOARD_DAILYDETAILSSELL"
# East Money 按源 IP 限流，请求间留足间隔，避免封禁。
# 席位明细接口对单个 TRADE_DATE 返回全部上榜个股的席位（top5 买卖），
# 单页上限 500 行，需翻页；故每交易日仅需 BUY+SELL 各 2 页 ≈ 4 次请求。
SEAT_REQ_INTERVAL = 0.3
SEAT_PAGE_SIZE = 500


def _fetch_seat_page(report, trade_date, page):
    """抓取某交易日席位明细的单页（TRADE_DATE 维度，返回全部个股）。失败重试 2 次。"""
    p = {
        "reportName": report,
        "columns": "ALL",
        "filter": "(TRADE_DATE='%s')" % trade_date,
        "pageSize": str(SEAT_PAGE_SIZE), "pageNumber": str(page),
        "sortColumns": "SECURITY_CODE", "sortTypes": "1",
        "source": "WEB", "client": "WEB",
    }
    last_err = None
    for _ in range(3):
        try:
            d = http_get_json(BILLBOARD_URL, p)
            return (d.get("result") or {}).get("data") or []
        except Exception as e:
            last_err = e
            time.sleep(0.6)
    print("[eastmoney] 席位明细分页抓取失败 %s/%s p%s: %s" % (trade_date, report, page, last_err))
    return []


def _norm_seat(r, side, name_map):
    code = r.get("SECURITY_CODE") or (str(r.get("SECUCODE") or ""))[:6]
    return {
        "trade_date": (str(r.get("TRADE_DATE") or ""))[:10] or None,
        "code": code,
        "name": name_map.get(code) or r.get("SECURITY_NAME_ABBR") or None,
        "seat_code": r.get("OPERATEDEPT_CODE"),
        "seat_name": r.get("OPERATEDEPT_NAME"),
        "side": side,
        "buy_amt": r.get("BUY"),
        "sell_amt": r.get("SELL"),
        "net_amt": r.get("NET"),
        "rise_prob_3d": r.get("RISE_PROBABILITY_3DAY"),
        "trade_times_3d": r.get("TOTAL_BUYER_SALESTIMES_3DAY"),
        "explanation": r.get("EXPLANATION"),
        "trade_id": r.get("TRADE_ID"),
    }


def fetch_billboard_seats(trade_date, appearances=None):
    """抓取某交易日全部上榜个股的席位明细，合并为席位记录列表。

    采用 TRADE_DATE 维度批量抓取（BUY/SELL 各翻页至末页），远快于逐股请求。
    返回: [{
      trade_date, code, name, seat_code, seat_name, side(BUY/SELL),
      buy_amt, sell_amt, net_amt, rise_prob_3d, trade_times_3d,
      explanation, trade_id
    }, ...]
    """
    if appearances is None:
        raw = fetch_billboard_raw(trade_date)
        appearances = [normalize_billboard(r) for r in raw]
    name_map = {a.get("code"): a.get("name") for a in appearances if a.get("code")}
    seats = []
    for side, report in (("BUY", SEAT_BUY_REPORT), ("SELL", SEAT_SELL_REPORT)):
        page = 1
        while True:
            rows = _fetch_seat_page(report, trade_date, page)
            if not rows:
                break
            for r in rows:
                seats.append(_norm_seat(r, side, name_map))
            if len(rows) < SEAT_PAGE_SIZE:
                break  # 末页
            page += 1
            time.sleep(SEAT_REQ_INTERVAL)
        time.sleep(SEAT_REQ_INTERVAL)
    return seats


# ------------------------- 极速拉升（新浪财经，替代被封的 push2） -------------------------
SINA_MARKET_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
SINA_HEADERS = {"User-Agent": UA, "Referer": "https://vip.stock.finance.sina.com.cn/"}


def fetch_rapid_rise_sina(top_n=50, timeout=30):
    """用新浪市场行情接口获取全市场涨幅排行（替代被封的 push2）。

    新浪 VIP Market Center 接口返回沪深京全部 A 股的实时行情 JSON，
    含现价/涨跌幅/成交量/成交额/换手率等基础字段。
    按 changepercent 降序排序后取前 top_n 返回。

    返回: [{code, name, price, change_pct, volume, turnover, turnover_rate}, ...]
    若抓取失败返回空列表（不回退假数据）。
    """
    all_stocks = []
    page = 1
    while True:
        params = {
            "page": str(page), "num": "5000",
            "sort": "symbol", "asc": "1", "node": "hs_a",
            "symbol": "", "_s_r_a": "auto",
        }
        try:
            data = http_get_json(SINA_MARKET_URL, params, headers=SINA_HEADERS, timeout=timeout)
            if not data or not isinstance(data, list):
                break
            for item in data:
                change_pct = _to_float(item.get("changepercent"))
                if change_pct is None:
                    continue
                all_stocks.append({
                    "code": item.get("code"),
                    "name": item.get("name"),
                    "price": _to_float(item.get("trade")),
                    "change_pct": change_pct,
                    "volume": item.get("volume"),                 # 成交量(股)
                    "turnover": _to_float(item.get("amount")),   # 成交额(元)
                    "turnover_rate": _to_float(item.get("turnoverratio")),
                })
            if len(data) < 5000:
                break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print("[eastmoney] 新浪行情抓取失败: %s" % e)
            break

    all_stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    return all_stocks[:top_n]


# ------------------------- 涨停板（开盘红 kaipanhong） -------------------------
# 免费、免鉴权的历史涨停池接口，返回逐股涨停数据，含连板数/涨停原因/题材/
# 封单金额/净流入等，是“昨日涨停排行榜”的核心数据源。
# 限制：仅支持历史日期（date < 今天），当日数据由 TCP 长连接推送无法获取。
KPH_HOST = "https://apphis.kaipanhong.com/w1/api/index.php"
KPH_BASE = {
    "PhoneOSNew": "1",
    "DeviceID": "1a609dd6-b2b8-3bf9-ac40-a77581551454",
    "VerSion": "6.0.6",
    "Token": "0",
    "UserID": "0",
    "Red": "1",
    "apiv": "w45",
}
KPH_HEAD = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; 2206123SC Build/c069a49.2)",
    "Accept-Encoding": "gzip",
}
KPH_PAGE = 50


def _kph_post(params, timeout=20):
    data = urllib.parse.urlencode({**KPH_BASE, **params}).encode("utf-8")
    req = urllib.request.Request(KPH_HOST, data=data, headers=KPH_HEAD, method="POST")
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":  # gzip
        import gzip
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", "ignore"))


def _parse_kph_row(row):
    """解析开盘红涨停数据行（索引取自 levistock 源码）。"""
    def g(i):
        return row[i] if i < len(row) else None
    return {
        "code": g(0),
        "name": g(1),
        "limit_time": g(6),
        "open_time": g(7),
        "seal_amount": g(8),
        "limit_tag": g(9),
        "limit_count": g(10),
        "themes": g(11),
        "net_inflow": g(12),
        "turnover": g(13),
        "turnover_rate": g(14),
        "market_cap": g(15),
        "reason": g(16),
        "seal_money": g(23),
        "industry_id": g(26),
        "industry_zt": g(27),
    }


def fetch_limit_up(trade_date, timeout=20):
    """抓取某交易日涨停股票列表（开盘红历史涨停池）。

    返回: [{trade_date, code, name, limit_count, limit_tag, reason, themes,
            industry_id, industry_zt, seal_amount, seal_money, net_inflow,
            turnover, turnover_rate, market_cap, limit_time, open_time}, ...]
    若 trade_date >= 今天（开盘红不支持当日/未来），返回空列表。
    """
    try:
        d = datetime.datetime.strptime(trade_date, "%Y-%m-%d").date()
    except Exception:
        return []
    if d >= datetime.date.today():
        return []
    rows = []
    index = 0
    while True:
        try:
            j = _kph_post({
                "a": "HisDaBanList", "c": "HisHomeDingPan",
                "Order": "1", "st": str(KPH_PAGE), "Index": str(index),
                "Is_st": "1", "PidType": "4", "Type": "6",
                "FilterMotherboard": "0", "Filter": "0",
                "FilterTIB": "0", "FilterGem": "0", "Day": trade_date,
            }, timeout=timeout)
        except Exception as e:
            print("[eastmoney] 开盘红涨停抓取失败 %s: %s" % (trade_date, e))
            break
        if j.get("errcode") != "0":
            print("[eastmoney] 开盘红返回异常 %s: errcode=%s" % (trade_date, j.get("errcode")))
            break
        batch = j.get("list") or []
        for r in batch:
            rec = _parse_kph_row(r)
            rec["trade_date"] = trade_date
            rows.append(rec)
        if len(batch) < KPH_PAGE:
            break
        index += KPH_PAGE
        time.sleep(0.3)
    return rows


# ------------------------- 个股近期公告（东方财富 np-anotice，best-effort） -------------------------
# 说明：np-anotice 的按股过滤参数在沙箱环境不稳定，故拉取最新公告后在本地按
# 股票名称做关键词匹配，作为“近期新闻/公告”的尽力而为来源。
ANN_HOST = "https://np-anotice-stock.eastmoney.com/api/security/ann"
_ANN_CACHE = {"ts": 0, "items": []}


def _fetch_latest_announcements(limit=120):
    now = time.time()
    if now - _ANN_CACHE["ts"] < 600 and _ANN_CACHE["items"]:
        return _ANN_CACHE["items"]
    items = []
    try:
        for page in range(1, 4):  # 最多 3 页 ≈ 150 条
            url = "%s?sr=-1&page_size=50&page_index=%d&client_source=web" % (ANN_HOST, page)
            j = http_get_json(url, headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"}, timeout=15)
            lst = (j.get("data") or {}).get("list") or []
            if not lst:
                break
            items.extend(lst)
            if len(lst) < 50:
                break
            time.sleep(0.2)
        _ANN_CACHE["ts"] = now
        _ANN_CACHE["items"] = items
    except Exception as e:
        print("[eastmoney] 公告抓取失败: %s" % e)
    return items


def fetch_stock_news(code, name, limit=10):
    """按股票名称尽力匹配近期公告，返回新闻/公告列表。

    返回: [{title, time, art_code, types}]（types 为公告栏目名列表）。
    若无可匹配项，返回空列表。
    """
    if not name:
        return []
    items = _fetch_latest_announcements()
    kw = name.replace(" ", "")
    out = []
    for it in items:
        title = (it.get("title") or "")
        cols = it.get("columns") or []
        col_names = [c.get("column_name", "") for c in cols if isinstance(c, dict)]
        short_names = [(c.get("short_name", "") if isinstance(c, dict) else "") for c in (it.get("codes") or [])]
        hit = (kw and kw in title) or name in col_names or name in short_names
        if hit:
            out.append({
                "title": title,
                "time": (it.get("display_time") or "")[:19],
                "art_code": it.get("art_code"),
                "types": [x for x in col_names if x],
            })
        if len(out) >= limit:
            break
    return out
