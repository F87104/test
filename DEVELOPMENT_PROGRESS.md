# アプリ開発 途中経過ログ（Progress Ledger）

最終更新: 2026-05-28

このファイルは、改善フローと現在地を「時系列」で把握するための記録です。  
実装を進めるたびに、`IMPLEMENTATION_BACKLOG.md` のステータス更新と合わせて更新します。

---

## 1) プロダクトの到達目標

- モバイル最優先のゲーム型学習コミュニティ
- 主要導線: ロビー（ホーム）/ クエスト / 報酬 / 講義 / マッチ
- 成果可視化: ポイント・ランキング・リーグ・週間レビュー
- 継続促進: チュートリアル、速報、仲間マッチング、報酬交換

---

## 2) 改善フロー（これまでの実装履歴）

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 0 | 事業コンセプト整理（教育×ゲーム化） | 完了 |
| Phase 1 | フロント中心モック（ランキング/速報/ポイントUI） | 完了 |
| Phase 2 | フルスタック化（Node/Express/SQLite/JWT/RBAC/Socket.IO） | 完了 |
| Phase 3 | Mission Match MVP（プロフィール/候補/チーム作成） | 完了 |
| Phase 4 | Pop Questテーマ適用、ロビー再設計、チュートリアル | 完了 |
| Phase 5 | RPG風UI強化（背景・スプライト・HUD調整） | 完了 |
| Phase 6 | 品質安定化（不整合解消/運用強化/機能仕上げ） | 進行中 |

---

## 3) 現在の実装スナップショット

### できていること
- API認証 / RBAC / ポイント付与 / state配信 / ops系API
- 週間レビュー算出ロジック
- 報酬交換UIと講義ロック解放
- Mission Match（プロフィール、候補提案、チーム作成）
- ロビー中心UI（モバイル寄り）

### 現在残っている主要不足
1. 報酬交換のサーバー永続化不足（現在はlocalStorage依存）
2. Mission Matchの申請/承認フロー未実装（チーム化導線の不足）
3. Socket認証の強化不足（HTTP認証との一貫性）

---

## 4) これからの進め方（見える化ルール）

### 更新ルール
- 実装開始時: `IMPLEMENTATION_BACKLOG.md` の対象チケットを `in_progress` に変更
- 実装完了時: 状態を `done` に変更し、ここに1行ログを追記
- 追加課題発見時: バックログへ新規チケット追加（優先度つき）

### ログ記録フォーマット
- `YYYY-MM-DD | チケットID | 変更概要 | 影響範囲 | 検証結果`

---

## 5) 進捗ログ

- 2026-05-28 | INIT | 進捗管理ファイルを新規作成 | ドキュメント | 以後このファイルを継続更新
- 2026-05-28 | BLK-01 | `fetchReview`, `getAuthToken` を client exports に追加 | `src/shared/client.js` | import不整合解消
- 2026-05-28 | BLK-02 | チュートリアル開始ボタンIDを `tutorialStartButton` に統一 | `app-client.js` | 「使い方」導線の配線復旧
- 2026-05-28 | BLK-03 | Mission Matchセクションに `id="missionPanel"` を追加 | `index.html` | ロビー導線からのスクロール先整合
- 2026-05-28 | BLK-04 | `weeklyReviewUpdatedAt` の重複IDを解消（片方を `insightUpdatedAt` へ変更） | `index.html` | DOM一意性確保
- 2026-05-28 | CORE-01 | 学習進捗をDB/APIで永続化（取得/保存/リセット） | `db.js`, `app.js`, `services.js`, `client.js`, `app-client.js`, `tests` | 端末を跨いでも講義完了状態を再現可能

