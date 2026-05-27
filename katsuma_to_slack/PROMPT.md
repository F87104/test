# 開発プロンプト: 「メルマガ → Slack 学習Bot（ワーク + 間隔反復リマインダー）」

このファイルは **他の AI コーディングアシスタントに丸ごとコピペで渡して、
本リポジトリの `katsuma_to_slack/` と同等のシステムをゼロから実装させる** ための
プロンプトです。

- **想定読者の AI**: ChatGPT / Claude / Cursor Composer / Codex CLI / Cline 等
- **想定タスク**: 新規リポジトリ or 既存リポジトリに `katsuma_to_slack/` を追加
- **使い方**:
  1. 下の `# === ここから AI に渡すプロンプト ===` 以下を **そのまま** AI に貼る
  2. 必要に応じて「件名フィルタは X にする」など差分だけ追加で指示する
- **言語**: 日本語の問い／英語の識別子 という前提で書いています

---

# === ここから AI に渡すプロンプト ===

あなたは熟練の Python アプリケーションエンジニアです。
これから **「Gmail に毎朝届く学習系メルマガを Slack に流して、自分ごと化のワークと
間隔反復の復習通知で学びを定着させる」** 小さなアプリを作ってもらいます。
私は既に Slack の Incoming Webhook を作成済みで、それを再利用したいです。

実装は **段階的に** 進めてください。各ステップで作業計画 → 必要なファイルを書く →
ローカルでテスト実行 → 失敗したら修正、を繰り返してください。
**README とテストは必ず最後まで仕上げる** こと。

---

## 1. ゴール

毎朝の生活の中に「読む → 自分ごと化する → 後日複数回振り返る」サイクルを
Slack だけで回せるようにする。**読みっぱなし**を解消することが最重要。

### 学習体験フロー（これが完成形）

```
[Gmail]                        [この Bot]                       [Slack]
  メルマガ着信   ──→  ingest (cron)               ──→  本文を投稿（Block Kit）
                          │   ↓                          ↑↓ スレッドに自分の答え
                          │   ワーク生成（テンプレ / LLM）       を返信
                          │   ↓
                          │   DB に保存
                          │   1d / 3d / 7d / 30d 後
                          └→ remind (cron)              ──→  振り返り問いをスレッドへ
```

具体的に Slack に流れるイメージ:

```
:books: 勝間和代の毎日メルマガ #100
本文サマリ ...
─────────────────────────
└─ :pencil: 今日のワーク
   今日のテーマ: *習慣の力*
   Q1. 今日のメルマガを「3行」で要約してください。
   Q2. 核心の主張に賛成・反対・保留？ 根拠を一つ。
   Q3. もし自分が同じ状況なら、どう考え、どう行動しますか？
   Q4. 24時間以内に試せる最小の一歩は？
   :arrow_right: スレッドに箇条書きで返信してください
```

翌朝には **同じスレッド** に `:alarm_clock: 行動編（1日後）` が届く。

---

## 2. 機能要件

### Must

1. **Gmail 取り込み**
   - IMAP + アプリパスワードでログイン
   - 件名・送信元・受信日でサーバーサイド検索（受信箱全件取得しない）
   - 日本語件名のヘッダーデコード（`make_header(decode_header(...))`）
   - `text/plain` を優先、なければ `text/html` を BeautifulSoup でテキスト化
   - 添付・`<script>`/`<style>` は除外
2. **Slack 投稿**
   - 既存の **Incoming Webhook URL** だけで動作可能（最低構成）
   - **任意で Bot Token (`xoxb-…`)** を設定できると、
     - `chat.postMessage` でスレッド指定（`thread_ts`）
     - `chat.getPermalink` で投稿リンク取得 → 復習通知に埋め込み
   - 投稿は Block Kit（ヘッダー / 差出人 / 受信時刻 / 本文サマリ / フッター）
3. **学習ワーク**（読みっぱなし防止の中核）
   - 投稿直後に **「今日のワーク」を別メッセージ**として出す
     - Bot Token があれば本文のスレッドに、なければ続けてチャンネルに
   - 2 モードを切替可能（`WORKSHEET_MODE` 環境変数）
     - `template`（既定・API キー不要）: 固定 4 問
       - 事実理解（3行要約）
       - 主張への賛否＋根拠
       - **「もし自分が同じ状況なら、どう考え、どう行動しますか？」**（必須）
       - 24時間以内に試せる最小の一歩
     - `llm`: OpenAI 互換 chat API でケース別の問いを 4〜5 個生成
       - JSON モード必須、失敗時は **黙って template にフォールバック**
     - `off`: ワーク投稿しない
4. **間隔反復リマインダー**
   - `REVIEW_INTERVALS_DAYS=1,3,7,30`（既定）で何日後に復習するか設定
   - 通知は interval ごとに **角度を変えた問い** を出す
     - 1日後: 行動編（最小の一歩はやれたか／違和感）
     - 3日後: 経過編（答えの差分／関連出来事）
     - 7日後: 習慣化編（残ったか／障害／続/変/捨）
     - 30日後: 振り返り編（自分の変化／読み返したら何が見えるか／1分要約）
   - 復習通知には **当時のワークの問いも参照表示** して比較できるように
   - Bot Token があれば元メッセージのスレッドに刺す
5. **永続化（SQLite）**
   - `messages` テーブル: メールごとに 1 行（`message_id` UNIQUE で重複防止）
   - `reminders` テーブル: 1 メール × 各 interval で 1 行、`(message_pk, interval_days)` UNIQUE
   - `due_reminders(now)` で「期限到来かつ未送信」のみ取得
   - **Slack 投稿成功してから DB に書く** / **送信成功してから sent_at を埋める**
     （途中失敗しても次回 cron で取り戻せる）
   - 既存 DB へのカラム追加は `PRAGMA table_info` で見て不在時のみ ALTER（idempotent）
6. **CLI**
   - `python -m <pkg>.cli ingest` 新着取り込み
   - `python -m <pkg>.cli remind` 期限到来分を通知
   - `python -m <pkg>.cli run` 上の 2 つを順に実行（cron 推奨）
   - `python -m <pkg>.cli list` 取り込み済み一覧
   - `--env-file` / `-v`（DEBUG ログ）オプション
7. **設定は `.env`**（`python-dotenv` で読み込み）

### Nice-to-have

- リアクション（`:fire:` 延長 / `:zzz:` 短縮）で interval を動的調整
- 未回答スレッドへの追い催促
- Notion / Obsidian 連携（ワーク + 自分の答えを書き出し）

---

## 3. 技術スタック

- Python 3.10+
- 外部依存は最小限:
  - `requests` (Slack / OpenAI HTTP)
  - `python-dotenv` (.env 読込)
  - `beautifulsoup4` (HTML → text)
  - `PyYAML` (将来の設定拡張用、必須ではない)
- DB: 標準ライブラリの `sqlite3`
- IMAP: 標準ライブラリの `imaplib`, `email`
- テスト: `pytest`
- LLM 呼び出しは **OpenAI 互換 API**（`base_url` を切替可能にして
  Azure OpenAI / OpenRouter / ローカル LLM でも使えるように）

---

## 4. プロジェクト構成（このとおりに作る）

```
katsuma_to_slack/
├── katsuma_to_slack/
│   ├── __init__.py
│   ├── cli.py               # argparse で ingest / remind / run / list
│   ├── config.py            # .env → Config dataclass + validate()
│   ├── gmail_client.py      # IMAP + 件名/送信者フィルタ + HTML フォールバック
│   ├── slack_client.py      # Webhook / chat.postMessage / Block Kit ビルダ
│   ├── store.py             # SQLite Store (messages / reminders) + マイグレーション
│   ├── worksheet.py         # Worksheet データクラス + Template/LLM Generator
│   │                        # + interval ごとの review_prompt_for()
│   └── pipeline.py          # ingest_new_mailmagazines / send_due_reminders
├── tests/
│   ├── test_config.py
│   ├── test_gmail_client.py
│   ├── test_slack_client.py
│   ├── test_store.py
│   ├── test_pipeline.py
│   └── test_worksheet.py
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md                # 日本語
```

`pyproject.toml` には `[project.scripts]` で `<pkg>-cli = "<pkg>.cli:main"` を登録する。

---

## 5. 環境変数（`.env.example` に書くもの）

| 変数名 | 説明 |
| --- | --- |
| `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` | IMAP ログイン情報（**必須**, アプリパスワード） |
| `GMAIL_IMAP_HOST` / `GMAIL_IMAP_PORT` / `GMAIL_MAILBOX` | 既定で OK |
| `KATSUMA_FROM` | メルマガの送信元（環境ごとに違う） |
| `KATSUMA_SUBJECT_CONTAINS` | 件名フィルタ（部分一致） |
| `LOOKBACK_DAYS` | Gmail を何日遡るか（既定 2） |
| `SLACK_WEBHOOK_URL` | 既存 Webhook（**必須**: これか Bot Token どちらか） |
| `SLACK_BOT_TOKEN` / `SLACK_CHANNEL_ID` | 任意。スレッド投稿 + permalink で必要 |
| `REVIEW_INTERVALS_DAYS` | 既定 `1,3,7,30` |
| `REMIND_HOUR` | cron 用メモ。プログラム内では未使用でよい |
| `WORKSHEET_MODE` | `template` / `llm` / `off` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` | LLM モードで使用 |
| `DB_PATH` | 既定 `./katsuma.sqlite3` |

`Config.validate()` で `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`,
（`SLACK_WEBHOOK_URL` または `SLACK_BOT_TOKEN+SLACK_CHANNEL_ID` のいずれか）
が無ければ **日本語のエラーメッセージで RuntimeError** を投げること。

---

## 6. データモデル

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,   -- 重複防止のキー
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    received_at TEXT NOT NULL,         -- ISO8601 UTC
    posted_at TEXT NOT NULL,
    slack_ts TEXT,                     -- スレッド親 ts
    slack_permalink TEXT,
    summary TEXT,
    worksheet TEXT                     -- Worksheet を JSON で保存
);

CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_pk INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    interval_days INTEGER NOT NULL,
    due_at TEXT NOT NULL,
    sent_at TEXT,                      -- NULL なら未送信
    UNIQUE(message_pk, interval_days)
);

CREATE INDEX idx_reminders_due
    ON reminders(due_at) WHERE sent_at IS NULL;
```

`Store` クラスで以下のメソッドを公開:
- `has_message(message_id)`
- `insert_message(*, message_id, subject, sender, received_at, posted_at,
   slack_ts, slack_permalink, summary, intervals_days, worksheet)`
- `due_reminders(now) -> List[ReminderRow]`（messages JOIN で `subject` /
  `slack_permalink` / `slack_ts` / `worksheet` も埋めて返す）
- `mark_reminder_sent(reminder_id, sent_at)`
- `list_messages(limit)`

時刻はすべて **timezone-aware UTC で保存**、Slack 表示時にだけ JST へ変換。

---

## 7. ワーク（Worksheet）仕様

```python
@dataclass
class Worksheet:
    case_summary: str
    questions: List[str]
    action_prompt: str
```

### Template モード（外部依存なし）

固定 4 問を返す。**Q3 には必ず**
「もし自分が同じ状況・テーマに直面したら、どう考え、どう行動しますか？」
の文言を含めること。`case_summary` は件名と本文先頭 280 文字を組み合わせる。

### LLM モード

OpenAI 互換 `/chat/completions` を `response_format={"type":"json_object"}`
で呼ぶ。`temperature` は 0.3〜0.5 程度。
システムプロンプトは下記スキーマで JSON だけ返させる:

```json
{
  "case_summary": "本文を 2〜3 行で要約 + 自分ごと化フック",
  "questions": [
    "事実理解（What）",
    "賛否+根拠（Why / Counter）",
    "自分の状況に置き換える問い（必ず『もしあなたが…なら』を含める）",
    "24時間以内の最小の一歩（Action）"
  ],
  "action_prompt": "1〜2文の取り組み促進メッセージ"
}
```

API エラー / JSON パース失敗時は `logger.warning` を出して **Template にフォールバック**。

### interval ごとの振り返り問い

```python
def review_prompt_for(interval_days: int) -> ReviewPrompt:
    """1d=行動編 / 3d=経過編 / 7d=習慣化編 / 30d=振り返り編。
    既知でない interval は最も近い既定にフォールバックし、
    label は『振り返り（{N}日後）』にする。
    """
```

各カテゴリに 3 問ずつ用意（実装例はコードで定義してよい）。

---

## 8. Slack Block Kit の組み立て

3 種類のビルダ関数を作る:

- `build_mailmagazine_blocks(subject, sender, received_at_str, summary)`
  - header → context(From/Received) → divider → section(本文) →
    divider → context（フッターでスレッド返信を促す）
- `build_worksheet_blocks(worksheet)`
  - header(`:pencil: 今日のワーク`) → section(case_summary) → divider →
    section(`*Q1.* … *Q2.* …` を改行で並べる) →
    context(`:arrow_right: action_prompt`) → context(答え方の例)
- `build_reminder_blocks(subject, interval_days, permalink, review, original_questions)`
  - header(`:alarm_clock: <label>: <subject>`) →
    section(リンク or 太字 subject) → divider →
    section(`*振り返りの問い*` + Q1, Q2, Q3) →
    context(`:books: あの日のワーク（参照用）` で `original_questions` を箇条書き) →
    context(`:speech_balloon: スレッドに追記してください`)

**いずれも 1 ブロック 3000 字制限を意識して切り詰める** こと（`text[:2800]+"…"` 程度）。

`SlackPoster.post_message(text, blocks, thread_ts)` は Bot Token があれば
`chat.postMessage`、なければ Webhook を使う **動的ディスパッチ**。
`supports_threading` プロパティで Bot Token+Channel が揃っているかを判定可能に。

Bot Token 経由の投稿後は `chat.getPermalink` を呼んで permalink を取得し、
失敗してもログ警告だけで処理は継続。

---

## 9. パイプラインの責務

### `ingest_new_mailmagazines(cfg, *, gmail, slack, store, generator, now)`

1. `cfg.validate()`
2. `since = now - timedelta(days=cfg.lookback_days)` で IMAP 検索
3. 各メールについて:
   - `matches_katsuma()` で念押しフィルタ
   - `store.has_message(message_id)` で重複チェック
   - 本文ブロックを Slack に投稿（**失敗したら DB に書かない**）
   - `generator.generate()` でワーク生成 → `worksheet.questions` があれば
     スレッド or チャンネルに投稿
   - `store.insert_message(..., intervals_days=cfg.review_intervals_days,
     worksheet=worksheet.to_json())`
4. 投稿できた件数を返す

### `send_due_reminders(cfg, *, slack, store, now)`

1. `due = store.due_reminders(now)`
2. 各リマインダーについて:
   - `review_prompt_for(r.interval_days)` を引く
   - `r.worksheet` があれば `Worksheet.from_json` で当時の問いを復元
   - `build_reminder_blocks(...)` で Block を組む
   - `slack.post_message(text, blocks, thread_ts=r.slack_ts)`
   - **送信成功時のみ** `store.mark_reminder_sent(r.id, now)`
3. 送れた件数を返す

依存は **コンストラクタ引数 / 関数引数で差し替え可能** にしてテスト容易性を確保する。

---

## 10. CLI 仕様

```bash
python -m katsuma_to_slack.cli [-v] [--env-file PATH] {ingest|remind|run|list}
```

- `--env-file` 指定時はそれを `load_dotenv` で読み、無ければ CWD と
  プロジェクトルートの `.env` を順に探す
- `-v` で `logging.DEBUG`、それ以外は `INFO`
- ログフォーマットは `%(asctime)s %(levelname)-7s %(name)s | %(message)s`
- `list` は `--limit N` 引数あり（既定 20）

---

## 11. テスト要件（pytest, 全 30 件以上）

最低限カバーすべき観点:

1. **store**: 同一 `message_id` の二重 INSERT で UNIQUE 例外、
   `due_reminders(now)` が時間経過に応じて段階的に増える、
   `mark_reminder_sent` 後は再度返らない、
   既存DBに `worksheet` カラムが無くても起動できる（マイグレーション）
2. **gmail_client**: 日本語件名のデコード、`text/plain` 優先、
   `text/html` フォールバック（`<script>` 除去）、
   `matches_katsuma` の送信者・件名フィルタ
3. **slack_client**: Webhook 経由は `requests.post` の URL/JSON が正しい、
   API 経由は `chat.postMessage` + `chat.getPermalink` を呼ぶ、
   `ok=false` を伝播、`build_*_blocks` の出力に必須文言が含まれる、
   `supports_threading` の真偽
4. **worksheet**: Template が必ず Q3 に「もし自分が同じ状況」を含む、
   LLM が JSON を正しくパース、API 例外時に Template へフォールバック、
   `review_prompt_for(1)` が「行動編」、未知 interval は近似ラベル
5. **pipeline**: 重複メールはスキップ、フィルタ不一致もスキップ、
   ingest 後にワークがスレッドに投稿される（`thread_ts` 検証）、
   remind が interval ごとに違う文言を含む、
   Slack 失敗時はリマインダーが未送信のまま残る

外部 API（IMAP / Slack / OpenAI）は **本物に繋がない**。
`unittest.mock.MagicMock` か小さなフェイクオブジェクトで差し替える。

---

## 12. README に必ず書くこと（日本語）

- ASCII 図のシステム概要
- 学習体験フロー（朝の本文+ワーク → 自分の返信 → 翌朝の行動編 → …）の
  **具体的な Slack スレッド例**
- セットアップ（venv → `pip install -e .` → `.env` 作成）
- Gmail アプリパスワードの取り方リンク
- Slack 側の最小構成（Webhook のみ）と推奨構成（Bot Token 併用）
- cron 例（朝 7:30 ingest / 8:00 remind）
- systemd 例
- トラブルシューティング（IMAP / フィルタ / 投稿失敗 / LLM 失敗 / ワーク無効化）
- ファイル構成ツリー

---

## 13. 受け入れ基準（Definition of Done）

- [ ] `pytest` がローカルで全件 green（最低 30 件）
- [ ] `WORKSHEET_MODE=template` だけで（OpenAI キー無しで）ingest〜remind が
      動作する
- [ ] `WORKSHEET_MODE=llm` で OpenAI を呼び、API 失敗時に Template に
      フォールバックする
- [ ] Webhook のみ構成 / Bot Token 併用構成のどちらでも動く
- [ ] 同じメルマガが 2 回投稿されない（`message_id` UNIQUE）
- [ ] 復習通知が予定日に来て、`sent_at` が更新され、再送されない
- [ ] Slack 投稿失敗時、メールも reminder も「次回再試行できる状態」で残る
- [ ] README からコピペで cron に登録できる粒度の手順がある
- [ ] **コードコメントは "なぜそうしたか" だけ**。「インポートする」のような
      自明なコメントを書かない
- [ ] 関数の docstring は **日本語** でよい

---

## 14. 進め方の指示

1. まず **TODO リスト** を提示して、私が承認したら順番に着手して
2. 1 ステップ書いたら **すぐにテストを走らせて** 失敗を直す
3. 大きな設計判断（例: `pyproject.toml` を使うか `setup.py` か）は
   **最初に簡潔に説明** してから進める。途中での揺り戻しは避ける
4. 最後に
   - `git add -A && git commit -m "..."` の例
   - `cron` への登録例
   - 動作確認のための **ドライラン手順**（自分宛にテストメールを送って ingest を回す）
   を README にまとめる

それでは、**まず TODO リストを出してから実装を始めてください**。

# === ここまで AI に渡すプロンプト ===

---

## 補足: 派生プロジェクトを作るときのヒント

このプロンプトは「勝間和代さんのメルマガ」を例に書いていますが、
以下を差し替えれば他のメルマガ／日刊配信にもそのまま使えます。

| 差し替えポイント | 例 |
| --- | --- |
| `KATSUMA_FROM` の値 | `noreply@morning-news.example` |
| `KATSUMA_SUBJECT_CONTAINS` の値 | `今日の英単語`, `日経モーニング` |
| Template の Q3 文言 | 「もし自分の業務に当てはめるなら…」 |
| interval (`REVIEW_INTERVALS_DAYS`) | 語学なら `1,2,4,8,16` の Leitner 風 |
| LLM システムプロンプト | 「英文記事を読解する読者向けのワーク設計」など |

このとき、**ワークの Q3（自分ごと化）と interval ごとの異なる問い** の
2 点だけは外さないでください。これがこの仕組みの中核だからです。
