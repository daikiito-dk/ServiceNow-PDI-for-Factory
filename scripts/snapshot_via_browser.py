#!/usr/bin/env python3
"""ブラウザセッション(ServiceNowログイン済み)経由でアプリ構成を取得する。

REST の Basic 認証が使えない環境でも、ユーザーがブラウザでServiceNowに
ログインしていれば、そのセッション + X-UserToken(g_ck) でAPIを呼び出せる
仕組みを利用する。パスワードを扱わない。

前提:
    - agent-browser が使えること
    - デスクトップアプリの場合: FACTORY_DESKTOP_CDP_PORT / AGENT_BROWSER_CDP が
      設定済みで、埋め込みブラウザペインでServiceNowにログイン済みであること
    - それ以外: --headed の名前付きセッションを開くので、開いたウィンドウで
      ユーザーがログインしてから再実行すること

使い方:
    python3 scripts/snapshot_via_browser.py               # .env の SN_APP_SYS_ID を使用
    python3 scripts/snapshot_via_browser.py <app_sys_id>  # sys_id 直接指定

出力:
    docs/app-snapshot.json  / docs/app-inventory.md(再生成)

注意:
    - sys_choice は sys_package フィルタが効かないため、スコープのテーブル名
      プレフィックス(nameSTARTSWITH<scope>)で絞り込む
    - 参照フィールドは {link, value} 形式で返るため value に正規化する
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from inspect_app import DEFAULT_REPORT, DEFAULT_SNAPSHOT, render_report, write_snapshot  # noqa: E402
from snow_api import load_env  # noqa: E402

FETCH_JS = r"""
(async () => {
  const APP = "%(app_id)s";
  const LIMIT = 1000;
  const H = {Accept: "application/json", "X-UserToken": window.g_ck};
  if (!window.g_ck) return JSON.stringify({fatal: "このページに g_ck がない。ServiceNowのページを開いてから再実行してください。"});
  const TABLES = [
    ["sys_db_object","sys_id,name,label,super_class,access,is_extendable","sys_package","テーブル"],
    ["sys_dictionary","sys_id,name,element,column_label,internal_type,reference,max_length,mandatory,active,default_value,dependent_on_field","sys_package","フィールド"],
    ["sys_documentation","sys_id,name,element,label,plural,language","sys_package","ラベル"],
    ["sys_script","sys_id,name,collection,when,condition,order,active,script,action","sys_package","ビジネスルール"],
    ["sys_script_client",null,"sys_package","クライアントスクリプト"],
    ["sys_script_include","sys_id,name,api_name,script,active,client_callable,access,description","sys_package","スクリプトインクルード"],
    ["sys_ui_action","sys_id,name,table,condition,active,client,script,show_insert,show_update,order","sys_package","UIアクション"],
    ["sys_security_acl","sys_id,name,operation,active,type,admin_overrides,advanced,condition,script,description","sys_package","ACL"],
    ["sys_security_acl_role",null,"sys_package","ACLロール"],
    ["sys_user_role","sys_id,name,suffix,description","sys_package","ロール"],
    ["sys_app_module","sys_id,title,table,link,uri,query,order,active,roles","sys_package","モジュール"],
    ["sys_ui_page",null,"sys_package","UIページ"],
    ["sys_ui_macro",null,"sys_package","UIマクロ"],
    ["sysevent_email_action",null,"sys_package","メール通知"],
    ["sys_properties",null,"sys_scope","システムプロパティ"],
    ["sys_hub_flow","sys_id,name,type,active,description","sys_scope","フロー"]
  ];
  const get = async (path) => {
    const r = await fetch("/api/now/table/" + path, {credentials: "include", headers: H});
    if (!r.ok) throw new Error("HTTP " + r.status);
    return (await r.json()).result;
  };
  const fetchAll = async (table, fields, key) => {
    let out = [], offset = 0;
    while (true) {
      let q = "sysparm_query=" + key + "=" + APP + "&sysparm_limit=" + LIMIT + "&sysparm_order_by=sys_id&sysparm_offset=" + offset;
      if (fields) q += "&sysparm_fields=" + fields;
      const page = await get(table + "?" + q);
      out = out.concat(page);
      if (page.length < LIMIT) return out;
      offset += LIMIT;
    }
  };
  const app = await get("sys_app/" + APP + "?sysparm_fields=sys_id,name,scope,version,active,short_description,sys_created_on,sys_updated_on");
  const scope = app.scope;
  const tables = {}, errors = {}, summary = {};
  for (const [table, fields, key, label] of TABLES) {
    try {
      const rows = await fetchAll(table, fields, key);
      tables[table] = rows;
      summary[label] = rows.length;
    } catch (e) {
      errors[table] = String(e);
      summary[label] = null;
    }
  }
  // sys_choice は fetchAll の key=<APP> 形式ではなく、スコープのテーブル名
  // プレフィックスで絞り込む(sys_package フィルタが効かないため)
  const fetchChoices = async () => {
    let out = [], offset = 0;
    const fields = "sys_id,name,element,label,value,sequence,dependent_value,inactive";
    while (true) {
      const q = "sysparm_query=nameSTARTSWITH" + scope + "&sysparm_limit=" + LIMIT
        + "&sysparm_order_by=sys_id&sysparm_offset=" + offset + "&sysparm_fields=" + fields;
      const page = await get("sys_choice?" + q);
      out = out.concat(page);
      if (page.length < LIMIT) return out;
      offset += LIMIT;
    }
  };
  try {
    const rows = await fetchChoices();
    tables["sys_choice"] = rows;
    summary["選択肢"] = rows.length;
  } catch (e) {
    errors["sys_choice"] = String(e);
    summary["選択肢"] = null;
  }
  const glossary = {glide_objects: {}, parent_tables: {}};
  try {
    const rows = await get("sys_glide_object?sysparm_fields=sys_id,name&sysparm_limit=1000&sysparm_order_by=sys_id");
    glossary.glide_objects = Object.fromEntries(rows.map(r => [r.sys_id, r.name]));
  } catch (e) {}
  try {
    const objs = tables.sys_db_object || [];
    const appIds = new Set(objs.map(r => r.sys_id));
    const ext = [...new Set(objs.map(r => r.super_class).filter(Boolean).filter(id => !appIds.has(id)))];
    if (ext.length) {
      const rows = await get("sys_db_object?sysparm_query=sys_idIN" + ext.join(",") + "&sysparm_fields=sys_id,name,label");
      glossary.parent_tables = Object.fromEntries(rows.map(r => [r.sys_id, r.name]));
    }
  } catch (e) {}
  return JSON.stringify({instance: location.host, fetched_at: new Date().toISOString(), app: app, summary: summary, tables: tables, glossary: glossary, errors: errors});
})()
"""


def norm(v):
    """参照ラッパー {link, value} を値(display name)に展開する。

    レコード自身が正当な value フィールド(sys_choice の選択肢値など)を
    持つ場合は壊さないよう、キーがちょうど link+value の場合だけ展開する。
    """
    if isinstance(v, dict) and set(v.keys()) == {"link", "value"}:
        return norm(v["value"])
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    return v


def run_eval(js):
    """agent-browser 経由でJSを実行し、結果(JSON文字列)を返す。"""
    cdp = os.environ.get("AGENT_BROWSER_CDP")
    cmd = ["agent-browser"]
    if cdp and os.environ.get("FACTORY_DESKTOP_CDP_PORT"):
        cmd += ["--cdp", cdp]
    else:
        cmd += ["--session", "snow-snapshot", "--headed"]
    cmd += ["eval", "--stdin"]
    proc = subprocess.run(cmd, input=js, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        sys.exit(f"ERROR: agent-browser 失敗: {proc.stderr.strip()[:400]}")
    return proc.stdout.strip()


def main():
    app_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not app_id:
        try:
            app_id = load_env().get("SN_APP_SYS_ID")
        except Exception:
            app_id = None
    if not app_id:
        sys.exit("ERROR: .env の SN_APP_SYS_ID を設定するか、引数でsys_idを指定してください。")

    raw = run_eval(FETCH_JS % {"app_id": app_id})
    try:
        snapshot = norm(json.loads(json.loads(raw)))
    except json.JSONDecodeError:
        sys.exit(f"ERROR: ブラウザの応答をJSONとして解釈できません。応答先頭: {raw[:200]!r}")
    if isinstance(snapshot, dict) and snapshot.get("fatal"):
        sys.exit(f"ERROR: {snapshot['fatal']}")

    errors = snapshot.get("errors", {})
    print(f"アプリ: {snapshot['app'].get('name')} (scope={snapshot['app'].get('scope')})")
    for label, count in snapshot.get("summary", {}).items():
        print(f"  {label}: {count if count is not None else '取得失敗'}")
    for table, err in errors.items():
        print(f"  WARN {table}: {err}")

    write_snapshot(snapshot, DEFAULT_SNAPSHOT)
    render_report(snapshot, DEFAULT_REPORT)
    print(f"スナップショット保存: {DEFAULT_SNAPSHOT}")


if __name__ == "__main__":
    main()
