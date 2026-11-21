#!/usr/bin/env python3
"""Run the self-made benchmark and report which claims actually hold.

    python run_benchmark.py --output report.md

Each case states the outcome it expects (success, a warning, a validation error,
or a chart). A pass means the skill behaved as documented on that case; it is not
a score for any official case, and the report says so.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
TMP = os.path.join(HERE, "_tmp")


def run(args):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True)


def build_case(case, workdir):
    cdir = os.path.join(workdir, case["id"])
    os.makedirs(os.path.join(cdir, "artifacts"), exist_ok=True)
    json.dump({"case_id": case["id"], "output_contract": {"required": ["editable_source"]}},
              open(os.path.join(cdir, "case.json"), "w", encoding="utf-8"))
    if "scene" in case:
        json.dump(case["scene"], open(os.path.join(cdir, "artifacts", "scene.json"), "w",
                                      encoding="utf-8"), ensure_ascii=False)
    if "chart" in case:
        rows = case["rows"]
        with open(os.path.join(cdir, "artifacts", "data.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        json.dump(case["chart"], open(os.path.join(cdir, "artifacts", "chart_spec.json"), "w",
                                      encoding="utf-8"), ensure_ascii=False)
    return cdir


def check_case(case, cdir, workdir):
    detail = {"id": case["id"], "expect": case["expect"], "ok": False, "why": ""}
    out = os.path.join(workdir, "out_" + case["id"])
    work = os.path.join(workdir, "work_" + case["id"])
    p = run([os.path.join(SCRIPTS, "run_case.py"), "--input", cdir, "--work", work,
             "--output", out])
    last = ""
    for line in p.stdout.strip().splitlines():
        if line.strip().startswith("{"):
            last = line
    if case["expect"] == "invalid":
        v = run([os.path.join(SCRIPTS, "scene.py"), "--validate",
                 os.path.join(cdir, "artifacts", "scene.json")])
        detail["ok"] = v.returncode == 1 and "missing source" in v.stdout
        detail["why"] = "validation rejected the scene" if detail["ok"] else "validation accepted it"
        return detail

    if not last:
        detail["why"] = "run_case produced no summary: %s" % (p.stderr or p.stdout)[-160:]
        return detail
    summary = json.loads(last)
    detail["status"] = summary.get("status")

    svg = os.path.join(out, "figure.svg")
    if case["expect"] == "chart":
        ok = summary.get("status") in ("success", "partial") and os.path.exists(
            os.path.join(out, "chart.png"))
        detail["ok"] = bool(ok)
        detail["why"] = "chart rendered" if ok else "chart missing"
        return detail

    chk = os.path.join(out, "export_check.json")
    if not os.path.exists(chk):
        detail["why"] = "no export check"
        return detail
    chk_data = json.load(open(chk, encoding="utf-8"))
    texts = chk_data.get("text_elements", 0)
    detail["texts"] = texts
    ledger = os.path.join(out, "ledger.csv")
    rows = 0
    if os.path.exists(ledger):
        with open(ledger, encoding="utf-8-sig") as f:
            rows = len(list(csv.DictReader(f)))
    detail["ledger_rows"] = rows
    n_elems = (len(case["scene"]["nodes"]) + len(case["scene"].get("edges") or [])
               + len(case["scene"].get("annotations") or []))

    if case["expect"] == "warning":
        v = run([os.path.join(SCRIPTS, "scene.py"), "--validate",
                 os.path.join(cdir, "artifacts", "scene.json")])
        warned = case.get("expect_warning", "") in v.stdout
        detail["ok"] = warned and chk_data.get("ok") is True and rows >= n_elems
        detail["why"] = "warned and still exported" if detail["ok"] else (
            "warning missing" if not warned else "export or ledger incomplete")
        return detail

    ok = (chk_data.get("ok") is True and texts >= case.get("min_text", 0)
          and rows >= n_elems and summary.get("status") == "success")
    detail["ok"] = ok
    detail["why"] = ("exports checked, %d labels, %d ledger rows" % (texts, rows)) if ok else (
        "check ok=%s texts=%d rows=%d/%d status=%s" % (
            chk_data.get("ok"), texts, rows, n_elems, summary.get("status")))
    return detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=os.path.join(HERE, "report.md"))
    a = ap.parse_args()

    sys.path.insert(0, HERE)
    from build_cases import CASES

    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    details = []
    for case in CASES:
        cdir = build_case(case, TMP)
        details.append(check_case(case, cdir, TMP))

    passed = sum(1 for d in details if d["ok"])
    lines = ["# 自建基准报告（科研绘图）", "",
             "说明：本基准由本题作品自行构建，使用合成场景，**不是**平台官方的三个固定案例，",
             "通过率不能当作官方得分。它检验的是：文档里声明的每条行为（出图、换行、中文、",
             "越界警告、缺来源拒绝、图表路线）是否真的成立。", "",
             "| 案例 | 期望 | 结果 | 标签数 | 台账行 | 说明 |", "|-|-|-|-:|-:|-|"]
    for d in details:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            d["id"], d["expect"], "✓" if d["ok"] else "✗",
            d.get("texts", "-"), d.get("ledger_rows", "-"), d["why"]))
    lines += ["", "通过 **%d/%d**。" % (passed, len(details)), ""]
    open(a.output, "w", encoding="utf-8").write("\n".join(lines))
    json.dump({"passed": passed, "total": len(details), "cases": details},
              open(os.path.join(HERE, "report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({"passed": passed, "total": len(details), "output": a.output},
                     ensure_ascii=False))
    return 0 if passed == len(details) else 1


if __name__ == "__main__":
    sys.exit(main())
