"""
yfinance非対応環境用の合成データ（サンプルダッシュボード表示用）。
実運用ではdata_loader.pyのyfinanceを使うこと。
"""
import numpy as np
import pandas as pd


def generate(pair: str, years: int = 15, seed: int = None) -> pd.DataFrame:
    if seed is None:
        seed = hash(pair) % (2**32)
    rng = np.random.default_rng(seed)
    n = int(years * 252)
    # 通貨ペアに応じて初期価格とボラ設定
    params = {
        "USDJPY": (115.0, 0.0075),
        "EURJPY": (130.0, 0.0085),
        "GBPJPY": (155.0, 0.0095),
    }
    start_price, daily_vol = params.get(pair, (100.0, 0.008))

    # レジーム変化: トレンド期とレンジ期を混合
    mu_trend = 0.0003
    mu_range = 0.0
    regime = np.zeros(n)
    i = 0
    while i < n:
        length = rng.integers(60, 300)
        end = min(i + length, n)
        is_trend = rng.random() < 0.55
        direction = rng.choice([-1, 1])
        regime[i:end] = direction * mu_trend if is_trend else mu_range
        i = end
    returns = regime + rng.normal(0, daily_vol, n)
    # ランダムショック（コロナ・スイスショック的）
    shock_days = rng.choice(n, size=rng.integers(2, 6), replace=False)
    for sd in shock_days:
        returns[sd] = rng.choice([-1, 1]) * rng.uniform(0.03, 0.06)

    prices = start_price * np.cumprod(1 + returns)

    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    close = pd.Series(prices, index=dates)
    # OHLC合成
    intra_range = rng.uniform(0.002, 0.009, n)
    high = close * (1 + intra_range / 2)
    low = close * (1 - intra_range / 2)
    open_ = close.shift(1).fillna(close.iloc[0])
    # swap high<->low if needed
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close})
    df["High"] = df[["Open", "High", "Low", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "High", "Low", "Close"]].min(axis=1)
    return df


if __name__ == "__main__":
    for p in ["USDJPY", "EURJPY", "GBPJPY"]:
        df = generate(p)
        print(p, len(df), f"{df.index[0].date()} -> {df.index[-1].date()}",
              f"close {df['Close'].iloc[-1]:.2f}")
