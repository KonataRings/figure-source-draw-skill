#!/usr/bin/env python3
"""Inspect the exported figure files and report what a reviewer can verify.

    python check_export.py --svg out/fig.svg --png out/fig.png --pdf out/fig.pdf \
        --min-text 3 --output out/export_check.json

Checks: file exists and is not empty, SVG carries text as <text> inside layers,
no drawn element falls outside the viewBox, PNG is non-blank at the declared size,
PDF opens with the expected page size. Anything that fails is reported as a
problem with the file that caused it.
"""
import argparse
import json
import os
import sys


def check_svg(path, max_colors=12):
    from lxml import etree
    res = {"file": path, "ok": True, "problems": [], "warnings": [], "facts": {}}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        res["ok"] = False
        res["problems"].append("missing or empty")
        return res
    tree = etree.parse(path)
    root = tree.getroot()
    vb = root.get("viewBox")
    res["facts"]["viewBox"] = vb
    res["facts"]["width"] = root.get("width")
    res["facts"]["height"] = root.get("height")
    ns = {"s": "http://www.w3.org/2000/svg"}
    texts = root.findall(".//s:text", ns)
    groups = root.findall(".//s:g", ns)
    res["facts"]["text_elements"] = len(texts)
    res["facts"]["groups"] = len(groups)
    res["facts"]["layer_ids"] = [g.get("id") for g in groups if (g.get("id") or "").startswith("layer-")]
    if not texts:
        res["ok"] = False
        res["problems"].append("no <text> elements: labels were converted to paths and cannot be edited")
    if not res["facts"]["layer_ids"]:
        res["problems"].append("no named layers: the file is still editable but not organised")
    if vb:
        _, _, vw, vh = [float(v) for v in vb.replace(",", " ").split()]
        for el in root.iter():
            tag = etree.QName(el).localname if isinstance(el.tag, str) else ""
            if tag in ("rect", "image"):
                try:
                    x, y = float(el.get("x", 0)), float(el.get("y", 0))
                    w, h = float(el.get("width", 0)), float(el.get("height", 0))
                except ValueError:
                    continue
                if el.get("id") == "canvas-bg":
                    continue
                if x < -1 or y < -1 or x + w > vw + 1 or y + h > vh + 1:
                    res["problems"].append("element %s falls outside the viewBox" % (el.get("id") or tag))
    families = sorted({el.get("font-family") for el in root.iter()
                       if isinstance(el.tag, str) and el.get("font-family")})
    colours = sorted({(el.get("fill") or "").lower() for el in root.iter()
                      if isinstance(el.tag, str) and el.get("fill")}
                     | {(el.get("stroke") or "").lower() for el in root.iter()
                        if isinstance(el.tag, str) and el.get("stroke")})
    colours = [c for c in colours if c not in ("none", "")]
    res["facts"]["font_families"] = families or ["inherited (no explicit font-family)"]
    res["facts"]["colors"] = len(colours)
    if len(colours) > max_colors:
        res["warnings"].append("%d distinct colours; a journal figure usually stays under %d"
                               % (len(colours), max_colors))
    return res


def check_png(path):
    from PIL import Image
    import numpy as np
    res = {"file": path, "ok": True, "problems": [], "warnings": [], "facts": {}}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        res["ok"] = False
        res["problems"].append("missing or empty")
        return res
    img = Image.open(path)
    arr = np.asarray(img.convert("L"))
    res["facts"].update({"size": img.size, "mode": img.mode,
                         "dpi": img.info.get("dpi"),
                         "stddev": round(float(arr.std()), 2),
                         "unique_levels": int(len(np.unique(arr)))})
    if arr.std() < 1.0:
        res["ok"] = False
        res["problems"].append("the image is blank")
    if img.size[0] < 200 or img.size[1] < 150:
        res["problems"].append("image is small (%dx%d); check the requested scale" % img.size)
    return res


def check_pdf(path):
    res = {"file": path, "ok": True, "problems": [], "warnings": [], "facts": {}}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        res["ok"] = False
        res["problems"].append("missing or empty")
        return res
    try:
        import pymupdf as fitz
    except Exception:
        try:
            import fitz
        except Exception:
            res["facts"]["note"] = "PyMuPDF not available; page size not checked"
            return res
    doc = fitz.open(path)
    res["facts"]["pages"] = doc.page_count
    if doc.page_count:
        r = doc[0].rect
        res["facts"]["page_size"] = [round(r.width, 1), round(r.height, 1)]
        text = doc[0].get_text().strip()
        res["facts"]["text_chars"] = len(text)
        if len(text) < 5:
            res["problems"].append("PDF page has almost no extractable text")
        try:
            fonts = doc[0].get_fonts()
            res["facts"]["fonts"] = sorted({f[3] for f in fonts if len(f) > 3})
            res["facts"]["fonts_embedded"] = all(
                (f[1] not in ("n/a", None)) for f in fonts) if fonts else None
        except Exception:
            pass
    doc.close()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg")
    ap.add_argument("--png")
    ap.add_argument("--pdf")
    ap.add_argument("--min-text", type=int, default=1)
    ap.add_argument("--output", default="export_check.json")
    a = ap.parse_args()

    report = {"checks": [], "ok": True, "problems": [], "warnings": []}
    for path, fn in ((a.svg, check_svg), (a.png, check_png), (a.pdf, check_pdf)):
        if not path:
            continue
        r = fn(path)
        report["checks"].append(r)
        if not r["ok"]:
            report["ok"] = False
        report["problems"].extend("%s: %s" % (os.path.basename(path), p) for p in r["problems"])
        report["warnings"].extend("%s: %s" % (os.path.basename(path), w)
                                  for w in r.get("warnings") or [])

    text_total = sum(c["facts"].get("text_elements", 0) for c in report["checks"])
    report["text_elements"] = text_total
    if a.svg and text_total < a.min_text:
        report["ok"] = False
        report["problems"].append("expected at least %d labels, found %d" % (a.min_text, text_total))

    json.dump(report, open(a.output, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"ok": report["ok"], "problems": report["problems"][:6],
                      "text_elements": text_total}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
