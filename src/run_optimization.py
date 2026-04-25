"""
Phase 1.5 メイン実行: グリッドサーチを全戦略×全ペアで回し、
最適化結果ダッシュボードを生成。
"""
import sys
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from optimization import grid_search_all, rank_results, GRIDS
from render_optimization import render_optimization

PAIRS = ["USDJPY", "EURJPY", "GBPJPY"]


def load_data(pair: str):
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
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, tuple):
        return [to_jsonable(x) for x in obj]
    return obj


def main():
    out_dir = ROOT.parent / "output"
    out_dir.mkdir(exist_ok=True)

    print("=== loading data ===", flush=True)
    data = {}
    data_source = "unknown"
    for pair in PAIRS:
        df, src = load_data(pair)
        data[pair] = df
        data_source = src
        print(f"  {pair}: {len(df)} rows ({df.index[0].date()} -> {df.index[-1].date()})")

    # 組み合わせ数の事前カウント
    print("\n=== grid sizes ===")
    total = 0
    for s, g in GRIDS.items():
        from itertools import product
        n = 1
        for v in g["params"].values():
            n *= len(v)
        total += n * len(PAIRS)
        print(f"  {s}: {n} combos x {len(PAIRS)} pairs = {n * len(PAIRS)} backtests")
    print(f"  TOTAL: {total} backtests (each runs IS+OOS = {total*2} actual runs)")

    print("\n=== running grid search ===", flush=True)
    t0 = time.time()
    all_results = grid_search_all(data)
    elapsed = time.time() - t0
    print(f"\nelapsed: {elapsed:.1f}s, results: {len(all_results)}")

    rank = rank_results(all_results, top_n=20)
    print(f"\nrobust candidates (both periods positive): {len(rank['top_robust'])}")
    if rank["top_robust"]:
        print("\nTop 10 by min(IS_sharpe, OOS_sharpe):")
        for i, r in enumerate(rank["top_robust"][:10]):
            print(f"  {i+1}. {r['strategy']} x {r['pair']}: "
                  f"IS_SR={r['is_metrics']['sharpe']:.2f} "
                  f"OOS_SR={r['oos_metrics']['sharpe']:.2f} "
                  f"params=({r['params_str']})")

    # JSONダンプ（軽量化のため equity_curve は含めない）
    payload = {
        "meta": {
            "data_source": data_source,
            "is_period": "2011-2020",
            "oos_period": "2021-present",
            "total_combinations": len(all_results),
            "robust_count": len(rank["top_robust"]),
        },
        "all_results": all_results,
        "top_robust": rank["top_robust"][:30],
        "best_per_combo": rank["best_per_combo"],
    }

    out_json = out_dir / "optimization_results.json"
    out_json.write_text(json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False))
    print(f"\nsaved {out_json}")

    html = render_optimization(payload)
    out_html = out_dir / "optimization.html"
    out_html.write_text(html)
    print(f"saved {out_html}")


if __name__ == "__main__":
    main()
