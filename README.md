# ServiceNow-PDI-for-Factory

ServiceNow PDI(個人開発インスタンス)で開発する金融系アプリケーションの開発リポジトリ。
ServiceNow Studio で作成したアプリをこのリポジトリでバージョン管理し、開発を進める。

## リポジトリ構成

```
ServiceNow-PDI-for-Factory/
├── README.md            # このファイル
├── update-sets/         # ServiceNowからエクスポートしたUpdate Set / アプリケーションXML
├── docs/                # 設計ドキュメント・仕様
│   └── app-design.md    # アプリ設計(テーブル・フロー・画面の定義)
└── .gitignore           # .env(接続情報)等の管理対象外ファイル
```

## 開発ワークフロー

1. ServiceNow Studio でアプリに変更を加える
2. 変更を Update Set(またはアプリケーションXML)としてエクスポートする
3. XML ファイルを `update-sets/` に保存してコミットする
4. XML を解析して差分や構成を確認し、次の開発タスクを計画する

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
