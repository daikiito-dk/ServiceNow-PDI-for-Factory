# ServiceNow-PDI-for-Factory

ServiceNow PDI(個人開発インスタンス)で開発する金融系アプリケーションの開発リポジトリ。
ServiceNow Studio で作成したアプリをこのリポジトリでバージョン管理し、開発を進める。

## リポジトリ構成

```
ServiceNow-PDI-for-Factory/
├── README.md            # このファイル
├── scripts/
│   ├── snow_api.py      # ServiceNow REST APIヘルパー(認証は.envから読込)
│   ├── inspect_app.py   # アプリ構成スナップショット取得・レポート生成(Basic認証)
│   └── snapshot_via_browser.py # ブラウザセッション経由のスナップショット取得(PW不要)
├── update-sets/         # ServiceNowからエクスポートしたUpdate Set / アプリケーションXML
├── docs/                # 設計ドキュメント・仕様
│   ├── app-design.md    # アプリ設計(手動で管理する設計書)
│   ├── app-snapshot.json # アプリ構成の生データ(自動生成・差分追跡用)
│   └── app-inventory.md  # アプリ構成一覧(自動生成・人が読む用)
└── .gitignore           # .env(接続情報)等の管理対象外ファイル
```

## セットアップ

1. リポジトリ直下に `.env` を作成(Git管理外):

   ```
   SN_INSTANCE=dev274447.service-now.com
   SN_USER=admin
   SN_PASSWORD=<PDIの管理者パスワード>
   SN_APP_SYS_ID=<Studioアプリ(sys_app)のsys_id>
   ```

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

## 開発ワークフロー

1. ServiceNow Studio でアプリに変更を加える
2. `python3 scripts/inspect_app.py` でスナップショットを取得し、git diff で変更を確認
3. 大きな変更は Update Set(またはアプリケーションXML)としてもエクスポートし、
   XML ファイルを `update-sets/` に保存してコミットする
4. 次の開発タスクを計画する

## アプリのエクスポート手順(スコープドアプリの場合)

### 方法A: アプリケーションXML(アプリ全体を一括で取得)

1. ServiceNow Studio を開き、対象アプリを選択
2. 左下の「Application」パネルでアプリ名を右クリック
3. 「アプリケーションXMLのエクスポート(Export application to XML)」を選択
4. ダウンロードされた XML を `update-sets/` に置く

### 方法B: Update Set XML(変更単位で管理)

1. 「フィルターナビゲーター」>「System Update Sets」>「Update Sets」
2. 対象の Update Set を「完了(Complete)」にする
3. コンテキストメニューから「XMLとしてエクスポート(Export to XML)」
4. ダウンロードされた XML を `update-sets/` に置く

## 注意事項

- **このリポジトリは公開(public)設定**。エクスポートXMLに個人情報や実データが
  含まれていないか、コミット前に必ず確認すること。
- インスタンスの接続情報(URL・ユーザー・パスワード)は `.env` に書き、
  Git管理下に置かないこと(`.gitignore` で除外済み)。
