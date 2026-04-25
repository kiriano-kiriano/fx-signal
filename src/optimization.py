"""
Phase 1.5: パラメータグリッドサーチ + IS/OOS バリデーション

設計:
- 各戦略のキーパラメータをグリッド化
- 期間を IS（2011-2020）と OOS（2021-現在）に分割
- 全組み合わせを両期間でバックテスト
- ロバストネス基準で評価:
  * IS_sharpe と OOS_sharpe が両方プラスかつそれなりに高いもの
  * 2つのSharpeの最小値（min_sharpe）が一番フェアな指標
"""
from itertools import product
import pandas as pd
import numpy as np
from functools import partial

from backtest import backtest
from metrics import compute_metrics
from strategies import (
    strategy_a_donchian,
    strategy_b_ma_adx,
    strategy_c_bb_meanrev,
)

# --- パラメータグリッド（戦略ごと） -------------------------------------
GRIDS = {
    "A_Donchian": {
        "fn": strategy_a_donchian,
        "params": {
            "breakout_n": [15, 20, 30, 55],
            "atr_mult": [2.0, 2.5, 3.0],
            "exit_n": [5, 10, 20],
        },
    },
    "B_MA_ADX": {
        "fn": strategy_b_ma_adx,
        "params": {
            # (fast, slow) を組で扱うため、fast/slow を独立に振らない
            "fast_slow": [(10, 30), (20, 50), (20, 100), (50, 200)],
            "adx_threshold": [20, 25, 30],
            "atr_mult": [2.0, 3.0],
        },
    },
    "C_BB_MeanRev": {
        "fn": strategy_c_bb_meanrev,
        "params": {
            "n": [20, 30],
            "k": [1.5, 2.0, 2.5],
            "adx_max": [20, 25],
            "stop_k": [2.5, 3.0],
        },
    },
}

# IS/OOS分割
IS_END = "2020-12-31"
OOS_START = "2021-01-01"


def split_is_oos(df: pd.DataFrame):
    is_df = df.loc[:IS_END].copy()
    oos_df = df.loc[OOS_START:].copy()
    return is_df, oos_df


def _expand_params(grid: dict):
    """グリッド辞書から全組み合わせのdictを生成"""
    keys = list(grid.keys())
    for vals in product(*[grid[k] for k in keys]):
        yield dict(zip(keys, vals))


def _build_signal_fn(strategy_name: str, params: dict):
    """戦略関数 + パラメータからsignal_fnを作る。fast_slowなど特殊ケース対応"""
    base_fn = GRIDS[strategy_name]["fn"]
    if strategy_name == "B_MA_ADX":
        fast, slow = params["fast_slow"]
        kw = {k: v for k, v in params.items() if k != "fast_slow"}
        kw["fast"] = fast
        kw["slow"] = slow
        return partial(base_fn, **kw)
    return partial(base_fn, **params)


def _serialize_params(strategy_name: str, params: dict) -> str:
    """params辞書をHTML/JSONで使える文字列に"""
    if strategy_name == "B_MA_ADX":
        fast, slow = params["fast_slow"]
        rest = {k: v for k, v in params.items() if k != "fast_slow"}
        rest["fast"] = fast
        rest["slow"] = slow
        return ", ".join(f"{k}={v}" for k, v in sorted(rest.items()))
    return ", ".join(f"{k}={v}" for k, v in sorted(params.items()))


def grid_search_one(strategy_name: str, df: pd.DataFrame, pair: str,
                    initial_capital: float = 100_000,
                    risk_per_trade: float = 0.01,
                    max_leverage: float = 10.0,
                    spread_pips: float = 2.0) -> list:
    """1戦略×1ペアを全パラメータで実行（IS/OOS両方）"""
    pip_size = 0.01 if pair.endswith("JPY") else 0.0001
    is_df, oos_df = split_is_oos(df)

    grid = GRIDS[strategy_name]["params"]
    results = []

    for params in _expand_params(grid):
        signal_fn = _build_signal_fn(strategy_name, params)

        try:
            is_eq, is_trades = backtest(
                is_df, signal_fn, risk_per_trade, max_leverage,
                spread_pips, pip_size, initial_capital,
            )
            is_m = compute_metrics(is_eq, is_trades, initial_capital)
        except Exception as e:
            is_m = None

        try:
            oos_eq, oos_trades = backtest(
                oos_df, signal_fn, risk_per_trade, max_leverage,
                spread_pips, pip_size, initial_capital,
            )
            oos_m = compute_metrics(oos_eq, oos_trades, initial_capital)
        except Exception as e:
            oos_m = None

        if is_m is None or oos_m is None:
            continue

        # ロバストネススコア:
        # 両期間のSharpeの最小値を採用（片方だけ良いものを排除）
        min_sharpe = min(is_m["sharpe"], oos_m["sharpe"])
        avg_sharpe = (is_m["sharpe"] + oos_m["sharpe"]) / 2
        # 両期間ともプラスならロバスト候補
        both_positive = is_m["total_return_pct"] > 0 and oos_m["total_return_pct"] > 0

        results.append({
            "strategy": strategy_name,
            "pair": pair,
            "params": params,
            "params_str": _serialize_params(strategy_name, params),
            "is_metrics": is_m,
            "oos_metrics": oos_m,
            "min_sharpe": min_sharpe,
            "avg_sharpe": avg_sharpe,
            "both_positive": both_positive,
        })

    return results


def grid_search_all(data: dict) -> list:
    """全戦略×全ペアでグリッドサーチ。dataは {pair: df} 形式"""
    all_results = []
    for strategy_name in GRIDS.keys():
        for pair, df in data.items():
            print(f"  -> grid_search {strategy_name} x {pair} ...", flush=True)
            results = grid_search_one(strategy_name, df, pair)
            all_results.extend(results)
            print(f"     done: {len(results)} combinations", flush=True)
    return all_results


def rank_results(results: list, top_n: int = 10) -> dict:
    """結果をランキング。複数の観点で。"""
    # 全体トップ（min_sharpe降順、両期間プラスのみ）
    robust = [r for r in results if r["both_positive"]]
    by_min_sharpe = sorted(robust, key=lambda r: r["min_sharpe"], reverse=True)[:top_n]

    # 戦略×ペア別のベスト
    best_per_combo = {}
    for r in results:
        key = f"{r['strategy']}__{r['pair']}"
        if key not in best_per_combo or r["min_sharpe"] > best_per_combo[key]["min_sharpe"]:
            best_per_combo[key] = r

    return {
        "top_robust": by_min_sharpe,
        "best_per_combo": list(best_per_combo.values()),
    }
