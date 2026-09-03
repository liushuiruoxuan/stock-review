"""妖股洞察端点（v2 新增）。

- GET /api/yao/list?days=60&top=20   妖股榜（妖气指数/涨幅/连板/换手/游资/阶段）
- GET /api/yao/profile/{code}        个股画像（走势+阶段+席位+涨停明细+风险）
"""
from fastapi import APIRouter

from quant import yao

router = APIRouter()


@router.get("/api/yao/dates")
def yao_dates(n: int = 40):
    """妖股「截止日期」下拉可选的交易日（倒序，最新在前）。"""
    n = max(5, min(int(n), 250))
    return {"dates": yao.available_dates(n)}


@router.get("/api/yao/list")
def yao_list(days: int = 60, top: int = 20, date: str = None):
    """妖股榜。days: 识别窗口（交易日），top: 返回数量，date: 截止交易日（空=最新）。"""
    days = max(20, min(int(days), 250))
    top = max(5, min(int(top), 100))
    return yao.scan(days=days, top=top, end=date or None)


@router.get("/api/yao/profile/{code}")
def yao_profile(code: str, days: int = 60, date: str = None):
    """个股妖股画像（date: 截止交易日，空=最新）。"""
    days = max(20, min(int(days), 250))
    return yao.profile(code, days=days, end=date or None)
