"""回填历史涨停数据（开盘红）。

遍历已有龙虎榜交易日（db.list_dates），逐日抓取涨停池并写入 stock_review_limitup。
开盘红仅支持历史日期（date < 今天），故仅对过去交易日生效。

用法：
  cd /app/backend && python backfill_limitup.py
"""
import sys
import time

sys.path.insert(0, "/app/backend")
import db
import eastmoney as em

dates = db.list_dates()
print("待回填交易日：%d" % len(dates))
ok = 0
skip = 0
for i, d in enumerate(dates, 1):
    if db.load_limit_up(d):
        skip += 1
        continue
    rows = em.fetch_limit_up(d)
    if rows:
        n = db.save_limit_up(rows)
        ok += 1
        print("[%d/%d] %s 涨停 %d 只" % (i, len(dates), d, n))
    else:
        print("[%d/%d] %s 无涨停数据（可能非交易日或源不可用）" % (i, len(dates), d))
    time.sleep(0.5)

print("完成：新增 %d 天，跳过(已有) %d 天" % (ok, skip))
