"""
Phase 2: 日次シグナルダッシュボード生成
朝開いて今日のトレード判断ができるページ。
"""
import json
import datetime as dt
import math
from gauges import (
    tachometer, linear_gauge, position_lamps, signal_lamp,
    progress_bar, equity_sparkline,
)


def _signal_card(state: dict, account_balance: float, risk_pct: float) -> str:
    """1ペア分のシグナルカード"""
    pair = state["pair"]
    last_close = state["last_close"]

    # 状態判定
    if state["open_position"]:
        op = state["open_position"]
        kind = "open"
    elif state["today_signal"]:
        sig = state["today_signal"]
        kind = "new"
    else:
        kind = "wait"

    if kind == "open":
        op = state["open_position"]
        direction = op["direction"]
        tp_str_op = f"{op['target_price']:.3f}" if op['target_price'] else "—"
        dir_label = "買い保有中" if direction == 1 else "売り保有中"
        dir_color = "#3fb950" if direction == 1 else "#f85149"
        pnl = op["unrealized_pnl_pct"] * 100
        pnl_color = "#3fb950" if pnl >= 0 else "#f85149"
        progress_html = ""
        if op["target_price"] and op["stop_price"]:
            progress_html = progress_bar(
                op["current_price"], op["entry_price"],
                op["target_price"], op["stop_price"],
                direction=direction,
            )
        body = f"""
        <div class="signal-status open" style="border-color: {dir_color};">
          {signal_lamp(True, direction)}
          <div class="status-label" style="color: {dir_color};">{dir_label}</div>
        </div>
        <div class="metric"><span>含み損益</span><b style="color:{pnl_color};">{pnl:+.2f}%</b></div>
        <div class="metric"><span>エントリー価格</span><b>{op['entry_price']:.3f}</b></div>
        <div class="metric"><span>現在価格</span><b>{op['current_price']:.3f}</b></div>
        <div class="metric"><span>損切り (SL)</span><b style="color:#f85149;">{op['stop_price']:.3f}</b></div>
        <div class="metric"><span>利確 (TP)</span><b style="color:#3fb950;">{tp_str_op}</b></div>
        <div class="metric"><span>保有日数</span><b>{op['hold_days']}日</b></div>
        {progress_html}
        <div class="action-box">
          <strong>📌 今日のアクション</strong>: 保有継続。SL/TPに到達したら自動決済される。
          10日経過で手動撤退検討。
        </div>
        """
    elif kind == "new":
        sig = state["today_signal"]
        direction = sig["direction"]
        tp_str_sig = f"{sig['target_price']:.3f}" if sig['target_price'] else "—"
        tp_str_ifdoco = f"{sig['target_price']:.3f}" if sig['target_price'] else "—"
        td_str_sig = f"{sig['target_distance_pct']:.2f}%" if sig['target_distance_pct'] else "—"
        dir_label = sig["direction_label"]
        dir_color = "#3fb950" if direction == 1 else "#f85149"
        # 推奨ロット計算: account_balance × risk_pct / stop_dist (in money)
        if sig["stop_distance_pct"]:
            risk_amount = account_balance * risk_pct
            stop_dist_price = abs(last_close - sig["stop_price"])
            # 1lot = 100,000通貨。JPYクロスなら 1lot * stop_dist_price = JPY損失
            # 推奨ロット = risk_amount / (stop_dist_price * 100,000)
            recommended_lots = risk_amount / (stop_dist_price * 100_000) if stop_dist_price > 0 else 0
        else:
            recommended_lots = 0

        ifdoco_html = f"""
          <div class="ifdoco-block">
            <div class="ifdoco-title">📋 IFDOCO 設定値（コピペ用）</div>
            <pre>新規 {dir_label}: 成行 {recommended_lots:.2f}lot
利確指値:    {tp_str_ifdoco}
損切り逆指値: {sig['stop_price']:.3f}</pre>
          </div>
        """ if sig["stop_price"] else ""

        body = f"""
        <div class="signal-status new" style="border-color: {dir_color}; box-shadow: 0 0 20px {dir_color}55;">
          {signal_lamp(True, direction)}
          <div class="status-label blink" style="color: {dir_color};">🔥 {dir_label}シグナル発火</div>
        </div>
        <div class="metric"><span>エントリー目安</span><b>{sig['entry_price_est']:.3f}</b><small>（東京寄付き成行）</small></div>
        <div class="metric"><span>損切り (SL)</span><b style="color:#f85149;">{sig['stop_price']:.3f}</b><small>{sig['stop_distance_pct']:.2f}%</small></div>
        <div class="metric"><span>利確 (TP)</span><b style="color:#3fb950;">{tp_str_sig}</b><small>{td_str_sig}</small></div>
        <div class="metric"><span>推奨レバ</span><b>{sig['estimated_leverage']:.1f}倍</b></div>
        <div class="metric highlight"><span>推奨ロット ({risk_pct*100:.0f}%リスク)</span><b>{recommended_lots:.2f}lot</b></div>
        {ifdoco_html}
        """
    else:  # wait
        body = f"""
        <div class="signal-status wait">
          {signal_lamp(False, 0)}
          <div class="status-label" style="color: #7d8590;">待機中</div>
        </div>
        <div class="metric"><span>現在価格</span><b>{last_close:.3f}</b></div>
        <div class="metric muted"><span>シグナル待ち</span><b>—</b></div>
        <div class="action-box muted">
          BB下限/上限へのタッチを待機中。アクション不要。
        </div>
        """

    # 昨日の結果（あれば）
    yest_html = ""
    if state["yesterday_result"]:
        yr = state["yesterday_result"]
        pnl = yr["pnl_pct"] * 100
        color = "#3fb950" if pnl > 0 else "#f85149"
        reason_label = {"stop": "損切り", "target": "利確", "signal_exit": "反転撤退"}.get(yr["reason"], yr["reason"])
        yest_html = f"""
        <div class="yesterday">
          昨日の結果: <span style="color:{color}; font-weight:600;">{pnl:+.2f}%</span>
          ({reason_label}, {yr['hold_days']}日保有)
        </div>
        """

    metrics = state["metrics"]
    spark = equity_sparkline(state["equity_curve"][-24:] if len(state["equity_curve"]) > 24 else state["equity_curve"])

    return f"""
    <div class="signal-card {kind}">
      <div class="card-header">
        <h3>{pair}</h3>
        <div class="trades-stat">過去 {metrics['trades']}トレード, 勝率 {metrics['win_rate_pct']:.0f}%</div>
      </div>
      {body}
      {yest_html}
      <div class="sparkline-block">
        <div class="sparkline-label">直近2年エクイティ</div>
        {spark}
      </div>
    </div>
    """


def render_daily_dashboard(payload: dict) -> str:
    meta = payload.get("meta", {})
    src = meta.get("data_source", "unknown")
    src_badge = "実データ" if src == "real" else "⚠️ 合成データ"
    pairs_state = payload.get("pairs", {})
    risk_pct = meta.get("risk_per_trade", 0.02)
    account_balance = meta.get("account_balance", 100_000)
    leverage = meta.get("max_leverage", 20)
    today_str = dt.datetime.now().strftime("%Y年%m月%d日 %H:%M")
    generated_iso = meta.get("generated_at", dt.datetime.now().isoformat())

    # 全ペアの集計
    total_equity = sum(s["current_equity"] for s in pairs_state.values())
    total_trades = sum(s["metrics"]["trades"] for s in pairs_state.values())
    avg_winrate = sum(s["metrics"]["win_rate_pct"] for s in pairs_state.values()) / max(len(pairs_state), 1)
    avg_dd = min(s["metrics"]["max_dd_pct"] for s in pairs_state.values()) if pairs_state else 0
    open_count = sum(1 for s in pairs_state.values() if s["open_position"])
    new_signal_count = sum(1 for s in pairs_state.values() if s["today_signal"])

    # 起動率（口座残高 / 初期資金）
    starting_capital = 100_000
    growth_pct = (total_equity / (starting_capital * len(pairs_state)) - 1) * 100 if pairs_state else 0

    # メーター類
    risk_used_pct = open_count / 3 * 100  # 同時保有3ペアまでが上限
    risk_meter = tachometer(
        risk_used_pct, max_value=100,
        label="ポジション使用率", unit="%",
        zones=[(0, 0.34, "#3fb950"), (0.34, 0.67, "#d29922"), (0.67, 1.0, "#f85149")]
    )
    win_meter = tachometer(
        avg_winrate, max_value=100,
        label="平均勝率", unit="%",
        zones=[(0, 0.4, "#f85149"), (0.4, 0.55, "#d29922"), (0.55, 1.0, "#3fb950")]
    )

    dd_meter = tachometer(
        abs(avg_dd), max_value=30,
        label="最大DD (バックテスト)", unit="%",
        zones=[(0, 0.5, "#3fb950"), (0.5, 0.8, "#d29922"), (0.8, 1.0, "#f85149")]
    )

    positions_dict = {p: s["open_position"] for p, s in pairs_state.items()}
    pos_lamp_html = position_lamps(positions_dict, list(pairs_state.keys()))

    # シグナルカード
    cards_html = "\n".join(
        _signal_card(state, account_balance, risk_pct)
        for state in pairs_state.values()
    )

    # 直近トレード履歴（全ペア合算、新しい順）
    all_trades = []
    for p, s in pairs_state.items():
        for t in s["recent_trades"]:
            t2 = dict(t)
            t2["pair"] = p
            all_trades.append(t2)
    all_trades.sort(key=lambda t: t["exit_date"], reverse=True)
    all_trades = all_trades[:15]
    trades_html = ""
    for t in all_trades:
        pnl = t["pnl_pct"] * 100
        color = "positive" if pnl > 0 else "negative"
        reason_label = {"stop": "損切り", "target": "利確", "signal_exit": "反転"}.get(t["reason"], t["reason"])
        trades_html += f"""
        <tr class="{color}">
          <td>{t['exit_date'][:10]}</td>
          <td>{t['pair']}</td>
          <td>{'買' if t['direction']==1 else '売'}</td>
          <td class="num">{t['entry_price']:.3f}</td>
          <td class="num">{t['exit_price']:.3f}</td>
          <td class="num"><b>{pnl:+.2f}%</b></td>
          <td>{reason_label}</td>
          <td>{t['hold_days']}日</td>
        </tr>
        """

    # ステータス表示
    status_msg = ""
    status_class = ""
    if new_signal_count > 0:
        status_msg = f"🔥 {new_signal_count}件の新規シグナル発火中。アクション必要"
        status_class = "alert"
    elif open_count > 0:
        status_msg = f"📊 {open_count}件保有中。決済を待機"
        status_class = "active"
    else:
        status_msg = "💤 待機中。シグナルなし"
        status_class = "idle"

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FX Daily Signal — {today_str}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Hiragino Sans", "Yu Gothic", sans-serif;
         margin: 0; padding: 16px; background: #0d1117; color: #e6edf3;
         line-height: 1.4; }}
  .topbar {{ display: flex; justify-content: space-between; align-items: center;
            padding-bottom: 16px; border-bottom: 1px solid #21262d; margin-bottom: 16px; }}
  .topbar h1 {{ font-size: 20px; margin: 0; }}
  .topbar small {{ color: #7d8590; font-size: 11px; margin-left: 8px; }}
  .nav {{ display: flex; gap: 16px; font-size: 13px; }}
  .nav a {{ color: #58a6ff; text-decoration: none; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 10px; background: {'#1f6feb' if src == 'real' else '#9e6a03'};
           color: white; margin-left: 8px; }}

  .status-banner {{ padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;
                   font-size: 16px; font-weight: 600; }}
  .status-banner.alert {{ background: linear-gradient(90deg, #2d1117, #3d1c12); border: 1px solid #f85149; color: #ffa198; }}
  .status-banner.active {{ background: linear-gradient(90deg, #1c2128, #1e3a2a); border: 1px solid #3fb950; color: #7ee787; }}
  .status-banner.idle {{ background: #161b22; border: 1px solid #30363d; color: #7d8590; }}

  .gauges {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px; margin-bottom: 24px; }}
  .gauge-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px;
                padding: 12px; text-align: center; }}
  .gauge-card.wide {{ grid-column: span 2; }}
  .gauge-svg {{ display: block; margin: 0 auto; max-width: 100%; }}

  .signals {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
             gap: 16px; margin-bottom: 24px; }}
  .signal-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px;
                 padding: 16px; }}
  .signal-card.new {{ border: 2px solid #f0883e; box-shadow: 0 0 24px #f0883e33; }}
  .signal-card.open {{ border-left: 4px solid #58a6ff; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: center;
                 margin-bottom: 12px; }}
  .card-header h3 {{ margin: 0; font-size: 18px; color: #58a6ff; }}
  .trades-stat {{ font-size: 11px; color: #7d8590; }}
  .signal-status {{ display: flex; align-items: center; gap: 12px;
                   padding: 12px; background: #0d1117; border-radius: 8px;
                   border: 2px solid #30363d; margin-bottom: 12px; }}
  .signal-status .gauge-svg {{ width: 60px; height: 60px; flex-shrink: 0; }}
  .status-label {{ font-size: 18px; font-weight: 700; }}
  .status-label.blink {{ animation: blink 1.5s ease-in-out infinite; }}
  @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
  .metric {{ display: flex; justify-content: space-between; padding: 4px 0;
            font-size: 13px; align-items: baseline; }}
  .metric span {{ color: #7d8590; }}
  .metric b {{ color: #e6edf3; font-weight: 600; }}
  .metric small {{ color: #7d8590; font-size: 10px; margin-left: 4px; }}
  .metric.highlight {{ background: linear-gradient(90deg, transparent, #1f6feb44, transparent);
                      padding: 6px 8px; border-radius: 4px; margin: 4px -4px; }}
  .metric.highlight b {{ color: #58a6ff; font-size: 16px; }}
  .ifdoco-block {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
                  padding: 8px 10px; margin-top: 12px; }}
  .ifdoco-title {{ font-size: 11px; color: #f0883e; margin-bottom: 4px; }}
  .ifdoco-block pre {{ margin: 0; color: #e6edf3; font-size: 12px;
                      font-family: ui-monospace, "SF Mono", monospace;
                      line-height: 1.6; }}
  .yesterday {{ font-size: 12px; color: #7d8590; padding-top: 12px;
               border-top: 1px solid #30363d; margin-top: 12px; }}
  .action-box {{ font-size: 12px; padding: 8px 10px;
                background: #1c2128; border-radius: 6px; margin-top: 8px;
                border-left: 3px solid #58a6ff; }}
  .action-box.muted {{ border-left-color: #30363d; color: #7d8590; }}
  .sparkline-block {{ margin-top: 12px; }}
  .sparkline-label {{ font-size: 10px; color: #7d8590; margin-bottom: 4px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 12px;
          background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          overflow: hidden; }}
  th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #30363d; }}
  th {{ background: #1c2128; color: #7d8590; font-weight: 500; font-size: 11px; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.positive td b {{ color: #7ee787; }}
  tr.negative td b {{ color: #ff7b72; }}

  h2 {{ font-size: 16px; margin: 24px 0 12px; color: #58a6ff;
       border-bottom: 1px solid #30363d; padding-bottom: 6px; }}

  .pos-lamp-card {{ display: flex; align-items: center; justify-content: center; min-height: 100px; }}
  @media (max-width: 600px) {{
    .gauge-card.wide {{ grid-column: span 1; }}
  }}

  .freshness-badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px;
                     background: #161b22; border: 1px solid #30363d; margin-left: 12px;
                     font-size: 11px; vertical-align: middle; }}
  .freshness-dot {{ font-size: 14px; margin-right: 4px; }}
  .freshness-dot.fresh {{ color: #3fb950; }}
  .freshness-dot.warn {{ color: #d29922; }}
  .freshness-dot.stale {{ color: #f85149; animation: pulse 1.5s ease-in-out infinite; }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
  .freshness-relative {{ color: #7d8590; margin-left: 6px; }}

  .rules-panel {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px;
                 padding: 12px 18px; margin-bottom: 20px; border-left: 4px solid #f0883e; }}
  .rules-panel summary {{ font-size: 14px; font-weight: 600; color: #f0883e; cursor: pointer;
                         user-select: none; padding: 4px 0; }}
  .rules-panel summary:hover {{ color: #ffa657; }}
  .rules-panel ul {{ margin: 8px 0 4px; padding-left: 20px; }}
  .rules-panel li {{ font-size: 12px; color: #c9d1d9; padding: 3px 0; line-height: 1.5; }}
  .rules-panel li b {{ color: #e6edf3; }}
</style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>📊 FX Daily Signal <span class="badge">{src_badge}</span></h1>
    <small>{today_str} 更新</small>
    <span class="freshness-badge" data-updated="{generated_iso}">
      <span class="freshness-dot" id="freshDot">●</span>
      <span id="freshLabel">最新</span>
      <small class="freshness-relative" id="freshRelative">数分前</small>
    </span>
  </div>
  <nav class="nav">
    <a href="workflow.html">▶ 1日の運用イメージ</a>
    <a href="phase_beta.html">📈 戦略詳細</a>
  </nav>
</div>

<div class="status-banner {status_class}">{status_msg}</div>

<details class="rules-panel" open>
  <summary>🚨 運用中の絶対ルール（必ず守る）</summary>
  <ul>
    <li>✅ <b>シグナル通り淡々と発注する</b> — 裁量介入は期待値を下げるだけ</li>
    <li>✅ <b>SL/TPは絶対に動かさない</b> — 動かしたくなる衝動が中級者を破滅させる</li>
    <li>✅ <b>5連敗したら一時停止</b> — 新規ポジ禁止、ルール再検証</li>
    <li>✅ <b>ロットは推奨値を死守</b> — 「今日だけ大きめ」は禁句</li>
    <li>❌ <b>シグナル無しの日に自分で売買しない</b> — 待機も戦略のうち</li>
    <li>❌ <b>含み損で「もう少し待てば戻る」は厳禁</b> — SLヒットで自動決済が正解</li>
  </ul>
</details>

<div class="gauges">
  <div class="gauge-card">
    <div style="font-size:11px;color:#7d8590;margin-bottom:4px;">使用ポジ枠</div>
    {risk_meter}
  </div>
  <div class="gauge-card">
    <div style="font-size:11px;color:#7d8590;margin-bottom:4px;">過去パフォーマンス</div>
    {win_meter}
  </div>
  <div class="gauge-card">
    <div style="font-size:11px;color:#7d8590;margin-bottom:4px;">最大ドローダウン</div>
    {dd_meter}
  </div>
  <div class="gauge-card pos-lamp-card">
    <div>
      <div style="font-size:11px;color:#7d8590;margin-bottom:8px;text-align:left;">保有状態</div>
      {pos_lamp_html}
    </div>
  </div>
</div>

<h2>🎯 今日のシグナル</h2>
<div class="signals">
  {cards_html}
</div>

<h2>📜 直近のトレード履歴（全ペア合算）</h2>
<table>
  <thead>
    <tr>
      <th>決済日</th><th>ペア</th><th>方向</th>
      <th>エントリー</th><th>決済</th><th>P&L</th>
      <th>理由</th><th>保有</th>
    </tr>
  </thead>
  <tbody>{trades_html or '<tr><td colspan="8" style="text-align:center;color:#7d8590;padding:20px;">まだトレード履歴がありません</td></tr>'}</tbody>
</table>

<script>
(function () {{
  var el = document.querySelector('.freshness-badge');
  if (!el) return;
  var iso = el.getAttribute('data-updated');
  if (!iso) return;
  var updated = new Date(iso);
  var now = new Date();
  var minsAgo = Math.round((now - updated) / 60000);
  var hoursAgo = minsAgo / 60;

  var dot = document.getElementById('freshDot');
  var label = document.getElementById('freshLabel');
  var relative = document.getElementById('freshRelative');

  // 相対時間
  var rel;
  if (minsAgo < 60) rel = minsAgo + '分前';
  else if (hoursAgo < 48) rel = Math.round(hoursAgo) + '時間前';
  else rel = Math.round(hoursAgo / 24) + '日前';
  relative.textContent = rel;

  // 鮮度判定（NY close = 06-07 JST。それ以降の朝の更新で 25時間以内なら最新扱い）
  if (hoursAgo < 25) {{
    dot.className = 'freshness-dot fresh';
    label.textContent = '最新';
  }} else if (hoursAgo < 49) {{
    dot.className = 'freshness-dot warn';
    label.textContent = '少し古い';
  }} else {{
    dot.className = 'freshness-dot stale';
    label.textContent = '⚠️ 異常 — 更新確認を';
  }}
}})();
</script>
</body>
</html>"""
