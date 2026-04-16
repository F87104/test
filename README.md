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

## 補足

フロントエンドは `app-client.js` から API と Socket.IO に接続します。
