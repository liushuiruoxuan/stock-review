"""
全球财经数据（v2）：全球主要指数 / 商品 / 外汇行情 + 财经要闻快讯。

数据源选型（服务器出口 IP 实测结论，2026-09-03）：
  - 行情：新浪 hq.sinajs.cn
      东财 push2his 在该 IP 被持久限流，新浪全球指数/商品/外汇全部可用且无需 key。
      注意不同前缀字段位置完全不同，按前缀分派解析（见 _PARSERS）。
  - 要闻：新浪财经 7x24 直播（zhibo_id=152，主源，实时）
          → 东财快讯 np-listapi（备源；该域名未被限流，与 push2his 不同域）

设计要点：
  - 进程内 TTL 缓存：大屏 30s 轮询，避免高频打上游触发限流
  - 逐条容错：单只解析失败跳过，整源不可用返回空结构由前端降级展示
  - 涨跌幅优先取源字段，缺失时用 (close - prev_close) / prev_close 反算
"""
import json
import ssl
import time
import urllib.request

SINA_QUOTE = "https://hq.sinajs.cn/list="
SINA_NEWS = ("https://zhibo.sina.com.cn/api/zhibo/feed"
             "?page=1&page_size=20&zhibo_id=152&tag_id=0&dire=f&dpc=1")
EM_NEWS = ("https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
           "?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=20&req_trace=1")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"
SINA_REFERER = "https://finance.sina.com.cn/"
EM_REFERER = "https://kuaixun.eastmoney.com/"

QUOTE_TTL = 25      # 行情缓存秒数（大屏 30s 轮询，保证每次刷新基本拿到新值）
NEWS_TTL = 60       # 要闻缓存秒数

# (新浪代码, 显示名, 分组)
# 说明：int_dax / int_cac / znb_CAC40 / hf_DX 实测返回空，故 DAX/富时统一用 znb_ 前缀
QUOTE_DEFS = [
    ("gb_dji",     "道琼斯",    "美股"),
    ("gb_ixic",    "纳斯达克",  "美股"),
    ("gb_inx",     "标普500",   "美股"),
    ("rt_hkHSI",   "恒生指数",  "港股"),
    ("rt_hkHSCEI", "国企指数",  "港股"),
    ("int_nikkei", "日经225",   "亚太"),
    ("znb_DAX",    "德国DAX",   "欧洲"),
    ("znb_FTSE",   "富时100",   "欧洲"),
    ("hf_GC",      "纽约黄金",  "商品"),
    ("hf_CL",      "纽约原油",  "商品"),
    ("hf_SI",      "纽约白银",  "商品"),
    ("fx_susdcny", "美元/人民币", "外汇"),
]

_SSL_CTX = None
_CACHE = {"quotes": None, "quotes_ts": 0.0, "news": None, "news_ts": 0.0}


def _ctx():
    global _SSL_CTX
    if _SSL_CTX is None:
        _SSL_CTX = ssl.create_default_context()
        _SSL_CTX.check_hostname = False
        _SSL_CTX.verify_mode = ssl.CERT_NONE
    return _SSL_CTX


def _http_get(url, referer, timeout=12, encoding="utf-8"):
    """GET 文本。失败返回 None（不抛异常，由调用方降级）。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": referer, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read().decode(encoding, "ignore")
    except Exception:
        return None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct_of(close, chg, prev):
    """涨跌幅：优先反算，保证与涨跌额口径一致。"""
    if close is None or prev is None:
        return None
    if not prev:
        return None
    return (close - prev) / prev * 100


# ====== 各前缀解析（字段位置由实测确定）======

def _parse_gb(p):
    """美股 gb_：名称,现价,涨跌幅%,时间,涨跌额,开,高,低,...,昨收(26)"""
    close, pct, chg = _f(p[1]), _f(p[2]), _f(p[4])
    prev = _f(p[26]) if len(p) > 26 else None
    if prev is None and close is not None and chg is not None:
        prev = close - chg
    return {"close": close, "chg": chg, "prev_close": prev, "pct": pct,
            "time": p[3] if len(p) > 3 else None}


def _parse_int(p):
    """国际指数 int_：名称,现价,涨跌额,涨跌幅%"""
    close, chg, pct = _f(p[1]), _f(p[2]), _f(p[3])
    prev = (close - chg) if (close is not None and chg is not None) else None
    return {"close": close, "chg": chg, "prev_close": prev, "pct": pct, "time": None}


def _parse_znb(p):
    """欧洲 znb_：名称,现价,涨跌额,涨跌幅%,...,日期(6),时间(7),...,昨收(9)"""
    close, chg, pct = _f(p[1]), _f(p[2]), _f(p[3])
    prev = _f(p[9]) if len(p) > 9 else None
    if prev is None and close is not None and chg is not None:
        prev = close - chg
    tm = None
    if len(p) > 7 and p[6] and p[7]:
        tm = "%s %s" % (p[6], p[7])
    return {"close": close, "chg": chg, "prev_close": prev, "pct": pct, "time": tm}


def _parse_rt_hk(p):
    """港股 rt_hk：代码,名称,今开,昨收,最高,最低,现价,涨跌额,涨跌幅%"""
    close, chg, pct = _f(p[6]), _f(p[7]), _f(p[8])
    return {"close": close, "chg": chg, "prev_close": _f(p[3]), "pct": pct,
            "time": None}


def _parse_hf(p):
    """商品 hf_：现价,,买,卖,最高,最低,时间(6),昨收(7),开盘(8),...,名称(13)"""
    close = _f(p[0])
    prev = _f(p[7]) if len(p) > 7 else None
    chg = (close - prev) if (close is not None and prev is not None) else None
    return {"close": close, "chg": chg, "prev_close": prev,
            "pct": _pct_of(close, chg, prev), "time": p[6] if len(p) > 6 else None}


def _parse_fx(p):
    """外汇 fx_：时间(0),现价(1),...,昨收(8)"""
    close = _f(p[1])
    prev = _f(p[8]) if len(p) > 8 else None
    chg = (close - prev) if (close is not None and prev is not None) else None
    return {"close": close, "chg": chg, "prev_close": prev,
            "pct": _pct_of(close, chg, prev), "time": p[0]}


_PARSERS = (
    ("gb_", _parse_gb),
    ("rt_hk", _parse_rt_hk),
    ("znb_", _parse_znb),
    ("int_", _parse_int),
    ("hf_", _parse_hf),
    ("fx_", _parse_fx),
)


def _parse_one(code, raw):
    """按前缀分派解析单只行情。失败返回 None。"""
    if not raw:
        return None
    p = raw.split(",")
    if len(p) < 2 or not p[0]:
        return None
    for prefix, fn in _PARSERS:
        if code.startswith(prefix):
            try:
                return fn(p)
            except (ValueError, IndexError, TypeError):
                return None
    return None


def _round(v, n=2):
    return None if v is None else round(v, n)


def _digits(code):
    """外汇保留 4 位小数（6.7183），其余 2 位。"""
    return 4 if code.startswith("fx_") else 2


def fetch_global_quotes(force=False):
    """全球行情。返回 {"updated_at": str|None, "quotes": [{code,name,group,close,chg,pct,time}]}"""
    now = time.time()
    if not force and _CACHE["quotes"] and now - _CACHE["quotes_ts"] < QUOTE_TTL:
        return _CACHE["quotes"]

    url = SINA_QUOTE + ",".join(c for c, _, _ in QUOTE_DEFS)
    raw = _http_get(url, SINA_REFERER, encoding="gbk")

    out = []
    if raw:
        kvs = {}
        for line in raw.strip().split("\n"):
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            kvs[k.replace("var hq_str_", "").strip()] = v.strip().strip(";").strip('"')
        for code, name, group in QUOTE_DEFS:
            d = _parse_one(code, kvs.get(code, ""))
            if not d or d.get("close") is None:
                continue
            pct = d.get("pct")
            if pct is None:
                pct = _pct_of(d.get("close"), d.get("chg"), d.get("prev_close"))
            nd = _digits(code)
            out.append({
                "code": code, "name": name, "group": group,
                "close": _round(d["close"], nd), "chg": _round(d.get("chg"), nd),
                "pct": _round(pct, 2), "time": d.get("time"),
            })

    res = {"updated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "quotes": out}
    # 源不可用且无缓存时，不写入空结果，避免短暂失败把好数据冲掉
    if out or _CACHE["quotes"] is None:
        _CACHE["quotes"] = res
        _CACHE["quotes_ts"] = now
        return res
    return _CACHE["quotes"]


def _clean(s):
    s = (s or "").replace("\r", " ").replace("\n", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


def _hhmm(t):
    """'2026-09-03 14:04:37' → '14:04'"""
    t = t or ""
    return t[11:16] if len(t) >= 16 else t


def _news_sina(limit):
    """新浪财经 7x24（主源）。"""
    raw = _http_get(SINA_NEWS, SINA_REFERER)
    if not raw:
        return []
    try:
        j = json.loads(raw)
    except ValueError:
        return []
    lst = ((j.get("result") or {}).get("data") or {}).get("feed", {}).get("list") or []
    out = []
    for it in lst:
        txt = _clean(it.get("rich_text") or it.get("text") or "")
        if not txt:
            continue
        out.append({"time": _hhmm(it.get("create_time")), "text": txt,
                    "source": "新浪7x24"})
        if len(out) >= limit:
            break
    return out


def _news_em(limit):
    """东财快讯（备源，np-listapi 域名未被限流）。"""
    raw = _http_get(EM_NEWS, EM_REFERER)
    if not raw:
        return []
    try:
        j = json.loads(raw)
    except ValueError:
        return []
    lst = (j.get("data") or {}).get("fastNewsList") or []
    out = []
    for it in lst:
        txt = _clean(it.get("summary") or it.get("title") or "")
        if not txt:
            continue
        out.append({"time": _hhmm(it.get("showTime")), "text": txt,
                    "source": "东财快讯"})
        if len(out) >= limit:
            break
    return out


def fetch_finance_news(limit=12, force=False):
    """财经要闻快讯。返回 [{time, text, source}]，源全不可用时返回 []。"""
    now = time.time()
    if not force and _CACHE["news"] and now - _CACHE["news_ts"] < NEWS_TTL:
        return _CACHE["news"]
    out = _news_sina(limit) or _news_em(limit)
    if out:
        _CACHE["news"] = out
        _CACHE["news_ts"] = now
    elif _CACHE["news"] is None:
        _CACHE["news"] = []
        _CACHE["news_ts"] = now
    return _CACHE["news"]


def snapshot(limit=12, force=False):
    """聚合：行情 + 要闻，供大屏一次请求取全。"""
    return {
        "quotes": fetch_global_quotes(force=force),
        "news": fetch_finance_news(limit=limit, force=force),
    }
