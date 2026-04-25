"""
バックテストエンジン（共通）
- 日足ベース、翌営業日寄付きエントリー（シグナル発生バーの次のOpenで入る）
- 1トレード＝口座の1%リスク
- スプレッドコスト考慮（JPYクロス2pips=0.02円想定、他は適宜）
- 途中撤退は次のバーのOpenまたは指定条件で
"""
from dataclasses import dataclass, field
from typing import Callable
import pandas as pd
import numpy as np


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    direction: int  # +1 long, -1 short
    entry_price: float
    exit_price: float
    stop_price: float
    leverage: float
    pnl_pct: float  # equityに対する%変化
    reason: str
    hold_days: int


def backtest(
    df: pd.DataFrame,
    signal_fn: Callable[[pd.DataFrame], pd.DataFrame],
    risk_per_trade: float = 0.01,
    max_leverage: float = 10.0,
    spread_pips: float = 2.0,
    pip_size: float = 0.01,  # JPYクロスは0.01、EUR/USD等は0.0001
    initial_capital: float = 100_000,
) -> tuple:
    """
    signal_fn: df -> DataFrameで以下の列を返す
        'signal': +1(long), -1(short), 0(no-op)
        'stop': float  # 損切り価格
        'target': float or NaN  # 利確価格（任意）
        'exit_reason_if_filled': str (任意)
    次バーOpenでエントリー。エントリー後は日足High/Lowで損切り/利確判定。
    逆シグナル発生時は次バーOpenで手仕舞って逆エントリー（ストップ&リバース）。
    """
    sig = signal_fn(df).reindex(df.index)
    sig["signal"] = sig["signal"].fillna(0).astype(int)

    trades: list[Trade] = []
    equity = initial_capital
    equity_curve = pd.Series(index=df.index, dtype=float)
    equity_curve.iloc[0] = equity

    position = 0  # 0 no-position, +1/-1 open
    entry_price = 0.0
    stop_price = 0.0
    target_price = np.nan
    entry_date = None
    leverage = 0.0

    for i in range(1, len(df)):
        today = df.index[i]
        bar = df.iloc[i]

        # --- 保有中の決済判定 ---
        if position != 0:
            exit_price = None
            exit_reason = None
            # 損切り／利確のヒット判定（日足内でどっちが先かは不明だが、保守的にstop優先）
            if position == 1:
                if bar["Low"] <= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop"
                elif not np.isnan(target_price) and bar["High"] >= target_price:
                    exit_price = target_price
                    exit_reason = "target"
            else:
                if bar["High"] >= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop"
                elif not np.isnan(target_price) and bar["Low"] <= target_price:
                    exit_price = target_price
                    exit_reason = "target"

            # 戦略シグナル側のexit(反転 or exitフラグ)
            sig_row = sig.iloc[i]
            sig_exit = sig_row.get("exit_signal", False)
            opposite_signal = (sig_row["signal"] != 0 and sig_row["signal"] != position)

            if exit_price is None and (sig_exit or opposite_signal):
                # 次バーのOpenで手仕舞い…今日のbarのOpenで手仕舞う扱い
                exit_price = bar["Open"]
                exit_reason = "signal_exit"

            if exit_price is not None:
                # pnl計算
                gross = (exit_price - entry_price) / entry_price * position
                spread_cost = spread_pips * pip_size / entry_price  # round-trip
                net_return_on_notional = gross - spread_cost
                equity_change_pct = net_return_on_notional * leverage
                # equity更新
                new_equity = equity * (1 + equity_change_pct)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=today,
                    direction=position, entry_price=entry_price,
                    exit_price=exit_price, stop_price=stop_price,
                    leverage=leverage, pnl_pct=equity_change_pct,
                    reason=exit_reason,
                    hold_days=(today - entry_date).days,
                ))
                equity = new_equity
                position = 0

        # --- エントリー判定（前日シグナル -> 当日Openで入る） ---
        if position == 0:
            prev_sig = sig.iloc[i - 1]
            s = int(prev_sig["signal"])
            if s != 0 and not np.isnan(prev_sig.get("stop", np.nan)):
                entry_price = bar["Open"]
                stop_price = float(prev_sig["stop"])
                target_price = float(prev_sig.get("target", np.nan)) if "target" in prev_sig else np.nan
                # サイジング
                stop_dist = abs(entry_price - stop_price) / entry_price
                if stop_dist > 1e-6:
                    lev = min(max_leverage, risk_per_trade / stop_dist)
                    leverage = lev
                    position = s
                    entry_date = today

        equity_curve.iloc[i] = equity

    equity_curve = equity_curve.ffill()
    return equity_curve, [t.__dict__ for t in trades]
