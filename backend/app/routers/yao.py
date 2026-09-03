"""妖股洞察端点（v2 新增）。

- GET /api/yao/list?days=60&top=20   妖股榜（妖气指数/涨幅/连板/换手/游资/阶段）
- GET /api/yao/profile/{code}        个股画像（走势+阶段+席位+涨停明细+风险）
"""
from fastapi import APIRouter

from quant import yao

router = APIRouter()


@router.get("/api/yao/list")
def yao_list(days: int = 60, top: int = 20):
    """妖股榜。days: 识别窗口（交易日），top: 返回数量。"""
    days = max(20, min(int(days), 250))
    top = max(5, min(int(top), 100))
    return yao.scan(days=days, top=top)


@router.get("/api/yao/profile/{code}")
def yao_profile(code: str, days: int = 60):
    """个股妖股画像。"""
    days = max(20, min(int(days), 250))
    return yao.profile(code, days=days)
