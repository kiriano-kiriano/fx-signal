"""
Phase 2: 日次シグナル生成のメインエントリー
GitHub Actionsから毎朝07:30 JSTに実行される。

処理フロー:
1. yfinanceから最新データ取得
2. 各ペアの状態を計算（今日のシグナル、保有ポジ、昨日の結果）
3. ダッシュボードHTML（index.html）と運用イメージページ（workflow.html）を生成
4. アクションがあれば LINE/Discord に通知
"""
import sys
import os
import json
import datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from live_state import compute_pair_state
from render_daily import render_daily_dashboard
from render_workflow import render_workflow_page
from notify import format_signal_message, notify_all

PAIRS = ["USDJPY", "EURJPY", "GBPJPY"]
WINNER_PARAMS = dict(adx_max=25, k=2.5, n=20, stop_k=2.5)

# 環境変数で運用設定（GitHub Actions Secrets経由でも可）
ACCOUNT_BALANCE = float(os.environ.get("FX_ACCOUNT_BALANCE", "100000"))
RISK_PCT = float(os.environ.get("FX_RISK_PCT", "0.02"))     # 1トレードのリスク%
MAX_LEVERAGE = float(os.environ.get("FX_MAX_LEVERAGE", "20"))


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

    print(f"=== generate_daily started: {dt.datetime.now()} ===")
    print(f"Account: ¥{ACCOUNT_BALANCE:,.0f}, Risk: {RISK_PCT*100:.1f}%, MaxLev: {MAX_LEVERAGE}x")

    pairs_state = {}
    data_source = "unknown"
    for pair in PAIRS:
        print(f"\nLoading {pair}...")
        df, src = load_data(pair)
        data_source = src
        print(f"  rows={len(df)}, last_date={df.index[-1].date()}, last_close={df['Close'].iloc[-1]:.3f}")

        state = compute_pair_state(
            df, pair, WINNER_PARAMS,
            risk_per_trade=RISK_PCT,
            max_leverage=MAX_LEVERAGE,
        )
        pairs_state[pair] = state

        if state["today_signal"]:
            s = state["today_signal"]
            print(f"  🔥 NEW SIGNAL: {s['direction_label']} entry={s['entry_price_est']:.3f} "
                  f"SL={s['stop_price']:.3f} TP={s['target_price']}")
        elif state["open_position"]:
            op = state["open_position"]
            pnl = op["unrealized_pnl_pct"] * 100
            print(f"  📌 OPEN: {'buy' if op['direction']==1 else 'sell'} "
                  f"unrealized={pnl:+.2f}% hold={op['hold_days']}d")
        else:
            print(f"  💤 wait")

    payload = {
        "meta": {
            "data_source": data_source,
            "params": WINNER_PARAMS,
            "account_balance": ACCOUNT_BALANCE,
            "risk_per_trade": RISK_PCT,
            "max_leverage": MAX_LEVERAGE,
            "generated_at": dt.datetime.now().isoformat(),
        },
        "pairs": pairs_state,
    }

    # JSON保存
    out_json = out_dir / "daily_state.json"
    out_json.write_text(json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False))
    print(f"\nsaved {out_json}")

    # HTML生成
    html = render_daily_dashboard(payload)
    out_html = out_dir / "index.html"
    out_html.write_text(html)
    print(f"saved {out_html}")

    workflow_html = render_workflow_page()
    workflow_path = out_dir / "workflow.html"
    workflow_path.write_text(workflow_html)
    print(f"saved {workflow_path}")

    # 通知
    today_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M JST")
    new_signals = []
    open_positions = []
    yesterday_results = []
    for p, s in pairs_state.items():
        if s["today_signal"]:
            ns = dict(s["today_signal"]); ns["pair"] = p
            new_signals.append(ns)
        if s["open_position"]:
            op = dict(s["open_position"]); op["pair"] = p
            open_positions.append(op)
        if s["yesterday_result"]:
            yr = dict(s["yesterday_result"]); yr["pair"] = p
            yesterday_results.append(yr)

    has_action = bool(new_signals or yesterday_results)
    msg = format_signal_message(today_str, new_signals, open_positions, yesterday_results)
    print("\n=== Notification message ===\n" + msg)

    notify_result = notify_all(msg, only_if_action=True, has_action=has_action)
    print(f"\nnotification result: {notify_result}")

    print(f"\n=== generate_daily completed: {dt.datetime.now()} ===")


if __name__ == "__main__":
    main()
