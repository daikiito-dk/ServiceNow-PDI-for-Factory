# AGENTS.md

ServiceNow PDI 上のスコープドアプリ「Loan Pre-Screening Management」(スコープ `x_2221323_loan_p_0`)を、
このリポジトリを正(source of truth)として開発・保守する。エージェントはこのファイルのルールに従うこと。

## 構成

- `app/<phase>/manifest.json` … PDI に適用するレコード定義。スクリプト本体は同じフォルダの `.js`
- `scripts/sn_client.py` … API 呼び出しの共通クライアント(Basic 認証 / ブラウザセッション)
- `scripts/apply_records.py` … マニフェストをアプリのスコープで適用(べき等)
- `scripts/inspect_app.py` … アプリ構成のスナップショット(`docs/app-snapshot.json`, `docs/app-inventory.md`)
- `scripts/run_tests.py` + `tests/scenarios/*.json` … ロール別の回帰テスト
- `scripts/setup_users.py` … 連携ユーザーとテストユーザーの作成(べき等)
- `docs/` … 設計書(`app-design.md`)、ロードマップ、自動生成の構成一覧

## 変更の手順(必ずこの順で)

1. 変更は PDI の画面ではなく、`app/` のマニフェストとスクリプトに書く
2. `python3 scripts/apply_records.py app/<phase>/manifest.json`
3. `python3 scripts/run_tests.py`(全件成功するまで完了にしない)。仕様を変えたらシナリオも追加・更新する
4. `python3 scripts/inspect_app.py` でスナップショットを更新し、`git diff docs/` で意図した差分だけか確認する
5. `docs/app-design.md` など関連ドキュメントを更新してからコミットする

## ServiceNow 固有の注意点

- **スコープ**: Table API はペイロードの `sys_scope` を無視し、セッションの「現在のアプリ」で決まる。
  作成前に `set_current_app()`(`PUT /api/now/ui/concoursepicker/application`)を呼ぶ。
  `apply_records.py` は自動で切り替え、結果のスコープも検証する。global に作られたら手で削除して再実行する
- **GlideElement**: 空でも truthy なので `String(current.field)` や `.nil()` で判定する
- **ロール名**: スコープ付きの完全名を使う(例: `x_2221323_loan_p_0.loan_underwriter`)
- **ビジネスルール**: スクリプトを使う場合は `advanced: true` が必要
- **フィールド単位の ACL**: `<table>.*` の create ACL がないと、作成時の入力値が write ACL で判定され、
  権限のないフィールドの値は黙って捨てられる
- **ACL の作成・変更には `security_admin` への昇格が必要**。連携ユーザーには付与していない。
  ACL を含むマニフェストは、人がブラウザで「Elevate role → security_admin」を行った後に
  `SN_TRANSPORT=browser` で適用する。昇格が必要になったら作業を止めてユーザーに依頼する
- **Basic 認証**: インスタンスで Basic 認証制限が有効。API を呼ぶユーザーには
  `snc_basic_auth_api_access` が必要(ないと admin でも 401)。人の `admin` アカウントには付与していない
- 認証失敗(401)を繰り返すとアカウントがロックされるため、同じ認証情報で何度も再試行しない
- PDI が休止中だと HTML が返る。developer.servicenow.com からの起動をユーザーに依頼する

## 秘密情報

- 接続情報とパスワードは `.env`(Git 管理外)にだけ置く。値を表示・ログ出力・コミットしない
- このリポジトリは public。エクスポート XML やスナップショットに実データが含まれていないか確認する
- テストデータは `TEST-` 接頭辞を付け、`run_tests.py` が最後に削除する

## 言語

- ドキュメント、コメント、ユーザーへの報告は日本語。コミットメッセージは英語(既存の履歴に合わせる)
- README.md は英語のセクションを先に、日本語のセクションを後に書く。片方を変更したらもう片方も同じ内容に更新する
