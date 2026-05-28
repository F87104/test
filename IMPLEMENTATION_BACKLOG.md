# 実装バックログ（優先度・状態管理）

最終更新: 2026-05-28

状態: `todo / in_progress / blocked / done`

---

## P0（先に解消しないと実装が不安定）

| ID | タイトル | 優先度 | 状態 | 依存 | 変更対象（予定） | DoD |
|---|---|---:|---|---|---|---|
| BLK-01 | client export不整合解消（`fetchReview`, `getAuthToken`） | P0 | done | なし | `src/shared/client.js`, `app-client.js` | フロント起動時にimportエラーが出ない |
| BLK-02 | チュートリアル開始ボタンID整合 | P0 | done | BLK-01 | `index.html`, `app-client.js` | 「使い方」ボタンでチュートリアルが開く |
| BLK-03 | `missionPanel` スクロール先ID整合 | P0 | done | BLK-01 | `index.html`, `app-client.js` | 「仲間を探す」でマッチセクションへ遷移する |
| BLK-04 | 重複DOM ID整理（`weeklyReviewUpdatedAt`） | P0 | done | なし | `index.html`, `app-client.js` | 更新対象DOMが一意で安定更新される |

---

## P1（事業価値を上げる実装）

| ID | タイトル | 優先度 | 状態 | 依存 | 変更対象（予定） | DoD |
|---|---|---:|---|---|---|---|
| CORE-01 | 学習進捗のサーバー永続化 | P1 | done | BLK-01 | `src/server/db.js`, `src/server/app.js`, `src/shared/client.js`, `app-client.js`, `tests/server.test.js` | 端末を変えても講義完了状態が保持される |
| CORE-02 | 報酬交換のサーバー永続化・検証 | P1 | todo | CORE-01 | 同上 + `services.js` | 不正なポイント消費がサーバー側で防止される |
| CORE-03 | Mission Match申請/承認フロー追加 | P1 | todo | BLK-03 | `db.js`, `services.js`, `app.js`, `app-client.js`, `tests/server.test.js` | 申請→承認→チーム化が成立する |
| CORE-04 | チームミッション完了時のボーナス付与 | P1 | todo | CORE-03 | `services.js`, `app.js`, `app-client.js`, `tests/server.test.js` | 完了イベントでpoint_eventsに記録される |

---

## P2（運用・品質・スケール）

| ID | タイトル | 優先度 | 状態 | 依存 | 変更対象（予定） | DoD |
|---|---|---:|---|---|---|---|
| OPS-01 | Socket認証をHTTPトークンと統合 | P2 | todo | BLK-01 | `src/server/index.js`, `src/shared/realtime.js` | 未認証Socket接続を拒否できる |
| OPS-02 | CORS/SECRETの本番安全設定 | P2 | todo | なし | `src/server/app.js`, `src/server/auth.js`, `README.md` | デフォルト危険設定に依存しない |
| OPS-03 | APIページング/期間指定（state/events） | P2 | todo | CORE-01 | `app.js`, `services.js`, `db.js`, `app-client.js`, `tests` | 大量データでも応答とUIが安定する |
| QA-01 | フロント統合テスト追加（主要導線） | P2 | todo | BLK-01〜04 | `tests/*` | ロビー/報酬/マッチ導線の回帰検知が可能 |

---

## 次の実装順（推奨）

1. BLK-01 → BLK-02 → BLK-03 → BLK-04  
2. CORE-01 → CORE-02  
3. CORE-03 → CORE-04  
4. OPS-01/OPS-02/OPS-03 → QA-01

