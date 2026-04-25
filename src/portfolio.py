"""
Phase β: 3ペアポートフォリオ合成バックテスト
個別ペアのトレード列を時系列マージし、単一資金で運用したと仮定した合成エクイティを計算。

サイズ調整：
- 各ペアは独立に計算したリスク%でサイジング
- 合成資金で実行する際、複数ペアが同時保有されることを許容（最大3ポジ同時）
- 1ペアあたりの最大エクスポージャは初期資金の100%まで（実効レバ制限）
"""
import pandas as pd
import numpy as np
from functools import partial

from backtest import backtest
from metrics import compute_metrics
from strategies import strategy_c_bb_meanrev


def run_single_pair(df: pd.DataFrame, pair: str, params: dict,
                     risk_per_trade: float, max_leverage: float,
                     initial_capital: float = 100_000,
                     spread_pips: float = 2.0) -> tuple:
    pip_size = 0.01 if pair.endswith("JPY") else 0.0001
    sig = partial(strategy_c_bb_meanrev, **params)
    eq, trades = backtest(
        df, sig, risk_per_trade, max_leverage,
        spread_pips, pip_size, initial_capital,
    )
    for t in trades:
        t["pair"] = pair
    return eq, trades


def portfolio_simulate(trades_per_pair: dict, initial_capital: float = 100_000,
                        max_concurrent: int = 3) -> tuple:
    """各ペアのトレード列を時系列マージして単一資金で運用シミュレーション。
    各トレードが個別に計算した equity_change_pct を、保有時の現資金に乗算。
    複数ペアが同時保有でもそれぞれが独立に資金を動かす想定（同時最大 max_concurrent）。
    """
    all_trades = []
    for pair, trades in trades_per_pair.items():
        all_trades.extend(trades)

    df = pd.DataFrame(all_trades)
    if df.empty:
        empty = pd.Series(dtype=float)
        return empty, []
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])

    # 全イベントを時系列に並べる
    events = []
    for _, row in df.iterrows():
        events.append((row["entry_date"], "open", row.to_dict()))
        events.append((row["exit_date"], "close", row.to_dict()))
    events.sort(key=lambda x: x[0])

    # シミュレーション
    equity = initial_capital
    open_positions = []
    equity_log = []  # (date, equity)

    # closeイベントが処理されたらequityを更新
    closed_trades = []
    for date, kind, t in events:
        if kind == "open":
            if len(open_positions) >= max_concurrent:
                continue  # 同時保有上限超過は見送り（保守的）
            open_positions.append(t)
        else:  # close
            # 該当ポジを探す
            match = None
            for op in open_positions:
                if (op["entry_date"] == t["entry_date"] and op["pair"] == t["pair"]):
                    match = op
                    break
            if match is None:
                continue
            open_positions.remove(match)
            # 資金更新
            equity *= (1 + t["pnl_pct"])
            closed_trades.append({**t, "post_equity": equity})
            equity_log.append((date, equity))

    if not equity_log:
        return pd.Series([initial_capital], index=[df["entry_date"].min()]), closed_trades

    eq_series = pd.Series(
        [e for _, e in equity_log],
        index=pd.DatetimeIndex([d for d, _ in equity_log]),
    )
    # 開始時点を初期資金として追加
    start_date = df["entry_date"].min() - pd.Timedelta(days=1)
    eq_series = pd.concat([pd.Series([initial_capital], index=[start_date]), eq_series])
    eq_series = eq_series.sort_index()
    # 同じ日に複数決済があった場合は最後の値を残す
    eq_series = eq_series[~eq_series.index.duplicated(keep="last")]
    return eq_series, closed_trades
