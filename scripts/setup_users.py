#!/usr/bin/env python3
"""自動化用の連携ユーザーと、ロール別テストユーザーを PDI に作成する(べき等)。

    python3 scripts/setup_users.py

- 作成はログイン済みブラウザセッション経由で行う(Basic 認証がまだ使えない前提)
- パスワードはローカルで生成して .env に保存する。画面・ログ・コマンドライン引数には出さない
- .env に既存のパスワードがあればそれを再設定する(何度実行しても同じ状態になる)
- 既存の SN_USER=admin の行は SN_ADMIN_USER / SN_ADMIN_PASSWORD に退避する
- 最後に各ユーザーで Basic 認証できることを確認する

PDI では連携ユーザーに admin を付与している(アプリファイルの作成・更新に必要)。
本番環境では委任開発者(delegated developer)など最小権限に置き換えること。
"""

import os
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sn_client import SnError, call, env, error_message, set_current_app  # noqa: E402
from snow_api import ROOT  # noqa: E402

SCOPE = "x_2221323_loan_p_0"
# インスタンスで Basic 認証制限(glide.authenticate.basic_auth.restriction.enforce)が有効なため、
# Basic 認証で API を呼ぶユーザーにはこのロールが必要(admin でも付与されていないと 401 になる)
BASIC_AUTH_ROLE = "snc_basic_auth_api_access"
USERS = [
    # (.env のキー接頭辞, user_name, 姓, 名, ロール, API専用ユーザーか, 確認用パス)
    ("SN", "svc_factory_droid", "Droid", "Factory", ["admin", BASIC_AUTH_ROLE], True,
     "/api/now/table/sys_app?sysparm_limit=1&sysparm_fields=sys_id"),
    # テストユーザーは画面操作の QA でも使うため UI ログインを許可しておく
    ("SN_TEST_APPLICANT", "test_loan_applicant", "Applicant", "Test",
     [f"{SCOPE}.loan_applicant", BASIC_AUTH_ROLE], False,
     f"/api/now/table/{SCOPE}_request?sysparm_limit=1&sysparm_fields=sys_id"),
    ("SN_TEST_UNDERWRITER", "test_loan_underwriter", "Underwriter", "Test",
     [f"{SCOPE}.loan_underwriter", BASIC_AUTH_ROLE], False,
     f"/api/now/table/{SCOPE}_request?sysparm_limit=1&sysparm_fields=sys_id"),
]
ENV_PATH = os.path.join(ROOT, ".env")


def generate_password():
    symbols = "!@%^*-_+"
    alphabet = string.ascii_letters + string.digits + symbols
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(24))
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw) and any(c in symbols for c in pw)):
            return pw


def update_env(values, renames):
    """.env の値を書き換える(他の行は保持)。値は表示しない。"""
    with open(ENV_PATH, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out, seen = [], set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in renames:
            out.append(f"{renames[key]}={line.split('=', 1)[1]}")
        elif key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in values.items():
        if key not in seen:
            out.append(f"{key}={value}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def browser(method, path, payload=None):
    status, body = call(method, path, payload, transport="browser")
    if not 200 <= status < 300:
        raise SnError(f"{method} {path.split('?')[0]} -> HTTP {status}: {error_message(body)}")
    return (body or {}).get("result")


def ensure_user(user_name, last, first, password, api_only):
    found = browser("GET", f"/api/now/table/sys_user?sysparm_query=user_name={user_name}&sysparm_fields=sys_id")
    fields = {"user_name": user_name, "last_name": last, "first_name": first, "user_password": password,
              "active": "true", "locked_out": "false", "password_needs_reset": "false",
              "web_service_access_only": "true" if api_only else "false"}
    # user_password は表示値として渡さないとハッシュ化されずに保存されてしまう
    if found:
        sys_id = found[0]["sys_id"]
        browser("PATCH", f"/api/now/table/sys_user/{sys_id}?sysparm_input_display_value=true", fields)
        return sys_id, "更新"
    created = browser("POST", "/api/now/table/sys_user?sysparm_input_display_value=true", fields)
    return created["sys_id"], "作成"


def ensure_role(user_id, role_name):
    roles = browser("GET", f"/api/now/table/sys_user_role?sysparm_query=name={role_name}&sysparm_fields=sys_id")
    if not roles:
        raise SnError(f"ロール {role_name} が見つかりません")
    role_id = roles[0]["sys_id"]
    q = f"user={user_id}^role={role_id}"
    if browser("GET", f"/api/now/table/sys_user_has_role?sysparm_query={q}&sysparm_fields=sys_id"):
        return "付与済み"
    browser("POST", "/api/now/table/sys_user_has_role", {"user": user_id, "role": role_id})
    return "付与"


def main():
    current = env()
    renames = {}
    if current.get("SN_USER") == "admin":
        renames = {"SN_USER": "SN_ADMIN_USER", "SN_PASSWORD": "SN_ADMIN_PASSWORD"}

    values = {}
    try:
        set_current_app("global", transport="browser")
        for prefix, user_name, last, first, roles, api_only, _ in USERS:
            existing = current.get(f"{prefix}_PASSWORD") if current.get(f"{prefix}_USER") == user_name else None
            password = existing or generate_password()
            user_id, action = ensure_user(user_name, last, first, password, api_only)
            role_results = [f"{r}({ensure_role(user_id, r)})" for r in roles]
            print(f"OK  {action}: {user_name}  ロール: {', '.join(role_results)}")
            values[f"{prefix}_USER"] = user_name
            values[f"{prefix}_PASSWORD"] = password
    except SnError as e:
        sys.exit(f"ERROR: {e}")
    finally:
        if values:
            update_env(values, renames)

    print(".env を更新しました(パスワードは表示しません)。Basic 認証を確認します:")
    failed = False
    for prefix, user_name, *_, check_path in USERS:
        status, body = call("GET", check_path, auth=(user_name, values[f"{prefix}_PASSWORD"]))
        ok = status == 200
        failed |= not ok
        print(f"  {'OK ' if ok else 'NG '} {user_name}: HTTP {status}" + ("" if ok else f" {error_message(body)}"))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
