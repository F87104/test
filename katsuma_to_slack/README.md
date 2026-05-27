# 勝間和代メルマガ → Slack 学習Bot

毎朝 Gmail に届く勝間和代さんのメールマガジンを **Slack に自動投稿** し、
本文を読みっぱなしにしないために **「自分ごと化のワーク」** を一緒に投げます。
スレッドに自分の答えを返信して残すと、**1日後 / 3日後 / 7日後 / 30日後** に
角度を変えた **復習問い**（行動編 / 経過編 / 習慣化編 / 振り返り編）が
同じスレッドに届く、間隔反復学習用の小さな Bot です。

```
[Gmail]                       [この Bot]                      [Slack]
   メルマガ着信  ──→  ingest (cron)             ──→  本文を投稿（Block Kit）
                          │   ↓                         ↑↓ スレッドにワークを返信
                          │   ワーク生成（テンプレ / LLM）
                          │   ↓                         ↑
                          │   DB に保存
                          │   1d / 3d / 7d / 30d 後
                          └→ remind (cron)            ──→  振り返りの問いをスレッドへ
```

---

## ハイライト機能

- **本文 → Slack**: ヘッダー / 差出人 / 受信時刻 / 本文サマリ（先頭 280 字）を
  Block Kit で読みやすく投稿。
- **学習ワーク**: 投稿直後に「今日のワーク」をスレッドに分けて投稿。
  - `template` モード（既定・APIキー不要）
    - `Q1`: 3 行要約
    - `Q2`: 核心の主張に賛成 / 反対 / 保留＋根拠
    - `Q3`: **「もし自分が同じ状況なら、どう考え、どう行動しますか？」**
    - `Q4`: 24 時間以内に試せる最小の一歩
  - `llm` モード（OpenAI 互換 API）
    - 本文から **ケース別** の問いを 4〜5 個生成。状況依存の自分ごと化問いを必ず含める。
- **間隔反復の振り返り**: 1d / 3d / 7d / 30d ごとに *視点を変えた* 問いを送信。
  - **行動編（1日後）**: 一歩を踏み出せたか／違和感は何か
  - **経過編（3日後）**: 答えに差分が出たか／関連する出来事は
  - **習慣化編（1週間後）**: 習慣として残ったか／障害は何か
  - **振り返り編（1ヶ月後）**: 当時の自分と今の自分の差分は
  - 同時に **あの日のワークの問いも参照表示** して、当時の自分の答えと比較できる。

---

## 必要なもの

1. **Gmail のアプリパスワード**（2 段階認証 + アプリパスワード）
   - <https://myaccount.google.com/apppasswords>
   - 通常パスワードは Gmail IMAP で使えません。
2. **Slack の Incoming Webhook URL**（既に作成済みのもの）
   - スレッドに復習通知を投げたい場合は、追加で **Bot Token (`xoxb-…`)** と
     **チャンネルID (`C…`)** を設定。Bot に必要なスコープは
     `chat:write`, `chat:write.public`。
3. （任意）**OpenAI API キー** — `WORKSHEET_MODE=llm` でケース別ワークを生成したい場合のみ。
4. Python 3.10 以上

---

## セットアップ

```bash
cd katsuma_to_slack
python -m venv .venv && source .venv/bin/activate
pip install -e .

cp .env.example .env
# .env を開いて GMAIL_ADDRESS / GMAIL_APP_PASSWORD / SLACK_WEBHOOK_URL などを記入
```

`.env.example` の主な設定:

| 環境変数 | 説明 |
| --- | --- |
| `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` | Gmail IMAP ログイン用 |
| `KATSUMA_FROM` | メルマガ送信元アドレス（環境に合わせて要変更） |
| `KATSUMA_SUBJECT_CONTAINS` | 件名フィルタ（部分一致, 例: `勝間和代`） |
| `LOOKBACK_DAYS` | 何日前まで遡って Gmail を見るか（毎日 cron なら 2 で十分） |
| `SLACK_WEBHOOK_URL` | 既存の Incoming Webhook |
| `SLACK_BOT_TOKEN` / `SLACK_CHANNEL_ID` | 任意。スレッド通知 & permalink 取得に使う |
| `REVIEW_INTERVALS_DAYS` | 復習通知の間隔（既定: `1,3,7,30`） |
| `WORKSHEET_MODE` | `template`（既定 / API 不要）, `llm`, `off` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | `WORKSHEET_MODE=llm` のとき使用 |

---

## 使い方

```bash
# 新着メルマガを Gmail から取り込み Slack へ投稿（ワーク付き）
python -m katsuma_to_slack.cli ingest

# 期限が来た復習リマインダーを送る（interval ごとに違う問い）
python -m katsuma_to_slack.cli remind

# 上の 2 つを続けて実行（cron 用）
python -m katsuma_to_slack.cli run

# 取り込み済みメルマガ一覧
python -m katsuma_to_slack.cli list
```

### cron で毎朝動かす

例: 毎朝 7:30 に取り込み、8:00 に復習リマインダーを送る。

```cron
30 7 * * *  cd /path/to/katsuma_to_slack && /path/to/.venv/bin/python -m katsuma_to_slack.cli ingest >> /var/log/katsuma_ingest.log 2>&1
0  8 * * *  cd /path/to/katsuma_to_slack && /path/to/.venv/bin/python -m katsuma_to_slack.cli remind >> /var/log/katsuma_remind.log 2>&1
```

### systemd で動かす（任意）

`/etc/systemd/system/katsuma.service`:
```ini
[Unit]
Description=Katsuma mailmagazine to Slack
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/katsuma_to_slack
EnvironmentFile=/path/to/katsuma_to_slack/.env
ExecStart=/path/to/.venv/bin/python -m katsuma_to_slack.cli run
```
`/etc/systemd/system/katsuma.timer`:
```ini
[Unit]
Description=Run Katsuma bot every morning

[Timer]
OnCalendar=*-*-* 07:30:00
Persistent=true

[Install]
WantedBy=timers.target
```
```bash
sudo systemctl enable --now katsuma.timer
```

---

## Slack 上の学習フロー（ワーク機能あり）

### 朝（7:30）— ingest が動く

1. Slack に **メルマガ本文** が投稿される（要約 280 字 + 元メールヘッダ）。
2. 同じスレッドに **「:pencil: 今日のワーク」** が続けて投稿される。

```
:books: 勝間和代の毎日メルマガ #100
本文サマリ ...
─────────────────
└─ :pencil: 今日のワーク
   今日のテーマ: *習慣の力*
   > 本日のテーマは『習慣の力』。小さな一歩を…

   Q1. 今日のメルマガを「3行」で要約してください。
   Q2. 核心の主張は何だと思いますか？ 賛成・反対・保留と根拠を一つ。
   Q3. もし自分が同じ状況なら、どう考え、どう行動しますか？
   Q4. 24時間以内に試せる最小の一歩は何ですか？
```

3. あなたは **同じスレッドに返信** で答える（箇条書き OK）。

```
Q1. 習慣の力 / 核は反復 / 自分はどこで反復してる？
Q2. 賛成。続けることでスキルが複利化する経験あり
Q3. もし自分なら、朝5分の散歩から始める。続かないなら時間を朝食前に固定
Q4. 今日 21:00 に明日の散歩アラームをセット
```

### 翌朝（8:00）— remind が動く

スレッドに **「行動編（1日後）」** が届く：

```
:alarm_clock: 行動編（1日後）: 勝間和代の毎日メルマガ #100
<https://slack.example/p1|あの日のメルマガをもう一度開く>
─────────────────
振り返りの問い
Q1. 昨日のワークで決めた「最小の一歩」は実行できましたか？
Q2. やってみて気付いた小さな違和感や発見は何ですか？
Q3. 今日もう一回続けるとしたら、何を変えますか？

:books: あの日のワーク（参照用）
・今日のメルマガを「3行」で要約してください。
・もし自分が同じ状況なら、どう考え、どう行動しますか？
・24時間以内に試せる最小の一歩は何ですか？
```

3 日後 → **経過編**、7 日後 → **習慣化編**、30 日後 → **振り返り編**。
**毎回違う角度から自分の頭をひねるので、スレッドが読書日記になります。**

### おすすめの運用

- リアクションで分類: `:eyes: 後で読む` `:white_check_mark: 実行した` `:star: 重要`
- 1 ヶ月後の振り返りでスレッド全体を再読 → 思考の変化が見える化される

---

## 開発

```bash
pip install -e .
pip install pytest
pytest
```

ファイル構成:
```
katsuma_to_slack/
├── katsuma_to_slack/
│   ├── cli.py             # CLI エントリ
│   ├── config.py          # 環境変数 → Config
│   ├── gmail_client.py    # IMAP + メール本文抽出
│   ├── pipeline.py        # ingest / remind のオーケストレーション
│   ├── slack_client.py    # Webhook / chat.postMessage / Block Kit
│   ├── store.py           # SQLite (messages / reminders, ワークも保存)
│   └── worksheet.py       # テンプレ & LLM ワーク生成 + interval ごとの振り返り問い
├── tests/                 # pytest (30 ケース)
├── .env.example
├── pyproject.toml
└── requirements.txt
```

---

## トラブルシューティング

- **Gmail にログインできない**: アプリパスワードか? IMAP は Gmail 側の
  「すべての設定 → メール転送と POP/IMAP → IMAP を有効にする」がオン?
- **メルマガが取り込まれない**: `KATSUMA_FROM` が実際の送信元と一致しているか
  Gmail の元メールヘッダで確認。`KATSUMA_SUBJECT_CONTAINS` を緩めて試す。
- **Slack に投稿されない**: `python -m katsuma_to_slack.cli -v ingest` で
  詳細ログを出して `Slack 投稿失敗` の `error` を確認。
- **リマインダーがスレッドに刺さらない**: Incoming Webhook はスレッド指定が
  できません。`SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` を設定してください。
- **LLM ワークが効かない**: `WORKSHEET_MODE=llm` かつ `OPENAI_API_KEY` を設定。
  失敗時は自動で `template` モードにフォールバックします。
- **ワーク不要**: `WORKSHEET_MODE=off` にすれば本文だけが流れます。
