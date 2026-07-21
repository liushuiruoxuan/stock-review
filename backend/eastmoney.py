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
# filter=(TRADE_DATE='YYYY-MM-DD')(SECURITY_CODE="XXXXXX")
SEAT_BUY_REPORT = "RPT_BILLBOARD_DAILYDETAILSBUY"
SEAT_SELL_REPORT = "RPT_BILLBOARD_DAILYDETAILSSELL"
# East Money 按源 IP 限流（约 0.5 rps），请求间留足间隔，避免封禁。
SEAT_REQ_INTERVAL = 0.4


def _fetch_seat_detail(trade_date, security_code, side):
    """抓取单只票的单侧（BUY/SELL）席位明细，失败重试 2 次。"""
    report = SEAT_BUY_REPORT if side == "BUY" else SEAT_SELL_REPORT
    p = {
        "reportName": report,
        "columns": "ALL",
        "filter": "(TRADE_DATE='%s')(SECURITY_CODE=\"%s\")" % (trade_date, security_code),
        "pageSize": "50", "pageNumber": "1",
        "sortColumns": "BUY" if side == "BUY" else "SELL",
        "sortTypes": "-1",
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
    print("[eastmoney] 席位明细抓取失败 %s/%s/%s: %s" % (trade_date, security_code, side, last_err))
    return []


def fetch_billboard_seats(trade_date, appearances=None):
    """抓取某交易日全部上榜个股的席位明细，合并为席位记录列表。

    appearances: 可选，已归一化的龙虎榜列表（含 code/name）。
                 不传则内部先抓当日 appearances。
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
    for a in appearances:
        code = a.get("code")
        if not code:
            continue
        name = a.get("name") or name_map.get(code)
        for side in ("BUY", "SELL"):
            rows = _fetch_seat_detail(trade_date, code, side)
            for r in rows:
                seats.append({
                    "trade_date": (r.get("TRADE_DATE") or "")[:10] or trade_date,
                    "code": r.get("SECURITY_CODE"),
                    "name": name,
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
                })
            time.sleep(SEAT_REQ_INTERVAL)  # 限流
    return seats
