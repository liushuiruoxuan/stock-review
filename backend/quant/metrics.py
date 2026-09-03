"""回测绩效指标。"""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def compute(equity: pd.Series, net: pd.Series, trades: list,
            benchmark: pd.Series = None) -> dict:
    """equity: 策略净值序列；net: 日收益率序列。"""
    if equity is None or len(equity) == 0:
        return {}
    total_return = float(equity.iloc[-1] - 1.0)
    n_days = len(equity)
    annual_return = float((equity.iloc[-1]) ** (TRADING_DAYS / max(n_days, 1)) - 1.0)

    ret = net.astype(float)
    vol = float(ret.std(ddof=1) * np.sqrt(TRADING_DAYS)) if n_days > 2 else 0.0
    sharpe = float(ret.mean() / ret.std(ddof=1) * np.sqrt(TRADING_DAYS)) \
        if n_days > 2 and ret.std(ddof=1) > 0 else 0.0

    # 最大回撤
    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    max_dd = float(dd.min())
    dd_end = dd.idxmin()
    dd_start = equity.loc[:dd_end].idxmax() if dd_end is not None else None

    # 日胜率
    win_days = int((ret > 0).sum())
    total_days = int((ret != 0).sum())

    # 交易统计
    pnls = [t["pnl"] for t in trades if t.get("pnl") is not None]
    n_trades = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = round(len(wins) / n_trades * 100, 2) if n_trades else None
    profit_factor = (round(sum(wins) / abs(sum(losses)), 3)
                     if losses and sum(losses) != 0 else None)
    avg_win = round(np.mean(wins) * 100, 2) if wins else None
    avg_loss = round(np.mean(losses) * 100, 2) if losses else None

    out = {
        "n_days": n_days,
        "total_return": round(total_return * 100, 2),          # %
        "annual_return": round(annual_return * 100, 2),        # %
        "annual_vol": round(vol * 100, 2),                     # %
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd * 100, 2),                # %
        "drawdown_start": str(dd_start) if dd_start is not None else None,
        "drawdown_end": str(dd_end) if dd_end is not None else None,
        "daily_win_rate": round(win_days / total_days * 100, 2) if total_days else None,
        "n_trades": n_trades,
        "trade_win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
    }

    # 基准对比
    if benchmark is not None and len(benchmark):
        b_total = float(benchmark.iloc[-1] - 1.0)
        b_annual = float((benchmark.iloc[-1]) ** (TRADING_DAYS / max(len(benchmark), 1)) - 1.0)
        out["benchmark_total_return"] = round(b_total * 100, 2)
        out["excess_return"] = round((total_return - b_total) * 100, 2)
        out["benchmark_annual_return"] = round(b_annual * 100, 2)
    return out
