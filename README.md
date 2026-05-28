# メモ魔塾 ダッシュボード（フルスタック版）

本リポジトリは、学習コミュニティ向けゲーム化ダッシュボードを
**認証 / RBAC / API永続化 / リアルタイム / テスト / CI / 運用ダッシュボード**
まで含めて実装したものです。

## 主な機能

- 認証（JWT）
- 権限（RBAC）
  - `admin` / `mentor` / `member`
- ポイント付与 API（権限チェック付き）
- SQLite 永続化（members / events / reviews / users）
- Socket.IO リアルタイム配信
- 運用ダッシュボード（KPI + 監査ログ）
- 週間レビュー（スコア・評価・達成率）
- 志マッチ（プロフィール保存 / 候補提案 / チーム作成）
- 自動テスト（Vitest + Supertest）
- GitHub Actions CI

## すぐ試す

```bash
npm install
npm run dev
```

ブラウザで `http://localhost:3001` を開きます。

## サンプルログイン

- 管理者: `admin@example.com / admin1234`
- メンター: `mentor@example.com / mentor1234`
- メンバー: `member@example.com / member1234`

## 開発コマンド

- `npm run dev` - サーバ起動
- `npm run test` - テスト実行
- `npm run test:watch` - テストウォッチ

## API（抜粋）

- `POST /api/auth/login`
- `GET /api/me`
- `GET /api/state`
- `POST /api/points/award` (`admin` / `mentor`)
- `GET /api/ops/metrics` (`admin` / `mentor`)
- `GET /api/ops/audit` (`admin`)
- `GET /api/mission/profile`
- `PUT /api/mission/profile`
- `GET /api/mission/matches`
- `GET /api/mission/teams`
- `POST /api/mission/teams`
- `GET /api/learning/progress`
- `PUT /api/learning/progress`
- `DELETE /api/learning/progress`

## 補足

フロントエンドは `app-client.js` から API と Socket.IO に接続します。

## 開発途中経過の確認方法（新規）

改善フローと進捗を追いやすくするため、以下を運用します。

- `DEVELOPMENT_PROGRESS.md`
  - 時系列の改善履歴、現在地、進捗ログ
- `IMPLEMENTATION_BACKLOG.md`
  - 優先度つき実装チケット（todo/in_progress/blocked/done）

運用ルール:
1. 実装着手時にバックログを `in_progress` へ更新
2. 完了時に `done` へ更新し、`DEVELOPMENT_PROGRESS.md` に1行追記
3. 新課題はバックログに優先度つきで追加
