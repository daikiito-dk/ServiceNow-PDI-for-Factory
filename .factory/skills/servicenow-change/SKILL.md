---
name: servicenow-change
description: 融資事前審査アプリ(x_2221323_loan_p_0)に変更を加えるときの標準手順。ビジネスルール、プロパティ、ACL などを追加・修正し、PDI へ適用、ロール別テスト、スナップショット更新、ドキュメント更新までを一貫して行う。ServiceNow アプリの機能追加・不具合修正・設定変更を依頼されたときに使う。
---

# servicenow-change

リポジトリを正として ServiceNow アプリを変更する手順。ルールの詳細は `AGENTS.md` を参照。

## 0. チケットを読む(Jira)

- 対象チケットを Jira から取得する(プロジェクト **KAN**、`jira__get_issue` / `jira__search_issues`)。要件と受け入れ条件を確認する
- `docs/roadmap.md` の対応表でキーとフェーズの対応を確認する
- チケットが無い場合は、先にチケットを作るか既存チケットに追記するかをユーザーに確認する

## 1. 現状を把握する

- `docs/app-design.md`、`docs/app-inventory.md`、対象の `app/<phase>/manifest.json` を読む
- PDI 側が手で変更されていないか確認する:
  `python3 scripts/inspect_app.py` → `git diff docs/`。想定外の差分があれば先にユーザーへ報告する

## 2. 変更を書く

- レコードはマニフェストに追加する。`lookup` は既存レコードを一意に特定できるキーにする
- スクリプトは別ファイル(`.js`)にして `script_file` で参照する
- 参照は `__APP__`、`{{id:<key>}}`、`{{role:<ロール名>}}` プレースホルダーを使う(sys_id を直書きしない)
- 振る舞いを変えたら `tests/scenarios/` にケースを追加する(成功と拒否の両方、ロールごと)

## 3. 適用する

```
python3 scripts/apply_records.py app/<phase>/manifest.json
```

- ACL(`sys_security_acl` / `sys_security_acl_role`)を含む場合は 403 になる。
  ユーザーにブラウザで「Elevate role → security_admin」を依頼し、完了後に
  `.env` に `SN_TRANSPORT=browser` を一時的に追加して再実行する(終わったら行を削除)
- 401 が続く場合は再試行を止め、認証設定を確認する(アカウントロック防止)

## 4. 検証する

```
python3 scripts/run_tests.py
python3 scripts/inspect_app.py
git diff --stat docs/
```

- テストが全件成功するまで次へ進まない。失敗は原因(BR / ACL / テストの誤り)を切り分けて直す
- スナップショットの差分が今回の変更だけであることを確認する

## 5. 仕上げる

- `docs/app-design.md`(必要なら `docs/roadmap.md`)を更新する
- `git status` で `.env` 等の秘密情報が含まれていないことを確認してコミットする(メッセージに `KAN-<n>` を含める)
- push はユーザーの了承を得てから行う
- チケットに結果をコメントし、ステータスを更新する(着手中 = 進行中、完了 = 完了)。Jira への書き込みは実行前に内容を示して了承を得る
- 報告には「適用したレコード」「テスト結果(件数)」「スナップショット差分の要約」を含める
