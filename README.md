# FX 戦略バックテスト比較ダッシュボード（Phase 1）

3つのFX戦略を15年分の日足でバックテストし、自分に合う戦略をデータで選ぶためのツール。

## ディレクトリ構成

```
爆益計画/
├── src/
│   ├── data_loader.py     # yfinanceで日足を取得（USDJPY/EURJPY/GBPJPY）
│   ├── synthetic_data.py  # yfinance不可環境での合成データ
│   ├── indicators.py      # ATR / ADX / SMA / Donchian / Bollinger
│   ├── backtest.py        # バックテストエンジン（共通）
│   ├── strategies.py      # 3戦略のシグナル定義
│   ├── metrics.py         # CAGR / Sharpe / DD / 期待値 等
│   ├── render_html.py     # HTML ダッシュボード生成
│   └── run_backtest.py    # メイン実行
├── data/                  # CSV キャッシュ（自動生成）
├── output/
│   ├── results.json       # 全結果のJSON
│   └── dashboard.html     # 比較ダッシュボード（このファイルを開く）
└── README.md
```

## セットアップ（Mac）

```bash
cd "/Users/kiriano/Desktop/ぎぺり/爆益計画"
pip3 install yfinance pandas numpy matplotlib jinja2
```

## 実行

```bash
python3 src/run_backtest.py
```

実行が終わると `output/dashboard.html` が生成されます。Finderから開けばChromeなどで表示されます。

## 3つの戦略

- **A. ドンチャン・ブレイクアウト** — 20日高値ブレイクで買い、20日安値ブレイクで売り。損切り 2×ATR、反対方向のドンチャン20日でドテン。純粋トレンドフォロー型。
- **B. MA + ADX トレンドフォロー** — 20MA > 50MA かつ ADX>25 のときに押し目買い、対称で売り。損切り 2×ATR。トレンド相場フィルタ付きで勝率重視。
- **C. ボリンジャー平均回帰** — BB(20, ±2σ)タッチで逆張り、20MA回帰で利確、3σ突破で損切り。ADX<20（レンジ相場）のときのみ発動。

すべて日足、1トレード当たり口座の1%リスク、最大レバレッジ10倍に制限。

## ダッシュボードの読み方

- **戦略サマリー（3ペア平均）**：CAGR、シャープ、最大DD、勝率、合計取引数
- **戦略×通貨ペア 詳細表**：9通りのバックテスト結果を横並び比較
- **エクイティカーブ**：戦略ごとに3ペアの資金曲線を重ねて表示

### 戦略選択の指針

- **シャープレシオ ≥ 1.0**：効率の良い戦略。0.5未満は再考。
- **最大DD ≤ 25%**：心理的に続けられる範囲。30%超は個人運用向きでない。
- **取引数 ≥ 100**：サンプル数十分。50以下は運の影響大。
- **ペア間の安定性**：3ペアとも同方向の結果ならロバスト。1ペアだけ突出してたら過剰最適化を疑う。

## Phase 2（次の段階）

勝った戦略を使って、毎朝の最新シグナルを自動で表示するダッシュボードを作る。

- GitHub Actions で毎朝7時に `python3 src/generate_daily.py` を実行
- 当日の新規シグナル + 昨日のシグナル結果 + 直近1ヶ月の集計をHTML化
- Render Static Site で配信（無料・常時稼働）
- LINE Notify or Discord Webhook でシグナル発火を通知

## 注意

- 過去のリターンは将来を保証しない
- バックテストはスリッページ・スワップポイントを完全には再現していない
- 1トレード1%リスク、最大レバ10倍は安全寄りの設定。実戦投入前に必ず自分の許容度を確認
- Phase 1 はあくまで「どの戦略タイプが自分に合うか」を判断するための比較ツール。実弾投入はPhase 2移行後、デモ口座での3ヶ月検証を経てから推奨

---

## Phase 1.5: パラメータ感度分析 + IS/OOSバリデーション

過剰最適化（オーバーフィッティング）を避けるため、過去データを2分割して検証する。

- **IS（In-Sample）期間**: 2011-01-01 〜 2020-12-31（パラメータ最適化用）
- **OOS（Out-of-Sample）期間**: 2021-01-01 〜 現在（独立検証用）

各戦略のキーパラメータをグリッドサーチし、両期間で機能する「ロバストな」組み合わせを抽出する。

### 探索パラメータ

- **A_Donchian**: breakout_n × atr_mult × exit_n = 36通り
- **B_MA_ADX**: (fast,slow) × adx_threshold × atr_mult = 24通り
- **C_BB_MeanRev**: n × k × adx_max × stop_k = 24通り

合計 84通り × 3ペア = 252バックテスト（IS/OOSそれぞれ実行 = 504ラン）

### 実行

```bash
cd "/Users/kiriano/Desktop/ぎぺり/爆益計画"
python3 src/run_optimization.py
open output/optimization.html
```

実行時間は実データで2〜5分程度。

### 結果ダッシュボードの読み方

- **ロバスト Top 20**: 両期間プラスかつ min(IS_SR, OOS_SR) で降順。同じ戦略×ペアが複数登場すればロバストなエッジの証拠
- **戦略×ペア別ベスト**: 9通りそれぞれの最良パラメータ
- **IS vs OOS 散布図**: 右上に点が密集 = ロバスト、対角線から大きく外れる = 過剰最適化

### Phase β の判断基準

ダッシュボードを見て、以下を満たす1〜2組み合わせを Phase β（深掘り）候補とする：

1. OOS_SR ≥ 0.7（OOS期間でも十分なエッジ）
2. OOS_SR / IS_SR ≥ 0.7（IS→OOSで性能が大きく劣化していない）
3. 同じ戦略×ペアでパラメータ違いの上位入賞が複数ある（ロバスト）
4. 最大DD（OOS） ≤ 25%（心理的に続けられる範囲）

これらを満たす組み合わせを Phase β でブラッシュアップ → Phase 2 で日次シグナル運用へ。

---

## Phase β: アグレッシブ運用シナリオ + アノマリー分析

最終的な実運用シナリオを決めるための統合分析。

### 内容

- **3シナリオ比較**: 保守(1%/レバ10) / 標準(2%/レバ20) / 攻撃(3%/レバ25)
- **3ペアポートフォリオ合成**: USDJPY/EURJPY/GBPJPY を同時運用したエクイティカーブ
- **10倍までの推定年数**: 各シナリオごと
- **アノマリー分析**: 曜日・月・ゴトー日・四半期末・米雇用統計週など、トレードの時間特性を集計
- **ウォークフォワード**: 年次の安定性チェック（プラスを維持できる年の割合）

### 採用パラメータ（Phase 1.5で確定）

```
戦略: C_BB_MeanRev (ボリンジャー平均回帰)
パラメータ: adx_max=25, k=2.5, n=20, stop_k=2.5
対象ペア: USDJPY, EURJPY, GBPJPY（3ペア同じパラメータ）
```

### 実行

```bash
cd "/Users/kiriano/Desktop/ぎぺり/爆益計画"
python3 src/run_phase_beta.py
open output/phase_beta.html
```

実行時間は実データで2〜3分。

### ダッシュボードの構成

1. **3シナリオサマリーカード** — CAGR、DD、Sharpe、勝率、10倍までの目安
2. **シナリオ別ポートフォリオ・エクイティカーブ** — 対数スケール表示
3. **シナリオ × ペア 詳細表** — 9通りの内訳
4. **アノマリー分析（曜日別／月別／日付フラグ別）** — エントリーすべきでない日が判明する
5. **フィルタ除外候補** — アノマリー駆動で「この曜日／月は外す」推奨
6. **ウォークフォワード年次推移** — レジーム不安定性のチェック

### 採用シナリオの判断基準

- **保守(1%)**: 「失っても惜しくない金額をデモ感覚で増やしたい」 → DD最小、複利は遅い
- **標準(2%)**: 「リスク資産として最適化したい、5年スパン」 → バランス型、最も推奨
- **攻撃(3%)**: 「10万円は完全リスク資産、最短で爆益狙う」 → DD大、心理的耐久必要

### 重要な注意

- 国内FX（レバ25倍）が前提。海外FXのハイレバは別ロジック
- 攻撃シナリオでも最大レバは25倍を超えない（国内法的上限）
- バックテストは過去の結果。スリッページ・スワップ・実際の約定で5〜15%劣化することを覚悟
- **採用前にデモ口座で1〜2ヶ月、シグナル通り執行できるか必ず検証**

---

## Phase 2: 日次シグナルダッシュボード + 自動化

毎朝、最新シグナルを表示する自動運用ダッシュボード。

### 出力ファイル

- `output/index.html` — メインダッシュボード（朝開く）
  - 今日のシグナルカード（IFDOCO設定値付き）
  - 保有中ポジションの含み損益・進捗バー
  - タコメーター類（リスク・勝率・最大DD）
  - 直近トレード履歴
- `output/workflow.html` — 1日の運用イメージ（タイムライン+ゲージ）
- `output/daily_state.json` — JSON状態ファイル
- `.github/workflows/daily.yml` — 毎朝07:30 JST自動実行

### Mac で手動実行（テスト用）

```bash
cd "/Users/kiriano/Desktop/ぎぺり/爆益計画"
python3 src/generate_daily.py
open output/index.html
```

### 環境変数（運用カスタマイズ）

```bash
export FX_ACCOUNT_BALANCE=100000   # 口座残高（円）
export FX_RISK_PCT=0.02            # 1トレードのリスク%（標準2%）
export FX_MAX_LEVERAGE=20          # 最大レバ
export DISCORD_WEBHOOK_URL=...     # Discord通知（任意）
export LINE_NOTIFY_TOKEN=...       # LINE通知（任意・LINE Notifyは終了済み）
```

### GitHub + Render セットアップ手順

#### 1. GitHubリポジトリ作成

```bash
cd "/Users/kiriano/Desktop/ぎぺり/爆益計画"
git init
git add .
git commit -m "Initial commit: FX signal system"
gh repo create fx-signal --private --source=. --remote=origin --push
# または手動で github.com で作成して git push
```

#### 2. GitHub Actions Variables / Secrets 設定

Settings → Secrets and variables → Actions

**Variables**（公開可能な値）:
- `FX_ACCOUNT_BALANCE` = `100000`
- `FX_RISK_PCT` = `0.02`
- `FX_MAX_LEVERAGE` = `20`

**Secrets**（秘密情報）:
- `DISCORD_WEBHOOK_URL` = Discord で「サーバ設定→連携サービス→Webhook作成」
- `LINE_NOTIFY_TOKEN` = （オプション）

#### 3. Render Static Site 設定

1. render.com で「New +」→「Static Site」
2. GitHub リポジトリを連携
3. Build Command: 空欄
4. Publish Directory: `output`
5. Auto-deploy on commit: ON

これで毎朝07:30 JST に：
- GitHub Actions が起動
- yfinance から最新データ取得
- シグナル計算
- HTML 生成・コミット
- Render が自動デプロイ
- Discord/LINE に通知（シグナル発火時のみ）

### 通知の仕組み

LINE Notify は2025年3月でサービス終了したため、Discord webhookが推奨：

1. Discordサーバを作成（または既存サーバを使う）
2. チャンネル設定 → 連携サービス → ウェブフックを作成
3. URLをコピー → GitHub Actions Secrets に `DISCORD_WEBHOOK_URL` で登録

これで毎朝、シグナル発火時にDiscordに通知が飛びます。スマホアプリで見られます。

### 運用ルール（重要）

- ✅ シグナル通り淡々と発注する（裁量介入しない）
- ✅ SL/TPは絶対に動かさない
- ✅ 5連敗したら一時停止してルール再検証
- ✅ デモ口座で1〜2ヶ月先行検証してから実弾投入
- ❌ シグナルが出てないのに自分で売買する
- ❌ 「今日の感覚」で見送る、サイズを変える
- ❌ 失っても困る金額を投入する
