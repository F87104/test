# 志マッチ（Mission Match）MVP 仕様書

このドキュメントは、既存の学習コミュニティ基盤に
「同じ志を持つメンバーを見つけて、実行チームを作る」機能を追加するための
実装向け仕様です。

---

## 1. 目的

- 学習継続率を上げる（孤独学習の離脱を減らす）
- 同志の自動発見で、行動の初速を上げる
- 個人成果だけでなく、チーム成果を生む

---

## 2. MVP スコープ

### 2.1 MVPでやること

1. 志プロフィール入力
2. マッチ候補提案（上位3名）
3. 1クリックでマッチ申請
4. 2〜4人のミッションチーム作成
5. チーム週次ミッション完了でボーナスポイント付与（手動運用可）

### 2.2 MVPでやらないこと（後続）

- 企業案件との自動接続
- チャット/通話の内蔵
- 複雑なAI推薦（まずはルールベース）
- マルチ言語化

---

## 3. 画面ワイヤー（テキスト）

## 3.1 志プロフィール画面 `/match/profile`

```
+--------------------------------------------------+
| 志プロフィール                                   |
+--------------------------------------------------+
| やりたいテーマ [教育, AI, SNS, ...]             |
| 3ヶ月目標    [入力欄]                            |
| 週の稼働時間  [1-3h / 3-5h / 5h+]               |
| 提供できる役割 [企画 / 開発 / デザイン / 営業]   |
| 欲しい役割    [企画 / 開発 / デザイン / 営業]   |
| 行動スタイル  [毎日コツコツ / 週末集中]         |
| [保存する]                                       |
+--------------------------------------------------+
```

---

## 3.2 マッチ候補画面 `/match/candidates`

```
+--------------------------------------------------+
| 今週のマッチ候補（上位3）                        |
+--------------------------------------------------+
| 1. なっちゃん   総合 92点                         |
|   テーマ一致: 40 / 稼働一致: 20 / 補完: 32       |
|   [プロフィールを見る] [マッチ申請]              |
|                                                  |
| 2. るなちゃん   総合 86点                         |
|   ...                                             |
|                                                  |
| 3. かなちゃん   総合 81点                         |
|   ...                                             |
+--------------------------------------------------+
```

---

## 3.3 マッチ成立・チーム画面 `/match/team/:id`

```
+--------------------------------------------------+
| Team: Growth Sprint #12                          |
+--------------------------------------------------+
| メンバー: あなた / なっちゃん / るなちゃん       |
| 週次ミッション: LP草案を金曜までに公開            |
| 進捗: 2/3 完了                                    |
| [完了を報告]                                      |
|                                                  |
| 今週のチーム報酬: +30pt / 人                      |
+--------------------------------------------------+
```

---

## 4. DB設計（SQLite前提）

> 命名は既存テーブル（`snake_case`）に合わせる。

## 4.1 `member_profiles`

| カラム | 型 | 必須 | 説明 |
|---|---|---|---|
| id | INTEGER PK | ○ | プロフィールID |
| member_name | TEXT UNIQUE | ○ | メンバー名（既存members.name参照） |
| themes | TEXT | ○ | JSON配列 `["教育","AI"]` |
| goal_90d | TEXT | ○ | 3ヶ月目標 |
| weekly_capacity | TEXT | ○ | `low / mid / high` |
| offer_roles | TEXT | ○ | JSON配列 |
| seek_roles | TEXT | ○ | JSON配列 |
| work_style | TEXT | ○ | `daily / weekend` |
| updated_at | INTEGER | ○ | Unix ms |

---

## 4.2 `match_scores`

| カラム | 型 | 必須 | 説明 |
|---|---|---|---|
| id | INTEGER PK | ○ | スコアID |
| source_member_name | TEXT | ○ | 提案元 |
| target_member_name | TEXT | ○ | 提案先 |
| total_score | INTEGER | ○ | 総合0-100 |
| theme_score | INTEGER | ○ | テーマ一致 |
| capacity_score | INTEGER | ○ | 稼働一致 |
| complement_score | INTEGER | ○ | 役割補完 |
| generated_at | INTEGER | ○ | 生成時刻 |

UNIQUE: `(source_member_name, target_member_name, generated_at)`

---

## 4.3 `match_requests`

| カラム | 型 | 必須 | 説明 |
|---|---|---|---|
| id | INTEGER PK | ○ | 申請ID |
| from_member_name | TEXT | ○ | 申請者 |
| to_member_name | TEXT | ○ | 申請先 |
| status | TEXT | ○ | `pending/accepted/rejected/cancelled` |
| created_at | INTEGER | ○ | 作成時刻 |
| updated_at | INTEGER | ○ | 更新時刻 |

---

## 4.4 `mission_teams`

| カラム | 型 | 必須 | 説明 |
|---|---|---|---|
| id | INTEGER PK | ○ | チームID |
| team_name | TEXT | ○ | 例: Growth Sprint #12 |
| mission_title | TEXT | ○ | 今週ミッション |
| mission_deadline | INTEGER | ○ | 期限 |
| status | TEXT | ○ | `active/completed/archived` |
| created_at | INTEGER | ○ | 作成時刻 |

---

## 4.5 `mission_team_members`

| カラム | 型 | 必須 | 説明 |
|---|---|---|---|
| id | INTEGER PK | ○ | 行ID |
| team_id | INTEGER | ○ | `mission_teams.id` |
| member_name | TEXT | ○ | メンバー |
| role_in_team | TEXT | - | 役割任意 |
| joined_at | INTEGER | ○ | 参加時刻 |

UNIQUE: `(team_id, member_name)`

---

## 4.6 `mission_reports`

| カラム | 型 | 必須 | 説明 |
|---|---|---|---|
| id | INTEGER PK | ○ | 報告ID |
| team_id | INTEGER | ○ | チームID |
| member_name | TEXT | ○ | 報告者 |
| status | TEXT | ○ | `done / blocked` |
| note | TEXT | - | コメント |
| created_at | INTEGER | ○ | 報告時刻 |

---

## 5. API設計（MVP）

## 5.1 プロフィール

- `GET /api/match/profile/me`
  - 自分の志プロフィール取得
- `PUT /api/match/profile/me`
  - 志プロフィール更新

### `PUT` リクエスト例
```json
{
  "themes": ["教育", "AI"],
  "goal90d": "3ヶ月で初受注を達成",
  "weeklyCapacity": "mid",
  "offerRoles": ["開発"],
  "seekRoles": ["企画", "営業"],
  "workStyle": "daily"
}
```

---

## 5.2 候補提案

- `GET /api/match/candidates?limit=3`
  - 推薦候補を返す（ルールベース計算）

### レスポンス例
```json
{
  "generatedAt": 1760000000000,
  "candidates": [
    {
      "memberName": "なっちゃん",
      "totalScore": 92,
      "scoreBreakdown": {
        "themeScore": 40,
        "capacityScore": 20,
        "complementScore": 32
      }
    }
  ]
}
```

---

## 5.3 マッチ申請

- `POST /api/match/requests`
  - マッチ申請を送る
- `GET /api/match/requests/inbox`
  - 自分への申請一覧
- `POST /api/match/requests/:id/accept`
  - 承認
- `POST /api/match/requests/:id/reject`
  - 拒否

> 承認時、2人以上揃えば `mission_teams` を生成して `teamId` を返す。

---

## 5.4 チーム運用

- `GET /api/match/teams/me`
  - 所属チーム一覧
- `GET /api/match/teams/:teamId`
  - チーム詳細
- `POST /api/match/teams/:teamId/reports`
  - 進捗報告
- `POST /api/match/teams/:teamId/complete`
  - ミッション完了（mentor/admin）

---

## 6. スコアリング仕様（ルールベース）

総合100点:

- テーマ一致: 0〜40
- 稼働時間一致: 0〜20
- 役割補完: 0〜30
- 行動スタイル一致: 0〜10

`total = theme + capacity + complement + style`

### 補完ロジック（MVP）
- Aの`seek_roles` と Bの`offer_roles` の一致数
- Bの`seek_roles` と Aの`offer_roles` の一致数
- 双方向一致が高いほど高得点

---

## 7. 既存機能との連携

- 週間ランキングに `team` タブ追加（後続）
- ミッション完了時に `point_events` へ一括付与記録
  - reason: `チームミッション完了`
  - source: `team_mission`

---

## 8. 実装順（推奨）

1. DB migration（6テーブル追加）
2. `src/server/db.js` にCRUD追加
3. `src/server/services.js` にスコアリング関数追加
4. `src/server/app.js` に `/api/match/*` 追加
5. `app-client.js` にプロフィール/候補/申請UI追加
6. テスト追加（認可、バリデーション、主要フロー）

---

## 9. 受け入れ条件（MVP完了条件）

- プロフィール保存ができる
- 候補3名が表示される
- 申請→承認でチームが作られる
- ミッション完了でポイント付与が記録される
- 主要APIのテストが通る

