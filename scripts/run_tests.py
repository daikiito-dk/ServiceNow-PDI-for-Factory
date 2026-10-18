#!/usr/bin/env python3
"""tests/scenarios/*.json のシナリオを PDI に対して実行する回帰テスト。

    python3 scripts/run_tests.py                              # 全シナリオ
    python3 scripts/run_tests.py tests/scenarios/phase1.json  # 指定したシナリオだけ

- ユーザーごとに Basic 認証で実行する(.env の SN_USER / SN_TEST_APPLICANT_* / SN_TEST_UNDERWRITER_*。
  未作成なら scripts/setup_users.py を先に実行)
- テスト中に作成したレコードは、成否にかかわらず最後に連携ユーザーで削除する
- 1件でも失敗すると終了コード 1(CI でそのまま使える)

シナリオ形式(tests/scenarios/phase1.json 参照):
    case.as / step.as : "integration" | "applicant" | "underwriter"(step が優先)
    step.op           : "insert" | "update" | "delete"
    step.expect       : "ok"(2xx) | "reject"(400/403。401 は認証設定の問題として ERROR)
    step.save         : insert したレコードに名前を付ける。後続の step.record で参照する
    step.then         : 実行後に連携ユーザーで読み直し、各フィールドの値を確認する
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sn_client import SnError, call, env, error_message  # noqa: E402
from snow_api import ROOT  # noqa: E402

USER_KEYS = {
    "integration": "SN",
    "applicant": "SN_TEST_APPLICANT",
    "underwriter": "SN_TEST_UNDERWRITER",
}
REJECT_STATUSES = (400, 403)


def auth_for(role):
    prefix = USER_KEYS[role]
    user, password = env().get(f"{prefix}_USER"), env().get(f"{prefix}_PASSWORD")
    if not user or not password:
        raise SnError(f".env に {prefix}_USER / {prefix}_PASSWORD がありません。scripts/setup_users.py を実行してください。")
    return user, password


class Runner:
    def __init__(self, table):
        self.table = table
        self.base = f"/api/now/table/{table}"
        self.created = []  # 後片付け対象の sys_id
        self.passed = self.failed = 0

    def run_case(self, case):
        print(f"\n■ {case['name']}")
        saved = {}
        for step in case["steps"]:
            role = step.get("as") or case.get("as") or "integration"
            label = f"{step['label']} [{role}]"
            try:
                problem = self.run_step(step, role, saved)
            except SnError as e:
                problem = f"ERROR {e}"
            self.report(label, problem)

    def run_step(self, step, role, saved):
        auth = auth_for(role)
        op = step["op"]
        if op == "insert":
            status, body = call("POST", f"{self.base}?sysparm_exclude_reference_link=true", step["data"], auth=auth)
            sys_id = ((body or {}).get("result") or {}).get("sys_id") if 200 <= status < 300 else None
            if sys_id:
                self.created.append(sys_id)
                if step.get("save"):
                    saved[step["save"]] = sys_id
        else:
            sys_id = saved.get(step["record"])
            if not sys_id:
                return f"前提のレコード「{step['record']}」が作成されていないため実行できません"
            if op == "update":
                status, body = call("PATCH", f"{self.base}/{sys_id}", step["data"], auth=auth)
            elif op == "delete":
                status, body = call("DELETE", f"{self.base}/{sys_id}", auth=auth)
                if 200 <= status < 300:
                    self.created.remove(sys_id)
            else:
                return f"未知の op: {op}"

        if status == 401:
            return f"ERROR HTTP 401(認証失敗。{role} ユーザーの設定を確認): {error_message(body)}"
        ok = 200 <= status < 300
        expected_ok = step["expect"] == "ok"
        if ok != expected_ok or (not ok and status not in REJECT_STATUSES):
            detail = error_message(body) or ""
            return f"期待={step['expect']} 実際=HTTP {status} {detail[:120]}"

        if step.get("then"):
            target = sys_id if op != "insert" else (sys_id if ok else None)
            if not target:
                return "then を確認するレコードがありません"
            fields = ",".join(step["then"])
            status, body = call("GET", f"{self.base}/{target}?sysparm_fields={fields}"
                                       "&sysparm_exclude_reference_link=true", auth=auth_for("integration"))
            actual = (body or {}).get("result") or {}
            diffs = [f"{k}: 期待={v} 実際={actual.get(k)}" for k, v in step["then"].items() if str(actual.get(k)) != str(v)]
            if diffs:
                return "; ".join(diffs)
        return None

    def report(self, label, problem):
        if problem:
            self.failed += 1
            print(f"  FAIL {label}\n       {problem}")
        else:
            self.passed += 1
            print(f"  PASS {label}")

    def cleanup(self):
        auth = auth_for("integration")
        leftovers = []
        for sys_id in self.created:
            status, _ = call("DELETE", f"{self.base}/{sys_id}", auth=auth)
            if status not in (200, 204, 404):
                leftovers.append(sys_id)
        print(f"\nテストデータ削除: {len(self.created) - len(leftovers)}/{len(self.created)}件")
        if leftovers:
            print(f"  WARN 削除できなかったレコード: {', '.join(leftovers)}")


def main():
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "tests", "scenarios", "*.json")))
    if not paths:
        sys.exit("ERROR: tests/scenarios/*.json がありません。")
    total_pass = total_fail = 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            scenario = json.load(f)
        print(f"=== {os.path.relpath(path, ROOT)}: {scenario.get('description', '')}")
        runner = Runner(scenario["table"])
        try:
            for case in scenario["cases"]:
                runner.run_case(case)
        except SnError as e:
            runner.report("シナリオ実行", f"ERROR {e}")
        finally:
            try:
                runner.cleanup()
            except SnError as e:
                print(f"  WARN 後片付けに失敗: {e}")
        total_pass += runner.passed
        total_fail += runner.failed

    print(f"\n結果: {total_pass} passed, {total_fail} failed")
    sys.exit(1 if total_fail else 0)


if __name__ == "__main__":
    main()
