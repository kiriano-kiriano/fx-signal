"""
Phase β: 統合実行
- 勝者戦略 (C_BB_MeanRev, params: adx_max=25, k=2.5, n=20, stop_k=2.5) を3ペアで運用
- リスク 1%/2%/3%、最大レバ 10/20/25 の3シナリオ
- アノマリー分析、ウォークフォワード、ポートフォリオ合成
"""
import sys
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from anomaly import analyze_trades, detect_filter_opportunities
from portfolio import run_single_pair, portfolio_simulate
from walkforward import yearly_breakdown
from metrics import compute_metrics
from render_phase_beta import render_phase_beta

PAIRS = ["USDJPY", "EURJPY", "GBPJPY"]
WINNER_PARAMS = dict(adx_max=25, k=2.5, n=20, stop_k=2.5)

# 3つのリスクシナリオ
SCENARIOS = [
    {"name": "保守 (1%/レバ10)", "risk": 0.01, "lev": 10, "label": "conservative"},
    {"name": "標準 (2%/レバ20)", "risk": 0.02, "lev": 20, "label": "standard"},
    {"name": "攻撃 (3%/レバ25)", "risk": 0.03, "lev": 25, "label": "aggressive"},
]


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

    payload = {
        "meta": {
            "data_source": data_source,
            "params": WINNER_PARAMS,
            "pairs": PAIRS,
        },
        "scenarios": [],
    }

    # 各シナリオでバックテスト + ポートフォリオ合成
    print("\n=== scenarios ===")
    all_pair_trades = {}  # pair -> trades for anomaly analysis (use standard scenario)
    for sc in SCENARIOS:
        print(f"  scenario: {sc['name']}")
        scenario_data = {
            "name": sc["name"],
            "label": sc["label"],
            "risk": sc["risk"],
            "leverage": sc["lev"],
            "by_pair": {},
        }
        trades_per_pair = {}
        for pair in PAIRS:
            eq, trades = run_single_pair(
                data[pair], pair, WINNER_PARAMS,
                risk_per_trade=sc["risk"], max_leverage=sc["lev"],
            )
            m = compute_metrics(eq, trades, 100_000)
            scenario_data["by_pair"][pair] = {
                "metrics": m,
                "n_trades": len(trades),
                "equity_monthly": [
                    {"date": str(d.date()), "equity": float(v)}
                    for d, v in eq.resample("ME").last().dropna().items()
                ],
            }
            trades_per_pair[pair] = trades
            print(f"    {pair}: trades={m['trades']}, "
                  f"CAGR={m['cagr_pct']:.1f}%, "
                  f"DD={m['max_dd_pct']:.1f}%, "
                  f"SR={m['sharpe']:.2f}")

            if sc["label"] == "standard":
                all_pair_trades[pair] = trades

        # ポートフォリオ合成
        port_eq, port_trades = portfolio_simulate(trades_per_pair, initial_capital=100_000)
        # 日次リサンプリング（forward-fill）してSharpe等を正しく計算
        port_eq_daily = port_eq.resample("D").ffill().dropna()
        port_m = compute_metrics(port_eq_daily, port_trades, 100_000)
        scenario_data["portfolio"] = {
            "metrics": port_m,
            "n_trades": len(port_trades),
            "equity_curve": [
                {"date": str(d.date()), "equity": float(v)}
                for d, v in port_eq.resample("ME").last().dropna().items()
            ],
        }
        # 10倍までの推定年数
        cagr = port_m["cagr_pct"] / 100
        if cagr > 0:
            years_to_10x = np.log(10) / np.log(1 + cagr)
        else:
            years_to_10x = float("inf")
        scenario_data["years_to_10x"] = float(years_to_10x)
        print(f"    [PORT] CAGR={port_m['cagr_pct']:.1f}%, "
              f"DD={port_m['max_dd_pct']:.1f}%, "
              f"SR={port_m['sharpe']:.2f}, "
              f"10x={years_to_10x:.1f}y")
        payload["scenarios"].append(scenario_data)

    # アノマリー分析（標準シナリオのトレードベース）
    print("\n=== anomaly analysis (standard scenario) ===")
    anomaly_results = {}
    for pair in PAIRS:
        a = analyze_trades(all_pair_trades[pair], label=pair)
        opps = detect_filter_opportunities(a, min_n=8)
        anomaly_results[pair] = {"analysis": a, "opportunities": opps}
        print(f"  {pair}: {len(opps)} filter opportunities")
        for o in opps[:3]:
            print(f"     - {o['reason']}")

    # 全ペア合算
    all_trades_concat = []
    for pair in PAIRS:
        for t in all_pair_trades[pair]:
            all_trades_concat.append(t)
    a_all = analyze_trades(all_trades_concat, label="ALL")
    opps_all = detect_filter_opportunities(a_all, min_n=15)
    anomaly_results["ALL"] = {"analysis": a_all, "opportunities": opps_all}
    print(f"  ALL_PAIRS: {len(opps_all)} filter opportunities")

    payload["anomaly"] = anomaly_results

    # ウォークフォワード（年次）
    print("\n=== walk-forward (yearly, standard scenario) ===")
    wf = {}
    for pair in PAIRS:
        years_results = yearly_breakdown(
            data[pair], pair, WINNER_PARAMS,
            risk_per_trade=0.02, max_leverage=20.0,
        )
        wf[pair] = years_results
        positive_years = sum(1 for y in years_results if y["return_pct"] > 0)
        total_years = len(years_results)
        print(f"  {pair}: {positive_years}/{total_years} positive years, "
              f"avg SR: {np.mean([y['sharpe'] for y in years_results]):.2f}")
    payload["walkforward"] = wf

    # JSON保存
    out_json = out_dir / "phase_beta_results.json"
    out_json.write_text(json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False))
    print(f"\nsaved {out_json}")

    # HTML生成
    html = render_phase_beta(payload)
    out_html = out_dir / "phase_beta.html"
    out_html.write_text(html)
    print(f"saved {out_html}")


if __name__ == "__main__":
    main()
