# 勝間和代メルマガ → Slack 学習Bot

毎朝 Gmail に届く勝間和代さんのメールマガジンを **Slack に自動投稿** し、
スレッドで自分の意見・気付きをメモして、**1日後 / 3日後 / 7日後 / 30日後** に
「もう一度読み返しましょう」という **復習リマインダー（間隔反復学習）** を
同じスレッドへ投げてくれる小さな Bot です。

```
[Gmail]                     [この Bot]                     [Slack]
  |  毎朝メルマガ着信  ──→  ingest (cron)            ──→  本文を投稿 (Block Kit)
                             |   ↓ DB に保存            ←──  自分の感想を返信
                             |   1d / 3d / 7d / 30d 後
                             └→ remind (cron)          ──→  スレッドに復習通知
```

---

## 必要なもの

1. **Gmail のアプリパスワード**（2 段階認証 + アプリパスワード）
   - <https://myaccount.google.com/apppasswords>
   - 通常パスワードは Gmail IMAP で使えません。
2. **Slack の Incoming Webhook URL**（既に作成済みのもの）
   - スレッドに復習通知を投げたい場合は、追加で **Bot Token (`xoxb-…`)** と
     **チャンネルID (`C…`)** を設定すると、メルマガ投稿の *スレッド内* に
     リマインダーが届くようになります。Bot に必要なスコープは
     `chat:write`, `chat:write.public` です。
3. Python 3.10 以上

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

---

## 使い方

```bash
# 新着メルマガを Gmail から取り込み Slack へ投稿
python -m katsuma_to_slack.cli ingest

# 期限が来た復習リマインダーを送る
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

## Slack 上での学習フロー

1. 朝、メルマガが Slack に投稿されます（件名 + 冒頭 280 文字の要約）。
2. 投稿の **スレッドに自分の感想・気付き・行動したいこと** を返信します。
   - 例:「今日の『習慣の力』、自分の朝ルーチンに XX を足してみる」
   - リアクションで `:eyes: 後で読む` `:white_check_mark: 実行した` `:star: 重要`
     のように分類するのもおすすめです（Slack 標準機能）。
3. 1 日 / 3 日 / 7 日 / 30 日後に、Bot が **同じスレッド** に復習通知を出します
   （Bot Token を入れていない場合はチャンネルへ直接投稿）。
4. リマインダーが来たら、もう一度メルマガとあなたの過去メモを読み返し、
   気付きの差分を返信して残します。これがそのまま「振り返り日記」になります。

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
│   ├── slack_client.py    # Webhook / chat.postMessage
│   └── store.py           # SQLite (messages / reminders)
├── tests/                 # pytest
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
