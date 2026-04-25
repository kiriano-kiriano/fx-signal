"""
Phase 1.5 最適化結果ダッシュボード生成
- ロバストTop20
- 戦略×ペアごとのベスト
- パラメータ感度ヒートマップ（戦略別）
- IS vs OOS 散布図
"""
import json
from collections import defaultdict
import datetime as dt


def render_optimization(payload: dict) -> str:
    meta = payload.get("meta", {})
    src = meta.get("data_source", "unknown")
    src_badge = "実データ (yfinance)" if src == "real" else "⚠️ 合成データ"

    top_robust = payload.get("top_robust", [])
    best_per_combo = payload.get("best_per_combo", [])
    all_results = payload.get("all_results", [])

    # --- ロバストTop表 ---
    top_html = ""
    for i, r in enumerate(top_robust[:20]):
        is_m = r["is_metrics"]
        oos_m = r["oos_metrics"]
        rank_class = "winner" if i < 3 else ""
        top_html += f"""
        <tr class="{rank_class}">
          <td>{i+1}</td>
          <td>{r['strategy']}</td>
          <td>{r['pair']}</td>
          <td class="num">{r['min_sharpe']:.2f}</td>
          <td class="num">{is_m['sharpe']:.2f}</td>
          <td class="num">{oos_m['sharpe']:.2f}</td>
          <td class="num">{is_m['cagr_pct']:.1f}%</td>
          <td class="num">{oos_m['cagr_pct']:.1f}%</td>
          <td class="num">{is_m['max_dd_pct']:.1f}%</td>
          <td class="num">{oos_m['max_dd_pct']:.1f}%</td>
          <td class="num">{is_m['win_rate_pct']:.0f}%/{oos_m['win_rate_pct']:.0f}%</td>
          <td class="num">{is_m['trades']}/{oos_m['trades']}</td>
          <td class="params">{r['params_str']}</td>
        </tr>
        """

    # --- 戦略×ペアのベスト表 ---
    best_html = ""
    for r in sorted(best_per_combo, key=lambda x: (x["strategy"], x["pair"])):
        is_m = r["is_metrics"]
        oos_m = r["oos_metrics"]
        positive_class = "positive" if r["both_positive"] else "negative"
        best_html += f"""
        <tr class="{positive_class}">
          <td>{r['strategy']}</td>
          <td>{r['pair']}</td>
          <td class="num">{r['min_sharpe']:.2f}</td>
          <td class="num">{is_m['sharpe']:.2f} / {oos_m['sharpe']:.2f}</td>
          <td class="num">{is_m['cagr_pct']:.1f}% / {oos_m['cagr_pct']:.1f}%</td>
          <td class="num">{is_m['max_dd_pct']:.1f}% / {oos_m['max_dd_pct']:.1f}%</td>
          <td class="params">{r['params_str']}</td>
        </tr>
        """

    # --- IS vs OOS 散布図用データ ---
    scatter_data = defaultdict(list)
    for r in all_results:
        is_sr = r["is_metrics"]["sharpe"]
        oos_sr = r["oos_metrics"]["sharpe"]
        if abs(is_sr) > 5 or abs(oos_sr) > 5:
            continue  # 異常値除外
        scatter_data[r["strategy"]].append({
            "x": round(is_sr, 3),
            "y": round(oos_sr, 3),
            "pair": r["pair"],
            "params": r["params_str"],
        })

    scatter_json = json.dumps(dict(scatter_data), ensure_ascii=False)

    today = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>Phase 1.5: パラメータ感度分析 + IS/OOS バリデーション</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Hiragino Sans", "Yu Gothic", sans-serif;
         margin: 0; padding: 24px; background: #0e1117; color: #e6edf3; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 32px 0 12px; color: #58a6ff;
       border-bottom: 1px solid #30363d; padding-bottom: 6px; }}
  .meta {{ color: #7d8590; font-size: 12px; margin-bottom: 12px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 11px; background: {'#1f6feb' if src == 'real' else '#9e6a03'};
           color: white; margin-left: 8px; }}
  .note {{ background: #1c2128; border-left: 3px solid #f0883e; padding: 12px 16px;
          margin: 16px 0; font-size: 13px; color: #c9d1d9; line-height: 1.6; }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
             gap: 12px; margin-bottom: 16px; }}
  .stat {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          padding: 12px 16px; }}
  .stat span {{ display: block; color: #7d8590; font-size: 11px; }}
  .stat b {{ font-size: 22px; color: #58a6ff; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px;
          background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          overflow: hidden; margin-bottom: 16px; }}
  th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #30363d; }}
  th {{ background: #1c2128; color: #7d8590; font-weight: 500; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.params {{ font-family: ui-monospace, "SF Mono", monospace; font-size: 11px;
              color: #a371f7; }}
  tr.winner td {{ background: linear-gradient(90deg, transparent, #0e3a1c, transparent); }}
  tr.positive td {{ color: #7ee787; }}
  tr.negative td {{ color: #f85149; }}
  .charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 16px; }}
  .chart-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                padding: 16px; }}
  canvas {{ max-height: 320px; }}
  h3 {{ margin: 0 0 8px; color: #f0883e; font-size: 14px; }}
  code {{ background: #1c2128; padding: 1px 6px; border-radius: 3px; font-size: 11px; }}
</style>
</head>
<body>

<h1>Phase 1.5: パラメータ感度分析 + IS/OOS バリデーション
   <span class="badge">{src_badge}</span></h1>
<div class="meta">
  生成日時: {today} ／
  IS期間: {meta.get("is_period", "")} ／ OOS期間: {meta.get("oos_period", "")}
</div>

<div class="summary">
  <div class="stat"><span>総検証数</span><b>{meta.get("total_combinations", 0)}</b></div>
  <div class="stat"><span>両期間プラスのロバスト候補</span><b>{meta.get("robust_count", 0)}</b></div>
  <div class="stat"><span>ロバスト率</span>
    <b>{(meta.get("robust_count", 0) / meta.get("total_combinations", 1) * 100):.1f}%</b></div>
</div>

<div class="note">
  <b>読み解き方：</b><br>
  ・ <b>min(IS_SR, OOS_SR)</b> が最重要：両期間で安定して効くものが本物のエッジ<br>
  ・ <b>IS_SR が高いのに OOS_SR が低い</b> ＝ 過剰最適化（過去にハマっただけ）<br>
  ・ <b>パラメータ違いの結果が広い範囲でプラス</b> ＝ ロバストな戦略<br>
  ・ <b>OOS期間（2021-2026）はコロナ後の高ボラ期</b>を含む。ここで生き残る戦略は実戦力あり<br>
  ・ <b>下の散布図</b>で右上に点が固まっていれば、その戦略は安定的にエッジがある証拠
</div>

<h2>🏆 ロバスト Top 20（両期間プラス & min(IS_SR, OOS_SR) 降順）</h2>
<table>
  <thead>
    <tr>
      <th>#</th><th>戦略</th><th>ペア</th>
      <th>min Sharpe</th><th>IS Sharpe</th><th>OOS Sharpe</th>
      <th>IS CAGR</th><th>OOS CAGR</th>
      <th>IS DD</th><th>OOS DD</th>
      <th>勝率 IS/OOS</th><th>取引 IS/OOS</th>
      <th>パラメータ</th>
    </tr>
  </thead>
  <tbody>{top_html}</tbody>
</table>

<h2>📊 戦略×ペア別 ベストパラメータ</h2>
<table>
  <thead>
    <tr>
      <th>戦略</th><th>ペア</th>
      <th>min Sharpe</th><th>Sharpe IS/OOS</th>
      <th>CAGR IS/OOS</th><th>最大DD IS/OOS</th>
      <th>パラメータ</th>
    </tr>
  </thead>
  <tbody>{best_html}</tbody>
</table>

<h2>🎯 IS vs OOS 散布図（戦略別、点1つ＝1パラメータ組）</h2>
<div class="note">
  右上（両軸プラス）の塊が大きいほど、その戦略はパラメータに対してロバスト。<br>
  対角線（y=x）から大きく外れる点は、IS と OOS で性能が乖離 → 過剰最適化のリスク。
</div>
<div class="charts" id="scatters"></div>

<h2>📝 次のステップ</h2>
<div class="note">
  <b>結果の解釈順序：</b><br>
  1. 上のロバストTop20で、<b>同じ戦略 × 同じペア</b>が複数回登場している組み合わせを探す（パラメータが違っても効く＝本物のエッジ）<br>
  2. 戦略×ペア別ベストで、<b>OOS_SR が IS_SR の70%以上を保っている</b>ものをピックアップ<br>
  3. 散布図で<b>右上に密集</b>しているかを目視確認（過剰最適化チェック）<br>
  4. これらを満たす1〜2組み合わせが「Phase β（深掘り）」候補<br>
  <br>
  どの組み合わせを Phase β で深掘りするかを決めれば、追加フィルタ（時間帯、レジーム判定、ニュース回避）と最終的なシグナル定義の磨き込みに進めます。
</div>

<script>
const scatterData = {scatter_json};
const colors = {{"USDJPY": "#58a6ff", "EURJPY": "#f0883e", "GBPJPY": "#a371f7"}};

const container = document.getElementById("scatters");
Object.entries(scatterData).forEach(([s, points]) => {{
  const card = document.createElement("div");
  card.className = "chart-card";
  card.innerHTML = `<h3>${{s}} — IS Sharpe vs OOS Sharpe</h3><canvas id="sc_${{s}}"></canvas>`;
  container.appendChild(card);

  const datasets = ["USDJPY", "EURJPY", "GBPJPY"].map(p => ({{
    label: p,
    data: points.filter(pt => pt.pair === p),
    backgroundColor: colors[p] + "AA",
    borderColor: colors[p],
    pointRadius: 4,
    pointHoverRadius: 6,
  }}));

  new Chart(document.getElementById("sc_" + s), {{
    type: "scatter",
    data: {{ datasets }},
    options: {{
      animation: false,
      scales: {{
        x: {{ title: {{ display: true, text: "IS Sharpe (2011-2020)", color: "#7d8590" }},
              ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }} }},
        y: {{ title: {{ display: true, text: "OOS Sharpe (2021-now)", color: "#7d8590" }},
              ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }} }}
      }},
      plugins: {{
        legend: {{ labels: {{ color: "#e6edf3" }} }},
        tooltip: {{ callbacks: {{
          label: (ctx) => {{
            const d = ctx.raw;
            return `${{d.pair}} (IS=${{d.x.toFixed(2)}}, OOS=${{d.y.toFixed(2)}}) ${{d.params}}`;
          }}
        }} }}
      }}
    }}
  }});
}});
</script>

</body>
</html>"""
