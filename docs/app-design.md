# アプリ設計書 — Loan Pre-Screening Management(融資事前審査管理)

> 本書はPDI上の実装(docs/app-snapshot.json / docs/app-inventory.md)を基に手動で管理する設計書。
> 自動生成の一覧は `docs/app-inventory.md` を参照(本書と矛盾する場合はスナップショットが正)。

## 1. 概要

| 項目 | 値 |
|---|---|
| アプリ名 | Loan Pre-Screening Management |
| スコープ | `x_2221323_loan_p_0` |
| バージョン | 1.0.0 |
| インスタンス | dev274447.service-now.com (PDI) |
| sys_id | `ea814ae7833f8310d9ffe270ceaad302` |

**用途**: 銀行・金融機関向けの融資事前審査リクエスト管理。営業担当者が融資事前審査申請を登録し、審査部門がリスク評価・承認判定を行う。融資希望金額1,000万円以上は二段階承認へルーティングする。

## 2. テーブル構成

### `x_2221323_loan_p_0_request`(融資事前審査リクエスト)

基底テーブル(継承なし)。監査(audit)設定は未確認。

| フィールド | ラベル | 型 | 必須 | 備考 |
|---|---|---|---|---|
| `number` | 申請番号 | string | - | 自動採番 `getNextObjNumberPadded()` |
| `customer_name` | 顧客名 | string | 必須 | |
| `requested_amount` | 融資希望金額 (JPY) | decimal | 必須 | 二段階承認の分岐点(1,000万円) |
| `annual_income` | 年収 (JPY) | decimal | - | 機微な個人情報(§5参照) |
| `credit_rating` | 信用格付 | choice | - | A / B / C / D |
| `purpose` | 資金使途 | choice | - | 住宅購入 / 事業資金 / マイカー / その他 |
| `status` | ステータス | choice | - | 既定「申請受付」。申請受付 → 審査中 → 条件付き承認 / 承認 / 否決 |
| `approver` | 審査部長(承認者) | reference → `sys_user` | - | 単一参照 |

## 3. ワークフロー / Flow

| フロー | 状態 | 内容 |
|---|---|---|
| 高額融資 二段階承認 (High-Value Loan Two-Stage Approval) | **active** | 融資希望金額1,000万円以上を二段階承認へルーティング。ノード構成は未取得(Studio / Flow Designerで確認要) |
| Test | inactive | テスト用と思われる。削除候補 |

現状、ステータス遷移を強制するサーバ側ロジック(ビジネスルール)は存在しない。

## 4. 画面・UI

- モジュール: **0件** — ServiceNowのナビゲーションから本アプリにたどり着けない(要追加)
- Workspace構成: 未取得(スナップショット対象外。UI Builder設定は別途確認要)
- クライアントスクリプト / UIポリシー / UIアクション: 0件
- フォームはStudio既定の自動生成レイアウト

## 5. セキュリティ

### ロール

| ロール | 説明 | 権限 |
|---|---|---|
| `loan_applicant` | Loan Applicant(営業担当者) | 作成・閲覧 |
| `loan_underwriter` | Loan Underwriter(審査担当者) | 作成・閲覧・更新・削除 |

### ACL(レコードレベル、type=record)

| 操作 | 許可ロール |
|---|---|
| read | loan_applicant, loan_underwriter |
| create | loan_applicant, loan_underwriter |
| write | loan_underwriter のみ |
| delete | loan_underwriter のみ |

### セキュリティ上のギャップ

- **フィールドレベルACLなし**: `annual_income`(年収)は営業担当にも見える。機微情報へのアクセス制御・マスキングが未対応
- **監査設定未確認**: 金融取引の証跡保全のため audit 有効化を推奨
- データ暗号化なし

## 6. 現状のギャップと開発候補(金融系アプリとして)

詳細はリポジトリの開発計画(ロードマップ)を参照。主な指摘:

1. 入力検証なし(金額0以下、年収の不整合等)
2. ステータス遷移の強制なし(受付→承認へ直接遷移可能)
3. 通知なし(申請受付・承認依頼・結果通知)
4. ナビゲーション・画面整備未完了
5. 与信計算ロジック(DSR等)なし
6. 二段階承認フローの詳細がリポジトリ上未記録(XMLエクスポートで保全を推奨)
