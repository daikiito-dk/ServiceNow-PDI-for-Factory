# ServiceNow-PDI-for-Factory

[English](#english) | [日本語](#日本語)

## English

A development repository for a financial application built on a ServiceNow PDI (Personal Developer Instance).
The app was created in ServiceNow Studio. This repository is its source of truth: changes are written here,
applied to the instance through the REST API, and verified with automated tests.

The app is **Loan Pre-Screening Management** (scope `x_2221323_loan_p_0`).

### Repository layout

```
ServiceNow-PDI-for-Factory/
├── README.md            # This file
├── AGENTS.md            # Development rules for agents (Factory Droid)
├── .factory/skills/servicenow-change/ # Standard procedure for making changes (Skill)
├── app/
│   └── phase1/          # Record definitions (manifest.json) and scripts applied to the PDI
├── tests/scenarios/     # Role-based regression test scenarios
├── scripts/
│   ├── sn_client.py     # Shared API client (Basic auth or browser session)
│   ├── snow_api.py      # Basic helpers such as loading .env
│   ├── setup_users.py   # Creates the integration user and test users (idempotent)
│   ├── inspect_app.py   # Takes a snapshot of the app configuration and generates a report
│   ├── snapshot_via_browser.py # Takes the snapshot through a logged-in browser session (no password)
│   ├── apply_records.py # Applies manifest.json records to the PDI in the app scope (idempotent)
│   └── run_tests.py     # Runs tests/scenarios as each role's user (exit code 1 on failure)
├── update-sets/         # Update Sets / application XML exported from ServiceNow
├── docs/                # Design documents and specifications
│   ├── app-design.md    # App design (maintained by hand)
│   ├── app-snapshot.json # Raw app configuration (generated, for tracking diffs)
│   └── app-inventory.md  # App configuration overview (generated, human-readable)
└── .gitignore           # Excludes .env (connection details) and other local files
```

### Setup

1. Create `.env` in the repository root (not tracked by Git):

   ```
   SN_INSTANCE=dev274447.service-now.com
   SN_APP_SYS_ID=<sys_id of the Studio app (sys_app)>
   ```

   User credentials such as `SN_USER` / `SN_PASSWORD` are added by `scripts/setup_users.py`.

2. Fetch the app configuration:

   ```
   python3 scripts/inspect_app.py
   ```

   This writes the app configuration on the PDI (tables, fields, business rules, ACLs, flows, and so on)
   to `docs/app-snapshot.json` (raw data) and `docs/app-inventory.md` (overview).
   Run it again after changing the PDI and use `git diff` to see what changed.

   To regenerate only the report (no API access needed):

   ```
   python3 scripts/inspect_app.py --report-only
   ```

   If Basic auth is not available (for example, you do not want a password in a file),
   log in to ServiceNow in a browser and run the command below. If you are logged in through
   Factory's embedded browser pane, it is used automatically and no password is needed:

   ```
   python3 scripts/snapshot_via_browser.py
   ```

### Applying changes from the repository to the PDI

```
python3 scripts/apply_records.py app/phase1/manifest.json
```

- Before applying, the script switches the session's current application to the target app.
  The Table API ignores the `sys_scope` in the request and uses the session's current application,
  so without this switch records would be created in the global scope.
- If a record matches `lookup`, it is updated; otherwise it is created. Running it again gives the same result.
- After applying, run the tests and take a new snapshot, then check the changes with `git diff`.

### Integration user and tests

```
python3 scripts/setup_users.py   # First time only. Run while logged in as admin in the browser
python3 scripts/run_tests.py     # Role-based regression tests
```

- `setup_users.py` creates the integration user `svc_factory_droid` and the test users
  `test_loan_applicant` / `test_loan_underwriter`, and saves their passwords to `.env` without printing them.
- The instance restricts Basic auth, so every user that calls the API has the `snc_basic_auth_api_access` role.
- Creating or changing ACLs (`sys_security_acl`) requires elevating to `security_admin`. The integration user
  does not have this role. Elevate in the browser, temporarily add `SN_TRANSPORT=browser` to `.env`,
  and run `apply_records.py`.

### Development workflow

1. Change the manifests and scripts under `app/` and apply them to the PDI with `apply_records.py`
   (see `AGENTS.md` and `.factory/skills/servicenow-change/SKILL.md` for details)
2. Test with `python3 scripts/run_tests.py`, take a snapshot with `python3 scripts/inspect_app.py`,
   and review the changes with `git diff`
3. For larger changes, also export an Update Set (or application XML), save the XML file to `update-sets/`, and commit it
4. Plan the next development task

### Exporting the app (scoped application)

#### Option A: Application XML (the whole app at once)

1. Open ServiceNow Studio and select the app
2. Right-click the app name in the "Application" panel at the bottom left
3. Select "Export application to XML"
4. Put the downloaded XML in `update-sets/`

#### Option B: Update Set XML (per change)

1. Filter Navigator > "System Update Sets" > "Update Sets"
2. Set the Update Set to "Complete"
3. From the context menu, select "Export to XML"
4. Put the downloaded XML in `update-sets/`

### Notes

- **This repository is public.** Before committing, check that exported XML contains no personal or real data.
- Keep instance connection details (URL, user, password) in `.env` and out of Git (already excluded by `.gitignore`).

## 日本語

ServiceNow PDI(個人開発インスタンス)で開発する金融系アプリケーションの開発リポジトリ。
ServiceNow Studio で作成したアプリをこのリポジトリでバージョン管理し、開発を進める。

### リポジトリ構成

```
ServiceNow-PDI-for-Factory/
├── README.md            # このファイル
├── AGENTS.md            # エージェント(Factory Droid)向けの開発ルール
├── .factory/skills/servicenow-change/ # 変更作業の標準手順(Skill)
├── app/
│   └── phase1/          # PDIに適用するレコード定義(manifest.json)とスクリプト本体
├── tests/scenarios/     # ロール別の回帰テストシナリオ
├── scripts/
│   ├── sn_client.py     # API共通クライアント(Basic認証 / ブラウザセッション)
│   ├── snow_api.py      # .env 読込などの基本ヘルパー
│   ├── setup_users.py   # 連携ユーザー・テストユーザーの作成(べき等)
│   ├── inspect_app.py   # アプリ構成スナップショット取得・レポート生成
│   ├── snapshot_via_browser.py # ブラウザセッション経由のスナップショット取得(PW不要)
│   ├── apply_records.py # manifest.json のレコードをアプリのスコープでPDIに適用(べき等)
│   └── run_tests.py     # tests/scenarios をロール別ユーザーで実行(失敗時は終了コード1)
├── update-sets/         # ServiceNowからエクスポートしたUpdate Set / アプリケーションXML
├── docs/                # 設計ドキュメント・仕様
│   ├── app-design.md    # アプリ設計(手動で管理する設計書)
│   ├── app-snapshot.json # アプリ構成の生データ(自動生成・差分追跡用)
│   └── app-inventory.md  # アプリ構成一覧(自動生成・人が読む用)
└── .gitignore           # .env(接続情報)等の管理対象外ファイル
```

### セットアップ

1. リポジトリ直下に `.env` を作成(Git管理外):

   ```
   SN_INSTANCE=dev274447.service-now.com
   SN_APP_SYS_ID=<Studioアプリ(sys_app)のsys_id>
   ```

   `SN_USER` / `SN_PASSWORD` などのユーザー情報は `scripts/setup_users.py` が追記する。

2. アプリの構成を取得:

   ```
   python3 scripts/inspect_app.py
   ```

   PDI上のアプリ構成(テーブル・フィールド・ビジネスルール・ACL・フロー等)を
   `docs/app-snapshot.json`(生データ)と `docs/app-inventory.md`(一覧)に書き出す。
   PDI側で変更した後にもう一度実行すれば、git diff で変更箇所を確認できる。

   レポートだけ再生成する場合(API接続不要):

   ```
   python3 scripts/inspect_app.py --report-only
   ```

   Basic認証が使えない場合(パスワードをファイルに置きたくない等)は、
   ブラウザでServiceNowにログインした状態で以下を実行する
   (Factoryの埋め込みブラウザペインでログイン済みなら自動でそれを使う。
   パスワードの扱いは一切不要):

   ```
   python3 scripts/snapshot_via_browser.py
   ```

### リポジトリからPDIへの変更適用

ブラウザでServiceNowにログインした状態で実行する:

```
python3 scripts/apply_records.py app/phase1/manifest.json
```

- 適用前に、セッションの「現在のアプリ」を対象アプリに自動で切り替える。
  Table APIはリクエストで指定した `sys_scope` を無視し、セッションの現在のアプリで
  スコープを決めるため、この切り替えをしないとglobalスコープに作成されてしまう。
- `lookup` に一致するレコードがあれば更新し、なければ作成する。何度実行しても結果は同じ。
- 適用後は `python3 scripts/snapshot_via_browser.py` を実行し、`git diff` で差分を確認する。

### 連携ユーザーとテスト

```
python3 scripts/setup_users.py   # 初回のみ。ブラウザでadminログイン済みの状態で実行
python3 scripts/run_tests.py     # ロール別の回帰テスト
```

- `setup_users.py` は連携ユーザー `svc_factory_droid` と、テストユーザー
  `test_loan_applicant` / `test_loan_underwriter` を作成し、パスワードを `.env` に保存する(表示しない)。
- インスタンスでBasic認証制限が有効なため、APIを呼ぶユーザーには `snc_basic_auth_api_access` を付与している。
- ACL(`sys_security_acl`)の作成・変更には `security_admin` への昇格が必要。連携ユーザーには付与せず、
  ブラウザで昇格した後に `.env` に `SN_TRANSPORT=browser` を一時的に追加して `apply_records.py` を実行する。

### 開発ワークフロー

1. `app/` のマニフェストとスクリプトを変更し、`apply_records.py` でPDIに適用する
   (詳細は `AGENTS.md` と `.factory/skills/servicenow-change/SKILL.md`)
2. `python3 scripts/run_tests.py` でテストし、`python3 scripts/inspect_app.py` でスナップショットを取得して git diff で変更を確認
3. 大きな変更は Update Set(またはアプリケーションXML)としてもエクスポートし、
   XML ファイルを `update-sets/` に保存してコミットする
4. 次の開発タスクを計画する

### アプリのエクスポート手順(スコープドアプリの場合)

#### 方法A: アプリケーションXML(アプリ全体を一括で取得)

1. ServiceNow Studio を開き、対象アプリを選択
2. 左下の「Application」パネルでアプリ名を右クリック
3. 「アプリケーションXMLのエクスポート(Export application to XML)」を選択
4. ダウンロードされた XML を `update-sets/` に置く

#### 方法B: Update Set XML(変更単位で管理)

1. 「フィルターナビゲーター」>「System Update Sets」>「Update Sets」
2. 対象の Update Set を「完了(Complete)」にする
3. コンテキストメニューから「XMLとしてエクスポート(Export to XML)」
4. ダウンロードされた XML を `update-sets/` に置く

### 注意事項

- **このリポジトリは公開(public)設定**。エクスポートXMLに個人情報や実データが
  含まれていないか、コミット前に必ず確認すること。
- インスタンスの接続情報(URL・ユーザー・パスワード)は `.env` に書き、
  Git管理下に置かないこと(`.gitignore` で除外済み)。
