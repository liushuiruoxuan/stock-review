"""
定时调度（v2，APScheduler 替代旧 server.py 内的 scheduler_loop）。

任务（均为北京时间）：
  - 15:35 / 16:30 / 18:00 / 20:00  看板数据构建（龙虎榜/席位/涨停，沿用旧逻辑）
  - 17:10  行情日线增量 + 指数/日历
  - 每日一次  历史缺失补齐（backfill_recent）
"""
import datetime
import threading

import db
import marketdb
import server as legacy_server

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAVE_APS = True
except Exception:
    HAVE_APS = False

# 容器时钟为 UTC：统一用固定 +8 时区，避免 slim 镜像缺 tzdata
CST = datetime.timezone(datetime.timedelta(hours=8))

_scheduler = None
_daily_backfill_done = {"date": None}


def _build_today():
    try:
        td = legacy_server.STATE.get("trade_date")
        legacy_server.build_all(td, force=True)
    except Exception as e:
        print("[jobs] 看板构建失败：", e)


def _sync_daily_bars():
    try:
        from datasvc import bars
        bars.sync_bars_daily()
    except Exception as e:
        print("[jobs] 日线增量失败：", e)


def _daily_backfill():
    """每日一次补齐历史缺失（含周末/假期漏抓）。"""
    today = datetime.datetime.now(CST).strftime("%Y-%m-%d")
    if _daily_backfill_done["date"] == today:
        return
    try:
        legacy_server.backfill_recent()
        _daily_backfill_done["date"] = today
    except Exception as e:
        print("[jobs] backfill 失败：", e)


def _fallback_loop():
    """无 APScheduler 时的兜底轮询（与旧 scheduler_loop 等价）。"""
    while True:
        import time
        try:
            now = datetime.datetime.now(CST)
            if now.weekday() < 5:
                for h, m in ((15, 35), (16, 30), (18, 0), (20, 0)):
                    if now.hour == h and now.minute >= m and now.minute < m + 2:
                        _build_today()
                if now.hour == 17 and now.minute >= 10 and now.minute < 12:
                    _sync_daily_bars()
            _daily_backfill()
        except Exception as e:
            print("[jobs] 兜底循环异常：", e)
        time.sleep(120)


def start():
    """启动调度器（幂等）。"""
    global _scheduler
    if _scheduler is not None:
        return
    if HAVE_APS:
        sched = BackgroundScheduler(timezone=CST)
        for h, m in ((15, 35), (16, 30), (18, 0), (20, 0)):
            sched.add_job(_build_today, "cron", hour=h, minute=m,
                          misfire_grace_time=3600, timezone=CST)
        sched.add_job(_sync_daily_bars, "cron", hour=17, minute=10,
                      misfire_grace_time=3600, timezone=CST)
        sched.add_job(_daily_backfill, "cron", hour=21, minute=0,
                      timezone=CST)
        sched.start()
        _scheduler = sched
        print("[jobs] APScheduler 已启动（北京时间：看板 15:35/16:30/18:00/20:00，"
              "日线 17:10，补齐 21:00）")
    else:
        threading.Thread(target=_fallback_loop, daemon=True).start()
        print("[jobs] 未安装 APScheduler，使用兜底轮询调度")


def init_market_db():
    """建行情库表（幂等）。"""
    ok = db.init_db()
    if ok:
        marketdb.init_tables()
    return ok
