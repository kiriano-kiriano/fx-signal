"""
Phase β: 統合ダッシュボード
- 3シナリオ比較（保守/標準/攻撃）
- ポートフォリオ合成エクイティ
- 10倍までの推定年数
- アノマリー分析（曜日・月・フラグ）
- ウォークフォワード年次推移
"""
import json
import datetime as dt


DOW_NAMES = ["月", "火", "水", "木", "金", "土", "日"]
MONTH_NAMES = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]


def render_phase_beta(payload: dict) -> str:
    meta = payload.get("meta", {})
    src = meta.get("data_source", "unknown")
    src_badge = "実データ (yfinance)" if src == "real" else "⚠️ 合成データ"
    params = meta.get("params", {})
    pairs = meta.get("pairs", [])
    scenarios = payload.get("scenarios", [])
    anomaly = payload.get("anomaly", {})
    wf = payload.get("walkforward", {})

    # シナリオサマリーカード
    sc_html = ""
    for sc in scenarios:
        port = sc["portfolio"]["metrics"]
        ten_x = sc["years_to_10x"]
        ten_x_str = f"{ten_x:.1f}年" if ten_x < 100 else "—"
        risk_class = {
            "conservative": "consv",
            "standard": "std",
            "aggressive": "aggr",
        }.get(sc["label"], "")
        sc_html += f"""
        <div class="card {risk_class}">
          <h3>{sc['name']}</h3>
          <div class="big">{port['cagr_pct']:.1f}%<small> CAGR (port)</small></div>
          <div class="metric"><span>Sharpe</span><b>{port['sharpe']:.2f}</b></div>
          <div class="metric"><span>最大DD</span><b>{port['max_dd_pct']:.1f}%</b></div>
          <div class="metric"><span>勝率</span><b>{port['win_rate_pct']:.1f}%</b></div>
          <div class="metric"><span>取引数</span><b>{port['trades']}</b></div>
          <div class="metric"><span>10倍までの目安</span><b class="hl">{ten_x_str}</b></div>
          <div class="metric"><span>総リターン</span><b>{port['total_return_pct']:.1f}%</b></div>
        </div>
        """

    # ペア×シナリオ表
    pair_table_html = ""
    for sc in scenarios:
        for pair in pairs:
            m = sc["by_pair"][pair]["metrics"]
            pair_table_html += f"""
            <tr>
              <td>{sc['name']}</td>
              <td>{pair}</td>
              <td class="num">{m['trades']}</td>
              <td class="num">{m['total_return_pct']:.1f}%</td>
              <td class="num">{m['cagr_pct']:.1f}%</td>
              <td class="num">{m['sharpe']:.2f}</td>
              <td class="num">{m['max_dd_pct']:.1f}%</td>
              <td class="num">{m['win_rate_pct']:.1f}%</td>
              <td class="num">{m['payoff']:.2f}</td>
            </tr>
            """

    # ポートフォリオエクイティカーブ用データ
    port_chart_data = {}
    for sc in scenarios:
        port_chart_data[sc["name"]] = sc["portfolio"]["equity_curve"]

    # アノマリー: 曜日別＋月別（ALL）
    if "ALL" in anomaly:
        all_a = anomaly["ALL"]["analysis"]
        dow_data = []
        for d in range(5):  # 月-金のみ
            v = all_a["by_dow"][d]
            dow_data.append({
                "name": DOW_NAMES[d],
                "n": v["n"],
                "win_rate": v["win_rate"],
                "avg_pnl": v["avg_pnl"],
                "total_pnl": v["total_pnl"],
            })
        month_data = []
        for m in range(1, 13):
            v = all_a["by_month"][m]
            month_data.append({
                "name": MONTH_NAMES[m-1],
                "n": v["n"],
                "win_rate": v["win_rate"],
                "avg_pnl": v["avg_pnl"],
                "total_pnl": v["total_pnl"],
            })
        flags = all_a["flags"]
    else:
        dow_data = []
        month_data = []
        flags = {}

    # アノマリーフラグ表
    flag_html = ""
    flag_labels = {
        "is_gotoubi": "ゴトー日 (5/10/15/20/25/末)",
        "is_not_gotoubi": "  〜以外",
        "is_month_first_3d": "月初3営業日",
        "is_month_last_5d": "月末5営業日",
        "is_quarter_end": "四半期末",
        "is_nfp_week": "米雇用統計週 (第1金曜±1日)",
        "is_not_nfp_week": "  〜以外",
    }
    for k, label in flag_labels.items():
        v = flags.get(k, {})
        if not v or v.get("n", 0) == 0:
            continue
        cls = "positive" if v["avg_pnl"] > 0 else "negative"
        flag_html += f"""
        <tr class="{cls}">
          <td>{label}</td>
          <td class="num">{v['n']}</td>
          <td class="num">{v['win_rate']:.1f}%</td>
          <td class="num">{v['avg_pnl']:+.2f}%</td>
          <td class="num">{v['total_pnl']:+.1f}%</td>
        </tr>
        """

    # フィルタ提案
    opps = anomaly.get("ALL", {}).get("opportunities", [])
    opps_html = ""
    if opps:
        for o in opps:
            opps_html += f"<li>{o['reason']} → 除外候補</li>"
    else:
        opps_html = "<li>明確な除外候補なし。全曜日・全月で平均期待値プラスを保てている（強い兆候）</li>"

    # ウォークフォワード年次表
    wf_html = ""
    years_set = set()
    for pair, yres in wf.items():
        for y in yres:
            years_set.add(y["year"])
    sorted_years = sorted(years_set)

    wf_chart_data = {}
    for pair in pairs:
        wf_chart_data[pair] = []
        ydict = {y["year"]: y for y in wf.get(pair, [])}
        for yr in sorted_years:
            if yr in ydict:
                wf_chart_data[pair].append({
                    "year": yr,
                    "return_pct": ydict[yr]["return_pct"],
                    "sharpe": ydict[yr]["sharpe"],
                    "max_dd_pct": ydict[yr]["max_dd_pct"],
                })

    today = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    port_chart_json = json.dumps(port_chart_data, ensure_ascii=False)
    dow_json = json.dumps(dow_data, ensure_ascii=False)
    month_json = json.dumps(month_data, ensure_ascii=False)
    wf_json = json.dumps(wf_chart_data, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>Phase β: アグレッシブ運用シナリオ + アノマリー分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Hiragino Sans", "Yu Gothic", sans-serif;
         margin: 0; padding: 24px; background: #0e1117; color: #e6edf3; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 32px 0 12px; color: #58a6ff;
       border-bottom: 1px solid #30363d; padding-bottom: 6px; }}
  h3 {{ font-size: 14px; margin: 0 0 12px; color: #f0883e; }}
  .meta {{ color: #7d8590; font-size: 12px; margin-bottom: 12px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 11px; background: {'#1f6feb' if src == 'real' else '#9e6a03'};
           color: white; margin-left: 8px; }}
  .params {{ background: #1c2128; padding: 8px 12px; border-radius: 4px;
            font-family: ui-monospace, monospace; font-size: 12px;
            color: #a371f7; display: inline-block; }}
  .note {{ background: #1c2128; border-left: 3px solid #f0883e; padding: 12px 16px;
          margin: 16px 0; font-size: 13px; color: #c9d1d9; line-height: 1.6; }}
  .danger {{ background: #2d1117; border-left: 3px solid #f85149; padding: 12px 16px;
            margin: 16px 0; font-size: 13px; color: #ffa198; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
           gap: 12px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          padding: 16px; position: relative; }}
  .card.consv {{ border-top: 3px solid #1f6feb; }}
  .card.std {{ border-top: 3px solid #f0883e; }}
  .card.aggr {{ border-top: 3px solid #f85149; }}
  .card .big {{ font-size: 28px; font-weight: 700; margin: 8px 0; color: #58a6ff; }}
  .card .big small {{ font-size: 12px; color: #7d8590; font-weight: 400; }}
  .metric {{ display: flex; justify-content: space-between; padding: 3px 0; font-size: 13px; }}
  .metric span {{ color: #7d8590; }}
  .metric b {{ color: #e6edf3; font-weight: 600; }}
  .metric b.hl {{ color: #7ee787; font-size: 15px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px;
          background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          overflow: hidden; }}
  th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #30363d; }}
  th {{ background: #1c2128; color: #7d8590; font-weight: 500; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.positive td {{ color: #7ee787; }}
  tr.negative td {{ color: #f85149; }}
  .charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
            gap: 16px; }}
  .chart-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                padding: 16px; }}
  canvas {{ max-height: 300px; }}
  ul {{ margin: 8px 0; padding-left: 24px; }}
  li {{ margin: 4px 0; font-size: 13px; }}
</style>
</head>
<body>

<h1>Phase β: アグレッシブ運用シナリオ + アノマリー分析
   <span class="badge">{src_badge}</span></h1>
<div class="meta">生成日時: {today} ／ 対象ペア: {", ".join(pairs)}</div>
<div class="params">戦略: C_BB_MeanRev | パラメータ: {", ".join(f"{k}={v}" for k, v in params.items())}</div>

<div class="danger">
  <b>⚠️ アグレッシブ運用についての警告：</b><br>
  リスク3%/トレード × レバ25倍は<b>許容できる損失資金（10万円）</b>であることが前提。<br>
  最大DDが大きくなり、最悪のシナリオで口座が半分以下になる可能性あり。<br>
  バックテスト結果は「将来の保証」ではない。スリッページ・スワップ・実際の約定は若干劣化する。
</div>

<h2>🎯 3シナリオ比較（3ペアポートフォリオ合成）</h2>
<div class="cards">{sc_html}</div>

<h2>📈 シナリオ別ポートフォリオ・エクイティカーブ</h2>
<div class="chart-card">
  <h3>初期資金 ¥100,000 → 各シナリオで運用した場合</h3>
  <canvas id="port_chart"></canvas>
</div>

<h2>📊 シナリオ × ペア 詳細</h2>
<table>
  <thead>
    <tr>
      <th>シナリオ</th><th>ペア</th><th>取引数</th>
      <th>総リターン</th><th>CAGR</th><th>Sharpe</th>
      <th>最大DD</th><th>勝率</th><th>ペイオフ</th>
    </tr>
  </thead>
  <tbody>{pair_table_html}</tbody>
</table>

<h2>🗓 アノマリー分析（標準シナリオのトレードを集計）</h2>

<div class="charts">
  <div class="chart-card">
    <h3>曜日別 平均期待値・勝率（全ペア合算）</h3>
    <canvas id="dow_chart"></canvas>
  </div>
  <div class="chart-card">
    <h3>月別 平均期待値・勝率（全ペア合算）</h3>
    <canvas id="month_chart"></canvas>
  </div>
</div>

<h3 style="margin-top: 24px;">日付フラグ別パフォーマンス</h3>
<table>
  <thead>
    <tr>
      <th>条件</th><th>取引数</th><th>勝率</th>
      <th>平均期待値</th><th>累計損益</th>
    </tr>
  </thead>
  <tbody>{flag_html}</tbody>
</table>

<h3 style="margin-top: 24px;">フィルタ除外候補（アノマリー駆動）</h3>
<div class="note">
  <ul>{opps_html}</ul>
</div>

<h2>🔄 ウォークフォワード分析（年次安定性）</h2>
<div class="charts">
  <div class="chart-card">
    <h3>年次リターン（標準シナリオ：2%/レバ20）</h3>
    <canvas id="wf_return"></canvas>
  </div>
  <div class="chart-card">
    <h3>年次Sharpe</h3>
    <canvas id="wf_sharpe"></canvas>
  </div>
</div>

<h2>📋 解釈ガイド & 次のステップ</h2>
<div class="note">
  <b>戦略の評価：</b><br>
  ・<b>勝率の高さ × ペイオフ低め</b> ＝ コツコツ積み上げ型。連敗が短期で起きるリスクがある<br>
  ・<b>Sharpe 1.0+</b> なら、エッジが本物の可能性が高い（運の閾値を超えている）<br>
  ・<b>年次リターンが一貫してプラス</b> なら、レジーム変化に対する耐性あり<br>
  <br>
  <b>アグレッシブ運用の現実：</b><br>
  ・10万円→100万円（10倍）は<b>標準シナリオでn年、攻撃シナリオでn/2年</b>程度<br>
  ・国内FX25倍 + 3%リスクは「ほぼ最大」。それ以上は海外FX or 入金追加が必要<br>
  ・最大DDが攻撃シナリオで20-30%超える可能性あり。心理的に耐えられるかが最大の関門<br>
  <br>
  <b>次のステップ：Phase 2 へ</b><br>
  1. 採用するシナリオを決める（保守/標準/攻撃）<br>
  2. デモ口座で1〜2ヶ月、シグナル通りに執行できるか検証<br>
  3. 問題なければ実弾投入、ただし最初は0.5×サイズで開始<br>
  4. Phase 2 で日次シグナルダッシュボード + LINE通知を構築
</div>

<script>
const portData = {port_chart_json};
const dowData = {dow_json};
const monthData = {month_json};
const wfData = {wf_json};

// Portfolio equity curve
const portColors = ["#1f6feb", "#f0883e", "#f85149"];
const portDatasets = Object.entries(portData).map(([name, curve], i) => ({{
  label: name,
  data: curve.map(x => ({{ x: x.date, y: x.equity }})),
  borderColor: portColors[i % portColors.length],
  backgroundColor: "transparent",
  pointRadius: 0,
  borderWidth: 2,
  tension: 0.1,
}}));
new Chart(document.getElementById("port_chart"), {{
  type: "line",
  data: {{ datasets: portDatasets }},
  options: {{
    animation: false,
    scales: {{
      x: {{ type: "category", ticks: {{ color: "#7d8590", maxTicksLimit: 10 }},
            grid: {{ color: "#30363d" }} }},
      y: {{ type: "logarithmic",
            ticks: {{ color: "#7d8590", callback: v => "¥" + Math.round(v).toLocaleString() }},
            grid: {{ color: "#30363d" }} }}
    }},
    plugins: {{ legend: {{ labels: {{ color: "#e6edf3" }} }} }}
  }}
}});

// DoW chart
new Chart(document.getElementById("dow_chart"), {{
  type: "bar",
  data: {{
    labels: dowData.map(d => d.name),
    datasets: [
      {{ label: "勝率(%)", data: dowData.map(d => d.win_rate), backgroundColor: "#1f6feb", yAxisID: "y" }},
      {{ label: "平均期待値(%)", data: dowData.map(d => d.avg_pnl), backgroundColor: "#f0883e", yAxisID: "y1" }},
    ],
  }},
  options: {{
    animation: false,
    scales: {{
      y: {{ position: "left", ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }},
            title: {{ display: true, text: "勝率(%)", color: "#7d8590" }} }},
      y1: {{ position: "right", ticks: {{ color: "#7d8590" }}, grid: {{ display: false }},
             title: {{ display: true, text: "平均期待値(%)", color: "#7d8590" }} }},
      x: {{ ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }} }}
    }},
    plugins: {{ legend: {{ labels: {{ color: "#e6edf3" }} }} }}
  }}
}});

// Month chart
new Chart(document.getElementById("month_chart"), {{
  type: "bar",
  data: {{
    labels: monthData.map(d => d.name),
    datasets: [
      {{ label: "勝率(%)", data: monthData.map(d => d.win_rate), backgroundColor: "#1f6feb", yAxisID: "y" }},
      {{ label: "平均期待値(%)", data: monthData.map(d => d.avg_pnl), backgroundColor: "#f0883e", yAxisID: "y1" }},
    ],
  }},
  options: {{
    animation: false,
    scales: {{
      y: {{ position: "left", ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }},
            title: {{ display: true, text: "勝率(%)", color: "#7d8590" }} }},
      y1: {{ position: "right", ticks: {{ color: "#7d8590" }}, grid: {{ display: false }},
             title: {{ display: true, text: "平均期待値(%)", color: "#7d8590" }} }},
      x: {{ ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }} }}
    }},
    plugins: {{ legend: {{ labels: {{ color: "#e6edf3" }} }} }}
  }}
}});

// Walk-forward charts
const wfColors = {{ "USDJPY": "#58a6ff", "EURJPY": "#f0883e", "GBPJPY": "#a371f7" }};
const wfPairs = Object.keys(wfData);
const allYears = [...new Set(wfPairs.flatMap(p => wfData[p].map(x => x.year)))].sort();

new Chart(document.getElementById("wf_return"), {{
  type: "bar",
  data: {{
    labels: allYears,
    datasets: wfPairs.map(p => ({{
      label: p,
      data: allYears.map(y => {{
        const found = wfData[p].find(x => x.year === y);
        return found ? found.return_pct : null;
      }}),
      backgroundColor: wfColors[p] + "AA",
      borderColor: wfColors[p],
    }})),
  }},
  options: {{
    animation: false,
    scales: {{
      y: {{ ticks: {{ color: "#7d8590", callback: v => v + "%" }},
            grid: {{ color: "#30363d" }} }},
      x: {{ ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }} }}
    }},
    plugins: {{ legend: {{ labels: {{ color: "#e6edf3" }} }} }}
  }}
}});

new Chart(document.getElementById("wf_sharpe"), {{
  type: "bar",
  data: {{
    labels: allYears,
    datasets: wfPairs.map(p => ({{
      label: p,
      data: allYears.map(y => {{
        const found = wfData[p].find(x => x.year === y);
        return found ? found.sharpe : null;
      }}),
      backgroundColor: wfColors[p] + "AA",
      borderColor: wfColors[p],
    }})),
  }},
  options: {{
    animation: false,
    scales: {{
      y: {{ ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }} }},
      x: {{ ticks: {{ color: "#7d8590" }}, grid: {{ color: "#30363d" }} }}
    }},
    plugins: {{ legend: {{ labels: {{ color: "#e6edf3" }} }} }}
  }}
}});
</script>

</body>
</html>"""
