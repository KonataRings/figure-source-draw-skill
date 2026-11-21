#!/usr/bin/env python3
"""Scene model for scientific figures: one JSON description, three renderers.

A scene is the editable source of truth. It carries entities (nodes), relations
(edges), a legend, annotations and, for every element, where it came from. The
renderer turns it into SVG (layered, text stays text), PDF and PNG, so the
deliverable is both editable and viewable without any external converter.

    python scene.py --validate scene.json
    python scene.py --template > scene_template.json
"""
import argparse
import json
import sys

SHAPES = ("rect", "roundrect", "ellipse", "diamond", "hexagon")
STYLES = ("solid", "dashed", "dotted")
ARROWS = ("end", "both", "none")
KINDS = ("stated", "inferred", "derived")


def blank_scene(width=1600, height=1000):
    return {
        "canvas": {"width": width, "height": height, "background": "#ffffff", "dpi": 300},
        "meta": {"title": "", "description": "", "case_id": ""},
        "layers": [
            {"id": "frame", "z": 0, "note": "axes, panel borders, scale bars"},
            {"id": "connectors", "z": 1, "note": "arrows and edges"},
            {"id": "shapes", "z": 2, "note": "entities"},
            {"id": "labels", "z": 3, "note": "text and legend"},
        ],
        "nodes": [],
        "edges": [],
        "legend": [],
        "annotations": [],
    }


def _check_source(el, errors, where):
    src = el.get("source")
    if src is None:
        errors.append("%s: missing source (use {\"kind\": \"inferred\", \"note\": ...} if derived)" % where)
        return
    kind = src.get("kind")
    if kind not in KINDS:
        errors.append("%s: source.kind must be one of %s" % (where, ", ".join(KINDS)))
    if kind == "stated" and not (src.get("artifact") or src.get("quote")):
        errors.append("%s: stated source needs artifact or quote" % where)
    if kind == "inferred" and not src.get("note"):
        errors.append("%s: inferred source needs a note saying why" % where)


def validate(scene):
    errors, warnings = [], []
    canvas = scene.get("canvas") or {}
    w, h = canvas.get("width"), canvas.get("height")
    if not (isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0):
        errors.append("canvas: width and height must be positive numbers")
        w = h = 0

    constraints = scene.get("constraints") or {}
    min_font = constraints.get("min_font_size")
    max_colors = constraints.get("max_colors")

    for i, panel in enumerate(scene.get("panels") or []):
        label = panel.get("label") or "#%d" % i
        for k in ("x", "y", "w", "h"):
            if not isinstance(panel.get(k), (int, float)):
                errors.append("panel %s: %s must be a number" % (label, k))
                break
        else:
            if w and (panel["x"] < 0 or panel["y"] < 0 or
                      panel["x"] + panel["w"] > w or panel["y"] + panel["h"] > h):
                warnings.append("panel %s: extends outside the canvas" % label)
        if not str(panel.get("label", "")).strip():
            warnings.append("panel %d: no label; panels are usually lettered A, B, C" % i)

    layer_ids = {l.get("id") for l in scene.get("layers") or []}
    if not layer_ids:
        errors.append("layers: at least one layer is required")

    ids, seen = set(), set()
    for n in scene.get("nodes") or []:
        nid = n.get("id")
        if not nid:
            errors.append("node: missing id")
            continue
        if nid in seen:
            errors.append("node %s: duplicate id" % nid)
        seen.add(nid)
        ids.add(nid)
        if n.get("shape", "rect") not in SHAPES:
            errors.append("node %s: unknown shape %s" % (nid, n.get("shape")))
        if n.get("layer") and n["layer"] not in layer_ids:
            errors.append("node %s: layer %s is not declared" % (nid, n["layer"]))
        for k in ("x", "y", "w", "h"):
            if not isinstance(n.get(k), (int, float)):
                errors.append("node %s: %s must be a number" % (nid, k))
                break
        else:
            if w and (n["x"] < 0 or n["y"] < 0 or n["x"] + n["w"] > w or n["y"] + n["h"] > h):
                warnings.append("node %s: extends outside the canvas" % nid)
        if not str(n.get("text", "")).strip():
            warnings.append("node %s: no text; an unlabelled entity is hard to check" % nid)
        if min_font and isinstance(n.get("font_size", 16), (int, float)) and n.get("font_size", 16) < min_font:
            errors.append("node %s: font_size %s is below the declared minimum %s"
                          % (nid, n.get("font_size"), min_font))
        _check_source(n, errors, "node %s" % nid)

    for e in scene.get("edges") or []:
        eid = e.get("id") or "edge"
        for end in ("from", "to"):
            if e.get(end) not in ids:
                errors.append("%s: %s=%r is not a declared node" % (eid, end, e.get(end)))
        if e.get("style", "solid") not in STYLES:
            errors.append("%s: unknown style %s" % (eid, e.get("style")))
        if e.get("arrow", "end") not in ARROWS:
            errors.append("%s: unknown arrow type %s" % (eid, e.get("arrow")))
        _check_source(e, errors, eid)

    for i, an in enumerate(scene.get("annotations") or []):
        if not str(an.get("text", "")).strip():
            errors.append("annotation %d: empty text" % i)
        _check_source(an, errors, "annotation %d" % i)

    if not (scene.get("nodes") or []):
        errors.append("nodes: the scene has no entities")
    if not (scene.get("meta") or {}).get("title"):
        warnings.append("meta.title is empty; exports will have no caption")

    colors = {n.get("fill", "#ffffff").lower() for n in scene.get("nodes") or []}
    colors |= {n.get("stroke", "#222222").lower() for n in scene.get("nodes") or []}
    if max_colors and len(colors) > max_colors:
        warnings.append("the scene uses %d colours, above the declared maximum %d"
                        % (len(colors), max_colors))

    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "counts": {"nodes": len(scene.get("nodes") or []),
                       "edges": len(scene.get("edges") or []),
                       "annotations": len(scene.get("annotations") or []),
                       "panels": len(scene.get("panels") or []),
                       "layers": len(layer_ids)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", metavar="SCENE")
    ap.add_argument("--template", action="store_true")
    a = ap.parse_args()
    if a.template:
        demo = blank_scene(1200, 700)
        demo["meta"]["title"] = "example scene"
        demo["nodes"] = [
            {"id": "a", "layer": "shapes", "shape": "roundrect", "x": 80, "y": 120,
             "w": 220, "h": 90, "text": "stimulus", "fill": "#dbe7f5", "stroke": "#2b4a6f",
             "source": {"kind": "stated", "artifact": "source.xml", "quote": "stimulus"}},
            {"id": "b", "layer": "shapes", "shape": "rect", "x": 420, "y": 120,
             "w": 220, "h": 90, "text": "response", "fill": "#f5e6db", "stroke": "#6f4a2b",
             "source": {"kind": "inferred", "note": "relation stated in one sentence"}},
        ]
        demo["edges"] = [{"id": "ab", "from": "a", "to": "b", "label": "drives",
                          "source": {"kind": "stated", "artifact": "source.xml", "quote": "drives"}}]
        json.dump(demo, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    if not a.validate:
        sys.exit("pass --validate SCENE or --template")
    scene = json.load(open(a.validate, encoding="utf-8-sig"))
    report = validate(scene)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
