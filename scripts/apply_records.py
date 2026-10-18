#!/usr/bin/env python3
"""マニフェストで定義したレコードを、アプリのスコープで PDI に適用する(べき等)。

使い方:
    python3 scripts/apply_records.py app/phase1/manifest.json [app_sys_id]

通信は scripts/sn_client.py を使う(.env の連携ユーザーで Basic 認証。
SN_TRANSPORT=browser ならログイン済みブラウザ経由)。

マニフェスト形式(app/phase1/manifest.json 参照):
    {
      "records": [
        {
          "table": "sys_script",
          "lookup": {"name": "...", "collection": "...", "sys_scope": "__APP__"},  # 既存チェック用
          "fields": {...},                                  # 作成/更新する値
          "script_file": "br_xxx.js",                        # 省略可。マニフェストからの相対パス
          "script_fields": ["script"]                       # script_file の内容を入れる欄
        }
      ]
    }

    - "__APP__" は適用時にアプリ(sys_app)の sys_id に置換される
    - "id": "<key>" を付けたレコードの sys_id は、後続レコードで "{{id:<key>}}" として参照できる
    - "{{role:<ロール名>}}" はロールの sys_id に置換される
    - lookup に一致するレコードがあれば更新(PUT)、なければ作成(POST)
    - 適用後に各レコードのスコープを検証し、アプリ以外なら失敗にする

実行後は scripts/inspect_app.py でスナップショットを再取得し、git diff で差分を確認すること。
"""

import json
import os
import re
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sn_client import SnError, call, env, error_message, set_current_app  # noqa: E402


def query_string(lookup):
    return "^".join(f"{k}={quote(str(v), safe='')}" for k, v in lookup.items())


_role_ids = {}


def resolve(value, app_id, ids):
    """プレースホルダーを sys_id に置き換える。

    __APP__        アプリの sys_id
    {{id:<key>}}   同じマニフェスト内で "id": "<key>" を付けたレコードの sys_id
    {{role:<name>}} ロール名から引いた sys_user_role の sys_id
    """
    if not isinstance(value, str):
        return value
    value = value.replace("__APP__", app_id)
    for match in re.findall(r"\{\{(id|role):([^}]+)\}\}", value):
        kind, key = match
        if kind == "id":
            if key not in ids:
                raise SnError(f"{{{{id:{key}}}}} が未定義です(参照先のレコードを先に記述してください)")
            sys_id = ids[key]
        else:
            if key not in _role_ids:
                status, body = call("GET", f"/api/now/table/sys_user_role?sysparm_query=name={key}&sysparm_fields=sys_id")
                found = (body or {}).get("result") or []
                if status != 200 or not found:
                    raise SnError(f"ロール {key} が見つかりません")
                _role_ids[key] = found[0]["sys_id"]
            sys_id = _role_ids[key]
        value = value.replace(f"{{{{{kind}:{key}}}}}", sys_id)
    return value


def apply_record(record, app_id, manifest_dir, ids):
    table = record["table"]
    lookup = {k: resolve(str(v), app_id, ids) for k, v in record.get("lookup", {}).items()}
    fields = {k: resolve(v, app_id, ids) for k, v in record["fields"].items()}

    script_file = record.get("script_file")
    if script_file:
        with open(os.path.join(manifest_dir, script_file), encoding="utf-8") as f:
            code = f.read()
        for field in record.get("script_fields", ["script"]):
            fields[field] = code

    path = f"/api/now/table/{table}"
    status, body = call("GET", f"{path}?sysparm_query={query_string(lookup)}&sysparm_limit=1&sysparm_fields=sys_id")
    if status != 200:
        raise SnError(f"{table} の既存チェックに失敗: HTTP {status} {error_message(body)}")

    found = (body or {}).get("result") or []
    if found:
        sys_id = found[0]["sys_id"]
        status, body = call("PUT", f"{path}/{sys_id}?sysparm_exclude_reference_link=true", fields)
        action = "更新"
    else:
        status, body = call("POST", f"{path}?sysparm_exclude_reference_link=true", fields)
        action = "作成"
    if not 200 <= status < 300:
        raise SnError(f"{action}失敗: {table} {lookup} HTTP {status} {error_message(body)}")

    result = body["result"]
    # スコープ切替が効いていないと、エラーにならずに global に作成されてしまうため必ず検証する
    if result.get("sys_scope") != app_id:
        raise SnError(f"{table} {result.get('sys_id')} がアプリ外のスコープ({result.get('sys_scope')})に"
                      "作成されました。手動で削除してから再実行してください。")
    if record.get("id"):
        ids[record["id"]] = result["sys_id"]
    print(f"OK  {action}: {table} {record.get('id') or lookup} (sys_id={result['sys_id']}, HTTP {status})")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    manifest_path = sys.argv[1]
    app_id = sys.argv[2] if len(sys.argv) > 2 else env().get("SN_APP_SYS_ID")
    if not app_id:
        sys.exit("ERROR: .env の SN_APP_SYS_ID を設定するか、第2引数でアプリのsys_idを指定してください。")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    records = manifest.get("records", [])

    try:
        # Table API はペイロードの sys_scope を無視し、セッションの「現在のアプリ」でスコープを決める
        set_current_app(app_id)
        print(f"適用対象: {len(records)}件 (manifest={manifest_path})")
        ids = {}
        for record in records:
            apply_record(record, app_id, os.path.dirname(os.path.abspath(manifest_path)), ids)
    except SnError as e:
        sys.exit(f"ERROR: {e}")
    print("完了。スナップショットを再取得して差分を確認してください: python3 scripts/inspect_app.py")


if __name__ == "__main__":
    main()
