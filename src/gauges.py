"""
SVGゲージ・メーター・ランプ等のコンポーネント生成
ダッシュボードに直接埋め込めるSVG文字列を返す。
"""
import math


def tachometer(value: float, max_value: float = 100, label: str = "",
               unit: str = "%", size: int = 200,
               zones: list = None) -> str:
    """半円タコメーター
    value: 現在値
    max_value: 最大値
    zones: [(start_pct, end_pct, color), ...] 例えば [(0, 0.6, "green"), (0.6, 0.85, "yellow"), (0.85, 1.0, "red")]
    """
    if zones is None:
        zones = [(0, 0.6, "#3fb950"), (0.6, 0.85, "#d29922"), (0.85, 1.0, "#f85149")]

    cx, cy = size / 2, size / 2 + 10
    r = size * 0.4
    # -135度から+135度まで（180度の半円ではなく270度の3/4扇）
    start_deg = -135
    end_deg = 135
    span = end_deg - start_deg

    def deg_to_xy(deg):
        rad = math.radians(deg)
        return cx + r * math.sin(rad), cy - r * math.cos(rad)

    def arc(start_pct, end_pct, color, sw=14):
        d_start = start_deg + start_pct * span
        d_end = start_deg + end_pct * span
        x1, y1 = deg_to_xy(d_start)
        x2, y2 = deg_to_xy(d_end)
        large_arc = 1 if (d_end - d_start) > 180 else 0
        return f'<path d="M {x1:.1f} {y1:.1f} A {r} {r} 0 {large_arc} 1 {x2:.1f} {y2:.1f}" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round"/>'

    arcs = "".join(arc(s, e, c) for s, e, c in zones)

    # 針
    pct = max(0, min(1, value / max_value))
    needle_deg = start_deg + pct * span
    needle_rad = math.radians(needle_deg)
    nx = cx + (r - 8) * math.sin(needle_rad)
    ny = cy - (r - 8) * math.cos(needle_rad)
    bx = cx - 8 * math.sin(needle_rad)
    by = cy + 8 * math.cos(needle_rad)

    # メモリ
    ticks = ""
    for i in range(11):
        td = start_deg + (i / 10) * span
        rad = math.radians(td)
        tx1 = cx + (r - 4) * math.sin(rad)
        ty1 = cy - (r - 4) * math.cos(rad)
        tx2 = cx + (r + 6) * math.sin(rad)
        ty2 = cy - (r + 6) * math.cos(rad)
        ticks += f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="#7d8590" stroke-width="1.5"/>'

    return f"""
    <svg viewBox="0 0 {size} {size}" class="gauge-svg">
      <defs>
        <radialGradient id="needle-grad-{id(value)}" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#fff"/>
          <stop offset="100%" stop-color="#aaa"/>
        </radialGradient>
        <filter id="shadow-{id(value)}">
          <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.3"/>
        </filter>
      </defs>
      <circle cx="{cx}" cy="{cy}" r="{r + 12}" fill="#0d1117" stroke="#21262d" stroke-width="2"/>
      {arcs}
      {ticks}
      <line x1="{bx:.1f}" y1="{by:.1f}" x2="{nx:.1f}" y2="{ny:.1f}"
            stroke="#fff" stroke-width="3" stroke-linecap="round"
            filter="url(#shadow-{id(value)})"/>
      <circle cx="{cx}" cy="{cy}" r="8" fill="url(#needle-grad-{id(value)})" stroke="#444" stroke-width="1"/>
      <text x="{cx}" y="{cy + r * 0.55}" text-anchor="middle" fill="#e6edf3"
            font-size="22" font-weight="700">{value:.1f}{unit}</text>
      <text x="{cx}" y="{cy + r * 0.55 + 18}" text-anchor="middle" fill="#7d8590" font-size="11">{label}</text>
    </svg>
    """


def linear_gauge(value: float, min_v: float, max_v: float,
                 label: str = "", color: str = "#3fb950",
                 zones: list = None, height: int = 30) -> str:
    """水平リニアゲージ（横長バー＋針）"""
    width = 320
    pad = 20
    bar_h = 14
    bar_y = (height - bar_h) / 2 + 20

    pct = (value - min_v) / (max_v - min_v) if max_v > min_v else 0
    pct = max(0, min(1, pct))
    val_x = pad + (width - 2 * pad) * pct

    if zones is None:
        zones = [(0, 1.0, color)]

    seg_html = ""
    for s, e, c in zones:
        x1 = pad + (width - 2 * pad) * s
        x2 = pad + (width - 2 * pad) * e
        seg_html += f'<rect x="{x1}" y="{bar_y}" width="{x2-x1}" height="{bar_h}" fill="{c}" opacity="0.7"/>'

    return f"""
    <svg viewBox="0 0 {width} {height + 30}" class="gauge-svg" style="width:100%; max-width:{width}px;">
      <text x="{pad}" y="14" fill="#7d8590" font-size="11">{label}</text>
      <text x="{width - pad}" y="14" fill="#e6edf3" font-size="13" text-anchor="end" font-weight="600">{value:.2f}</text>
      <rect x="{pad}" y="{bar_y}" width="{width - 2*pad}" height="{bar_h}" fill="#21262d" rx="3"/>
      {seg_html}
      <line x1="{val_x:.1f}" y1="{bar_y - 4}" x2="{val_x:.1f}" y2="{bar_y + bar_h + 4}"
            stroke="#fff" stroke-width="2.5"/>
      <circle cx="{val_x:.1f}" cy="{bar_y + bar_h/2}" r="3" fill="#fff"/>
    </svg>
    """


def position_lamps(positions: dict, all_pairs: list) -> str:
    """各通貨ペアの保有状態を信号灯で表示"""
    lamps = ""
    pad = 60
    for i, p in enumerate(all_pairs):
        cx = pad / 2 + i * pad
        is_open = positions.get(p, None) is not None
        direction = positions[p].get("direction", 0) if is_open else 0
        if direction == 1:
            color = "#3fb950"
            label = "買い保有"
        elif direction == -1:
            color = "#f85149"
            label = "売り保有"
        else:
            color = "#21262d"
            label = "—"
        lamps += f"""
        <g transform="translate({cx}, 30)">
          <defs>
            <radialGradient id="lamp-{i}-{p}" cx="40%" cy="35%" r="60%">
              <stop offset="0%" stop-color="{color}" stop-opacity="1"/>
              <stop offset="100%" stop-color="{color}" stop-opacity="0.3"/>
            </radialGradient>
          </defs>
          <circle cx="0" cy="0" r="22" fill="#0d1117" stroke="#30363d" stroke-width="2"/>
          <circle cx="0" cy="0" r="16" fill="url(#lamp-{i}-{p})" {"" if is_open else 'opacity="0.3"'}/>
          <text x="0" y="42" text-anchor="middle" fill="#e6edf3" font-size="11" font-weight="600">{p}</text>
          <text x="0" y="55" text-anchor="middle" fill="#7d8590" font-size="9">{label}</text>
        </g>
        """
    width = pad * len(all_pairs)
    return f'<svg viewBox="0 0 {width} 70" class="gauge-svg" style="width:100%; max-width:{width}px;">{lamps}</svg>'


def signal_lamp(active: bool, direction: int = 0) -> str:
    """単一のシグナル発火ランプ"""
    if active and direction == 1:
        color = "#3fb950"; text = "BUY"
    elif active and direction == -1:
        color = "#f85149"; text = "SELL"
    else:
        color = "#30363d"; text = "WAIT"
    return f"""
    <svg viewBox="0 0 80 80" class="gauge-svg">
      <defs>
        <radialGradient id="siglamp-{direction}" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stop-color="{color}" stop-opacity="1"/>
          <stop offset="80%" stop-color="{color}" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <circle cx="40" cy="40" r="38" fill="#0d1117" stroke="#21262d"/>
      <circle cx="40" cy="40" r="28" fill="url(#siglamp-{direction})"/>
      <text x="40" y="44" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">{text}</text>
    </svg>
    """


def progress_bar(current: float, entry: float, target: float, stop: float,
                 direction: int = 1, width: int = 320) -> str:
    """エントリー→現在価格→目標までの進捗バー"""
    if direction == 1:
        # 買い: stop < entry < current ... < target
        lo, hi = stop, target
    else:
        lo, hi = target, stop

    span = hi - lo
    if span <= 0:
        return ""

    def x_at(price):
        return 20 + (width - 40) * (price - lo) / span

    entry_x = x_at(entry)
    current_x = x_at(current)
    stop_x = x_at(stop)
    target_x = x_at(target)
    bar_y = 35
    bar_h = 12

    return f"""
    <svg viewBox="0 0 {width} 70" class="gauge-svg" style="width:100%;">
      <text x="{stop_x:.1f}" y="20" fill="#f85149" font-size="10" text-anchor="middle">SL {stop:.3f}</text>
      <text x="{target_x:.1f}" y="20" fill="#3fb950" font-size="10" text-anchor="middle">TP {target:.3f}</text>
      <rect x="20" y="{bar_y}" width="{width - 40}" height="{bar_h}" fill="#21262d" rx="2"/>
      <rect x="{stop_x:.1f}" y="{bar_y}" width="3" height="{bar_h}" fill="#f85149"/>
      <rect x="{target_x:.1f}" y="{bar_y}" width="3" height="{bar_h}" fill="#3fb950"/>
      <rect x="{entry_x:.1f}" y="{bar_y}" width="2" height="{bar_h}" fill="#7d8590"/>
      <text x="{entry_x:.1f}" y="62" fill="#7d8590" font-size="9" text-anchor="middle">ENTRY {entry:.3f}</text>
      <line x1="{current_x:.1f}" y1="{bar_y - 4}" x2="{current_x:.1f}" y2="{bar_y + bar_h + 4}" stroke="#fff" stroke-width="2.5"/>
      <circle cx="{current_x:.1f}" cy="{bar_y + bar_h/2}" r="4" fill="#fff" stroke="#0d1117" stroke-width="1.5"/>
      <text x="{current_x:.1f}" y="{bar_y - 8}" fill="#fff" font-size="11" text-anchor="middle" font-weight="700">{current:.3f}</text>
    </svg>
    """


def equity_sparkline(equity_curve: list, width: int = 220, height: int = 60,
                     color: str = "#3fb950") -> str:
    """エクイティカーブの簡易スパークライン"""
    if not equity_curve or len(equity_curve) < 2:
        return f'<svg viewBox="0 0 {width} {height}" class="gauge-svg"></svg>'
    vals = [p["equity"] for p in equity_curve]
    lo, hi = min(vals), max(vals)
    span = hi - lo if hi > lo else 1
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = (i / (n - 1)) * (width - 8) + 4
        y = height - 4 - ((v - lo) / span) * (height - 8)
        pts.append(f"{x:.1f},{y:.1f}")
    pts_str = " ".join(pts)
    last_color = "#3fb950" if vals[-1] >= vals[0] else "#f85149"
    return f"""
    <svg viewBox="0 0 {width} {height}" class="gauge-svg" style="width:100%;">
      <polyline points="{pts_str}" fill="none" stroke="{last_color}" stroke-width="2"/>
      <circle cx="{pts[-1].split(',')[0]}" cy="{pts[-1].split(',')[1]}" r="3" fill="{last_color}"/>
    </svg>
    """
