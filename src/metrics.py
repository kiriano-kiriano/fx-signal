"""バックテスト結果の指標計算"""
import numpy as np
import pandas as pd


def compute_metrics(equity: pd.Series, trades: list, initial_capital: float) -> dict:
    if len(equity) < 2 or not trades:
        return {"trades": 0, "total_return_pct": 0, "cagr_pct": 0,
                "sharpe": 0, "max_dd_pct": 0, "win_rate_pct": 0,
                "payoff": 0, "expectancy_pct": 0, "avg_win_pct": 0,
                "avg_loss_pct": 0, "profit_factor": 0}

    # Total return
    total_return = equity.iloc[-1] / initial_capital - 1

    # CAGR
    days = (equity.index[-1] - equity.index[0]).days
    years = max(days / 365.25, 1e-6)
    cagr = (equity.iloc[-1] / initial_capital) ** (1 / years) - 1 if equity.iloc[-1] > 0 else -1

    # Daily returns for Sharpe
    daily_ret = equity.pct_change().dropna()
    if daily_ret.std() > 0:
        sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252)
    else:
        sharpe = 0

    # Max drawdown
    rolling_max = equity.cummax()
    dd = (equity - rolling_max) / rolling_max
    max_dd = dd.min()

    # Trade-level
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    n = len(trades)
    win_rate = len(wins) / n if n else 0
    avg_win = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
    avg_loss = np.mean([t["pnl_pct"] for t in losses]) if losses else 0
    payoff = (avg_win / -avg_loss) if avg_loss < 0 else float("inf")
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    gross_win = sum(t["pnl_pct"] for t in wins)
    gross_loss = -sum(t["pnl_pct"] for t in losses)
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")

    return {
        "trades": n,
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "sharpe": sharpe,
        "max_dd_pct": max_dd * 100,
        "win_rate_pct": win_rate * 100,
        "payoff": payoff,
        "expectancy_pct": expectancy * 100,
        "avg_win_pct": avg_win * 100,
        "avg_loss_pct": avg_loss * 100,
        "profit_factor": profit_factor,
    }
