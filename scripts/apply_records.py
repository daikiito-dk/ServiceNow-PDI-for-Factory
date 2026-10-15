#!/usr/bin/env python3
"""マニフェストで定義したレコードをブラウザセッション経由でPDIに適用する。

使い方:
    python3 scripts/apply_records.py app/phase1/manifest.json

前提:
    - Factoryの埋め込みブラウザペイン(またはagent-browserのセッション)で
      ServiceNowにログイン済みであること。API呼び出しはそのセッションの
      X-UserToken(g_ck)を使うため、パスワードを扱わない。

マニフェスト形式(app/phase1/manifest.json 参照):
    {
      "records": [
        {
          "table": "sys_script",
          "lookup": {"name": "...", "collection": "..."},   # 既存チェック用
          "fields": {...},                                  # 作成/更新する値
          "script_file": "br_xxx.js",                        # 省略可。相対パス
          "script_fields": ["script", "action"]             # script_file の内容を入れる欄
        }
      ]
    }

    - "__APP__" は適用時にアプリ(sys_app)のsys_idに置換される
    - lookup に一致するレコードがあれば更新(PUT)、なければ作成(POST)。
      何度実行しても同じ結果になる(べき等)。

注意:
    - 実行後は scripts/snapshot_via_browser.py でスナップショットを再取得し、
      git diff で意図した差分かを確認すること。
"""

import json
import os
import subprocess
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from snow_api import load_env  # noqa: E402

CALL_JS_TEMPLATE = r"""
(async () => {
  const r = await fetch(%(path)s, {method: %(method)s, credentials: "include",
    headers: {Accept: "application/json", "Content-Type": "application/json", "X-UserToken": window.g_ck},
    body: %(body)s});
  const t = await r.text();
  let j = null;
  try { j = JSON.parse(t); } catch (e) {}
  return JSON.stringify({status: r.status, body: j});
})()
"""


def api_call(method, path, payload=None):
    js = CALL_JS_TEMPLATE % {
        "path": json.dumps(path),
        "method": json.dumps(method),
        "body": "null" if payload is None else json.dumps(json.dumps(payload)),
    }
    cdp = os.environ.get("AGENT_BROWSER_CDP")
    cmd = ["agent-browser"]
    if cdp and os.environ.get("FACTORY_DESKTOP_CDP_PORT"):
        cmd += ["--cdp", cdp]
    else:
        cmd += ["--session", "snow-snapshot", "--headed"]
    cmd += ["eval", "--stdin"]
    proc = subprocess.run(cmd, input=js, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        sys.exit(f"ERROR: agent-browser 失敗: {proc.stderr.strip()[:400]}")
    raw = proc.stdout.strip()
    try:
        result = json.loads(json.loads(raw))
    except json.JSONDecodeError:
        sys.exit(f"ERROR: ブラウザの応答を解釈できません: {raw[:200]!r}")
    return result


def query_string(lookup):
    return "^".join(f"{k}={quote(str(v), safe='')}" for k, v in lookup.items())


def apply_record(record, app_id, manifest_dir):
    table = record["table"]
    lookup = {k: str(v).replace("__APP__", app_id) for k, v in record.get("lookup", {}).items()}
    fields = {k: (v.replace("__APP__", app_id) if isinstance(v, str) else v)
              for k, v in record["fields"].items()}

    script_file = record.get("script_file")
    if script_file:
        with open(os.path.join(manifest_dir, script_file), encoding="utf-8") as f:
            code = f.read()
        for field in record.get("script_fields", ["script"]):
            fields[field] = code

    path = f"/api/now/table/{table}"
    existing = api_call("GET", f"{path}?sysparm_query={query_string(lookup)}"
                              "&sysparm_limit=1&sysparm_fields=sys_id")
    if existing["status"] != 200:
        sys.exit(f"ERROR: {table} の既存チェックに失敗: {json.dumps(existing['body'], ensure_ascii=False)[:300]}")

    found = (existing["body"] or {}).get("result") or []
    if found:
        sys_id = found[0]["sys_id"]
        result = api_call("PUT", f"{path}/{sys_id}", fields)
        action = "更新"
    else:
        result = api_call("POST", path, fields)
        action = "作成"
        sys_id = (result.get("body") or {}).get("result", {}).get("sys_id")

    status = result["status"]
    ok = 200 <= status < 300
    mark = "OK " if ok else "FAIL"
    print(f"{mark} {action}: {table} {lookup} (sys_id={sys_id}, HTTP {status})")
    if not ok:
        print(f"     {json.dumps(result['body'], ensure_ascii=False)[:400]}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    manifest_path = sys.argv[1]
    app_id = sys.argv[2] if len(sys.argv) > 2 else None
    if not app_id:
        try:
            app_id = load_env().get("SN_APP_SYS_ID")
        except Exception:
            app_id = None
    if not app_id:
        sys.exit("ERROR: .env の SN_APP_SYS_ID を設定するか、第2引数でアプリのsys_idを指定してください。")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    # Table API はリクエスト内の sys_scope / sys_package やスコープヘッダーを無視し、
    # セッションの「現在のアプリ」でレコードのスコープを決める。
    # そのため UI のアプリピッカーと同じAPIで現在のアプリを切り替えてから書き込む。
    switched = api_call("PUT", "/api/now/ui/concoursepicker/application", {"app_id": app_id})
    if switched["status"] != 200:
        sys.exit(f"ERROR: アプリスコープの切替に失敗: HTTP {switched['status']}")
    print(f"セッションのアプリスコープを切替: {app_id}")

    records = manifest.get("records", [])
    print(f"適用対象: {len(records)}件 (manifest={manifest_path})")
    for record in records:
        apply_record(record, app_id, os.path.dirname(os.path.abspath(manifest_path)))
    print("完了。スナップショットを再取得して差分確認してください:")
    print("  python3 scripts/snapshot_via_browser.py")


if __name__ == "__main__":
    main()
