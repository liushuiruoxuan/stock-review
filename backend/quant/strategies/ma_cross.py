"""双均线策略：快线上穿慢线持有，下穿清仓；多标的等权，按动量取前 N 只。"""
import pandas as pd

from . import register


@register
class MaCross:
    name = "ma_cross"
    label = "双均线"
    description = "MA(fast) > MA(slow) 时持有，反之空仓；多标的信号中按 20 日动量取前 N 只等权持有。"
    PARAMS = [
        {"key": "fast", "label": "快线(日)", "type": "int", "default": 5, "min": 2, "max": 60},
        {"key": "slow", "label": "慢线(日)", "type": "int", "default": 20, "min": 5, "max": 250},
        {"key": "max_positions", "label": "最大持仓数", "type": "int", "default": 10, "min": 1, "max": 50},
    ]

    @staticmethod
    def weights(close_df: pd.DataFrame, params: dict, extra: dict) -> pd.DataFrame:
        fast = int(params.get("fast", 5))
        slow = int(params.get("slow", 20))
        max_pos = int(params.get("max_positions", 10))
        if fast >= slow:
            raise ValueError("快线周期需小于慢线周期")

        ma_f = close_df.rolling(fast, min_periods=fast).mean()
        ma_s = close_df.rolling(slow, min_periods=slow).mean()
        signal = (ma_f > ma_s).astype(float)          # 1=金叉状态

        mom20 = close_df.pct_change(20)

        w = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)
        for dt in close_df.index:
            sig = signal.loc[dt]
            cands = sig[sig > 0].index.tolist()
            if not cands:
                continue
            # 按 20 日动量取前 max_pos 只
            mom = mom20.loc[dt, cands].dropna()
            mom = mom.sort_values(ascending=False)
            picked = list(mom.index[:max_pos])
            if picked:
                w.loc[dt, picked] = 1.0 / len(picked)
        return w
