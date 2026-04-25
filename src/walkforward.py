"""
Phase β: ウォークフォワード分析
ローリング窓で繰り返し訓練・検証し、毎年の安定性を確認。

簡易版：固定パラメータでローリングテスト（年単位）
- 2011-2025の全データを年単位でスライス
- 各年で独立にバックテストし、Sharpe / CAGR / DD を記録
- 一貫してプラスかを可視化
"""
import pandas as pd
import numpy as np
from functools import partial

from backtest import backtest
from metrics import compute_metrics
from strategies import strategy_c_bb_meanrev


def yearly_breakdown(df: pd.DataFrame, pair: str, params: dict,
                     risk_per_trade: float = 0.02,
                     max_leverage: float = 20.0,
                     initial_capital: float = 100_000) -> list:
    """各年で独立にバックテスト（前年の結果は引き継がない）"""
    pip_size = 0.01 if pair.endswith("JPY") else 0.0001
    sig = partial(strategy_c_bb_meanrev, **params)

    years = sorted(df.index.year.unique())
    results = []
    for y in years:
        # 当該年の前60日（指標準備用）+ 当該年
        year_start = pd.Timestamp(f"{y}-01-01")
        year_end = pd.Timestamp(f"{y}-12-31")
        prep_start = year_start - pd.Timedelta(days=90)
        sub = df.loc[prep_start:year_end]
        if len(sub) < 100:
            continue
        try:
            eq, trades = backtest(sub, sig, risk_per_trade, max_leverage, 2.0, pip_size, initial_capital)
            # 当該年だけの部分を切り出してメトリクス計算
            year_eq = eq[year_start:year_end]
            year_trades = [t for t in trades if pd.Timestamp(t["entry_date"]).year == y]
            if len(year_eq) < 10:
                continue
            # 当該年の開始equityを基準に再計算
            base = year_eq.iloc[0] if year_eq.iloc[0] > 0 else initial_capital
            year_eq_norm = year_eq / base * initial_capital
            m = compute_metrics(year_eq_norm, year_trades, initial_capital)
            results.append({
                "year": int(y),
                "trades": m["trades"],
                "return_pct": m["total_return_pct"],
                "sharpe": m["sharpe"],
                "max_dd_pct": m["max_dd_pct"],
                "win_rate_pct": m["win_rate_pct"],
            })
        except Exception as e:
            print(f"  [warn] year {y} {pair}: {e}")
    return results
