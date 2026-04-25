"""
Phase β: アノマリー分析
勝者戦略のトレードリストを以下の軸で集計：
- 曜日 (DoW): 月-金
- 月 (1-12)
- 月内日 (1-10/11-20/21-末)
- ゴトー日 (5,10,15,20,25,末日)
- 四半期末 (3,6,9,12月の最終週)
- 雇用統計週 (毎月第1金曜日±1日)
- 月初・月末
"""
import pandas as pd
import numpy as np


def _gotoubi_flag(date: pd.Timestamp) -> bool:
    """ゴトー日: 5,10,15,20,25,末日の月内営業日"""
    d = date.day
    if date.is_month_end:
        return True
    return d in (5, 10, 15, 20, 25)


def _nfp_week_flag(date: pd.Timestamp) -> bool:
    """米雇用統計週（月第1金曜日±1営業日）"""
    # 月の第1金曜日
    first = date.replace(day=1)
    while first.weekday() != 4:
        first += pd.Timedelta(days=1)
    return abs((date - first).days) <= 1


def analyze_trades(trades: list, label: str = "") -> dict:
    """trades: list of dict with entry_date, pnl_pct, direction"""
    if not trades:
        return {"label": label, "n": 0}

    df = pd.DataFrame(trades)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["dow"] = df["entry_date"].dt.dayofweek
    df["month"] = df["entry_date"].dt.month
    df["day"] = df["entry_date"].dt.day
    df["is_gotoubi"] = df["entry_date"].apply(_gotoubi_flag)
    df["is_quarter_end"] = df["entry_date"].dt.is_quarter_end
    df["is_month_first"] = df["day"] <= 3
    df["is_month_last"] = df["day"] >= 25
    df["is_nfp_week"] = df["entry_date"].apply(_nfp_week_flag)
    df["win"] = df["pnl_pct"] > 0

    def agg(group_df: pd.DataFrame) -> dict:
        if len(group_df) == 0:
            return {"n": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0}
        return {
            "n": int(len(group_df)),
            "win_rate": float(group_df["win"].mean() * 100),
            "avg_pnl": float(group_df["pnl_pct"].mean() * 100),
            "total_pnl": float(group_df["pnl_pct"].sum() * 100),
            "median_pnl": float(group_df["pnl_pct"].median() * 100),
        }

    by_dow = {int(d): agg(df[df["dow"] == d]) for d in range(7)}
    by_month = {int(m): agg(df[df["month"] == m]) for m in range(1, 13)}

    flags = {
        "is_gotoubi": agg(df[df["is_gotoubi"]]),
        "is_not_gotoubi": agg(df[~df["is_gotoubi"]]),
        "is_month_first_3d": agg(df[df["is_month_first"]]),
        "is_month_last_5d": agg(df[df["is_month_last"]]),
        "is_quarter_end": agg(df[df["is_quarter_end"]]),
        "is_nfp_week": agg(df[df["is_nfp_week"]]),
        "is_not_nfp_week": agg(df[~df["is_nfp_week"]]),
    }

    direction_split = {
        "long": agg(df[df["direction"] == 1]),
        "short": agg(df[df["direction"] == -1]),
    }

    overall = agg(df)

    return {
        "label": label,
        "overall": overall,
        "by_dow": by_dow,  # 0=月,1=火,2=水,3=木,4=金,5=土,6=日
        "by_month": by_month,
        "flags": flags,
        "direction": direction_split,
    }


def detect_filter_opportunities(analysis: dict, min_n: int = 10) -> list:
    """アノマリー分析から「除外候補」を提案。
    各カテゴリで、サンプル数十分かつ期待値が大きく負になっている群を抽出。
    """
    opps = []

    # 曜日チェック
    DOW_NAMES = ["月", "火", "水", "木", "金", "土", "日"]
    for k, v in analysis["by_dow"].items():
        if v.get("n", 0) >= min_n and v["avg_pnl"] < -0.05:
            opps.append({
                "type": "dow_exclude",
                "key": DOW_NAMES[k],
                "stat": v,
                "reason": f"{DOW_NAMES[k]}曜エントリーは平均{v['avg_pnl']:.2f}%（{v['n']}回）",
            })

    # 月チェック
    for k, v in analysis["by_month"].items():
        if v.get("n", 0) >= min_n and v["avg_pnl"] < -0.05:
            opps.append({
                "type": "month_exclude",
                "key": f"{k}月",
                "stat": v,
                "reason": f"{k}月のエントリーは平均{v['avg_pnl']:.2f}%（{v['n']}回）",
            })

    # フラグチェック
    for k, v in analysis["flags"].items():
        if v.get("n", 0) >= min_n and v["avg_pnl"] < -0.05:
            opps.append({
                "type": "flag_exclude",
                "key": k,
                "stat": v,
                "reason": f"{k}=True のエントリーは平均{v['avg_pnl']:.2f}%（{v['n']}回）",
            })

    return opps
