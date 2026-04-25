"""テクニカル指標ユーティリティ（numpy/pandasで自前実装、外部依存なし）"""
import numpy as np
import pandas as pd


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    h_l = df["High"] - df["Low"]
    h_pc = (df["High"] - df["Close"].shift(1)).abs()
    l_pc = (df["Low"] - df["Close"].shift(1)).abs()
    return pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = true_range(df)
    return tr.rolling(n).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ADX。ADXは方向に関わらずトレンドの強さ（0-100）"""
    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = true_range(df)

    atr_ = tr.rolling(n).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(n).mean() / atr_.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(n).mean() / atr_.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(n).mean()


def donchian_high(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).max()


def donchian_low(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).min()


def bollinger(series: pd.Series, n: int = 20, k: float = 2.0):
    mid = series.rolling(n).mean()
    sd = series.rolling(n).std(ddof=0)
    return mid, mid + k * sd, mid - k * sd
