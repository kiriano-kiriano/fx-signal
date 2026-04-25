"""
価格データ取得モジュール
yfinance経由でUSD/JPY, EUR/JPY, GBP/JPYの日足を取得し、CSVキャッシュ。
"""
import os
from pathlib import Path
import pandas as pd
import yfinance as yf

PAIRS = {
    "USDJPY": "JPY=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch_daily(pair: str, years: int = 15, use_cache: bool = True) -> pd.DataFrame:
    if pair not in PAIRS:
        raise ValueError(f"Unknown pair: {pair}. Available: {list(PAIRS.keys())}")

    DATA_DIR.mkdir(exist_ok=True)
    cache = DATA_DIR / f"{pair}_daily.csv"

    if use_cache and cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        return df

    ticker = PAIRS[pair]
    period = f"{years}y"
    raw = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False)
    if raw.empty:
        raise RuntimeError(f"No data for {pair} ({ticker})")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Open", "High", "Low", "Close"]].copy()
    df = df.dropna()
    df.to_csv(cache)
    return df


def fetch_all(years: int = 15) -> dict:
    return {p: fetch_daily(p, years=years) for p in PAIRS}


if __name__ == "__main__":
    for p in PAIRS:
        df = fetch_daily(p, years=15, use_cache=False)
        print(f"{p}: {len(df)} rows, {df.index.min().date()} -> {df.index.max().date()}")
