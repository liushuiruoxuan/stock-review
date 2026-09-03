"""
全球财经端点（v2 新增）。

- GET /api/global/quotes  全球指数/商品/外汇行情（新浪 hq.sinajs.cn）
- GET /api/global/news    财经要闻快讯（新浪7x24 主 → 东财快讯 备）

模块名用 globfin 而非 global：`global` 是 Python 关键字，无法作为包名 import。
"""
from fastapi import APIRouter

from datasvc import globfin

router = APIRouter()


@router.get("/api/global/quotes")
def quotes(force: bool = False):
    """全球行情。force=true 跳过缓存强制刷新。"""
    return globfin.fetch_global_quotes(force=force)


@router.get("/api/global/news")
def news(limit: int = 12, force: bool = False):
    """财经要闻快讯，默认 12 条。"""
    return {"news": globfin.fetch_finance_news(limit=limit, force=force)}
