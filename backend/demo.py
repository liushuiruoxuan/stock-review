"""
内置示例数据（仅当实时接口返回空时使用，UI 会标注“示例数据”）。
使用真实知名标的名称 + 基于交易日种子的稳定随机值，便于预览与演示。
"""

import random
import datetime

# 真实知名标的（代码, 名称）
STOCKS = [
    ("600519", "贵州茅台"), ("300750", "宁德时代"), ("002594", "比亚迪"),
    ("601012", "隆基绿能"), ("000858", "五粮液"), ("600036", "招商银行"),
    ("601318", "中国平安"), ("000333", "美的集团"), ("600276", "恒瑞医药"),
    ("002415", "海康威视"), ("600900", "长江电力"), ("601899", "紫金矿业"),
    ("300059", "东方财富"), ("688981", "中芯国际"), ("002230", "科大讯飞"),
    ("600030", "中信证券"), ("000001", "平安银行"), ("601166", "兴业银行"),
    ("300760", "迈瑞医疗"), ("002475", "立讯精密"), ("600887", "伊利股份"),
    ("601888", "中国中免"), ("000651", "格力电器"), ("603259", "药明康德"),
    ("688041", "海光信息"), ("300308", "中际旭创"), ("002371", "北方华创"),
]

SECTORS = [
    ("半导体", 4.8), ("人工智能", 3.6), ("汽车整车", 2.9), ("光伏设备", 2.2),
    ("白酒", 1.8), ("证券", 1.5), ("银行", 0.9), ("医药生物", 1.2),
    ("消费电子", 2.4), ("军工", 1.1), ("有色金属", 0.7), ("煤炭", -0.6),
    ("房地产", -1.3), ("钢铁", -0.9), ("教育", -2.1), ("传媒", -1.7),
]


def _seed(trade_date):
    s = 0
    for ch in trade_date:
        s = (s * 31 + ord(ch)) % (2 ** 31)
    return random.Random(s)


def gen_stocks(trade_date, n=60):
    rnd = _seed(trade_date + "stock")
    out = []
    pool = STOCKS + [("60%03d" % (1000 + i), "示例股%s" % chr(65 + i % 26)) for i in range(20)]
    rnd.shuffle(pool)
    for code, name in pool[:n]:
        change = round(rnd.uniform(-6, 10), 2)
        price = round(rnd.uniform(8, 1800), 2)
        main_net = round(rnd.uniform(-8, 12), 2) * 1e8  # 元
        out.append({
            "code": code, "name": name, "price": price,
            "change_pct": change,
            "main_net": main_net,
            "main_net_pct": round(rnd.uniform(-8, 12), 2),
            "main_in": abs(main_net) + rnd.uniform(0, 5e8),
            "super_net": round(rnd.uniform(-5, 8), 2) * 1e8,
            "big_net": round(rnd.uniform(-5, 8), 2) * 1e8,
            "mid_net": round(rnd.uniform(-4, 4), 2) * 1e8,
            "small_net": round(rnd.uniform(-4, 4), 2) * 1e8,
        })
    return out


def gen_sectors(trade_date):
    rnd = _seed(trade_date + "sector")
    out = []
    for name, base in SECTORS:
        change = round(base + rnd.uniform(-0.8, 0.8), 2)
        main_net = round((base * 8 + rnd.uniform(-3, 6)), 2) * 1e8
        out.append({
            "code": "", "name": name, "index": round(rnd.uniform(800, 3500), 2),
            "change_pct": change,
            "main_net": main_net,
            "main_net_pct": round(rnd.uniform(-6, 10), 2),
            "leader_code": "", "leader_name": rnd.choice([n for _, n in STOCKS[:12]]),
        })
    return out


def gen_billboard(trade_date, n=40):
    """龙虎榜示例（实时不可用时）。"""
    rnd = _seed(trade_date + "bb")
    pool = STOCKS + [("30%03d" % (1000 + i), "示例股%s" % chr(65 + i % 26)) for i in range(20)]
    rnd.shuffle(pool)
    out = []
    reasons = ["日涨幅偏离值达7%", "日换手率达20%", "日振幅值达15%", "连续三个交易日涨幅偏离20%", "ST股日均换手超25%"]
    for i, (code, name) in enumerate(pool[:n]):
        net = round(rnd.uniform(-3, 6), 2) * 1e8
        out.append({
            "code": code, "name": name, "seucode": "",
            "date": trade_date,
            "close": round(rnd.uniform(6, 120), 2),
            "change_pct": round(rnd.uniform(-10, 11), 2),
            "turnover": round(rnd.uniform(3, 35), 2),
            "buy_amt": abs(net) + rnd.uniform(1, 8) * 1e8,
            "sell_amt": rnd.uniform(1, 8) * 1e8,
            "net_amt": net,
            "deal_amt": rnd.uniform(3, 20) * 1e8,
            "reason": rnd.choice(reasons),
            "explain": rnd.choice(["", "1家机构买入，成功率62.3%", "2家机构卖出，成功率11.99%", "游资博弈，买一主买"]),
            "d1": round(rnd.uniform(-9, 9), 2),
            "d2": None, "free_cap": rnd.uniform(40, 600) * 1e8,
            "market": "上交所主板" if code.startswith("6") else "深交所主板",
            "inst_buy_cnt": rnd.choice([0, 0, 1, 2]),
            "inst_sell_cnt": rnd.choice([0, 0, 1]),
        })
    return out
