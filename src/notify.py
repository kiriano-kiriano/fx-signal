"""
Phase 2: 通知モジュール
LINE Notify互換 / Discord Webhook対応。
環境変数 LINE_NOTIFY_TOKEN / DISCORD_WEBHOOK_URL を読み取る。
※ LINE Notifyは2025年3月でサービス終了。代替として LINE Messaging APIへの直接送信や
   Discord, Slack, Telegram等を利用する想定。本コードはDiscordを主、LINE互換を副として実装。
"""
import os
import json
import urllib.request
import urllib.error


def format_signal_message(today_str: str, signals: list, open_positions: list,
                           yesterday_results: list) -> str:
    """通知用メッセージを整形（プレーンテキスト）"""
    lines = [f"📊 FX Daily Signal — {today_str}"]

    if signals:
        lines.append("")
        lines.append(f"🔥 新規シグナル: {len(signals)}件")
        for s in signals:
            dir_label = "🟢買い" if s["direction"] == 1 else "🔴売り"
            lines.append(
                f"  {s['pair']} {dir_label} | "
                f"目安 {s['entry_price_est']:.3f} / "
                f"SL {s['stop_price']:.3f} / "
                f"TP {s['target_price']:.3f if s['target_price'] else '—'}"
            )

    if open_positions:
        lines.append("")
        lines.append(f"📌 保有中: {len(open_positions)}件")
        for p in open_positions:
            pnl = p["unrealized_pnl_pct"] * 100
            sign = "+" if pnl >= 0 else ""
            dir_label = "買い" if p["direction"] == 1 else "売り"
            lines.append(
                f"  {p.get('pair', '?')} {dir_label} | "
                f"含み {sign}{pnl:.2f}% | "
                f"{p['hold_days']}日保有"
            )

    if yesterday_results:
        lines.append("")
        lines.append("✅ 昨日の決済:")
        for r in yesterday_results:
            pnl = r["pnl_pct"] * 100
            sign = "+" if pnl >= 0 else ""
            reason = {"stop": "損切り", "target": "利確", "signal_exit": "反転"}.get(r["reason"], r["reason"])
            lines.append(f"  {r.get('pair', '?')} {sign}{pnl:.2f}% ({reason})")

    if not signals and not open_positions and not yesterday_results:
        lines.append("")
        lines.append("💤 シグナルなし。今日はアクション不要。")

    return "\n".join(lines)


def send_discord(webhook_url: str, message: str, title: str = None) -> bool:
    """Discord Webhook送信"""
    if not webhook_url:
        return False
    payload = {"content": message}
    if title:
        payload["embeds"] = [{
            "title": title,
            "description": message,
            "color": 0x58a6ff,
        }]
        del payload["content"]
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 204)
    except urllib.error.HTTPError as e:
        print(f"Discord notify failed: {e.code} {e.reason}")
        return False
    except Exception as e:
        print(f"Discord notify error: {e}")
        return False


def send_line_notify(token: str, message: str) -> bool:
    """LINE Notify互換（公式は終了。互換APIを使う場合のテンプレート）"""
    if not token:
        return False
    url = "https://notify-api.line.me/api/notify"
    data = urllib.parse.urlencode({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"LINE notify error: {e}")
        return False


def notify_all(message: str, only_if_action: bool = True,
               has_action: bool = False) -> dict:
    """設定済みの全通知先に送信。only_if_action=Trueなら、アクション必要時のみ送る"""
    if only_if_action and not has_action:
        return {"skipped": True, "reason": "no action"}

    results = {}
    discord_url = os.environ.get("DISCORD_WEBHOOK_URL")
    line_token = os.environ.get("LINE_NOTIFY_TOKEN")

    if discord_url:
        results["discord"] = send_discord(discord_url, message, title="FX Signal Update")
    if line_token:
        results["line"] = send_line_notify(line_token, message)

    if not results:
        results["skipped"] = True
        results["reason"] = "no webhook configured"
    return results
