"""
行情库（v2）：标的主数据 / 交易日历 / 日线 OHLCV / 指数基准 / 回测任务。

独立于旧看板三表（stock_review_data / _seat / _limitup），全部列式存储、可 SQL 查询。
依赖 db.get_conn() 连接池；MySQL 不可用时所有函数安全降级（返回空值），不抛异常。

表清单：
  sr_instruments      标的主数据（code/name）
  sr_trade_calendar   交易日历（从指数 K 线日期推导）
  sr_daily_bars       个股日线 OHLCV（前复权）
  sr_index_bars       指数基准日线（上证/深成/创业板）
  sr_backtest_runs    量化回测任务与结果
"""
import datetime
import json

import db  # 复用连接池与可用性判断

T_INSTRUMENTS = "sr_instruments"
T_CALENDAR = "sr_trade_calendar"
T_BARS = "sr_daily_bars"
T_INDEX_BARS = "sr_index_bars"
T_RUNS = "sr_backtest_runs"

# 指数基准（code 与东财 secid 前缀对应：1.000001 / 0.399001 / 0.399006）
INDEXES = [
    {"code": "1.000001", "name": "上证指数", "short": "SH"},
    {"code": "0.399001", "name": "深证成指", "short": "SZ"},
    {"code": "0.399006", "name": "创业板指", "short": "CYB"},
]

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS {t} (
      code VARCHAR(12) PRIMARY KEY,
      name VARCHAR(40) NOT NULL,
      market VARCHAR(8) DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.format(t=T_INSTRUMENTS),
    """
    CREATE TABLE IF NOT EXISTS {t} (
      trade_date DATE PRIMARY KEY
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.format(t=T_CALENDAR),
    """
    CREATE TABLE IF NOT EXISTS {t} (
      code VARCHAR(12) NOT NULL,
      trade_date DATE NOT NULL,
      open DECIMAL(12,3), high DECIMAL(12,3),
      low DECIMAL(12,3), close DECIMAL(12,3),
      volume BIGINT, amount DECIMAL(18,2),
      turnover DECIMAL(8,4), pct_chg DECIMAL(8,4),
      PRIMARY KEY (code, trade_date),
      KEY idx_date (trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.format(t=T_BARS),
    """
    CREATE TABLE IF NOT EXISTS {t} (
      code VARCHAR(12) NOT NULL,
      trade_date DATE NOT NULL,
      open DECIMAL(12,3), high DECIMAL(12,3),
      low DECIMAL(12,3), close DECIMAL(12,3),
      volume BIGINT, amount DECIMAL(18,2),
      turnover DECIMAL(8,4), pct_chg DECIMAL(8,4),
      PRIMARY KEY (code, trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.format(t=T_INDEX_BARS),
    """
    CREATE TABLE IF NOT EXISTS {t} (
      id BIGINT AUTO_INCREMENT PRIMARY KEY,
      strategy VARCHAR(64) NOT NULL,
      params JSON,
      universe VARCHAR(32) DEFAULT 'all',
      date_start DATE, date_end DATE,
      status VARCHAR(16) DEFAULT 'running',
      progress INT DEFAULT 0,
      error VARCHAR(500),
      metrics JSON, trades JSON, equity JSON,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      finished_at DATETIME NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """.format(t=T_RUNS),
]


def init_tables():
    """建表（幂等）。MySQL 不可用返回 False。"""
    if not db.is_available():
        return False
    conn = db.get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            for ddl in _DDL:
                cur.execute(ddl)
        return True
    except Exception as e:
        print("[marketdb] 建表失败：", e)
        return False
    finally:
        conn.close()


def _exec(sql, args=None, fetch=False):
    """执行单条 SQL；fetch 时返回行列表。失败返回 None。"""
    if not db.is_available():
        return None
    conn = db.get_conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            if fetch:
                return cur.fetchall()
            return True
    except Exception as e:
        print("[marketdb] SQL 失败：%s ... %s" % (sql[:60], e))
        return None
    finally:
        conn.close()


# ------------------------- 标的主数据 -------------------------
def upsert_instruments(rows):
    """批量 upsert 标的列表。rows: [{code, name, market}]"""
    if not rows:
        return 0
    conn = db.get_conn()
    if not conn:
        return 0
    sql = ("INSERT INTO %s (code, name, market) VALUES (%%s,%%s,%%s) "
           "ON DUPLICATE KEY UPDATE name=VALUES(name), market=VALUES(market)"
           % T_INSTRUMENTS)
    n = 0
    try:
        with conn.cursor() as cur:
            for i in range(0, len(rows), 500):
                batch = rows[i:i + 500]
                cur.executemany(sql, [(r.get("code"), r.get("name"), r.get("market") or "")
                                      for r in batch])
                n += len(batch)
    except Exception as e:
        print("[marketdb] 写入标的失败：", e)
    finally:
        conn.close()
    return n


def list_instruments(q=None, limit=50, offset=0):
    """标的列表，支持名称/代码模糊查询。"""
    sql = "SELECT code, name, market FROM %s" % T_INSTRUMENTS
    args = []
    if q:
        sql += " WHERE code LIKE %s OR name LIKE %s"
        args = ["%" + q + "%", "%" + q + "%"]
    sql += " ORDER BY code LIMIT %s OFFSET %s"
    args += [int(limit), int(offset)]
    rows = _exec(sql, args, fetch=True)
    if not rows:
        return []
    return [{"code": r[0], "name": r[1], "market": r[2]} for r in rows]


def count_instruments():
    r = _exec("SELECT COUNT(*) FROM %s" % T_INSTRUMENTS, fetch=True)
    return int(r[0][0]) if r else 0


# ------------------------- 交易日历 -------------------------
def save_calendar(dates):
    """保存交易日列表（dates: ['YYYY-MM-DD', ...]）。"""
    if not dates:
        return 0
    conn = db.get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT IGNORE INTO %s (trade_date) VALUES (%%s)" % T_CALENDAR,
                [(d,) for d in dates])
        return len(dates)
    except Exception as e:
        print("[marketdb] 写入日历失败：", e)
        return 0
    finally:
        conn.close()


def load_calendar(start=None, end=None):
    """交易日列表（升序）。start/end: 'YYYY-MM-DD'。"""
    sql = "SELECT trade_date FROM %s" % T_CALENDAR
    args = []
    if start:
        sql += " WHERE trade_date >= %s"
        args.append(start)
    if end:
        sql += " AND trade_date <= %s" if start else " WHERE trade_date <= %s"
        args.append(end)
    sql += " ORDER BY trade_date"
    rows = _exec(sql, args, fetch=True)
    return [str(r[0]) for r in rows] if rows else []


def is_trade_date(d):
    """d: 'YYYY-MM-DD'。日历无数据时退化为工作日判定。"""
    r = _exec("SELECT 1 FROM %s WHERE trade_date=%%s" % T_CALENDAR, (d,), fetch=True)
    if r is None:
        try:
            dt = datetime.date.fromisoformat(d)
            return dt.weekday() < 5
        except Exception:
            return False
    return bool(r)


def calendar_count():
    r = _exec("SELECT COUNT(*) FROM %s" % T_CALENDAR, fetch=True)
    return int(r[0][0]) if r else 0


# ------------------------- 日线 OHLCV -------------------------
def upsert_bars(rows, table=T_BARS):
    """批量 upsert 日线。rows: [{code, trade_date, open, high, low, close,
    volume, amount, turnover, pct_chg}, ...]"""
    if not rows:
        return 0
    conn = db.get_conn()
    if not conn:
        return 0
    sql = (
        "INSERT INTO {t} (code, trade_date, open, high, low, close, volume, "
        "amount, turnover, pct_chg) VALUES "
        "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
        "open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close), "
        "volume=VALUES(volume), amount=VALUES(amount), turnover=VALUES(turnover), "
        "pct_chg=VALUES(pct_chg)"
    ).format(t=table)
    n = 0
    try:
        with conn.cursor() as cur:
            for i in range(0, len(rows), 1000):
                batch = rows[i:i + 1000]
                cur.executemany(sql, [
                    (r.get("code"), r.get("trade_date"), r.get("open"), r.get("high"),
                     r.get("low"), r.get("close"), r.get("volume"), r.get("amount"),
                     r.get("turnover"), r.get("pct_chg"))
                    for r in batch])
                n += len(batch)
    except Exception as e:
        print("[marketdb] 写入日线失败：", e)
    finally:
        conn.close()
    return n


_BAR_COLS = "code, trade_date, open, high, low, close, volume, amount, turnover, pct_chg"


def load_bars(codes=None, start=None, end=None, table=T_BARS, limit=200000):
    """读取日线（字典列表）。codes: list 或 None(全部)。"""
    sql = "SELECT %s FROM %s" % (_BAR_COLS, table)
    args = []
    where = []
    if codes is not None:
        if not codes:
            return []
        where.append("code IN (%s)" % ",".join(["%s"] * len(codes)))
        args.extend(list(codes))
    if start:
        where.append("trade_date >= %s")
        args.append(start)
    if end:
        where.append("trade_date <= %s")
        args.append(end)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY code, trade_date LIMIT %s"
    args.append(int(limit))
    rows = _exec(sql, args, fetch=True)
    if not rows:
        return []
    keys = ["code", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "turnover", "pct_chg"]
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        d["trade_date"] = str(d["trade_date"])
        out.append(d)
    return out


def latest_bar_date(table=T_BARS):
    """全库最新行情日期。"""
    r = _exec("SELECT MAX(trade_date) FROM %s" % table, fetch=True)
    return str(r[0][0]) if r and r[0][0] else None


def bars_count(table=T_BARS):
    r = _exec("SELECT COUNT(*) FROM %s" % table, fetch=True)
    return int(r[0][0]) if r else 0


def bar_coverage():
    """每个标的的最新行情日期（增量同步用）。{code: 'YYYY-MM-DD'}"""
    rows = _exec("SELECT code, MAX(trade_date) FROM %s GROUP BY code" % T_BARS, fetch=True)
    if not rows:
        return {}
    return {r[0]: str(r[1]) for r in rows}


def liquid_universe(top_n=500, days=60, end=None):
    """按近 N 日平均成交额取流动性前 N 的标的（回测默认股票池）。"""
    sql = (
        "SELECT code, AVG(amount) AS avg_amt FROM ("
        "  SELECT code, amount FROM %s "
        "  WHERE trade_date > DATE_SUB(%s, INTERVAL %s DAY)"
        ") t GROUP BY code ORDER BY avg_amt DESC LIMIT %%s"
        % (T_BARS, "%s", "%s")
    )
    args = [end or latest_bar_date() or "2099-01-01", int(days), int(top_n)]
    rows = _exec(sql, args, fetch=True)
    return [r[0] for r in rows] if rows else []


def index_snapshot(days=60):
    """指数快照：每只指数最新值 + 近 N 日收盘序列（大屏用）。"""
    out = []
    for idx in INDEXES:
        rows = _exec(
            "SELECT trade_date, close, pct_chg FROM %s WHERE code=%%s "
            "ORDER BY trade_date DESC LIMIT %%s" % T_INDEX_BARS,
            (idx["code"], int(days)), fetch=True)
        if not rows:
            continue
        latest = rows[0]
        spark = [{"date": str(r[0]), "close": float(r[1])} for r in reversed(rows)]
        out.append({
            "code": idx["code"], "name": idx["name"],
            "date": str(latest[0]), "close": float(latest[1]),
            "pct_chg": float(latest[2]) if latest[2] is not None else None,
            "spark": spark,
        })
    return out


# ------------------------- 回测任务 -------------------------
def create_run(strategy, params, universe, date_start, date_end):
    conn = db.get_conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO %s (strategy, params, universe, date_start, date_end, status) "
                "VALUES (%%s,%%s,%%s,%%s,%%s,'running')" % T_RUNS,
                (strategy, json.dumps(params or {}, ensure_ascii=False), universe,
                 date_start, date_end))
            return cur.lastrowid
    except Exception as e:
        print("[marketdb] 创建回测任务失败：", e)
        return None
    finally:
        conn.close()


def update_run(run_id, status=None, progress=None, error=None,
               metrics=None, trades=None, equity=None):
    conn = db.get_conn()
    if not conn:
        return False
    sets, args = [], []
    if status is not None:
        sets.append("status=%s"); args.append(status)
    if progress is not None:
        sets.append("progress=%s"); args.append(int(progress))
    if error is not None:
        sets.append("error=%s"); args.append(error[:500])
    if metrics is not None:
        sets.append("metrics=%s"); args.append(json.dumps(metrics, ensure_ascii=False))
    if trades is not None:
        sets.append("trades=%s"); args.append(json.dumps(trades, ensure_ascii=False))
    if equity is not None:
        sets.append("equity=%s"); args.append(json.dumps(equity, ensure_ascii=False))
    if status in ("done", "failed"):
        sets.append("finished_at=NOW()")
    if not sets:
        return False
    args.append(run_id)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE %s SET %s WHERE id=%%s" % (T_RUNS, ",".join(sets)), args)
        return True
    except Exception as e:
        print("[marketdb] 更新回测任务失败：", e)
        return False
    finally:
        conn.close()


def _run_row(r):
    return {
        "id": r[0], "strategy": r[1], "params": r[2], "universe": r[3],
        "date_start": str(r[4]) if r[4] else None,
        "date_end": str(r[5]) if r[5] else None,
        "status": r[6], "progress": r[7], "error": r[8],
        "metrics": r[9], "trades": r[10], "equity": r[11],
        "created_at": str(r[12]) if r[12] else None,
        "finished_at": str(r[13]) if r[13] else None,
    }


_RUN_COLS = ("id, strategy, params, universe, date_start, date_end, status, "
             "progress, error, metrics, trades, equity, created_at, finished_at")


def get_run(run_id):
    rows = _exec("SELECT %s FROM %s WHERE id=%%s" % (_RUN_COLS, T_RUNS),
                 (run_id,), fetch=True)
    if not rows:
        return None
    return _run_row(rows[0])


def list_runs(limit=20):
    rows = _exec("SELECT %s FROM %s ORDER BY id DESC LIMIT %%s"
                 % (_RUN_COLS, T_RUNS), (int(limit),), fetch=True)
    if not rows:
        return []
    return [_run_row(r) for r in rows]
