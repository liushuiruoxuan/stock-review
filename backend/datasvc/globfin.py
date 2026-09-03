"""
全球财经数据（v2）：全球主要指数 / 商品 / 外汇行情 + 财经要闻快讯。

数据源选型（服务器出口 IP 实测结论，2026-09-03）：
  - 行情（混合，各自尽力）：
      * 美股/港股指数：腾讯 qt.gtimg.cn —— 容器稳定可达（200，~0.2s），覆盖道指/纳指/恒生等。
      * 标普/亚太/欧洲/商品/外汇：东方财富 push2 ulist.np —— 覆盖最全，但服务器 IP 对该域
        间歇性限流（RemoteDisconnected），故带重试；被限流时这些分组降级为空，不影响已得的
        美股/港股。
      （注：原新浪 hq.sinajs.cn 行情源在本环境容器 DNS 不可达，已弃用。）
  - 要闻：新浪财经 7x24 直播（zhibo_id=152，主源，实测 200）→ 东财快讯 np-listapi（备源）。

设计要点：
  - 进程内 TTL 缓存：大屏 30s 轮询，避免高频打上游触发限流
  - 逐条容错：单只解析失败跳过；整源不可用返回空结构由前端降级展示
  - 输出结构稳定：quotes={updated_at, quotes:[{code,name,group,close,chg,pct,time}]}
"""
import datetime
import json
import ssl
import time
import urllib.request

SINA_NEWS = ("https://zhibo.sina.com.cn/api/zhibo/feed"
             "?page=1&page_size=20&zhibo_id=152&tag_id=0&dire=f&dpc=1")
EM_NEWS = ("https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
           "?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=20&req_trace=1")

# 行情源
TX_QUOTE = "https://qt.gtimg.cn/q="
EM_QUOTE = ("https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&"
            "fields=f1,f2,f3,f4,f6,f12,f13,f14&secids=")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"
SINA_REFERER = "https://finance.sina.com.cn/"
EM_REFERER = "https://kuaixun.eastmoney.com/"
TX_REFERER = "https://gu.qq.com/"

QUOTE_TTL = 25      # 行情缓存秒数（大屏 30s 轮询，保证每次刷新基本拿到新值）
NEWS_TTL = 60       # 要闻缓存秒数

# (源, 上游代码, 对外code, 显示名, 分组)
# 美股/港股走腾讯(稳)；标普/亚太/欧洲/商品/外汇走东财(尽力)。
# 外汇对外 code 以 fx_ 开头：前端/后端均按此前缀保留 4 位小数。
QUOTE_DEFS = [
    ("tx", "usDJI", "usDJI", "道琼斯", "美股"),
    ("tx", "usIXIC", "usIXIC", "纳斯达克", "美股"),
    ("tx", "usNDX", "usNDX", "纳斯达克100", "美股"),
    ("tx", "hkHSI", "hkHSI", "恒生指数", "港股"),
    ("tx", "hkHSCEI", "hkHSCEI", "国企指数", "港股"),
    ("tx", "hkHSTECH", "hkHSTECH", "恒生科技", "港股"),
    ("em", "100.SPX", "SPX", "标普500", "美股"),
    ("em", "100.N225", "N225", "日经225", "亚太"),
    ("em", "100.KOSPI", "KOSPI", "韩国KOSPI", "亚太"),
    ("em", "100.TWII", "TWII", "台湾加权", "亚太"),
    ("em", "100.GDAXI", "GDAXI", "德国DAX", "欧洲"),
    ("em", "100.FCHI", "FCHI", "法国CAC40", "欧洲"),
    ("em", "100.FTSE", "FTSE", "英国富时100", "欧洲"),
    ("em", "101.XAU", "XAU", "伦敦金", "商品"),
    ("em", "101.XAG", "XAG", "伦敦银", "商品"),
    ("em", "101.CL", "CL", "WTI原油", "商品"),
    ("em", "101.BRENT", "BRENT", "布伦特原油", "商品"),
    ("em", "119.USDCNH", "fx_usdcnh", "美元/离岸人民币", "外汇"),
    ("em", "119.USDJPY", "fx_usdjpy", "美元/日元", "外汇"),
    ("em", "119.USDIX", "USDIX", "美元指数", "外汇"),
]

_SSL_CTX = None
_CACHE = {"quotes": None, "quotes_ts": 0.0, "news": None, "news_ts": 0.0}

# 容器时区为 UTC，直接 time.strftime 会显示成凌晨，与新闻的北京时间对不上
_CST = datetime.timezone(datetime.timedelta(hours=8))


def _now_cst():
    """北京时间 'YYYY-MM-DD HH:MM:SS'。"""
    return datetime.datetime.now(_CST).strftime("%Y-%m-%d %H:%M:%S")


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
    if close is None or prev is None or not prev:
        return None
    return (close - prev) / prev * 100


def _round(v, n=2):
    return None if v is None else round(v, n)


def _digits(code):
    """外汇保留 4 位小数（6.7183），其余 2 位。"""
    return 4 if (code or "").startswith("fx_") else 2


# ====== 行情抓取（腾讯 + 东财，尽力合并）======

def _fetch_tencent():
    """腾讯 qt.gtimg.cn → {sym: {close, pct}}。仅美股/港股可靠。"""
    syms = [d[1] for d in QUOTE_DEFS if d[0] == "tx"]
    url = TX_QUOTE + ",".join("s_" + s for s in syms)
    raw = _http_get(url, TX_REFERER, encoding="gbk")
    out = {}
    if not raw:
        return out
    for line in raw.split(";"):
        line = line.strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip().strip('"')
        if not val or "~" not in val:
            continue
        sym = key.replace("v_s_", "").strip()
        p = val.split("~")
        try:
            close = float(p[3])
            pct = float(p[5])
        except (ValueError, IndexError):
            continue
        out[sym] = {"close": close, "pct": pct, "time": None}
    return out


def _fetch_eastmoney():
    """东财 push2 ulist.np → {f12: {close, pct}}。补全 标普/亚太/欧洲/商品/外汇。
    该域在服务器 IP 间歇性限流，故重试一次；失败返回空（这些分组降级）。"""
    secids = [d[1] for d in QUOTE_DEFS if d[0] == "em"]
    url = EM_QUOTE + ",".join(secids)
    out = {}
    for attempt in range(2):
        try:
            raw = _http_get(url, EM_REFERER)
            if not raw:
                if attempt == 0:
                    time.sleep(1)
                    continue
                break
            j = json.loads(raw)
            diff = (j.get("data") or {}).get("diff") or []
            for d in diff:
                f12 = d.get("f12")
                try:
                    close = float(d.get("f2"))
                    pct = float(d.get("f3"))
                except (TypeError, ValueError):
                    continue
                out[f12] = {"close": close, "pct": pct, "time": None}
            break
        except Exception:
            if attempt == 0:
                time.sleep(1)
                continue
            break
    return out


def fetch_global_quotes(force=False):
    """全球行情。返回 {"updated_at": str|None, "quotes": [{code,name,group,close,chg,pct,time}]}"""
    now = time.time()
    if not force and _CACHE["quotes"] and now - _CACHE["quotes_ts"] < QUOTE_TTL:
        return _CACHE["quotes"]

    tdata = _fetch_tencent()
    edata = _fetch_eastmoney()
    out = []
    for src, fetch_code, emit_code, name, group in QUOTE_DEFS:
        d = tdata.get(fetch_code) if src == "tx" else edata.get(fetch_code)
        if not d or d.get("close") is None:
            continue
        nd = _digits(emit_code)
        out.append({
            "code": emit_code, "name": name, "group": group,
            "close": _round(d["close"], nd),
            "chg": _round(d.get("chg"), nd),
            "pct": _round(d.get("pct"), 2),
            "time": d.get("time"),
        })

    res = {"updated_at": _now_cst(), "quotes": out}
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
