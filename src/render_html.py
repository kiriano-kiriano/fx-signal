"""
バックテスト比較ダッシュボード（静的HTML）
Chart.jsをCDNで読み込んでエクイティカーブを描画。
"""
import json
import datetime as dt


def render(results: dict) -> str:
    meta = results.get("meta", {})
    by_strat = results.get("by_strategy", {})
    by_ps = results.get("by_pair_strategy", {})
    src = meta.get("data_source", "unknown")
    src_badge = "実データ (yfinance)" if src == "real" else "⚠️ 合成データ (yfinanceブロック中)"

    strat_names = sorted(by_strat.keys())
    pairs = sorted(set(v["pair"] for v in by_ps.values()))

    # 戦略サマリーカード
    cards_html = ""
    for s in strat_names:
        d = by_strat[s]
        cards_html += f'''
        <div class="card">
          <h3>{s}</h3>
          <div class="metric"><span>平均CAGR</span><b>{d["avg_cagr_pct"]:.1f}%</b></div>
          <div class="metric"><span>平均シャープ</span><b>{d["avg_sharpe"]:.2f}</b></div>
          <div class="metric"><span>平均最大DD</span><b>{d["avg_max_dd_pct"]:.1f}%</b></div>
          <div class="metric"><span>平均勝率</span><b>{d["avg_win_rate_pct"]:.1f}%</b></div>
          <div class="metric"><span>合計取引数</span><b>{d["total_trades"]}</b></div>
        </div>
        '''

    # ペア×戦略の詳細テーブル
    rows_html = ""
    for s in strat_names:
        for p in pairs:
            key = f"{s}__{p}"
            r = by_ps.get(key)
            if not r:
                continue
            m = r["metrics"]
            rows_html += f'''
            <tr>
              <td>{s}</td>
              <td>{p}</td>
              <td class="num">{m["trades"]}</td>
              <td class="num">{m["total_return_pct"]:.1f}%</td>
              <td class="num">{m["cagr_pct"]:.1f}%</td>
              <td class="num">{m["sharpe"]:.2f}</td>
              <td class="num">{m["max_dd_pct"]:.1f}%</td>
              <td class="num">{m["win_rate_pct"]:.1f}%</td>
              <td class="num">{m["expectancy_pct"]:.2f}%</td>
            </tr>
            '''

    # エクイティカーブ用データ（戦略別、ペアでグループ化）
    chart_data = {}
    for s in strat_names:
        chart_data[s] = {}
        for p in pairs:
            key = f"{s}__{p}"
            r = by_ps.get(key)
            if r:
                chart_data[s][p] = r["equity_curve"]

    chart_data_json = json.dumps(chart_data, ensure_ascii=False)
    pairs_json = json.dumps(pairs)
    strats_json = json.dumps(strat_names)

    today = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>FX 戦略バックテスト比較ダッシュボード</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Hiragino Sans", "ヒラギノ角ゴ ProN", "Yu Gothic", sans-serif;
         margin: 0; padding: 24px; background: #0e1117; color: #e6edf3; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 32px 0 12px; color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 6px; }}
  h3 {{ font-size: 15px; margin: 0 0 12px; color: #f0883e; }}
  .meta {{ color: #7d8590; font-size: 12px; margin-bottom: 12px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
           background: {'#1f6feb' if src == 'real' else '#9e6a03'}; color: white; margin-left: 8px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
  .metric {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }}
  .metric span {{ color: #7d8590; }}
  .metric b {{ color: #e6edf3; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: #161b22;
          border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #30363d; }}
  th {{ background: #1c2128; color: #7d8590; font-weight: 500; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; }}
  .chart-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
  canvas {{ max-height: 280px; }}
  .note {{ background: #1c2128; border-left: 3px solid #f0883e; padding: 12px 16px;
          margin: 16px 0; font-size: 13px; color: #c9d1d9; }}
  .winner {{ background: linear-gradient(90deg, #1c2128, #0e3a1c); }}
</style>
</head>
<body>

<h1>FX 戦略バックテスト比較ダッシュボード <span class="badge">{src_badge}</span></h1>
<div class="meta">生成日時: {today} ／ 初期資金: ¥{meta.get("initial_capital", 0):,} ／
  1トレードリスク: {meta.get("risk_per_trade", 0)*100:.1f}% ／
  最大レバ: {meta.get("max_leverage", 0):.0f}倍</div>

{f'<div class="note">⚠️ サンドボックス環境でyfinanceがブロックされたため、合成データで動作確認しています。実運用ではご自身のMacで <code>python3 src/run_backtest.py</code> を実行すると、yfinance経由で実データに切り替わり、リアルな結果が得られます。</div>' if src != "real" else ""}

<h2>戦略サマリー（3ペア平均）</h2>
<div class="cards">{cards_html}</div>

<h2>戦略 × 通貨ペア 詳細</h2>
<table>
  <thead>
    <tr>
      <th>戦略</th><th>ペア</th><th>取引数</th><th>総リターン</th><th>CAGR</th>
      <th>シャープ</th><th>最大DD</th><th>勝率</th><th>期待値/トレード</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>

<h2>エクイティカーブ</h2>
<div class="charts" id="charts"></div>

<h2>戦略選択ガイド（読み解き方）</h2>
<div class="note">
  <b>選び方の指針：</b><br>
  ・<b>シャープレシオ</b>が高い ＝ ボラあたりのリターン効率が良い（最重要指標）<br>
  ・<b>最大DD</b>が浅い ＝ 心理的に続けやすい（30%超えると個人運用は厳しい）<br>
  ・<b>取引数</b>が少なすぎる ＝ サンプル不足で運の影響大（年5回以下は要警戒）<br>
  ・<b>勝率と期待値の組み合わせ</b>：勝率30%でもペイオフ高ければ◎、勝率60%でもペイオフ低いと△<br>
  ・<b>ペア間の安定性</b>：3ペアとも同方向の結果なら戦略がロバスト。1ペアだけ突出してたら過剰最適化の可能性
</div>

<script>
const chartData = {chart_data_json};
const pairs = {pairs_json};
const strats = {strats_json};
const colors = {{"USDJPY": "#58a6ff", "EURJPY": "#f0883e", "GBPJPY": "#a371f7"}};

const container = document.getElementById("charts");
strats.forEach(s => {{
  const card = document.createElement("div");
  card.className = "chart-card";
  card.innerHTML = `<h3>${{s}}</h3><canvas id="c_${{s}}"></canvas>`;
  container.appendChild(card);

  const datasets = pairs.map(p => {{
    const data = (chartData[s] || {{}})[p] || [];
    return {{
      label: p,
      data: data.map(x => ({{ x: x.date, y: x.equity }})),
      borderColor: colors[p] || "#888",
      backgroundColor: "transparent",
      tension: 0.1,
      pointRadius: 0,
      borderWidth: 1.5,
    }};
  }});
  new Chart(document.getElementById("c_" + s), {{
    type: "line",
    data: {{ datasets }},
    options: {{
      animation: false,
      scales: {{
        x: {{ type: "category", ticks: {{ color: "#7d8590", maxTicksLimit: 8 }}, grid: {{ color: "#30363d" }} }},
        y: {{ ticks: {{ color: "#7d8590", callback: v => "¥" + Math.round(v/1000) + "k" }}, grid: {{ color: "#30363d" }} }}
      }},
      plugins: {{ legend: {{ labels: {{ color: "#e6edf3" }} }} }}
    }}
  }});
}});
</script>

</body>
</html>"""
