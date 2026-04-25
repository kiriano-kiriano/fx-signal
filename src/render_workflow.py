"""
Phase 2: 1日の運用イメージページ
タイムライン + ゲージ多用で、運用フローを視覚的に示す。
"""
import math
import datetime as dt


def _analog_clock(hours: int, minutes: int, size: int = 100, label: str = "") -> str:
    """アナログ時計"""
    cx, cy = size / 2, size / 2
    r = size * 0.42
    # 時針 (12時間表記、分も加味)
    h_deg = ((hours % 12) + minutes / 60) * 30 - 90
    m_deg = minutes * 6 - 90
    h_rad = math.radians(h_deg)
    m_rad = math.radians(m_deg)
    h_x = cx + r * 0.5 * math.cos(h_rad)
    h_y = cy + r * 0.5 * math.sin(h_rad)
    m_x = cx + r * 0.75 * math.cos(m_rad)
    m_y = cy + r * 0.75 * math.sin(m_rad)
    # メモリ
    ticks = ""
    for i in range(12):
        td = i * 30 - 90
        rad = math.radians(td)
        ix1 = cx + (r - 4) * math.cos(rad)
        iy1 = cy + (r - 4) * math.sin(rad)
        ix2 = cx + r * math.cos(rad)
        iy2 = cy + r * math.sin(rad)
        ticks += f'<line x1="{ix1:.1f}" y1="{iy1:.1f}" x2="{ix2:.1f}" y2="{iy2:.1f}" stroke="#7d8590" stroke-width="2"/>'
    return f"""
    <svg viewBox="0 0 {size} {size + 30}" class="clock-svg">
      <circle cx="{cx}" cy="{cy}" r="{r + 6}" fill="#0d1117" stroke="#21262d" stroke-width="2"/>
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="#161b22"/>
      {ticks}
      <line x1="{cx}" y1="{cy}" x2="{h_x:.1f}" y2="{h_y:.1f}" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
      <line x1="{cx}" y1="{cy}" x2="{m_x:.1f}" y2="{m_y:.1f}" stroke="#58a6ff" stroke-width="2" stroke-linecap="round"/>
      <circle cx="{cx}" cy="{cy}" r="3" fill="#fff"/>
      <text x="{cx}" y="{size + 18}" text-anchor="middle" fill="#e6edf3" font-size="14" font-weight="600">{hours:02d}:{minutes:02d}</text>
      <text x="{cx}" y="{size + 30}" text-anchor="middle" fill="#7d8590" font-size="10">{label}</text>
    </svg>
    """


def _step_card(time_label: str, hours: int, minutes: int, icon: str,
               title: str, body: str, status_color: str = "#58a6ff",
               extra_html: str = "") -> str:
    """タイムラインの1ステップカード"""
    clock = _analog_clock(hours, minutes, size=80, label=time_label)
    return f"""
    <div class="step">
      <div class="step-time">{clock}</div>
      <div class="step-icon" style="background: {status_color}33; border-color: {status_color};">
        <div class="step-icon-inner">{icon}</div>
      </div>
      <div class="step-body">
        <h3 style="color: {status_color};">{title}</h3>
        <div class="step-text">{body}</div>
        {extra_html}
      </div>
    </div>
    """


def _gauge_demo(value: float, max_v: float, label: str, color: str) -> str:
    """シンプル円ゲージ"""
    pct = max(0, min(1, value / max_v))
    radius = 35
    circumference = 2 * math.pi * radius
    offset = circumference * (1 - pct)
    return f"""
    <svg viewBox="0 0 100 100" class="mini-gauge">
      <circle cx="50" cy="50" r="{radius}" fill="none" stroke="#21262d" stroke-width="6"/>
      <circle cx="50" cy="50" r="{radius}" fill="none" stroke="{color}" stroke-width="6"
              stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{offset:.1f}"
              stroke-linecap="round" transform="rotate(-90 50 50)"/>
      <text x="50" y="48" text-anchor="middle" fill="#fff" font-size="16" font-weight="700">{value:.0f}</text>
      <text x="50" y="62" text-anchor="middle" fill="#7d8590" font-size="9">{label}</text>
    </svg>
    """


def render_workflow_page() -> str:
    today_str = dt.datetime.now().strftime("%Y年%m月%d日")

    # ステップ1: NY close (06:00)
    step1 = _step_card(
        "NY市場クローズ", 6, 0, "🌅",
        "日足が確定",
        "NY市場のクローズと同時に、対円通貨ペアの日足ローソクが完成します。<br>"
        "この瞬間に「昨日のシグナル」が確定します。あなたは寝ています。",
        "#1f6feb",
    )

    # ステップ2: GitHub Actions (07:30)
    gauge_demo_html = f"""
    <div class="gauge-row">
      {_gauge_demo(82, 100, "勝率", "#3fb950")}
      {_gauge_demo(15, 30, "DD", "#d29922")}
      {_gauge_demo(2, 3, "保有", "#58a6ff")}
    </div>
    """
    step2 = _step_card(
        "自動更新", 7, 30, "⚙️",
        "GitHub Actionsが起動",
        "クラウド上で自動的に：<br>"
        "① yfinanceから最新価格を取得<br>"
        "② シグナル計算（C_BB_MeanRev × 3ペア）<br>"
        "③ ダッシュボードHTML生成<br>"
        "④ Render Static Siteへデプロイ<br>"
        "あなたはまだ寝てます。GitHubが代わりに働いてくれてます。",
        "#3fb950",
        gauge_demo_html,
    )

    # ステップ3: 通知 (07:30)
    step3 = _step_card(
        "通知", 7, 35, "📱",
        "LINE通知 / Discord通知",
        "新規シグナルが発火していたら、スマホに通知が飛びます。<br><br>"
        "<code>🟢 USDJPY 買いシグナル<br>"
        "Entry 154.50 / SL 152.30 / TP 155.40<br>"
        "推奨ロット 0.6lot</code><br><br>"
        "シグナルなしの日は通知も来ません（無音）。",
        "#f0883e",
    )

    # ステップ4: 朝の確認 (07:45)
    step4 = _step_card(
        "朝の確認", 7, 45, "👀",
        "ダッシュボードを開く",
        "通知のリンクからダッシュボードを開きます。<br>"
        "・タコメーターでリスク状態を一瞥<br>"
        "・ポジションランプで保有状況確認<br>"
        "・シグナルカードで今日の指示を確認",
        "#58a6ff",
        '<a href="index.html" class="cta">→ ダッシュボードを開く</a>',
    )

    # ステップ5: 発注 (08:00)
    ifdoco_demo = """
    <div class="ifdoco-demo">
      <strong>📋 業者ツール（例：GMOクリック）</strong>
      <pre>注文方式: IFDOCO
新規:    成行買い 0.6lot
利確:    指値 155.40
損切り:  逆指値 152.30</pre>
    </div>
    """
    step5 = _step_card(
        "発注", 8, 0, "🎯",
        "30秒で発注完了",
        "業者アプリでIFDOCO注文。コピペするだけ。<br>"
        "発注後は東京寄付き(09:00)に自動約定。<br>"
        "決済も自動。あなたは何もしなくていい。",
        "#a371f7",
        ifdoco_demo,
    )

    # ステップ6: Tokyo open (09:00)
    step6 = _step_card(
        "Tokyo Open", 9, 0, "🏯",
        "自動エントリー",
        "東京市場の寄付きで自動的にエントリー。<br>"
        "あなたは出勤中。スマホに約定通知が届く程度。",
        "#3fb950",
    )

    # ステップ7: 日中 (12:00 / 15:00)
    step7 = _step_card(
        "日中", 12, 0, "💼",
        "放置（仕事に集中）",
        "ポジションは業者側のSL/TPで自動管理。<br>"
        "あなたは仕事に集中。ランチタイムに気が向いたらスマホでチラ見。<br>"
        "動かしてもいいことはひとつもない（裁量介入は期待値を下げる）。",
        "#7d8590",
    )

    # ステップ8: NY時間 (22:00)
    step8 = _step_card(
        "夜", 22, 0, "🌙",
        "NY時間で動きが出る",
        "対円通貨ペアの本格的な動きはNY時間で発生。<br>"
        "SL/TPに到達したら自動決済 → 通知。<br>"
        "未決済なら持ち越し。",
        "#f0883e",
    )

    # ステップ9: 翌日へ (06:00)
    step9 = _step_card(
        "翌日へ", 6, 0, "🔁",
        "ループ",
        "NYクローズで日足確定 → 翌朝07:30にシグナル更新 → 繰り返し。<br>"
        "週末は市場クローズなので発注なし。",
        "#1f6feb",
    )

    # 月間カレンダーイメージ（赤=損切り日、緑=利確日、灰=シグナルなし）
    calendar_html = ""
    import random
    random.seed(42)
    for i in range(28):
        r = random.random()
        if r < 0.5:
            cls = "cal-none"
        elif r < 0.85:
            cls = "cal-win"
        else:
            cls = "cal-loss"
        calendar_html += f'<div class="cal-day {cls}"></div>'

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>1日の運用イメージ — FX Daily Signal</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Hiragino Sans", "Yu Gothic", sans-serif;
         margin: 0; padding: 16px; background: #0d1117; color: #e6edf3;
         line-height: 1.5; }}
  .topbar {{ display: flex; justify-content: space-between; align-items: center;
            padding-bottom: 16px; border-bottom: 1px solid #21262d; margin-bottom: 24px; }}
  h1 {{ font-size: 22px; margin: 0; }}
  h2 {{ font-size: 18px; margin: 32px 0 16px; color: #58a6ff;
       border-bottom: 1px solid #30363d; padding-bottom: 6px; }}
  .nav a {{ color: #58a6ff; text-decoration: none; margin-left: 16px; font-size: 13px; }}
  .intro {{ background: linear-gradient(135deg, #161b22, #1c2128);
           border: 1px solid #30363d; border-radius: 12px;
           padding: 20px 24px; margin-bottom: 32px; font-size: 14px; }}
  .intro b {{ color: #f0883e; }}
  .timeline {{ position: relative; padding-left: 0; }}
  .step {{ display: grid; grid-template-columns: 100px 60px 1fr; gap: 16px;
          align-items: start; padding: 16px 0;
          position: relative; }}
  .step::before {{ content: ""; position: absolute; left: 130px; top: 0; bottom: 0;
                  width: 2px; background: linear-gradient(#30363d, #21262d); }}
  .step:last-child::before {{ display: none; }}
  .step-time {{ display: flex; justify-content: center; }}
  .clock-svg {{ width: 80px; height: 110px; }}
  .step-icon {{ width: 48px; height: 48px; border-radius: 50%;
               border: 2px solid; display: flex;
               align-items: center; justify-content: center;
               font-size: 22px; margin-top: 16px;
               position: relative; z-index: 2; background: #0d1117; }}
  .step-icon-inner {{ }}
  .step-body {{ background: #161b22; border: 1px solid #30363d;
               border-radius: 10px; padding: 14px 18px; }}
  .step-body h3 {{ margin: 0 0 8px; font-size: 16px; }}
  .step-text {{ color: #c9d1d9; font-size: 13px; }}
  .step-text code {{ background: #0d1117; padding: 4px 8px; border-radius: 4px;
                    color: #58a6ff; font-size: 11px; display: inline-block;
                    line-height: 1.6; }}
  .gauge-row {{ display: flex; gap: 12px; margin-top: 12px; }}
  .mini-gauge {{ width: 90px; height: 90px; }}
  .ifdoco-demo {{ background: #0d1117; border: 1px solid #30363d;
                 border-radius: 6px; padding: 8px 12px; margin-top: 10px;
                 font-size: 11px; }}
  .ifdoco-demo pre {{ margin: 4px 0 0; color: #e6edf3;
                     font-family: ui-monospace, monospace; }}
  .ifdoco-demo strong {{ color: #f0883e; font-size: 11px; }}
  .cta {{ display: inline-block; margin-top: 10px; padding: 8px 16px;
         background: #1f6feb; color: white; border-radius: 6px;
         text-decoration: none; font-size: 13px; font-weight: 500; }}

  .calendar {{ display: grid; grid-template-columns: repeat(7, 1fr);
              gap: 6px; max-width: 320px; }}
  .cal-day {{ aspect-ratio: 1; border-radius: 4px; }}
  .cal-none {{ background: #21262d; }}
  .cal-win {{ background: linear-gradient(135deg, #3fb950, #2ea043); }}
  .cal-loss {{ background: linear-gradient(135deg, #f85149, #da3633); }}
  .legend {{ display: flex; gap: 16px; margin-top: 12px; font-size: 12px; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; color: #7d8590; }}
  .legend-dot {{ width: 14px; height: 14px; border-radius: 3px; }}

  .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                   gap: 12px; margin: 24px 0; }}
  .summary-card {{ background: #161b22; border: 1px solid #30363d;
                  border-radius: 10px; padding: 16px; }}
  .summary-card .big {{ font-size: 28px; font-weight: 700; color: #58a6ff; }}
  .summary-card span {{ font-size: 11px; color: #7d8590; display: block; }}
  .summary-card.warn .big {{ color: #f0883e; }}
  .summary-card.success .big {{ color: #3fb950; }}

  @media (max-width: 600px) {{
    .step {{ grid-template-columns: 80px 40px 1fr; gap: 8px; }}
    .step::before {{ left: 100px; }}
    .clock-svg {{ width: 64px; height: 90px; }}
    .step-icon {{ width: 36px; height: 36px; font-size: 16px; }}
  }}
</style>
</head>
<body>

<div class="topbar">
  <h1>📅 1日の運用イメージ</h1>
  <nav class="nav">
    <a href="index.html">← ダッシュボードに戻る</a>
    <a href="phase_beta.html">📈 戦略詳細</a>
  </nav>
</div>

<div class="intro">
  <b>あなたが実際にやること：</b> 朝、起きたらスマホで通知を確認 → ダッシュボードを開く →
  シグナルがあれば業者アプリでIFDOCO発注（30秒）。<br><br>
  <b>あとは全部自動：</b> 計算・通知・配信はGitHub Actions、約定・決済は業者側のOCO注文。
  あなたが頭を使うのは「シグナル通り発注するか、しないか」だけ。
</div>

<div class="summary-cards">
  <div class="summary-card">
    <span>1日の作業時間</span>
    <div class="big">~5分</div>
    <span>朝の確認 + 発注</span>
  </div>
  <div class="summary-card success">
    <span>月間シグナル発火数（推定）</span>
    <div class="big">10〜20回</div>
    <span>レンジ相場の歪み待ち</span>
  </div>
  <div class="summary-card warn">
    <span>裁量判断</span>
    <div class="big">0回</div>
    <span>すべて事前ルール化</span>
  </div>
</div>

<h2>🕒 タイムライン（平日の例）</h2>
<div class="timeline">
{step1}
{step2}
{step3}
{step4}
{step5}
{step6}
{step7}
{step8}
{step9}
</div>

<h2>📅 1ヶ月のイメージ（イメージ）</h2>
<div class="intro">
  毎日シグナルが出るわけではない。レンジ相場の歪みが発生したときだけ発注する。<br>
  だいたい月10〜20回のエントリー、勝率55〜70%の前提。
</div>
<div class="calendar">
  {calendar_html}
</div>
<div class="legend">
  <div class="legend-item"><div class="legend-dot cal-none"></div>シグナルなし</div>
  <div class="legend-item"><div class="legend-dot cal-win"></div>利確</div>
  <div class="legend-item"><div class="legend-dot cal-loss"></div>損切り</div>
</div>

<h2>🎯 大事なルール</h2>
<div class="intro">
  <ul>
    <li><b>シグナルが出ても「気が乗らない」なら見送ってOK。</b>ただし長期的には期待値が落ちるので最低限の規律は保つ。</li>
    <li><b>シグナルが出てないのに自分で売買は厳禁。</b>裁量介入は期待値を下げるだけ。</li>
    <li><b>SL/TPは絶対に動かさない。</b>動かしたくなる衝動が中級者を破滅させる。</li>
    <li><b>連敗したら一時停止。</b>5連敗したらルールを見直し、その期間は新規ポジ禁止。</li>
    <li><b>10万円が消えても困らない金額にする。</b>困る金額になったら、それはもうリスク資産じゃない。</li>
  </ul>
</div>

</body>
</html>"""
