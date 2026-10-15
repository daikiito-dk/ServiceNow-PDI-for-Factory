#!/usr/bin/env python3
"""ServiceNow REST API ヘルパー。

認証情報はリポジトリ直下の .env から読み込む(.gitignore 済み・コミットされない)。
パスワードをコマンドラインやチャットに露出させないためにこのスクリプト経由でAPIを呼ぶ。

使い方:
    python3 scripts/snow_api.py get  "/api/now/table/sys_app/<sys_id>" "sysparm_fields=name,scope"
    python3 scripts/snow_api.py post "/api/now/table/<table>" '{"field": "value"}'
    python3 scripts/snow_api.py put  "/api/now/table/<table>/<sys_id>" '{"field": "value"}'
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ApiError(Exception):
    """ServiceNow API呼び出しのエラー(HTTPエラー/設定不足/接続エラー)。"""


def load_env():
    """リポジトリ直下の .env を読み込む。存在しない場合はエラー。

    値を引用符(" または ')で囲んだ書き方(SN_PASSWORD="xxx")は
    引用符をパスワードの一部として扱ってしまうため、外側の一致する
    引用符ペアは自動で取り除く。
    """
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        raise ApiError(".env が見つかりません。リポジトリ直下に .env を作成してください。")
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                env[key.strip()] = value
    return env


def request(method, path, payload=None, query=None):
    env = load_env()
    instance = env.get("SN_INSTANCE")
    user = env.get("SN_USER")
    password = env.get("SN_PASSWORD")
    if not all([instance, user, password]):
        raise ApiError(".env に SN_INSTANCE / SN_USER / SN_PASSWORD を設定してください。")
    if "パスワードを入力" in password:
        raise ApiError(".env の SN_PASSWORD が未入力です。PDIのパスワードを設定してください。")

    url = f"https://{instance}{path}"
    if query:
        url += ("&" if "?" in url else "?") + query

    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode(errors="replace")
            if not body:
                return {}
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                raise ApiError(
                    f"HTTP {resp.status} ({resp.headers.get('Content-Type', '?')}): "
                    f"JSON以外の応答が返りました。応答先頭: {body[:200]!r}"
                )
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise ApiError(f"HTTP {e.code}: {detail[:500]}")
    except urllib.error.URLError as e:
        raise ApiError(f"接続エラー: {e.reason}")


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("get", "post", "put"):
        print(__doc__)
        sys.exit(1)
    method = sys.argv[1].upper()
    path = sys.argv[2]
    query = sys.argv[3] if len(sys.argv) > 3 and method == "GET" else None
    payload = json.loads(sys.argv[3]) if method != "GET" and len(sys.argv) > 3 else None
    try:
        result = request(method, path, payload, query)
    except ApiError as e:
        sys.exit(f"ERROR: {e}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
