"""
席位明细历史回填：对已有龙虎榜交易日逐日抓取席位明细并落库。
在容器内执行： docker compose exec stock-review-web-1 python backfill_seats.py
- 断点续传：已存在的交易日跳过。
- 限流：复用 eastmoney.fetch_billboard_seats 内置 sleep(0.4)。
"""
import sys
import time

sys.path.insert(0, "/app/backend")
import db
import em


def main():
    dates = db.list_dates()
    if not dates:
        print("[backfill_seats] 未找到龙虎榜交易日，无法回填。")
        return
    print("[backfill_seats] 待处理日期(%d): %s" % (len(dates), dates))
    done = 0
    for td in dates:
        if db.has_seat_date(td):
            print("  跳过(已有):", td)
            continue
        print("  抓取席位明细:", td)
        try:
            seats = em.fetch_billboard_seats(td)  # appearances=None 内部自取
        except Exception as e:
            print("    抓取异常:", e)
            continue
        if seats:
            ok = db.save_seats(seats)
            print("    写入 %d 条, ok=%s" % (len(seats), ok))
            done += 1
        else:
            print("    无席位数据（可能当日接口空）。")
        time.sleep(1)
    print("[backfill_seats] 完成，本次新增 %d 个交易日。" % done)


if __name__ == "__main__":
    main()
