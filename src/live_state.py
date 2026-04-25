"""
Phase 2: 現在の運用状態抽出
backtest.py を参考に、保有中ポジションも返すバージョン。
"""
import pandas as pd
import numpy as np
from typing import Callable


def backtest_with_state(
    df: pd.DataFrame,
    signal_fn: Callable[[pd.DataFrame], pd.DataFrame],
    risk_per_trade: float = 0.02,
    max_leverage: float = 20.0,
    spread_pips: float = 2.0,
    pip_size: float = 0.01,
    initial_capital: float = 100_000,
) -> tuple:
    """backtest()と同じロジックだが、終端での保有ポジ状態も返す。
    Returns: (equity_curve, closed_trades, open_position_or_None, signals_df)
    """
    sig = signal_fn(df).reindex(df.index)
    sig["signal"] = sig["signal"].fillna(0).astype(int)

    closed: list[dict] = []
    equity = initial_capital
    eq_curve = pd.Series(index=df.index, dtype=float)
    eq_curve.iloc[0] = equity

    position = 0
    entry_price = 0.0
    stop_price = 0.0
    target_price = np.nan
    entry_date = None
    leverage = 0.0

    for i in range(1, len(df)):
        today = df.index[i]
        bar = df.iloc[i]

        if position != 0:
            exit_price = None
            exit_reason = None
            if position == 1:
                if bar["Low"] <= stop_price:
                    exit_price = stop_price; exit_reason = "stop"
                elif not np.isnan(target_price) and bar["High"] >= target_price:
                    exit_price = target_price; exit_reason = "target"
            else:
                if bar["High"] >= stop_price:
                    exit_price = stop_price; exit_reason = "stop"
                elif not np.isnan(target_price) and bar["Low"] <= target_price:
                    exit_price = target_price; exit_reason = "target"

            sig_row = sig.iloc[i]
            sig_exit = sig_row.get("exit_signal", False)
            opposite_signal = (sig_row["signal"] != 0 and sig_row["signal"] != position)

            if exit_price is None and (sig_exit or opposite_signal):
                exit_price = bar["Open"]
                exit_reason = "signal_exit"

            if exit_price is not None:
                gross = (exit_price - entry_price) / entry_price * position
                spread_cost = spread_pips * pip_size / entry_price
                net_return = gross - spread_cost
                eq_change_pct = net_return * leverage
                equity = equity * (1 + eq_change_pct)
                closed.append({
                    "entry_date": entry_date.isoformat() if hasattr(entry_date, "isoformat") else str(entry_date),
                    "exit_date": today.isoformat() if hasattr(today, "isoformat") else str(today),
                    "direction": position,
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "stop_price": float(stop_price),
                    "target_price": float(target_price) if not np.isnan(target_price) else None,
                    "leverage": float(leverage),
                    "pnl_pct": float(eq_change_pct),
                    "reason": exit_reason,
                    "hold_days": (today - entry_date).days if entry_date else 0,
                })
                position = 0

        if position == 0:
            prev_sig = sig.iloc[i - 1]
            s = int(prev_sig["signal"])
            if s != 0 and not np.isnan(prev_sig.get("stop", np.nan)):
                entry_price = float(bar["Open"])
                stop_price = float(prev_sig["stop"])
                target_price = float(prev_sig.get("target", np.nan))
                stop_dist = abs(entry_price - stop_price) / entry_price
                if stop_dist > 1e-6:
                    leverage = float(min(max_leverage, risk_per_trade / stop_dist))
                    position = s
                    entry_date = today

        eq_curve.iloc[i] = equity

    eq_curve = eq_curve.ffill()

    # 終端での保有ポジション
    open_position = None
    if position != 0:
        last_close = float(df["Close"].iloc[-1])
        unrealized_gross = (last_close - entry_price) / entry_price * position
        unrealized_pnl_pct = unrealized_gross * leverage
        open_position = {
            "entry_date": entry_date.isoformat() if hasattr(entry_date, "isoformat") else str(entry_date),
            "direction": position,
            "entry_price": float(entry_price),
            "current_price": last_close,
            "stop_price": float(stop_price),
            "target_price": float(target_price) if not np.isnan(target_price) else None,
            "leverage": float(leverage),
            "unrealized_pnl_pct": float(unrealized_pnl_pct),
            "hold_days": (df.index[-1] - entry_date).days if entry_date else 0,
        }

    return eq_curve, closed, open_position, sig


def compute_pair_state(df: pd.DataFrame, pair: str, params: dict,
                       risk_per_trade: float, max_leverage: float,
                       initial_capital: float = 100_000) -> dict:
    """1ペアの完全な状態（今日のシグナル、保有ポジ、最近のトレード、エクイティ）を返す"""
    from functools import partial
    from strategies import strategy_c_bb_meanrev
    pip_size = 0.01 if pair.endswith("JPY") else 0.0001
    sig_fn = partial(strategy_c_bb_meanrev, **params)

    eq, closed, open_pos, signals = backtest_with_state(
        df, sig_fn, risk_per_trade, max_leverage, 2.0, pip_size, initial_capital,
    )

    # 今日のシグナル: 最新バー(i=-1)のsignal列が非ゼロかつ保有なし
    last_signal_row = signals.iloc[-1]
    last_close = float(df["Close"].iloc[-1])
    today_signal = None
    if int(last_signal_row["signal"]) != 0 and open_pos is None:
        direction = int(last_signal_row["signal"])
        stop = float(last_signal_row["stop"]) if not np.isnan(last_signal_row.get("stop", np.nan)) else None
        target = float(last_signal_row["target"]) if not np.isnan(last_signal_row.get("target", np.nan)) else None
        # 推定エントリー価格 = 最新Close（実際には翌日Open）
        if stop is not None and stop > 0:
            stop_dist = abs(last_close - stop) / last_close
            est_lev = min(max_leverage, risk_per_trade / stop_dist) if stop_dist > 1e-6 else max_leverage
        else:
            est_lev = 0
        today_signal = {
            "pair": pair,
            "direction": direction,
            "direction_label": "買い" if direction == 1 else "売り",
            "entry_price_est": last_close,
            "stop_price": stop,
            "target_price": target,
            "estimated_leverage": float(est_lev),
            "stop_distance_pct": float(abs(last_close - stop) / last_close * 100) if stop else None,
            "target_distance_pct": float(abs(target - last_close) / last_close * 100) if target else None,
            "signal_date": df.index[-1].isoformat(),
        }

    # 昨日の結果: closed_tradesの最後のtradeが直近Nバー以内か
    yesterday_result = None
    if closed:
        last_trade = closed[-1]
        ex_date = pd.Timestamp(last_trade["exit_date"])
        latest_date = df.index[-1]
        days_ago = (latest_date - ex_date).days
        if days_ago <= 1:
            yesterday_result = last_trade

    # 直近30トレード
    recent_trades = closed[-30:]

    # エクイティカーブ（月次）
    equity_curve = [
        {"date": str(d.date()), "equity": float(v)}
        for d, v in eq.resample("ME").last().dropna().items()
    ]

    # 全期間メトリクス
    from metrics import compute_metrics
    metrics = compute_metrics(eq, closed, initial_capital)

    return {
        "pair": pair,
        "current_equity": float(eq.iloc[-1]),
        "today_signal": today_signal,
        "open_position": open_pos,
        "yesterday_result": yesterday_result,
        "recent_trades": recent_trades,
        "equity_curve": equity_curve,
        "metrics": metrics,
        "last_close": last_close,
        "last_date": df.index[-1].isoformat(),
    }
