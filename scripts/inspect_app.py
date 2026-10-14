#!/usr/bin/env python3
"""ServiceNowスコープドアプリの構成スナップショットを取得し、レポートを生成する。

モード:
    python3 scripts/inspect_app.py                 # スナップショット取得 + レポート生成
    python3 scripts/inspect_app.py --report-only   # 既存スナップショットからレポート再生成(API不要)

オプション:
    --snapshot <path>   スナップショットJSONのパス(デフォルト docs/app-snapshot.json)
    --out <path>        レポート出力先(デフォルト docs/app-inventory.md)
    app_sys_id          アプリ(sys_app)のsys_id。省略時は .env の SN_APP_SYS_ID

出力:
    docs/app-snapshot.json  アプリ構成の生データ(gitで差分追跡可能)
    docs/app-inventory.md   自動生成される構成一覧(人が読む用。手で編集しない)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from snow_api import ApiError, load_env, request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SNAPSHOT = os.path.join(ROOT, "docs", "app-snapshot.json")
DEFAULT_REPORT = os.path.join(ROOT, "docs", "app-inventory.md")
PAGE_LIMIT = 1000

# (テーブル, 取得フィールド(None=全フィールド), 検索キー, 表示名)
TABLES = [
    ("sys_db_object",
     "sys_id,name,label,super_class,access,is_extendable",
     "sys_package", "テーブル"),
    ("sys_dictionary",
     "sys_id,name,element,column_label,internal_type,reference,max_length,mandatory,active,default_value,dependent_on_field",
     "sys_package", "フィールド"),
    ("sys_documentation",
     "sys_id,name,element,label,plural,language",
     "sys_package", "ラベル"),
    ("sys_choice",
     "sys_id,name,element,label,value,sequence,dependent_value,inactive",
     "sys_package", "選択肢"),
    ("sys_script",
     "sys_id,name,collection,when,condition,order,active,script,action",
     "sys_package", "ビジネスルール"),
    ("sys_script_client",
     None,
     "sys_package", "クライアントスクリプト"),
    ("sys_script_include",
     "sys_id,name,api_name,script,active,client_callable,access,description",
     "sys_package", "スクリプトインクルード"),
    ("sys_ui_action",
     "sys_id,name,table,condition,active,client,script,show_insert,show_update,order",
     "sys_package", "UIアクション"),
    ("sys_security_acl",
     "sys_id,name,operation,active,type,admin_overrides,advanced,condition,script,description",
     "sys_package", "ACL"),
    ("sys_security_acl_role",
     None,
     "sys_package", "ACLロール"),
    ("sys_user_role",
     "sys_id,name,suffix,description",
     "sys_package", "ロール"),
    ("sys_app_module",
     "sys_id,title,table,link,uri,query,order,active,roles",
     "sys_package", "モジュール"),
    ("sys_ui_page",
     None,
     "sys_package", "UIページ"),
    ("sys_ui_macro",
     None,
     "sys_package", "UIマクロ"),
    ("sysevent_email_action",
     None,
     "sys_package", "メール通知"),
    ("sys_properties",
     None,
     "sys_scope", "システムプロパティ"),
    ("sys_hub_flow",
     "sys_id,name,type,active,description",
     "sys_scope", "フロー"),
]


# ---------------------------------------------------------------- 取得系

def fetch_table_records(table, fields, key, app_id):
    """1テーブル分のレコードをページングしながら全件取得する。"""
    records = []
    offset = 0
    while True:
        query = (
            f"sysparm_query={key}={app_id}"
            f"&sysparm_limit={PAGE_LIMIT}&sysparm_order_by=sys_id&sysparm_offset={offset}"
        )
        if fields:
            query += f"&sysparm_fields={fields}"
        page = request("GET", f"/api/now/table/{table}", query).get("result", [])
        records.extend(page)
        if len(page) < PAGE_LIMIT:
            return records
        offset += PAGE_LIMIT


def build_glossary(tables):
    """スナップショット内の参照(sys_id)を人が読める名前に解決するための対応表。"""
    glossary = {"glide_objects": {}, "parent_tables": {}}

    # フィールド型(internal_type)の解決
    try:
        rows = request(
            "GET", "/api/now/table/sys_glide_object",
            "sysparm_fields=sys_id,name&sysparm_limit=1000&sysparm_order_by=sys_id",
        ).get("result", [])
        glossary["glide_objects"] = {r["sys_id"]: r.get("name", "") for r in rows}
    except ApiError as e:
        print(f"WARN: 型名(sys_glide_object)の取得に失敗: {e}")

    # 継承元テーブル(super_class)の解決(アプリ内テーブル以外)
    app_table_ids = {r.get("sys_id") for r in tables.get("sys_db_object", [])}
    parents = {
        r.get("super_class")
        for r in tables.get("sys_db_object", [])
        if r.get("super_class")
    }
    external = sorted(p for p in parents if p not in app_table_ids)
    if external:
        try:
            rows = request(
                "GET", "/api/now/table/sys_db_object",
                f"sysparm_query=sys_idIN{','.join(external)}&sysparm_fields=sys_id,name,label",
            ).get("result", [])
            glossary["parent_tables"] = {r["sys_id"]: r.get("name", "") for r in rows}
        except ApiError as e:
            print(f"WARN: 継承元テーブルの解決に失敗: {e}")
    return glossary


def fetch_app(app_id):
    """アプリ本体(sys_app)を取得。IDが別物の場合はヒントを出す。"""
    try:
        app = request(
            "GET", f"/api/now/table/sys_app/{app_id}",
            "sysparm_fields=sys_id,name,scope,version,active,short_description,sys_created_on,sys_updated_on",
        ).get("result", {})
    except ApiError as e:
        if "404" not in str(e):
            raise
        try:
            us = request(
                "GET", f"/api/now/table/sys_update_set/{app_id}",
                "sysparm_fields=sys_id,name,state",
            ).get("result", {})
        except ApiError:
            us = {}
        if us:
            sys.exit(
                f"ERROR: このsys_idはUpdate Set「{us.get('name')}」のIDです。"
                "Studioアプリ(sys_app)のsys_idを指定してください。"
            )
        sys.exit(
            "ERROR: アプリ(sys_app)が見つかりません。"
            "Studio > アプリ右クリック >「アプリケーションのsys_idをコピー」で確認してください。"
        )
    return app


def take_snapshot(app_id, instance):
    app = fetch_app(app_id)
    print(f"アプリ: {app.get('name')} (scope={app.get('scope')}, v{app.get('version')})")

    tables, errors, summary = {}, {}, {}
    for table, fields, key, label in TABLES:
        try:
            rows = fetch_table_records(table, fields, key, app_id)
        except ApiError as e:
            errors[table] = str(e)
            summary[label] = None
            print(f"  {label}({table}): 取得失敗 - {e}")
            continue
        tables[table] = rows
        summary[label] = len(rows)
        print(f"  {label}({table}): {len(rows)}件")

    glossary = build_glossary(tables)
    return {
        "instance": instance,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "app": app,
        "summary": summary,
        "tables": tables,
        "glossary": glossary,
        "errors": errors,
    }


# ---------------------------------------------------------------- レポート系

def fmt(value):
    if value is None or value == "":
        return "-"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def type_name(glossary, ref):
    return glossary.get("glide_objects", {}).get(ref, ref or "-")


def parent_name(glossary, tables, ref):
    if not ref:
        return "-"
    if ref in glossary.get("parent_tables", {}):
        return glossary["parent_tables"][ref]
    for row in tables.get("sys_db_object", []):
        if row.get("sys_id") == ref:
            return row.get("name", ref)
    return ref


def label_map(tables):
    """(テーブル, 要素) -> ラベル の対応表。日本語ラベル優先。"""
    docs = tables.get("sys_documentation", [])
    result = {}
    for row in sorted(docs, key=lambda r: r.get("language") == "ja"):  # jaを後勝ちに
        result[(row.get("name"), row.get("element"))] = row.get("label")
    return result


def render_report(snapshot, out_path):
    app = snapshot.get("app", {})
    tables = snapshot.get("tables", {})
    glossary = snapshot.get("glossary", {})
    labels = label_map(tables)
    lines = []
    add = lines.append

    add("# アプリ構成一覧(自動生成)")
    add("")
    add("> このファイルは `scripts/inspect_app.py` が自動生成します。手動で編集しないでください。")
    add("")
    add(f"- 生成日時(UTC): {snapshot.get('fetched_at', '-')}")
    add(f"- インスタンス: {snapshot.get('instance', '-')}")
    add(f"- アプリ: {fmt(app.get('name'))} (scope: `{fmt(app.get('scope'))}`, version: {fmt(app.get('version'))})")
    add("")

    # --- テーブル ---
    objs = tables.get("sys_db_object", [])
    add(f"## テーブル({len(objs)}件)")
    add("")
    if objs:
        add("| テーブル | ラベル | 継承元 |")
        add("|---|---|---|")
        for row in sorted(objs, key=lambda r: r.get("name", "")):
            add(f"| `{row.get('name')}` | {fmt(row.get('label'))} | "
                f"`{parent_name(glossary, tables, row.get('super_class'))}` |")
        add("")

    # --- フィールド ---
    dicts = tables.get("sys_dictionary", [])
    by_table = {}
    for row in dicts:
        by_table.setdefault(row.get("name"), []).append(row)
    add(f"## フィールド({len(dicts)}件)")
    add("")
    for table_name in sorted(by_table):
        rows = sorted(by_table[table_name], key=lambda r: r.get("element") or "")
        add(f"### `{table_name}`({len(rows)}件)")
        add("")
        add("| フィールド | ラベル | 型 | 必須 | 参照先 | 既定値 |")
        add("|---|---|---|---|---|---|")
        for row in rows:
            col_label = labels.get((table_name, row.get("element"))) or row.get("column_label")
            add(
                f"| `{fmt(row.get('element'))}` | {fmt(col_label)} | "
                f"{type_name(glossary, row.get('internal_type'))} | {fmt(row.get('mandatory'))} | "
                f"`{fmt(row.get('reference'))}` | {fmt(row.get('default_value'))} |"
            )
        add("")

    # --- 選択肢 ---
    choices = tables.get("sys_choice", [])
    add(f"## 選択肢リスト({len(choices)}件)")
    add("")
    for (table_name, element), rows in sorted(_group(choices).items()):
        add(f"- `{table_name}.{element}`: "
            + ", ".join(f"{r.get('value')}({r.get('label')})" for r in rows))
    add("")

    # --- ロジック系 ---
    def simple_section(title, table, columns):
        rows = tables.get(table, [])
        add(f"## {title}({len(rows)}件)")
        add("")
        if rows:
            add("| " + " | ".join(columns) + " |")
            add("|" + "---|" * len(columns))
            for row in sorted(rows, key=lambda r: str(r.get("name", ""))):
                cells = [
                    f"`{fmt(row.get(col))}`" if col in ("collection", "table", "name", "api_name")
                    else fmt(row.get(col))
                    for col in columns
                ]
                add("| " + " | ".join(cells) + " |")
        else:
            add("なし")
        add("")

    add("> スクリプト本文は `docs/app-snapshot.json` に含まれます。")
    add("")
    simple_section("ビジネスルール", "sys_script",
                   ["name", "collection", "when", "condition", "active"])
    simple_section("クライアントスクリプト", "sys_script_client",
                   ["name", "type", "table", "active"])
    simple_section("スクリプトインクルード", "sys_script_include",
                   ["name", "access", "client_callable", "active"])
    simple_section("UIアクション", "sys_ui_action",
                   ["name", "table", "client", "active"])

    # --- セキュリティ ---
    acls = tables.get("sys_security_acl", [])
    add(f"## ACL({len(acls)}件)")
    add("")
    if acls:
        add("| 対象 | 操作 | type | active | condition |")
        add("|---|---|---|---|---|")
        for row in sorted(acls, key=lambda r: str(r.get("name", ""))):
            add(f"| `{fmt(row.get('name'))}` | {fmt(row.get('operation'))} | "
                f"{fmt(row.get('type'))} | {fmt(row.get('active'))} | {fmt(row.get('condition'))} |")
        add("")
    roles = tables.get("sys_user_role", [])
    add(f"## アプリのロール({len(roles)}件)")
    add("")
    for row in sorted(roles, key=lambda r: str(r.get("name", ""))):
        add(f"- `{fmt(row.get('name'))}`: {fmt(row.get('description'))}")
    add("")

    # --- その他 ---
    add("## その他の構成要素")
    add("")
    flows = tables.get("sys_hub_flow", [])
    add(f"- フロー: {len(flows)}件")
    for row in sorted(flows, key=lambda r: str(r.get("name", ""))):
        add(f"  - {fmt(row.get('name'))} (type: {fmt(row.get('type'))}, active: {fmt(row.get('active'))})")
    for title, table in [("モジュール", "sys_app_module"), ("システムプロパティ", "sys_properties"),
                         ("UIページ", "sys_ui_page"), ("UIマクロ", "sys_ui_macro"),
                         ("メール通知", "sysevent_email_action")]:
        rows = tables.get(table, [])
        names = [str(r.get("name") or r.get("title") or "?") for r in rows]
        add(f"- {title}: {len(rows)}件" + (f" ({', '.join(names)})" if names else ""))
    add("")

    if snapshot.get("errors"):
        add("## 取得失敗テーブル")
        add("")
        for table, err in snapshot["errors"].items():
            add(f"- `{table}`: {err}")
        add("")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"レポート生成: {out_path}")


def _group(rows):
    grouped = {}
    for row in rows:
        key = (row.get("name"), row.get("element"))
        grouped.setdefault(key, []).append(row)
    for key in grouped:
        grouped[key].sort(key=lambda r: r.get("sequence") or 0)
    return grouped


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="ServiceNowスコープドアプリの構成スナップショット取得・レポート生成")
    parser.add_argument("--report-only", action="store_true",
                        help="APIに接続せず、既存スナップショットからレポートのみ再生成")
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT,
                        help=f"スナップショットJSONのパス(デフォルト: {DEFAULT_SNAPSHOT})")
    parser.add_argument("--out", default=DEFAULT_REPORT,
                        help=f"レポート出力先(デフォルト: {DEFAULT_REPORT})")
    parser.add_argument("app_sys_id", nargs="?",
                        help="アプリ(sys_app)のsys_id(省略時は .env の SN_APP_SYS_ID)")
    args = parser.parse_args()

    if args.report_only:
        if not os.path.exists(args.snapshot):
            sys.exit(f"ERROR: {args.snapshot} がありません。先にスナップショットを取得してください。")
        with open(args.snapshot, encoding="utf-8") as f:
            snapshot = json.load(f)
        render_report(snapshot, args.out)
        return

    try:
        env = load_env()
    except ApiError as e:
        sys.exit(f"ERROR: {e}")
    app_id = args.app_sys_id or env.get("SN_APP_SYS_ID")
    if not app_id:
        sys.exit("ERROR: .env に SN_APP_SYS_ID を設定するか、引数でsys_idを指定してください。")

    try:
        snapshot = take_snapshot(app_id, env.get("SN_INSTANCE", ""))
    except ApiError as e:
        sys.exit(f"ERROR: {e}")

    os.makedirs(os.path.dirname(args.snapshot), exist_ok=True)
    with open(args.snapshot, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"スナップショット保存: {args.snapshot}")
    render_report(snapshot, args.out)


if __name__ == "__main__":
    main()
