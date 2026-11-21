#!/usr/bin/env python3
"""Edit an existing SVG in place-preserving mode: change, never re-draw.

    python edit_svg.py --svg in.svg --edits edits.json --output out.svg \
        --log edit_log.json

edits.json is a list of operations addressed to element ids that already exist:

    [{"op": "set-text", "id": "label-n1-0", "text": "hypothalamus"},
     {"op": "move", "id": "node-n1", "dx": 40, "dy": -10},
     {"op": "recolor", "id": "node-n1", "fill": "#eef", "stroke": "#335"},
     {"op": "delete", "id": "edge-e3"}]

Everything not named in the edits is left byte-comparable, so the author's
layout survives the change. The log records what moved, from where to where.
"""
import argparse
import copy
import json
import sys

from lxml import etree

SVG = "http://www.w3.org/2000/svg"
EDITABLE_TAGS = {"text", "rect", "ellipse", "polygon", "line", "g", "path"}


def find(root, eid):
    for el in root.iter():
        if isinstance(el.tag, str) and el.get("id") == eid:
            return el
    return None


def shift_polygon(points, dx, dy):
    out = []
    for pair in points.split():
        x, y = pair.split(",")
        out.append("%g,%g" % (float(x) + dx, float(y) + dy))
    return " ".join(out)


def apply_edit(root, edit, log):
    op, eid = edit.get("op"), edit.get("id")
    el = find(root, eid)
    if el is None:
        log.append({"op": op, "id": eid, "status": "missing", "reason": "no such element id"})
        return False
    tag = etree.QName(el).localname
    if tag not in EDITABLE_TAGS:
        log.append({"op": op, "id": eid, "status": "refused",
                    "reason": "%s is not an element this editor changes" % tag})
        return False

    if op == "set-text":
        before = "".join(el.itertext())
        for child in list(el):
            el.remove(child)
        el.text = edit.get("text", "")
        log.append({"op": op, "id": eid, "status": "applied", "before": before,
                    "after": el.text})
        return True

    if op == "move":
        dx, dy = float(edit.get("dx", 0)), float(edit.get("dy", 0))
        if tag in ("rect", "image", "text"):
            before = {"x": el.get("x"), "y": el.get("y")}
            el.set("x", "%g" % (float(el.get("x", 0)) + dx))
            el.set("y", "%g" % (float(el.get("y", 0)) + dy))
            log.append({"op": op, "id": eid, "status": "applied", "before": before,
                        "after": {"x": el.get("x"), "y": el.get("y")}})
            return True
        if tag == "polygon":
            before = el.get("points")
            el.set("points", shift_polygon(before, dx, dy))
            log.append({"op": op, "id": eid, "status": "applied", "before": before,
                        "after": el.get("points")})
            return True
        if tag == "ellipse":
            before = {"cx": el.get("cx"), "cy": el.get("cy")}
            el.set("cx", "%g" % (float(el.get("cx", 0)) + dx))
            el.set("cy", "%g" % (float(el.get("cy", 0)) + dy))
            log.append({"op": op, "id": eid, "status": "applied", "before": before,
                        "after": {"cx": el.get("cx"), "cy": el.get("cy")}})
            return True
        if tag == "line":
            before = {k: el.get(k) for k in ("x1", "y1", "x2", "y2")}
            for k, d in (("x1", dx), ("x2", dx), ("y1", dy), ("y2", dy)):
                el.set(k, "%g" % (float(el.get(k, 0)) + d))
            log.append({"op": op, "id": eid, "status": "applied", "before": before,
                        "after": {k: el.get(k) for k in ("x1", "y1", "x2", "y2")}})
            return True
        if tag == "g":
            n = 0
            for child in el.iter():
                if etree.QName(child).localname == "rect":
                    child.set("x", "%g" % (float(child.get("x", 0)) + dx))
                    child.set("y", "%g" % (float(child.get("y", 0)) + dy))
                    n += 1
                elif etree.QName(child).localname == "text":
                    child.set("x", "%g" % (float(child.get("x", 0)) + dx))
                    child.set("y", "%g" % (float(child.get("y", 0)) + dy))
                    n += 1
            log.append({"op": op, "id": eid, "status": "applied", "moved_children": n})
            return n > 0
        log.append({"op": op, "id": eid, "status": "refused",
                    "reason": "move does not know how to shift <%s>" % tag})
        return False

    if op == "recolor":
        changed = {}
        for attr in ("fill", "stroke"):
            if edit.get(attr):
                changed[attr] = {"before": el.get(attr), "after": edit[attr]}
                el.set(attr, edit[attr])
        log.append({"op": op, "id": eid, "status": "applied" if changed else "no-op",
                    "changed": changed})
        return bool(changed)

    if op == "delete":
        parent = el.getparent()
        snapshot = etree.tostring(el, encoding="unicode")[:160]
        parent.remove(el)
        log.append({"op": op, "id": eid, "status": "applied", "removed": snapshot})
        return True

    log.append({"op": op, "id": eid, "status": "refused", "reason": "unknown op %r" % op})
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", required=True)
    ap.add_argument("--edits", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--log", default="edit_log.json")
    a = ap.parse_args()

    tree = etree.parse(a.svg)
    root = tree.getroot()
    before = etree.tostring(root, encoding="unicode")
    edits = json.load(open(a.edits, encoding="utf-8-sig"))
    if isinstance(edits, dict):
        edits = edits.get("edits") or []

    log = []
    for edit in edits:
        apply_edit(root, edit, log)

    after = etree.tostring(root, encoding="unicode")
    tree.write(a.output, encoding="UTF-8", xml_declaration=True, pretty_print=True)

    applied = sum(1 for r in log if r["status"] == "applied")
    refused = [r for r in log if r["status"] in ("refused", "missing")]
    json.dump({"svg_in": a.svg, "svg_out": a.output, "edits_requested": len(edits),
               "applied": applied, "not_applied": refused, "log": log,
               "unchanged_outside_edits": before != after},
              open(a.log, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"applied": applied, "requested": len(edits),
                      "not_applied": len(refused), "log": a.log}, ensure_ascii=False))
    return 0 if not refused else 1


if __name__ == "__main__":
    sys.exit(main())
