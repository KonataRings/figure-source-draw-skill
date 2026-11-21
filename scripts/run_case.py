#!/usr/bin/env python3
"""One command for a figure case: inventory, draw or edit, export, check, record.

    python run_case.py --input /input --work /app/work --output /app/output

Picks the route the material supports:
  scene  -- a scene JSON is present (or the case asks for a new figure)
  chart  -- a data table plus a chart spec are present
  edit   -- the case points at an existing SVG and an edit list
Each route ends with real SVG/PDF/PNG files, an element ledger, an export check
and a result.json whose status is honest about what could not be produced.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    p = subprocess.run([sys.executable] + cmd, capture_output=True, text=True)
    return {"cmd": os.path.basename(cmd[0]), "rc": p.returncode,
            "out": (p.stdout or "").strip()[-600:], "err": (p.stderr or "").strip()[-600:]}


def find(pattern, roots):
    hits = []
    for root in roots:
        hits += glob.glob(os.path.join(root, pattern))
        hits += glob.glob(os.path.join(root, "**", pattern), recursive=True)
    return sorted(set(hits))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/input")
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--output", default="/app/output")
    a = ap.parse_args()

    os.makedirs(a.work, exist_ok=True)
    os.makedirs(a.output, exist_ok=True)
    case_path = os.path.join(a.input, "case.json")
    case = {}
    if os.path.exists(case_path):
        case = json.load(open(case_path, encoding="utf-8-sig"))
    artifacts = os.path.join(a.input, "artifacts")
    roots = [r for r in (a.input, artifacts) if os.path.isdir(r)]

    inventory = {"case_id": case.get("case_id") or case.get("id") or "unknown",
                 "artifacts": []}
    for root in roots:
        for path in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
            if os.path.isfile(path):
                inventory["artifacts"].append({
                    "path": os.path.relpath(path, a.input),
                    "bytes": os.path.getsize(path),
                    "ext": os.path.splitext(path)[1].lower()})

    scene_files = find("scene*.json", roots)
    spec_files = find("*spec*.json", roots) + find("chart*.json", roots)
    data_files = find("*.csv", roots) + find("*.tsv", roots)
    svg_files = find("*.svg", roots)
    edits_files = find("edits*.json", roots)

    steps, produced = [], {}
    status = "success"
    notes = []
    scene_path = chart_mapping = ledger_scene = None

    if scene_files:
        scene_path = scene_files[0]
        steps.append(run([os.path.join(HERE, "scene.py"), "--validate", scene_path]))
        if steps[-1]["rc"] != 0:
            status = "partial"
            notes.append("scene failed validation: %s" % steps[-1]["out"][:200])

    if data_files and spec_files:
        # chart route: the spec names the columns, never the values
        steps.append(run([os.path.join(HERE, "chart.py"), "--data", data_files[0],
                          "--spec", spec_files[0], "--outdir", a.output,
                          "--basename", "chart"]))
        chart_mapping = os.path.join(a.output, "chart_mapping.json")
        if steps[-1]["rc"] != 0:
            status = "failed" if not scene_path else "partial"
            notes.append("chart failed: %s" % steps[-1]["err"][:200])

    if not scene_path and not (data_files and spec_files) and svg_files and edits_files:
        out_svg = os.path.join(a.output, "figure.svg")
        steps.append(run([os.path.join(HERE, "edit_svg.py"), "--svg", svg_files[0],
                          "--edits", edits_files[0], "--output", out_svg,
                          "--log", os.path.join(a.work, "edit_log.json")]))
        if steps[-1]["rc"] != 0:
            status = "partial"
            notes.append("some edits were refused; see work/edit_log.json")

    if not scene_path and not (data_files and spec_files) and not (svg_files and edits_files):
        status = "insufficient_evidence"
        notes.append("no scene JSON, no data+spec pair and no SVG+edits pair were found; "
                     "describe the material that is missing instead of inventing a figure")

    if scene_path:
        steps.append(run([os.path.join(HERE, "render.py"), "--scene", scene_path,
                          "--outdir", a.output, "--basename", "figure",
                          "--formats", "svg,pdf,png"]))
        if steps[-1]["rc"] != 0:
            status = "failed"
            notes.append("render failed: %s" % steps[-1]["err"][:200])
        ledger_scene = scene_path

    check_path = os.path.join(a.output, "export_check.json")
    steps.append(run([os.path.join(HERE, "check_export.py"),
                      "--svg", os.path.join(a.output, "figure.svg"),
                      "--png", os.path.join(a.output, "figure.png"),
                      "--pdf", os.path.join(a.output, "figure.pdf"),
                      "--min-text", "2", "--output", check_path]))
    if steps[-1]["rc"] != 0 and status == "success":
        status = "partial"
        notes.append("export check reported problems; see export_check.json")

    ledger_path = os.path.join(a.output, "ledger.csv")
    ledger_cmd = [os.path.join(HERE, "ledger.py"), "--output", ledger_path]
    if ledger_scene:
        ledger_cmd += ["--scene", ledger_scene]
    if chart_mapping and os.path.exists(chart_mapping):
        ledger_cmd += ["--chart-mapping", chart_mapping]
    if ledger_scene or (chart_mapping and os.path.exists(chart_mapping)):
        steps.append(run(ledger_cmd))

    outputs = {name: {"path": os.path.join(a.output, name),
                      "bytes": os.path.getsize(os.path.join(a.output, name))}
               for name in sorted(os.listdir(a.output))
               if name.endswith((".svg", ".pdf", ".png", ".csv"))}

    element_map = []
    if os.path.exists(ledger_path):
        import csv as _csv
        with open(ledger_path, encoding="utf-8-sig") as f:
            element_map = list(_csv.DictReader(f))

    result = {
        "case_id": inventory["case_id"],
        "status": status,
        "route": "scene" if scene_path else ("chart" if chart_mapping else
                                            ("edit" if svg_files and edits_files else "none")),
        "editable_source": outputs.get("figure.svg", {}).get("path"),
        "exports": {k: v["path"] for k, v in outputs.items() if k != "ledger.csv"},
        "provenance": ledger_path if os.path.exists(ledger_path) else None,
        "element_map": element_map,
        "export_check": check_path if os.path.exists(check_path) else None,
        "notes": notes,
        "uncertainty": ("元素来源标为 inferred 的由推断得到，需人工确认" if element_map
                        else "没有 ledger，无法逐元素回溯"),
    }

    contract = case.get("output_contract") or {}
    required = []
    if isinstance(contract, dict):
        required = list(contract.get("required") or (contract.get("properties") or {}).keys() or [])
    missing = [f for f in required if f not in result]
    for f in missing:
        result[f] = {"status": "insufficient_evidence",
                     "reason": "material did not support this field"}
    if missing and result["status"] == "success":
        result["status"] = "partial"
    result["contract_fields"] = required
    result["contract_missing"] = missing

    json.dump(result, open(os.path.join(a.output, "result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({"inventory": inventory, "steps": steps, "notes": notes},
              open(os.path.join(a.work, "run_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(json.dumps({"case_id": result["case_id"], "status": status, "route": result["route"],
                      "outputs": sorted(outputs), "missing_contract": missing},
                     ensure_ascii=False))
    return 0 if status in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
