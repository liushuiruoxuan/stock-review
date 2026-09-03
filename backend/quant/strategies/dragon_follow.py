"""龙虎榜跟随策略（本项目独有 alpha）。

信号源：热点重合榜（龙虎榜 ∩ 涨停榜，来自 hot_billboard section）。
逻辑：净买额 >= min_net_wan 万的热点股，次日买入并持有 hold_days 日；
      同日信号过多时按净买额取前 max_positions 只。
extra: {"signals": {date: [{code, net_amt}, ...]}, "trade_dates": [date, ...]}
"""
import pandas as pd

from . import register


@register
class DragonFollow:
    name = "dragon_follow"
    label = "龙虎榜跟随"
    description = "热点重合榜（龙虎榜∩涨停）净买额达标个股，次日买入持有 N 日；依赖旧看板历史数据。"
    PARAMS = [
        {"key": "min_net_wan", "label": "净买门槛(万)", "type": "int", "default": 3000, "min": 0, "max": 100000},
        {"key": "hold_days", "label": "持有(交易日)", "type": "int", "default": 3, "min": 1, "max": 20},
        {"key": "max_positions", "label": "同日最多买(只)", "type": "int", "default": 5, "min": 1, "max": 20},
    ]

    @staticmethod
    def weights(close_df: pd.DataFrame, params: dict, extra: dict) -> pd.DataFrame:
        min_net_wan = float(params.get("min_net_wan", 3000))
        hold_days = int(params.get("hold_days", 3))
        max_positions = int(params.get("max_positions", 5))

        signals = extra.get("signals") or {}
        if not signals:
            raise ValueError("无热点重合榜历史数据，无法运行龙虎榜跟随策略")

        dates = list(close_df.index)
        date_pos = {d: i for i, d in enumerate(dates)}

        # holdings: code -> 剩余持有天数
        holdings = {}
        w = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)
        for i, dt in enumerate(dates):
            dt_str = str(dt)[:10]
            # 1) 递减持有期
            for c in list(holdings.keys()):
                holdings[c] -= 1
                if holdings[c] <= 0:
                    del holdings[c]
            # 2) 当日信号入场（次日生效由引擎 shift 处理）
            day_signals = signals.get(dt_str) or []
            day_signals = [s for s in day_signals
                           if (s.get("net_amt") or 0) >= min_net_wan * 1e4]
            day_signals.sort(key=lambda s: s.get("net_amt") or 0, reverse=True)
            for s in day_signals[:max_positions]:
                code = s.get("code")
                if code in close_df.columns and code not in holdings:
                    holdings[code] = hold_days
            # 3) 写权重（等权）
            if holdings:
                codes = [c for c in holdings if c in close_df.columns]
                if codes:
                    w.loc[dt, codes] = 1.0 / len(codes)
        return w
