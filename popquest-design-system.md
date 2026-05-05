# Pop Quest Design System v1

本ドキュメントは、`popquest-*-v2.png` を実装へ落とし込むためのUI設計ガイドです。  
目的は「若者向けでワクワクするが、情報は読みやすい」体験の両立です。

## 1. デザインコンセプト

- コンセプト名: **Pop Quest**
- 体験方針:
  - タスク実行がゲームのクエストのように感じられる
  - 達成が視覚的に気持ちいい（チップ、色、カード）
  - 長時間見ても疲れない可読性

## 2. カラートークン

### Core

- `--pq-primary`: `#7A5CFF` (主要CTA、選択状態)
- `--pq-secondary`: `#FF5FA2` (強調、MVP、注目要素)
- `--pq-accent`: `#FFD84D` (報酬、達成、ハイライト)
- `--pq-mint`: `#53F2B2` (成功、進行、ポジティブ状態)
- `--pq-sky`: `#25D7FF` (情報通知、補助強調)

### Surface

- `--pq-bg-top`: `#FAF8FF`
- `--pq-bg-bottom`: `#FFEAF6`
- `--pq-surface`: `#FFFFFF`
- `--pq-surface-soft`: `#FFF9FF`
- `--pq-border`: `#EADFFF`

### Text

- `--pq-text`: `#3F376D`
- `--pq-text-muted`: `#8D84A7`
- `--pq-text-inverse`: `#FFFFFF`

## 3. タイポグラフィ

- 推奨フォント:
  - 見出し: `Noto Sans CJK JP Bold`
  - 本文: `Noto Sans CJK JP Regular`
- サイズ基準:
  - `h1`: 44px
  - `h2`: 34px
  - `body`: 30px（デザインモック基準、実装は 16-18px相当へスケール）
  - `caption`: 20-24px

## 4. コンポーネント仕様

### 4.1 Hero Header

- 背景: `primary -> secondary` グラデーション
- 角丸: 28px
- タイトル: 白、太字
- サブタイトル: 白（透明度を少し下げる）

### 4.2 Quest Card

- 背景: 白
- 境界線: `--pq-border`
- 角丸: 20-26px
- シャドウ: 弱め（実装時は `0 6px 18px rgba(122,92,255,0.12)`）

### 4.3 Status Chip

- 成功: ミント系
- 情報: スカイ系
- 報酬: イエロー系
- 角丸: 16-20px

### 4.4 CTA Button

- Primary: `--pq-primary`, 文字白
- Success: `--pq-mint`, 文字濃色
- 角丸: 18-24px
- 高さ: 56px以上（モバイル操作性）

### 4.5 Bottom Navigation

- 背景: `#20204A`
- 非アクティブ文字: `#CFD2DF`
- アクティブ文字: `#FFFFFF`

## 5. 画面別ルール

### Home

- 上部に「今日のミッション」固定表示
- 1タップで実行できる主CTAを最上段に配置
- マッチ候補は3件まで（迷わせない）

### Match

- 候補カードに「一致理由」を1-2行表示
- `いいね` ボタンはカード内左下に統一
- 画面最下部に「チーム作成」固定CTA

### Reward

- 交換可能ポイントは最上段チップで常時表示
- 各報酬カードに「必要pt」「交換条件」「結果」を明示

### Lecture

- 進捗バー + 完了本数を先頭に表示
- 講義カードは状態別に色分け
  - 完了: ミント
  - 未完了: 白
  - 解放済み: イエロー寄り

## 6. アイコン方針

- 線 + 塗りのミックス（過度に細くしない）
- 角丸を優先（尖りすぎない）
- 絵文字依存は避け、同系統アイコンへ移行

## 7. モーション方針（実装時）

- Duration: 160ms / 240ms / 320ms の3段階
- Easing: `cubic-bezier(0.2, 0.8, 0.2, 1)`
- 重要イベント:
  - 報酬交換成功
  - 講義解放
  - チーム作成完了

## 8. アクセシビリティ

- 文字コントラスト: WCAG AA以上
- ボタン最小タップ領域: 44px
- 色だけで状態を判別しない（文言ラベル併用）

## 9. 実装アセット

- `popquest-logo.png`
- `popquest-app-icon.png`
- `popquest-icon-set.png`
- `popquest-home-v2.png`
- `popquest-match-v2.png`
- `popquest-reward-v2.png`
- `popquest-lecture-v2.png`

