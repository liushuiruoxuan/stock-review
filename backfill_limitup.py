import sys
sys.path.insert(0, "/app/backend")
import db, eastmoney as em, datetime, server

# 1) 补齐近期交易日的涨停数据（独立于龙虎榜是否已存，避免时区守卫漏存）
end = datetime.date(2026, 7, 23)
d = end
saved = 0
for _ in range(45):
    if em.is_trading_day(d):
        td = d.isoformat()
        if not db.load_limit_up(td):
            try:
                lu = em.fetch_limit_up(td)
            except Exception as e:
                lu = None
                print("fetch_limit_up %s EXC: %s" % (td, e))
            if lu:
                db.save_limit_up(lu)
                saved += 1
                print("limit_up saved %s -> %d rows" % (td, len(lu)))
    d -= datetime.timedelta(days=1)
print("total limit_up saved:", saved)

# 2) 重算并写入热点重合榜（不重抓席位，直接用已存龙虎榜+涨停）
for td in ["2026-07-23", "2026-07-22", "2026-07-21"]:
    lu = db.load_limit_up(td) or []
    hb_date = td
    hb_bb = db.load_section(td, "billboard") or []
    if not lu:
        lu_dates = db.list_limitup_dates()
        if lu_dates:
            hb_date = lu_dates[0]
            lu = db.load_limit_up(hb_date) or []
            hb_bb = db.load_section(hb_date, "billboard") or []
            if not hb_bb:
                raw = em.fetch_billboard_raw(hb_date)
                hb_bb = [em.normalize_billboard(r) for r in raw] if raw else []
    hb = server.compute_hot_billboard(hb_bb, lu)
    for it in hb:
        it["hb_date"] = hb_date
    server.save_cache("hot_billboard", td, hb)
    db.save_section(td, "hot_billboard", hb)
    print("hot_billboard %s -> %d items (hb_date=%s, lu=%d, bb=%d)"
          % (td, len(hb), hb_date, len(lu), len(hb_bb)))
print("DONE")
