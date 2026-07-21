"""
MySQL 连接配置（股票每日复盘）。

连接方式（按优先级）：
  1) 环境变量：STOCK_DB_HOST / STOCK_DB_PORT / STOCK_DB_USER /
     STOCK_DB_PASSWORD / STOCK_DB_NAME / STOCK_DB_ENABLED
  2) 否则用下方默认值。

用法：
  - 直接修改下方 DB_CONFIG 默认值；或
  - 通过环境变量注入（推荐生产环境，避免把密码写进代码）。

关闭 MySQL：
  - 设置 STOCK_DB_ENABLED=0，或把 DB_ENABLED 改为 False，
    此时系统完全退化为仅用本地 JSON 缓存，看板照常工作。
"""
import os

DB_CONFIG = {
    "host": os.environ.get("STOCK_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("STOCK_DB_PORT", "3306")),
    "user": os.environ.get("STOCK_DB_USER", "root"),
    "password": os.environ.get("STOCK_DB_PASSWORD", ""),
    "database": os.environ.get("STOCK_DB_NAME", "stock_review"),
    "charset": "utf8mb4",
}

# 是否启用 MySQL（0 / false 关闭）。关闭后仅用 JSON 缓存。
DB_ENABLED = str(os.environ.get("STOCK_DB_ENABLED", "1")).lower() not in ("0", "false", "no")
