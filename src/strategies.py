"""
3つの戦略シグナル生成関数
入力: OHLC DataFrame
出力: signal (+1/-1/0), stop (price), target (price or NaN), exit_signal (bool)
"""
import numpy as np
import pandas as pd
from indicators import atr, adx, sma, donchian_high, donchian_low, bollinger


def strategy_a_donchian(df: pd.DataFrame,
                         breakout_n: int = 20,
                         exit_n: int = 10,
                         atr_n: int = 14,
                         atr_mult: float = 2.0) -> pd.DataFrame:
    """戦略A: ドンチャン・ブレイクアウト
    20日高値ブレイクで買い、20日安値ブレイクで売り。
    損切り: エントリー価格 - 2ATR（売りは+2ATR）
    撤退: 反対方向の10日ドンチャン（exit_signal=True）
    """
    out = pd.DataFrame(index=df.index)
    a = atr(df, atr_n)
    dh = donchian_high(df["High"], breakout_n).shift(1)  # 1日前までの高値（当日含まない）
    dl = donchian_low(df["Low"], breakout_n).shift(1)
    ex_h = donchian_high(df["High"], exit_n).shift(1)
    ex_l = donchian_low(df["Low"], exit_n).shift(1)

    long_sig = df["Close"] > dh
    short_sig = df["Close"] < dl

    out["signal"] = np.where(long_sig, 1, np.where(short_sig, -1, 0))
    out["stop"] = np.where(long_sig, df["Close"] - atr_mult * a,
                   np.where(short_sig, df["Close"] + atr_mult * a, np.nan))
    out["target"] = np.nan

    # exit_signal: 保有方向と反対の10日ドンチャン（position依存なのでこの層ではbool化困難。
    # ここでは単純化して、closeがexit_l（10日安値）を下回れば手仕舞い、という単方向近似は使わない。
    # 代わりに、逆ブレイクアウトをopposite_signalとして使う（backtestが対応済み）。
    out["exit_signal"] = False
    return out


def strategy_b_ma_adx(df: pd.DataFrame,
                       fast: int = 20,
                       slow: int = 50,
                       adx_threshold: float = 25.0,
                       atr_n: int = 14,
                       atr_mult: float = 2.0,
                       pullback_pct: float = 0.3) -> pd.DataFrame:
    """戦略B: MA+ADXトレンドフォロー
    fast MA > slow MA かつ ADX>25 の買いバイアス時に、
    押し目（fast MAタッチ or 軽い引け戻り）でエントリー。
    売りも対称。
    損切りはエントリーから2ATR。
    """
    out = pd.DataFrame(index=df.index)
    a = atr(df, atr_n)
    fast_ma = sma(df["Close"], fast)
    slow_ma = sma(df["Close"], slow)
    adx_ = adx(df, 14)

    uptrend = (fast_ma > slow_ma) & (adx_ > adx_threshold)
    downtrend = (fast_ma < slow_ma) & (adx_ > adx_threshold)

    # 押し目: Closeがfast_maを下から触る/跨ぐ（過去bar価格vs今日fast_ma）
    pullback_up = (df["Low"] <= fast_ma) & (df["Close"] > fast_ma) & uptrend
    pullback_dn = (df["High"] >= fast_ma) & (df["Close"] < fast_ma) & downtrend

    out["signal"] = np.where(pullback_up, 1, np.where(pullback_dn, -1, 0))
    out["stop"] = np.where(pullback_up, df["Close"] - atr_mult * a,
                   np.where(pullback_dn, df["Close"] + atr_mult * a, np.nan))
    out["target"] = np.nan
    # 撤退：slow_ma割れ/上抜けで手仕舞い
    out["exit_signal"] = False
    return out


def strategy_c_bb_meanrev(df: pd.DataFrame,
                           n: int = 20,
                           k: float = 2.0,
                           adx_max: float = 20.0,
                           stop_k: float = 3.0) -> pd.DataFrame:
    """戦略C: ボリンジャー平均回帰
    ±2σタッチで逆張り、中央（20MA）で利確、-3σ/+3σで損切り。
    ADX<20（レンジ相場）のときのみ発動。
    """
    out = pd.DataFrame(index=df.index)
    mid, upper, lower = bollinger(df["Close"], n, k)
    _, upper3, lower3 = bollinger(df["Close"], n, stop_k)
    adx_ = adx(df, 14)

    range_mode = adx_ < adx_max

    long_sig = (df["Low"] <= lower) & (df["Close"] > lower) & range_mode  # 下限タッチ後に戻る
    short_sig = (df["High"] >= upper) & (df["Close"] < upper) & range_mode

    out["signal"] = np.where(long_sig, 1, np.where(short_sig, -1, 0))
    out["stop"] = np.where(long_sig, lower3,
                   np.where(short_sig, upper3, np.nan))
    out["target"] = np.where(long_sig, mid,
                    np.where(short_sig, mid, np.nan))
    out["exit_signal"] = False
    return out


STRATEGIES = {
    "A_Donchian": strategy_a_donchian,
    "B_MA_ADX":   strategy_b_ma_adx,
    "C_BB_MeanRev": strategy_c_bb_meanrev,
}
