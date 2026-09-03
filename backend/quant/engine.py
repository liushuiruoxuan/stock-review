"""
向量化回测引擎。

约定：
  - 输入 close_df: DataFrame(index=交易日升序, columns=标的代码, values=收盘价)
  - 输入 weights_df: 与 close_df 同形状的目标持仓权重（当日收盘产生信号，
    次日生效，即 T+1）；多头权重 >= 0，每行权重和建议 <= 1
  - 成本：换手率 × (佣金 + 滑点)，双边计
  - 基准：可选 close 序列（如上证指数），用于超额收益对比
"""
import numpy as np
import pandas as pd


def run(close_df: pd.DataFrame, weights_df: pd.DataFrame,
        benchmark: pd.Series = None,
        fee: float = 0.0005, slippage: float = 0.0010):
    """执行回测，返回 {equity, net, gross, turnover, trades, nav_df}。"""
    close = close_df.astype(float)
    ret = close.pct_change().fillna(0.0)

    w = weights_df.reindex(index=close.index, columns=close.columns).fillna(0.0)
    w = w.clip(lower=0.0)
    w = w.shift(1).fillna(0.0)          # T+1：当日信号次日生效

    gross = (w * ret).sum(axis=1)
    turnover = (w - w.shift(1)).abs().sum(axis=1)
    cost = turnover * (fee + slippage)
    net = gross - cost

    equity = (1.0 + net).cumprod()

    # 基准净值
    bench_nav = None
    if benchmark is not None:
        b = benchmark.reindex(close.index).astype(float)
        bench_nav = (1.0 + b.pct_change().fillna(0.0)).cumprod()

    trades = _extract_trades(close, w)

    nav_df = pd.DataFrame({"strategy": equity})
    if bench_nav is not None:
        nav_df["benchmark"] = bench_nav
    return {
        "equity": equity, "net": net, "gross": gross,
        "turnover": turnover, "trades": trades, "nav_df": nav_df,
    }


def _extract_trades(close: pd.DataFrame, w: pd.DataFrame):
    """从权重矩阵提取逐笔交易（0→正=开仓，正→0=清仓）。
    记录开/平仓日、对应收盘价、区间收益。"""
    trades = []
    for col in w.columns:
        pos = w[col]
        in_pos = False
        entry_date = None
        entry_px = None
        weight = 0.0
        for dt, v in pos.items():
            if not in_pos and v > 0:
                in_pos = True
                entry_date = dt
                entry_px = float(close.at[dt, col]) if not np.isnan(close.at[dt, col]) else None
                weight = float(v)
            elif in_pos and v <= 0:
                exit_px = float(close.at[dt, col]) if not np.isnan(close.at[dt, col]) else None
                pnl = None
                if entry_px and exit_px:
                    pnl = round(exit_px / entry_px - 1.0, 6)
                trades.append({
                    "code": col, "entry": str(entry_date), "exit": str(dt),
                    "entry_px": entry_px, "exit_px": exit_px,
                    "weight": round(weight, 4), "pnl": pnl,
                })
                in_pos = False
        # 期末仍持仓：按最后价格虚拟平仓
        if in_pos:
            last_dt = close.index[-1]
            exit_px = float(close.at[last_dt, col]) if not np.isnan(close.at[last_dt, col]) else None
            pnl = None
            if entry_px and exit_px:
                pnl = round(exit_px / entry_px - 1.0, 6)
            trades.append({
                "code": col, "entry": str(entry_date), "exit": str(last_dt),
                "entry_px": entry_px, "exit_px": exit_px,
                "weight": round(weight, 4), "pnl": pnl, "open": True,
            })
    return trades
