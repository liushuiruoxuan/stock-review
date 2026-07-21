"""
MySQL 存储层（股票每日复盘）。

职责：
  - 连接 / 建库 / 建表（首次运行自动初始化）。
  - 按交易日 upsert 各看板数据（paylaod 存为 JSON 列）。
  - 读取：优先 MySQL，失败/缺失时返回 None，由调用方回退 JSON 缓存。
  - 列出有数据的交易日，支持历史回看。

降级策略：
  - 若 PyMySQL 未安装、或 MySQL 显式关闭，则硬禁用；若连接连续失败多次，则软禁用
    并定期自动重试，连接恢复后自动启用（应对启动竞态 / MySQL 重启）。
  - 任意读写失败都静默返回，不抛异常、不阻塞，系统退化为仅 JSON 缓存。
  - 这样即使 MySQL 完全不可用，看板依旧可用。
"""
import json
import threading
import time

try:
    import pymysql
    HAVE_PYMYSQL = True
except Exception:
    HAVE_PYMYSQL = False

from db_config import DB_CONFIG, DB_ENABLED

_lock = threading.Lock()
# 硬禁用：仅在 PyMySQL 未装或显式关闭 MySQL 时。
_hard_disabled = (not HAVE_PYMYSQL) or (not DB_ENABLED)
# 软禁用：连续连接失败过多时短暂停用，并按间隔自动重试以恢复（应对启动竞态/MySQL 重启）。
_soft_bad = False
_fail_streak = 0
_fail_max = 5
_last_try = 0.0
_retry_interval = 30.0  # 秒：软禁用状态下再次试探的间隔
_conn_err_shown = False

TABLE = "stock_review_data"

CREATE_DB_SQL = "CREATE DATABASE IF NOT EXISTS `%s` DEFAULT CHARACTER SET utf8mb4" % DB_CONFIG["database"]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS %s (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  trade_date DATE NOT NULL,
  section VARCHAR(40) NOT NULL,
  payload JSON NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_section (trade_date, section)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""" % TABLE

SECTIONS = [
    "summary", "billboard", "stocks_flow", "rapid_rise",
    "capital_attention", "sectors_hot", "sectors_outflow",
    "institution", "youzi",
]

# 席位级明细（Tier B）：逐席位（营业部/机构/沪深股通）买卖记录
SEAT_TABLE = "stock_review_seat"

CREATE_SEAT_SQL = """
CREATE TABLE IF NOT EXISTS %s (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  trade_date DATE NOT NULL,
  security_code VARCHAR(12),
  security_name VARCHAR(40),
  seat_code VARCHAR(20),
  seat_name VARCHAR(80),
  side VARCHAR(4),
  buy_amt BIGINT,
  sell_amt BIGINT,
  net_amt BIGINT,
  rise_prob_3d FLOAT,
  trade_times_3d INT,
  explanation VARCHAR(200),
  trade_id VARCHAR(40),
  UNIQUE KEY uk_seat (trade_date, security_code, seat_code, side)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""" % SEAT_TABLE


def is_available():
    return (not _hard_disabled) and (not _soft_bad)


def get_conn():
    """返回连接；不可用/失败返回 None。失败不永久禁用，会按间隔自动重试。"""
    global _fail_streak, _soft_bad, _conn_err_shown, _last_try
    if _hard_disabled:
        return None
    now = time.time()
    if _soft_bad and (now - _last_try) < _retry_interval:
        return None
    _last_try = now
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG["charset"],
            connect_timeout=5,
            autocommit=True,
        )
        _fail_streak = 0
        _soft_bad = False
        if _conn_err_shown:
            print("[db] MySQL 连接已恢复。")
            _conn_err_shown = False
        return conn
    except Exception as e:
        _fail_streak += 1
        if not _conn_err_shown:
            print("[db] MySQL 连接失败（将按间隔自动重试）：", e)
            _conn_err_shown = True
        if _fail_streak >= _fail_max:
            _soft_bad = True
        return None


def init_db():
    """建库 + 建表。成功返回 True，否则 False（不影响看板）。"""
    if _hard_disabled:
        if not HAVE_PYMYSQL and DB_ENABLED:
            print("[db] 未安装 PyMySQL（pip install PyMySQL），MySQL 存储已禁用，仅用 JSON 缓存。")
        return False
    # 1) 先连（不指定库）建库
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            charset=DB_CONFIG["charset"],
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute(CREATE_DB_SQL)
        conn.close()
    except Exception as e:
        print("[db] 建库失败（请手动 CREATE DATABASE %s）：" % DB_CONFIG["database"], e)
        return False
    # 2) 建表
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.execute(CREATE_SEAT_SQL)
        return True
    except Exception as e:
        print("[db] 建表失败：", e)
        return False
    finally:
        conn.close()


def save_section(trade_date, section, data):
    """upsert 单个看板到 MySQL。失败静默返回 False。"""
    if not is_available():
        return False
    conn = get_conn()
    if not conn:
        return False
    try:
        payload_str = json.dumps(data, ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO %s (trade_date, section, payload) "
                "VALUES (%%s, %%s, %%s) "
                "ON DUPLICATE KEY UPDATE payload=VALUES(payload), updated_at=NOW()" % TABLE,
                (trade_date, section, payload_str),
            )
        return True
    except Exception as e:
        print("[db] 写入 %s 失败：" % section, e)
        return False
    finally:
        conn.close()


def save_all(trade_date, payloads):
    """批量双写所有看板。"""
    if not is_available():
        return
    for name, data in payloads.items():
        save_section(trade_date, name, data)


def load_section(trade_date, section):
    """优先从 MySQL 读取单个看板。无数据/失败返回 None。"""
    if not is_available():
        return None
    conn = get_conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM %s WHERE trade_date=%%s AND section=%%s" % TABLE,
                (trade_date, section),
            )
            row = cur.fetchone()
        if row and row[0]:
            # pymysql 对 JSON 列默认返回字符串
            if isinstance(row[0], str):
                return json.loads(row[0])
            return row[0]
        return None
    except Exception as e:
        print("[db] 读取 %s 失败：" % section, e)
        return None
    finally:
        conn.close()


def list_dates():
    """返回有数据的交易日（倒序，最多 200）。"""
    if not is_available():
        return []
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT trade_date FROM %s ORDER BY trade_date DESC LIMIT 200" % TABLE
            )
            return [str(r[0]) for r in cur.fetchall()]
    except Exception as e:
        print("[db] 列出交易日失败：", e)
        return []
    finally:
        conn.close()


def load_history(date):
    """读取某交易日全部看板（JSON 字段）。"""
    out = {}
    for s in SECTIONS:
        out[s] = load_section(date, s)
    return out


# ----------------------- 席位明细（Tier B） -----------------------
def save_seats(rows):
    """批量写入席位明细（upsert）。失败静默返回 False。"""
    if not is_available() or not rows:
        return False
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    "INSERT INTO %s "
                    "(trade_date, security_code, security_name, seat_code, seat_name, "
                    " side, buy_amt, sell_amt, net_amt, rise_prob_3d, trade_times_3d, "
                    " explanation, trade_id) "
                    "VALUES (%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s) "
                    "ON DUPLICATE KEY UPDATE "
                    "security_name=VALUES(security_name), buy_amt=VALUES(buy_amt), "
                    "sell_amt=VALUES(sell_amt), net_amt=VALUES(net_amt), "
                    "rise_prob_3d=VALUES(rise_prob_3d), trade_times_3d=VALUES(trade_times_3d), "
                    "explanation=VALUES(explanation)" % SEAT_TABLE,
                    (
                        r.get("trade_date"), r.get("code"), r.get("name"),
                        r.get("seat_code"), r.get("seat_name"), r.get("side"),
                        r.get("buy_amt"), r.get("sell_amt"), r.get("net_amt"),
                        r.get("rise_prob_3d"), r.get("trade_times_3d"),
                        r.get("explanation"), r.get("trade_id"),
                    ),
                )
        return True
    except Exception as e:
        print("[db] 写入席位明细失败：", e)
        return False
    finally:
        conn.close()


def has_seat_date(trade_date):
    """该交易日是否已有席位明细（用于回填断点续传）。"""
    if not is_available():
        return False
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM %s WHERE trade_date=%%s LIMIT 1" % SEAT_TABLE, (trade_date,))
            return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def load_seats(trade_date, seat=None, side=None, seat_type=None, min_net=None, limit=2000):
    """读取某交易日席位明细，支持筛选：席位名关键词/方向/类型/最小净额。"""
    if not is_available():
        return None
    conn = get_conn()
    if not conn:
        return None
    try:
        sql = "SELECT trade_date, security_code, security_name, seat_code, seat_name, " \
              "side, buy_amt, sell_amt, net_amt, rise_prob_3d, trade_times_3d, " \
              "explanation, trade_id FROM %s WHERE trade_date=%%s" % SEAT_TABLE
        args = [trade_date]
        if seat:
            sql += " AND seat_name LIKE %s"
            args.append("%" + seat + "%")
        if side:
            sql += " AND side=%s"
            args.append(side)
        if seat_type == "inst":
            sql += " AND seat_name LIKE %s"
            args.append("%机构专用%")
        elif seat_type == "hk":
            sql += " AND (seat_name LIKE %s OR seat_name LIKE %s OR seat_name LIKE %s)"
            args.extend(["%沪股通%", "%深股通%", "%陆股通%"])
        elif seat_type == "youzi":
            sql += " AND seat_name NOT LIKE %s AND seat_name NOT LIKE %s AND seat_name NOT LIKE %s AND seat_name NOT LIKE %s"
            args.extend(["%机构专用%", "%沪股通%", "%深股通%", "%陆股通%"])
        if min_net is not None:
            sql += " AND net_amt >= %s"
            args.append(min_net)
        sql += " ORDER BY net_amt DESC"
        if limit:
            sql += " LIMIT %s"
            args.append(limit)
        with conn.cursor() as cur:
            cur.execute(sql, args)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        print("[db] 读取席位明细失败：", e)
        return None
    finally:
        conn.close()


def list_seat_dates():
    """返回有席位明细的交易日（倒序）。"""
    if not is_available():
        return []
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT trade_date FROM %s ORDER BY trade_date DESC LIMIT 200" % SEAT_TABLE)
            return [str(r[0]) for r in cur.fetchall()]
    except Exception as e:
        print("[db] 列出席位交易日失败：", e)
        return []
    finally:
        conn.close()
