#!/usr/bin/env python3
"""ServiceNow への API 呼び出しを、Basic 認証とブラウザセッションの両方で同じように扱う共通クライアント。

    from sn_client import call
    status, body = call("GET", "/api/now/table/sys_app?sysparm_limit=1")

通信方式(transport)の決まり方:
    1. 引数 transport="basic" | "browser"
    2. .env の SN_TRANSPORT
    3. .env に SN_USER / SN_PASSWORD があれば basic、なければ browser

- basic:   .env の認証情報(または auth=(user, password))で直接 HTTPS 接続する。CI/定期実行向け
- browser: agent-browser でログイン済みのブラウザから X-UserToken 付きで fetch する。パスワード不要

HTTP エラーでも例外にせず (status, body) を返す(テストで 403 等を検証するため)。
接続できない・休止中など、API として応答していない場合だけ SnError を送出する。
"""

import base64
import http.cookiejar
import json
import os
import subprocess
import urllib.error
import urllib.request

from snow_api import ApiError, load_env


class SnError(Exception):
    """API として応答が得られない(休止中・未ログイン・接続不可など)。"""


_env_cache = None
_browser_ready = False


def env():
    global _env_cache
    if _env_cache is None:
        try:
            _env_cache = load_env()
        except ApiError:
            _env_cache = {}
    return _env_cache


def instance():
    host = env().get("SN_INSTANCE")
    if not host:
        raise SnError(".env に SN_INSTANCE を設定してください。")
    return host


def default_transport():
    e = env()
    if e.get("SN_TRANSPORT"):
        return e["SN_TRANSPORT"]
    return "basic" if e.get("SN_USER") and e.get("SN_PASSWORD") else "browser"


def call(method, path, payload=None, *, auth=None, transport=None):
    transport = "basic" if auth else (transport or default_transport())
    if transport == "basic":
        return _call_basic(method, path, payload, auth)
    if transport == "browser":
        return _call_browser(method, path, payload)
    raise SnError(f"未知の transport: {transport}")


# ---------------------------------------------------------------- basic

# 「現在のアプリ」はセッションに紐づくため、ユーザーごとにクッキーを保持して同じセッションを使い続ける。
# これがないと set_current_app の効果が次のリクエストに引き継がれず、global に作成されてしまう。
_openers = {}


def _opener(user):
    if user not in _openers:
        _openers[user] = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    return _openers[user]


def _call_basic(method, path, payload, auth):
    user, password = auth or (env().get("SN_USER"), env().get("SN_PASSWORD"))
    if not user or not password:
        raise SnError(".env に SN_USER / SN_PASSWORD を設定してください。")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"https://{instance()}{path}", data=data, method=method)
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with _opener(user).open(req, timeout=60) as resp:
            status, text = resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        raise SnError(f"接続エラー: {e.reason}")
    return status, _parse(status, text)


def _parse(status, text):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if "Hibernating" in text:
            raise SnError("PDI が休止中です。developer.servicenow.com からインスタンスを起動してください。")
        raise SnError(f"HTTP {status}: JSON 以外の応答: {text[:200]!r}")


# ---------------------------------------------------------------- browser

_FETCH_JS = r"""
(async () => {
  if (!window.g_ck) return JSON.stringify({fatal: "no_token"});
  const r = await fetch(%(path)s, {method: %(method)s, credentials: "include",
    headers: {Accept: "application/json", "Content-Type": "application/json", "X-UserToken": window.g_ck},
    body: %(body)s});
  return JSON.stringify({status: r.status, text: await r.text()});
})()
"""


def _browser_cmd(*args):
    cmd = ["agent-browser"]
    cdp = os.environ.get("AGENT_BROWSER_CDP")
    if cdp and os.environ.get("FACTORY_DESKTOP_CDP_PORT"):
        cmd += ["--cdp", cdp]
    else:
        cmd += ["--session", "snow-snapshot", "--headed"]
    return cmd + list(args)


def _run(args, stdin=None, timeout=90):
    proc = subprocess.run(_browser_cmd(*args), input=stdin, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise SnError(f"agent-browser 失敗: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def _ensure_browser_page():
    """相対 URL の fetch が使えるよう、アクティブタブをインスタンスのページにしておく。"""
    global _browser_ready
    if _browser_ready:
        return
    # 同じホストでも Studio 等 g_ck を持たないページがあるため、トークンの有無も確認する
    state = json.loads(json.loads(_run(["eval", "--stdin"],
                                       "JSON.stringify({h: location.host, t: !!window.g_ck})")))
    if state["h"] != instance() or not state["t"]:
        _run(["open", f"https://{instance()}/"], timeout=120)
        _run(["wait", "--load", "networkidle"], timeout=120)
    _browser_ready = True


def _call_browser(method, path, payload):
    _ensure_browser_page()
    # payload は stdin 経由で渡し、コマンドライン引数やログにパスワード等が出ないようにする
    js = _FETCH_JS % {
        "path": json.dumps(path),
        "method": json.dumps(method),
        "body": "undefined" if payload is None else json.dumps(json.dumps(payload)),
    }
    raw = _run(["eval", "--stdin"], js)
    try:
        result = json.loads(json.loads(raw))
    except json.JSONDecodeError:
        raise SnError(f"ブラウザの応答を解釈できません: {raw[:200]!r}")
    if result.get("fatal") == "no_token":
        raise SnError("ブラウザが ServiceNow にログインしていません。ブラウザでログインしてから再実行してください。")
    return result["status"], _parse(result["status"], result["text"])


# ---------------------------------------------------------------- helpers

def set_current_app(app_id, **kw):
    """セッションの「現在のアプリ」を切り替える(UI のアプリピッカーと同じ API)。

    Table API はペイロード中の sys_scope を無視し、現在のアプリでスコープを決めるため、
    アプリファイルを作成・更新する前に必ず呼ぶ。"global" で Global に戻る。
    """
    status, body = call("PUT", "/api/now/ui/concoursepicker/application", {"app_id": app_id}, **kw)
    if status != 200:
        raise SnError(f"アプリスコープの切替に失敗: HTTP {status} {json.dumps(body, ensure_ascii=False)[:200]}")


def error_message(body):
    if isinstance(body, dict) and body.get("error"):
        err = body["error"]
        return f"{err.get('message', '')} {err.get('detail', '') or ''}".strip()
    return None
