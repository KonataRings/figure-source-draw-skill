#!/usr/bin/env python3
"""Self-test for the figure skill: all three routes plus the refusal paths."""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
TMP = os.path.join(HERE, "_selftest")


def run(args, expect=0):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    if expect is not None and p.returncode != expect:
        sys.stderr.write(p.stdout + p.stderr)
        raise AssertionError("%s exited %d, expected %s" % (os.path.basename(args[0]),
                                                            p.returncode, expect))
    return p


def main():
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP)
    case = os.path.join(HERE, "examples", "case")
    work = os.path.join(TMP, "work")
    out = os.path.join(TMP, "out")

    # 1. scene + chart in one case
    p = run([os.path.join(SCRIPTS, "run_case.py"), "--input", case, "--work", work,
             "--output", out])
    report = json.loads(p.stdout.strip().splitlines()[-1])
    assert report["status"] == "success", report
    for name in ("figure.svg", "figure.pdf", "figure.png", "chart.svg", "chart.png",
                 "chart_mapping.json", "ledger.csv", "export_check.json", "result.json"):
        path = os.path.join(out, name)
        assert os.path.exists(path) and os.path.getsize(path) > 0, "missing " + name

    res = json.load(open(os.path.join(out, "result.json"), encoding="utf-8"))
    assert res["element_map"], "element_map must list every element"
    kinds = {row["source_kind"] for row in res["element_map"]}
    assert "inferred" in kinds and "stated" in kinds, kinds
    assert res["contract_missing"] == [], res["contract_missing"]

    svg = open(os.path.join(out, "figure.svg"), encoding="utf-8").read()
    assert '<g id="layer-shapes">' in svg and "<text" in svg, "layers and text must survive"
    assert "stimulus" in svg, "label text must stay searchable in the SVG"

    # 2. edit route: rename one label, move one node, keep the rest
    base = os.path.join(TMP, "base.svg")
    shutil.copy2(os.path.join(out, "figure.svg"), base)
    edits = os.path.join(TMP, "edits.json")
    json.dump([
        {"op": "set-text", "id": "label-n-stim-0", "text": "brief stimulus"},
        {"op": "move", "id": "node-n-relay", "dx": 30, "dy": 0},
        {"op": "recolor", "id": "node-n-rec", "fill": "#ffe9c7"},
        {"op": "delete", "id": "edge-e-3"},
        {"op": "set-text", "id": "does-not-exist", "text": "x"},
    ], open(edits, "w", encoding="utf-8"), ensure_ascii=False)
    edited = os.path.join(TMP, "edited.svg")
    log = os.path.join(TMP, "edit_log.json")
    run([os.path.join(SCRIPTS, "edit_svg.py"), "--svg", base, "--edits", edits,
         "--output", edited, "--log", log], expect=1)
    edit_log = json.load(open(log, encoding="utf-8"))
    assert edit_log["applied"] == 4, edit_log["applied"]
    assert edit_log["not_applied"] and edit_log["not_applied"][0]["id"] == "does-not-exist"
    new_svg = open(edited, encoding="utf-8").read()
    assert ">brief stimulus</text>" in new_svg, "the rename must land in the source file"
    assert ">stimulus</text>" not in new_svg, "the old label must be gone"
    assert "inhibits" not in new_svg, "the deleted edge should be gone"

    # 3. refusal: a scene without sources must not validate
    bad = json.load(open(os.path.join(case, "artifacts", "scene.json"), encoding="utf-8"))
    bad["nodes"][0].pop("source")
    bad_path = os.path.join(TMP, "bad_scene.json")
    json.dump(bad, open(bad_path, "w", encoding="utf-8"), ensure_ascii=False)
    run([os.path.join(SCRIPTS, "scene.py"), "--validate", bad_path], expect=1)

    # 4. refusal: missing material becomes insufficient_evidence, not a made-up figure
    empty_in = os.path.join(TMP, "empty_in")
    os.makedirs(os.path.join(empty_in, "artifacts"))
    json.dump({"case_id": "EMPTY", "output_contract": {"required": ["editable_source"]}},
              open(os.path.join(empty_in, "case.json"), "w", encoding="utf-8"))
    p = run([os.path.join(SCRIPTS, "run_case.py"), "--input", empty_in,
             "--work", os.path.join(TMP, "w2"), "--output", os.path.join(TMP, "o2")],
            expect=1)
    empty = json.loads(p.stdout.strip().splitlines()[-1])
    assert empty["status"] == "insufficient_evidence", empty
    res2 = json.load(open(os.path.join(TMP, "o2", "result.json"), encoding="utf-8"))
    assert res2["editable_source"] is None and res2["notes"], res2

    # 5. the export checker must catch a blank PNG
    from PIL import Image
    blank = os.path.join(TMP, "blank.png")
    Image.new("RGB", (300, 200), "white").save(blank)
    p = run([os.path.join(SCRIPTS, "check_export.py"), "--png", blank,
             "--output", os.path.join(TMP, "blank_check.json")], expect=1)
    assert "blank" in p.stdout

    print(json.dumps({"routes": ["scene", "chart", "edit"],
                      "ledger_rows": len(res["element_map"]),
                      "edits_applied": edit_log["applied"],
                      "refusals": ["missing source", "missing material", "blank export"],
                      "result": "PASS"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
