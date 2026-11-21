#!/usr/bin/env python3
"""Element ledger: every drawn element, where it came from, and its version.

    python ledger.py --scene scene.json --chart-mapping out/chart_mapping.json \
        --output out/ledger.csv

One row per element, so a reviewer can point at a box in the figure and see the
sentence, table column or file it came from. Elements whose source is marked
"inferred" say so, which keeps inference visible instead of hidden in the art.
"""
import argparse
import csv
import json
import os


def rows_from_scene(scene, version):
    rows = []
    for n in scene.get("nodes") or []:
        src = n.get("source") or {}
        rows.append({
            "element_id": n.get("id"), "kind": "node", "label": n.get("text", ""),
            "shape": n.get("shape", "rect"),
            "source_kind": src.get("kind", ""),
            "artifact": src.get("artifact", ""), "page": src.get("page", ""),
            "evidence": src.get("quote") or src.get("note") or "",
            "version": version, "editable": "yes",
            "confirmed": "yes" if src.get("confirmed") else "no"})
    for e in scene.get("edges") or []:
        src = e.get("source") or {}
        rows.append({
            "element_id": e.get("id"), "kind": "edge",
            "label": "%s -> %s%s" % (e.get("from"), e.get("to"),
                                     (" (%s)" % e["label"]) if e.get("label") else ""),
            "shape": e.get("style", "solid"),
            "source_kind": src.get("kind", ""),
            "artifact": src.get("artifact", ""), "page": src.get("page", ""),
            "evidence": src.get("quote") or src.get("note") or "",
            "version": version, "editable": "yes",
            "confirmed": "yes" if src.get("confirmed") else "no"})
    for i, an in enumerate(scene.get("annotations") or []):
        src = an.get("source") or {}
        rows.append({
            "element_id": an.get("id") or "annotation-%d" % i, "kind": "annotation",
            "label": an.get("text", ""), "shape": "text",
            "source_kind": src.get("kind", ""),
            "artifact": src.get("artifact", ""), "page": src.get("page", ""),
            "evidence": src.get("quote") or src.get("note") or "",
            "version": version, "editable": "yes",
            "confirmed": "yes" if src.get("confirmed") else "no"})
    return rows


def rows_from_chart(mapping, version):
    rows = []
    if not mapping:
        return rows
    rows.append({"element_id": "chart", "kind": "chart", "label": mapping.get("style", ""),
                 "shape": "axes", "source_kind": "stated",
                 "artifact": os.path.basename(mapping.get("data", "")), "page": "",
                 "evidence": "%d rows, x=%s" % (mapping.get("rows", 0), mapping.get("x", "")),
                 "version": version, "editable": "yes (regenerated from data)"})
    for s in mapping.get("series") or []:
        rows.append({"element_id": "series:%s" % s.get("column"), "kind": "series",
                     "label": s.get("label", ""), "shape": "series",
                     "source_kind": "stated",
                     "artifact": os.path.basename(mapping.get("data", "")), "page": "",
                     "evidence": "column %s, %d points, %d missing" % (
                         s.get("column"), s.get("points", 0), s.get("missing", 0)),
                     "version": version, "editable": "yes"})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene")
    ap.add_argument("--chart-mapping")
    ap.add_argument("--version", default="1")
    ap.add_argument("--output", default="ledger.csv")
    a = ap.parse_args()

    rows = []
    if a.scene:
        rows += rows_from_scene(json.load(open(a.scene, encoding="utf-8-sig")), a.version)
    if a.chart_mapping and os.path.exists(a.chart_mapping):
        rows += rows_from_chart(json.load(open(a.chart_mapping, encoding="utf-8-sig")), a.version)
    if not rows:
        raise SystemExit("nothing to record: pass --scene and/or --chart-mapping")

    fields = ["element_id", "kind", "label", "shape", "source_kind", "artifact",
              "page", "evidence", "version", "editable", "confirmed"]
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    with open(a.output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    stated = sum(1 for r in rows if r["source_kind"] == "stated")
    inferred = sum(1 for r in rows if r["source_kind"] == "inferred")
    print(json.dumps({"rows": len(rows), "stated": stated, "inferred": inferred,
                      "output": a.output}, ensure_ascii=False))


if __name__ == "__main__":
    main()

