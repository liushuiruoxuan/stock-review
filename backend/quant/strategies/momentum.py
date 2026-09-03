"""动量轮动策略：每 N 个交易日调仓一次，持有 lookback 期收益最高的前 N 只。"""
import pandas as pd

from . import register


@register
class Momentum:
    name = "momentum"
    label = "动量轮动"
    description = "每 rebalance 个交易日调仓，持有 lookback 期收益最高的前 top_n 只（等权）。"
    PARAMS = [
        {"key": "lookback", "label": "动量回看(日)", "type": "int", "default": 20, "min": 5, "max": 120},
        {"key": "top_n", "label": "持仓数", "type": "int", "default": 10, "min": 1, "max": 50},
        {"key": "rebalance", "label": "调仓间隔(日)", "type": "int", "default": 20, "min": 1, "max": 60},
    ]

    @staticmethod
    def weights(close_df: pd.DataFrame, params: dict, extra: dict) -> pd.DataFrame:
        lookback = int(params.get("lookback", 20))
        top_n = int(params.get("top_n", 10))
        rebalance = int(params.get("rebalance", 20))

        mom = close_df.pct_change(lookback)
        w = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)
        last_rebalance = -10**9
        current = []
        for i, dt in enumerate(close_df.index):
            if i - last_rebalance >= rebalance:
                m = mom.loc[dt].dropna()
                m = m.sort_values(ascending=False)
                current = list(m.index[:top_n])
                last_rebalance = i
            if current:
                w.loc[dt, current] = 1.0 / len(current)
        return w
