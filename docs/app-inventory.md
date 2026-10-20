# アプリ構成一覧(自動生成)

> このファイルは `scripts/inspect_app.py` が自動生成します。手動で編集しないでください。

- 生成日時(UTC): 2026-10-20T15:03:25.388255+00:00
- インスタンス: dev274447.service-now.com
- アプリ: Loan Pre-Screening Management (scope: `x_2221323_loan_p_0`, version: 1.0.0)

## テーブル(1件)

| テーブル | ラベル | 継承元 |
|---|---|---|
| `x_2221323_loan_p_0_request` | 融資事前審査リクエスト | `-` |

## フィールド(9件)

### `x_2221323_loan_p_0_request`(9件)

| フィールド | ラベル | 型 | 必須 | 参照先 | 既定値 |
|---|---|---|---|---|---|
| `-` | 融資事前審査リクエスト | collection | false | `-` | - |
| `annual_income` | 年収 (JPY) | decimal | false | `-` | - |
| `approver` | 審査部長 (承認者) | reference | false | `sys_user` | - |
| `credit_rating` | 信用格付 | choice | false | `-` | - |
| `customer_name` | 顧客名 | string | true | `-` | - |
| `number` | 申請番号 | string | false | `-` | javascript:getNextObjNumberPadded(); |
| `purpose` | 資金使途 | choice | false | `-` | - |
| `requested_amount` | 融資希望金額 (JPY) | decimal | true | `-` | - |
| `status` | ステータス | choice | false | `-` | received |

## 選択肢リスト(13件)

- `x_2221323_loan_p_0_request.credit_rating`: a(A), b(B), c(C), d(D)
- `x_2221323_loan_p_0_request.purpose`: home_purchase(住宅購入), business(事業資金), car(マイカー), other(その他)
- `x_2221323_loan_p_0_request.status`: received(申請受付), reviewing(審査中), conditional(条件付き承認), approved(承認), rejected(否決)

> スクリプト本文は `docs/app-snapshot.json` に含まれます。

## ビジネスルール(2件)

| name | collection | when | condition | active |
|---|---|---|---|---|
| `融資事前審査 ステータス遷移の強制` | `x_2221323_loan_p_0_request` | before | - | true |
| `融資事前審査 入力検証` | `x_2221323_loan_p_0_request` | before | - | true |

## クライアントスクリプト(0件)

なし

## スクリプトインクルード(0件)

なし

## UIアクション(0件)

なし

## ACL(4件)

| 対象 | 操作 | type | active | condition |
|---|---|---|---|---|
| `x_2221323_loan_p_0_request` | read | record | true | - |
| `x_2221323_loan_p_0_request` | write | record | true | - |
| `x_2221323_loan_p_0_request` | delete | record | true | - |
| `x_2221323_loan_p_0_request` | create | record | true | - |

## アプリのロール(2件)

- `x_2221323_loan_p_0.loan_applicant`: Loan Applicant (営業担当者) — can create and view loan pre-screening requests.
- `x_2221323_loan_p_0.loan_underwriter`: Loan Underwriter (審査担当者) — can review, edit, and decide on loan pre-screening requests.

## その他の構成要素

- フロー: 2件
  - Test (type: flow, active: false)
  - 高額融資 二段階承認 (High-Value Loan Two-Stage Approval) (type: flow, active: true)
- モジュール: 0件
- システムプロパティ: 1件 (x_2221323_loan_p_0.max_request_amount)
- UIページ: 0件
- UIマクロ: 0件
- メール通知: 0件
