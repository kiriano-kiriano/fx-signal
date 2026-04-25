"""
Phase 2.1: 基本Unit Test
バグ早期検出のための最小限テスト。
実行: cd 爆益計画 && python3 -m unittest tests.test_basic -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd


class TestIndicators(unittest.TestCase):
    def setUp(self):
        from synthetic_data import generate
        self.df = generate("USDJPY", years=2)

    def test_atr_positive(self):
        from indicators import atr
        a = atr(self.df, 14).dropna()
        self.assertTrue((a > 0).all())
        self.assertGreater(len(a), 200)

    def test_adx_range(self):
        from indicators import adx
        a = adx(self.df, 14).dropna()
        self.assertTrue((a >= 0).all() and (a <= 100).all())

    def test_bollinger_ordering(self):
        from indicators import bollinger
        mid, upper, lower = bollinger(self.df["Close"], 20, 2)
        valid = mid.notna()
        self.assertTrue(((upper >= mid) & (mid >= lower))[valid].all())

    def test_donchian_high_ge_low(self):
        from indicators import donchian_high, donchian_low
        h = donchian_high(self.df["High"], 20)
        l = donchian_low(self.df["Low"], 20)
        valid = h.notna()
        self.assertTrue((h >= l)[valid].all())


class TestStrategies(unittest.TestCase):
    def setUp(self):
        from synthetic_data import generate
        self.df = generate("USDJPY", years=2)

    def test_signal_has_stop(self):
        from strategies import strategy_c_bb_meanrev
        sig = strategy_c_bb_meanrev(self.df)
        signaled = sig[sig["signal"] != 0]
        self.assertTrue(signaled["stop"].notna().all())


class TestBacktest(unittest.TestCase):
    def setUp(self):
        from synthetic_data import generate
        self.df = generate("USDJPY", years=3)

    def test_equity_never_negative(self):
        from backtest import backtest
        from strategies import strategy_c_bb_meanrev
        from functools import partial
        sig = partial(strategy_c_bb_meanrev, adx_max=25, k=2.5, n=20, stop_k=2.5)
        eq, trades = backtest(self.df, sig, risk_per_trade=0.02,
                               max_leverage=20.0, spread_pips=2.0,
                               pip_size=0.01, initial_capital=100_000)
        self.assertGreater(len(eq), 100)
        self.assertTrue((eq > 0).all())
        for t in trades:
            self.assertTrue(np.isfinite(t["pnl_pct"]))


class TestLiveState(unittest.TestCase):
    def test_compute_pair_state_returns_required_keys(self):
        from synthetic_data import generate
        from live_state import compute_pair_state
        df = generate("USDJPY", years=3)
        state = compute_pair_state(df, "USDJPY",
                                   dict(adx_max=25, k=2.5, n=20, stop_k=2.5),
                                   risk_per_trade=0.02, max_leverage=20.0)
        for key in ["pair", "current_equity", "today_signal", "open_position",
                    "yesterday_result", "recent_trades", "equity_curve",
                    "metrics", "last_close", "last_date"]:
            self.assertIn(key, state)


class TestNotifyMessage(unittest.TestCase):
    def test_no_signal_message_includes_guidance(self):
        from notify import format_signal_message
        msg = format_signal_message("2026-01-01", [], [], [])
        self.assertIn("シグナルなし", msg)
        self.assertIn("お休み", msg)

    def test_signal_message_contains_prices(self):
        from notify import format_signal_message
        signals = [{
            "pair": "USDJPY", "direction": 1,
            "entry_price_est": 150.0,
            "stop_price": 148.0, "target_price": 152.0,
        }]
        msg = format_signal_message("2026-01-01", signals, [], [])
        self.assertIn("USDJPY", msg)
        self.assertIn("150.000", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
