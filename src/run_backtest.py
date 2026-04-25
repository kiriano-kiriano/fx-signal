"""
3戦略 × 3通貨ペアのバックテスト一括実行
出力: output/results.json + output/dashboard.html
"""
import sys
import os
import json
from pathlib import Path
import traceback
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from indicators import atr, adx
from backtest import backtest
from strategies import STRATEGIES
from metrics import compute_metrics
from render_html import render

PAIRS = ["USDJPY", "EURJPY", "GBPJPY"]
INITIAL_CAPITAL = 100_000
RISK_PER_TRADE = 0.01
MAX_LEVERAGE = 10.0


def load_data(pair: str):
    """yfinanceで取得を試みて、失敗したら合成データにフォールバック"""
    try:
        from data_loader import fetch_daily
        df = fetch_daily(pair, years=15, use_cache=True)
        if len(df) < 1000:
            raise RuntimeError("Not enough data")
        return df, "real"
    except Exception as e:
        print(f"[warn] yfinance failed for {pair}: {e}; using synthetic", file=sys.stderr)
        from synthetic_data import generate
        return generate(pair, years=15), "synthetic"


def to_jsonable(obj):
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    return obj


def main():
    out_dir = ROOT.parent / "output"
    out_dir.mkdir(exist_ok=True)

    results = {"meta": {}, "by_strategy": {}, "by_pair_strategy": {}}
    data_source = "unknown"

    for pair in PAIRS:
        df, src = load_data(pair)
        data_source = src
        results["meta"][pair] = {
            "rows": len(df),
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
        }

        for sname, sfn in STRATEGIES.items():
            try:
                # 通貨ペアのpip_size（JPYクロスは0.01、それ以外は0.0001）
                pip_size = 0.01 if pair.endswith("JPY") else 0.0001
                equity, trades = backtest(
                    df, sfn,
                    risk_per_trade=RISK_PER_TRADE,
                    max_leverage=MAX_LEVERAGE,
                    spread_pips=2.0,
                    pip_size=pip_size,
                    initial_capital=INITIAL_CAPITAL,
                )
                m = compute_metrics(equity, trades, INITIAL_CAPITAL)
                # エクイティカーブを月次サンプリング（描画用）
                equity_monthly = equity.resample("ME").last().dropna()
                ec = [{"date": str(d.date()), "equity": float(v)}
                      for d, v in equity_monthly.items()]

                key = f"{sname}__{pair}"
                results["by_pair_strategy"][key] = {
                    "strategy": sname,
                    "pair": pair,
                    "metrics": m,
                    "equity_curve": ec,
                    "n_trades": len(trades),
                    "last_trades": [
                        {**{k: (v.isoformat() if hasattr(v, "isoformat") else v)
                           for k, v in t.items()}}
                        for t in trades[-5:]
                    ],
                }
                print(f"{pair} {sname}: trades={m['trades']}, "
                      f"return={m['total_return_pct']:.1f}%, "
                      f"DD={m['max_dd_pct']:.1f}%, "
                      f"Sharpe={m['sharpe']:.2f}, "
                      f"WR={m['win_rate_pct']:.1f}%")
            except Exception as e:
                print(f"[error] {pair} {sname}: {e}")
                traceback.print_exc()

    # 戦略別の集約（3ペア合算でなく、平均的な傾向）
    for sname in STRATEGIES.keys():
        rows = [v for k, v in results["by_pair_strategy"].items()
                if v["strategy"] == sname]
        if rows:
            avg = lambda key: float(np.mean([r["metrics"][key] for r in rows]))
            results["by_strategy"][sname] = {
                "avg_total_return_pct": avg("total_return_pct"),
                "avg_cagr_pct": avg("cagr_pct"),
                "avg_sharpe": avg("sharpe"),
                "avg_max_dd_pct": avg("max_dd_pct"),
                "avg_win_rate_pct": avg("win_rate_pct"),
                "avg_payoff": avg("payoff") if all(
                    np.isfinite(r["metrics"]["payoff"]) for r in rows) else None,
                "total_trades": int(sum(r["metrics"]["trades"] for r in rows)),
            }

    results["meta"]["data_source"] = data_source
    results["meta"]["initial_capital"] = INITIAL_CAPITAL
    results["meta"]["risk_per_trade"] = RISK_PER_TRADE
    results["meta"]["max_leverage"] = MAX_LEVERAGE

    # JSON保存
    out_json = out_dir / "results.json"
    out_json.write_text(json.dumps(to_jsonable(results), indent=2, ensure_ascii=False))
    print(f"saved {out_json}")

    # HTML生成
    html = render(results)
    out_html = out_dir / "dashboard.html"
    out_html.write_text(html)
    print(f"saved {out_html}")


if __name__ == "__main__":
    main()
