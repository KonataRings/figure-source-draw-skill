#!/usr/bin/env python3
"""Render a scene JSON to SVG, PDF and PNG without external converters.

    python render.py --scene scene.json --outdir out --basename figure \
        --formats svg,pdf,png --scale 2

SVG keeps every string as <text> inside a named layer, so the export stays
editable. PDF and PNG are drawn from the same coordinates, so all three agree.
"""
import argparse
import json
import math
import os
import sys

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def find_font():
    """A font that can carry both Latin and CJK, or None for the built-in one."""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    try:
        import matplotlib
        p = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return None


def wrap(text, max_width, font_path, size):
    """Break text to fit a box; CJK characters count as one glyph."""
    text = str(text)
    if not text:
        return []
    if font_path:
        try:
            from PIL import ImageFont
            f = ImageFont.truetype(font_path, int(size))
            width = lambda s: f.getlength(s)
        except Exception:
            width = lambda s: len(s) * size * 0.55
    else:
        width = lambda s: len(s) * size * 0.55

    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if width(trial) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _anchor(node):
    return (node["x"] + node["w"] / 2.0, node["y"] + node["h"] / 2.0)


def _border_point(node, toward):
    """Where the straight line to `toward` leaves the node's bounding box."""
    cx, cy = _anchor(node)
    tx, ty = toward
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    hw, hh = node["w"] / 2.0, node["h"] / 2.0
    scale = min(hw / abs(dx) if dx else float("inf"), hh / abs(dy) if dy else float("inf"))
    return cx + dx * scale, cy + dy * scale


def _arrow_head(x1, y1, x2, y2, size=12.0):
    ang = math.atan2(y2 - y1, x2 - x1)
    a1, a2 = ang + math.radians(155), ang - math.radians(155)
    p1 = (x2 + size * math.cos(a1), y2 + size * math.sin(a1))
    p2 = (x2 + size * math.cos(a2), y2 + size * math.sin(a2))
    return [(x2, y2), p1, p2]


def _dash(style):
    return {"solid": None, "dashed": "8,6", "dotted": "2,5"}.get(style, None)


def render_svg(scene, path):
    c = scene["canvas"]
    W, H, bg = c["width"], c["height"], c.get("background", "#ffffff")
    font = find_font()
    family = "sans-serif"
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
           'font-family="%s">' % (W, H, W, H, family),
           "<title>%s</title>" % _esc(scene.get("meta", {}).get("title", "")),
           "<desc>%s</desc>" % _esc(scene.get("meta", {}).get("description", "")),
           '<rect id="canvas-bg" x="0" y="0" width="%d" height="%d" fill="%s"/>' % (W, H, bg)]

    layers = sorted(scene.get("layers") or [{"id": "content", "z": 0}], key=lambda l: l.get("z", 0))
    for layer in layers:
        lid = layer["id"]
        out.append('<g id="layer-%s">' % lid)
        if lid == "connectors":
            for e in scene.get("edges") or []:
                out.extend(_svg_edge(scene, e))
        elif lid == "shapes":
            for n in scene.get("nodes") or []:
                out.extend(_svg_node(n, font))
        elif lid == "labels":
            for n in scene.get("nodes") or []:
                out.extend(_svg_node_text(n))
            out.extend(_svg_legend(scene))
            out.extend(_svg_annotations(scene))
        else:
            if lid == "frame":
                out.extend(_svg_panels(scene))
            for n in scene.get("nodes") or []:
                if n.get("layer") == lid:
                    out.extend(_svg_node(n, font))
        out.append("</g>")
    out.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(out))
    return path


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _svg_shape(n):
    t, x, y, w, h = n.get("shape", "rect"), n["x"], n["y"], n["w"], n["h"]
    fill, stroke = n.get("fill", "#ffffff"), n.get("stroke", "#222222")
    sw = n.get("stroke_width", 2)
    style = 'fill="%s" stroke="%s" stroke-width="%s"' % (fill, stroke, sw)
    if t == "ellipse":
        return ['<ellipse cx="%g" cy="%g" rx="%g" ry="%g" %s/>' % (x + w / 2, y + h / 2, w / 2, h / 2, style)]
    if t == "diamond":
        pts = "%g,%g %g,%g %g,%g %g,%g" % (x + w / 2, y, x + w, y + h / 2, x + w / 2, y + h, x, y + h / 2)
        return ['<polygon points="%s" %s/>' % (pts, style)]
    if t == "hexagon":
        k = w * 0.18
        pts = "%g,%g %g,%g %g,%g %g,%g %g,%g %g,%g" % (
            x + k, y, x + w - k, y, x + w, y + h / 2, x + w - k, y + h, x + k, y + h, x, y + h / 2)
        return ['<polygon points="%s" %s/>' % (pts, style)]
    rx = ' rx="%g"' % n.get("radius", 12) if t == "roundrect" else ""
    return ['<rect x="%g" y="%g" width="%g" height="%g"%s %s/>' % (x, y, w, h, rx, style)]


def _svg_node(n, font):
    out = ['<g id="node-%s" data-source-kind="%s">' % (
        _esc(n.get("id", "n")), _esc((n.get("source") or {}).get("kind", "")))]
    out.extend(_svg_shape(n))
    out.append("</g>")
    return out


def _svg_node_text(n):
    size = n.get("font_size", 16)
    color = n.get("text_color", "#111111")
    lines = wrap(n.get("text", ""), n["w"] - 16, find_font(), size)
    lh = size * 1.3
    total = lh * len(lines)
    x = n["x"] + n["w"] / 2
    y0 = n["y"] + n["h"] / 2 - total / 2 + size * 0.95
    out = []
    for i, line in enumerate(lines):
        out.append('<text id="label-%s-%d" x="%g" y="%g" font-size="%s" fill="%s" '
                   'text-anchor="middle">%s</text>' % (
                       _esc(n.get("id", "n")), i, x, y0 + i * lh, size, color, _esc(line)))
    return out


def _svg_edge(scene, e):
    nodes = {n["id"]: n for n in scene.get("nodes") or []}
    a, b = nodes.get(e.get("from")), nodes.get(e.get("to"))
    if not a or not b:
        return []
    x1, y1 = _border_point(a, _anchor(b))
    x2, y2 = _border_point(b, _anchor(a))
    dash = _dash(e.get("style", "solid"))
    attrs = 'stroke="%s" stroke-width="%s" fill="none"' % (
        e.get("stroke", "#333333"), e.get("stroke_width", 2))
    if dash:
        attrs += ' stroke-dasharray="%s"' % dash
    out = ['<g id="edge-%s">' % _esc(e.get("id", "e")),
           '<line x1="%g" y1="%g" x2="%g" y2="%g" %s/>' % (x1, y1, x2, y2, attrs)]
    if e.get("arrow", "end") in ("end", "both"):
        pts = _arrow_head(x1, y1, x2, y2, e.get("arrow_size", 12))
        out.append('<polygon points="%s" fill="%s"/>' % (
            " ".join("%g,%g" % p for p in pts), e.get("stroke", "#333333")))
    if e.get("arrow") == "both":
        pts = _arrow_head(x2, y2, x1, y1, e.get("arrow_size", 12))
        out.append('<polygon points="%s" fill="%s"/>' % (
            " ".join("%g,%g" % p for p in pts), e.get("stroke", "#333333")))
    if e.get("label"):
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
        out.append('<text id="edge-label-%s" x="%g" y="%g" font-size="%s" fill="#222222" '
                   'text-anchor="middle">%s</text>' % (
                       _esc(e.get("id", "e")), mx, my, e.get("font_size", 14), _esc(e["label"])))
    out.append("</g>")
    return out


def _svg_panels(scene):
    """Panel frames with a letter in the corner, the way journal figures are labelled."""
    out = []
    for i, panel in enumerate(scene.get("panels") or []):
        x, y, w, h = panel["x"], panel["y"], panel["w"], panel["h"]
        out.append('<rect id="panel-%s" x="%g" y="%g" width="%g" height="%g" fill="none" '
                   'stroke="%s" stroke-width="%s" stroke-dasharray="6,4"/>' % (
                       _esc(panel.get("label") or i), x, y, w, h,
                       panel.get("stroke", "#9aa5b1"), panel.get("stroke_width", 1.2)))
        if panel.get("label"):
            out.append('<text id="panel-label-%s" x="%g" y="%g" font-size="%s" '
                       'font-weight="bold" fill="%s">%s</text>' % (
                           _esc(panel["label"]), x + 8, y + 26,
                           panel.get("font_size", 24), panel.get("label_color", "#1b1b1b"),
                           _esc(panel["label"])))
    return out


def _svg_legend(scene):
    items = scene.get("legend") or []
    if not items:
        return []
    c = scene["canvas"]
    x, y = c["width"] - 260, 24
    out = ['<g id="legend">']
    for i, it in enumerate(items):
        yy = y + i * 26
        out.append('<rect x="%g" y="%g" width="18" height="18" fill="%s" stroke="#333"/>' % (
            x, yy, it.get("color", "#cccccc")))
        out.append('<text x="%g" y="%g" font-size="15" fill="#111">%s</text>' % (
            x + 26, yy + 14, _esc(it.get("label", ""))))
    out.append("</g>")
    return out


def _svg_annotations(scene):
    out = []
    for i, an in enumerate(scene.get("annotations") or []):
        out.append('<text id="annotation-%d" x="%g" y="%g" font-size="%s" fill="#333">%s</text>' % (
            i, an.get("x", 24), an.get("y", 40), an.get("font_size", 15), _esc(an.get("text", ""))))
    return out


def _text_block(canvas_obj, font_name, size, n, color, align="center"):
    """Shared line-breaking and vertical centring for the PDF and PNG backends."""
    lines = wrap(n.get("text", ""), n["w"] - 16, find_font(), size)
    lh = size * 1.3
    total = lh * len(lines)
    cx = n["x"] + n["w"] / 2
    top = n["y"] + n["h"] / 2 - total / 2
    return lines, lh, cx, top


def render_pdf(scene, path):
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.colors import HexColor

    c = scene["canvas"]
    W, H = c["width"], c["height"]
    pdf = rl_canvas.Canvas(path, pagesize=(W, H))
    pdf.setFillColor(HexColor(c.get("background", "#ffffff")))
    pdf.rect(0, 0, W, H, stroke=0, fill=1)
    font_path = find_font()
    font_name = "F1"
    if font_path:
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception:
            font_name = "Helvetica"
    else:
        font_name = "Helvetica"

    def draw_text(x, y, text, size, color, align="left"):
        pdf.setFillColor(HexColor(color))
        pdf.setFont(font_name, size)
        if align == "center":
            pdf.drawCentredString(x, H - y, text)
        else:
            pdf.drawString(x, H - y, text)

    for e in scene.get("edges") or []:
        nodes = {n["id"]: n for n in scene.get("nodes") or []}
        a, b = nodes.get(e.get("from")), nodes.get(e.get("to"))
        if not a or not b:
            continue
        x1, y1 = _border_point(a, _anchor(b))
        x2, y2 = _border_point(b, _anchor(a))
        pdf.setStrokeColor(HexColor(e.get("stroke", "#333333")))
        pdf.setLineWidth(e.get("stroke_width", 2))
        style = e.get("style", "solid")
        if style == "dashed":
            pdf.setDash(8, 6)
        elif style == "dotted":
            pdf.setDash(2, 5)
        else:
            pdf.setDash()
        pdf.line(x1, H - y1, x2, H - y2)
        if e.get("arrow", "end") in ("end", "both"):
            pts = _arrow_head(x1, y1, x2, y2, e.get("arrow_size", 12))
            p = pdf.beginPath()
            p.moveTo(pts[0][0], H - pts[0][1])
            for q in pts[1:]:
                p.lineTo(q[0], H - q[1])
            p.close()
            pdf.setFillColor(HexColor(e.get("stroke", "#333333")))
            pdf.drawPath(p, stroke=0, fill=1)
        if e.get("label"):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
            draw_text(mx, my, e["label"], e.get("font_size", 14), "#222222", "center")

    for panel in scene.get("panels") or []:
        pdf.setStrokeColor(HexColor(panel.get("stroke", "#9aa5b1")))
        pdf.setLineWidth(panel.get("stroke_width", 1.2))
        pdf.setDash(6, 4)
        pdf.rect(panel["x"], H - panel["y"] - panel["h"], panel["w"], panel["h"],
                 stroke=1, fill=0)
        pdf.setDash()
        if panel.get("label"):
            draw_text(panel["x"] + 8, panel["y"] + 26, panel["label"],
                      panel.get("font_size", 24), panel.get("label_color", "#1b1b1b"))

    for n in scene.get("nodes") or []:
        x, y, w, h = n["x"], n["y"], n["w"], n["h"]
        pdf.setFillColor(HexColor(n.get("fill", "#ffffff")))
        pdf.setStrokeColor(HexColor(n.get("stroke", "#222222")))
        pdf.setLineWidth(n.get("stroke_width", 2))
        shape = n.get("shape", "rect")
        if shape == "ellipse":
            pdf.ellipse(x, H - y - h, x + w, H - y, stroke=1, fill=1)
        elif shape in ("diamond", "hexagon"):
            if shape == "diamond":
                pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
            else:
                k = w * 0.18
                pts = [(x + k, y), (x + w - k, y), (x + w, y + h / 2),
                       (x + w - k, y + h), (x + k, y + h), (x, y + h / 2)]
            p = pdf.beginPath()
            p.moveTo(pts[0][0], H - pts[0][1])
            for q in pts[1:]:
                p.lineTo(q[0], H - q[1])
            p.close()
            pdf.drawPath(p, stroke=1, fill=1)
        else:
            pdf.roundRect(x, H - y - h, w, h, n.get("radius", 12) if shape == "roundrect" else 0,
                          stroke=1, fill=1)
        size = n.get("font_size", 16)
        lines, lh, cx, top = _text_block(None, None, size, n, n.get("text_color", "#111111"))
        for i, line in enumerate(lines):
            draw_text(cx, top + i * lh + size * 0.95, line, size,
                      n.get("text_color", "#111111"), "center")

    legend = scene.get("legend") or []
    for i, it in enumerate(legend):
        x, y = W - 260, 24 + i * 26
        pdf.setFillColor(HexColor(it.get("color", "#cccccc")))
        pdf.setStrokeColor(HexColor("#333333"))
        pdf.rect(x, H - y - 18, 18, 18, stroke=1, fill=1)
        draw_text(x + 26, y + 14, it.get("label", ""), 15, "#111111")

    for an in scene.get("annotations") or []:
        draw_text(an.get("x", 24), an.get("y", 40), an.get("text", ""),
                  an.get("font_size", 15), "#333333")

    pdf.showPage()
    pdf.save()
    return path


def render_png(scene, path, scale=2):
    from PIL import Image, ImageDraw, ImageFont

    c = scene["canvas"]
    W, H = int(c["width"] * scale), int(c["height"] * scale)
    img = Image.new("RGB", (W, H), c.get("background", "#ffffff"))
    d = ImageDraw.Draw(img)
    font_path = find_font()

    def F(size):
        if font_path:
            return ImageFont.truetype(font_path, int(size * scale))
        return ImageFont.load_default()

    def text(x, y, s, size, color, anchor="mm"):
        d.text((x * scale, y * scale), s, font=F(size), fill=color, anchor=anchor)

    for e in scene.get("edges") or []:
        nodes = {n["id"]: n for n in scene.get("nodes") or []}
        a, b = nodes.get(e.get("from")), nodes.get(e.get("to"))
        if not a or not b:
            continue
        x1, y1 = _border_point(a, _anchor(b))
        x2, y2 = _border_point(b, _anchor(a))
        d.line([(x1 * scale, y1 * scale), (x2 * scale, y2 * scale)],
               fill=e.get("stroke", "#333333"), width=int(e.get("stroke_width", 2) * scale))
        if e.get("arrow", "end") in ("end", "both"):
            pts = _arrow_head(x1, y1, x2, y2, e.get("arrow_size", 12))
            d.polygon([(p[0] * scale, p[1] * scale) for p in pts], fill=e.get("stroke", "#333333"))
        if e.get("label"):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
            text(mx, my, e["label"], e.get("font_size", 14), "#222222", "mm")

    for panel in scene.get("panels") or []:
        d.rectangle([panel["x"] * scale, panel["y"] * scale,
                     (panel["x"] + panel["w"]) * scale, (panel["y"] + panel["h"]) * scale],
                    outline=panel.get("stroke", "#9aa5b1"),
                    width=max(1, int(panel.get("stroke_width", 1.2) * scale)))
        if panel.get("label"):
            text(panel["x"] + 8, panel["y"] + 26, panel["label"],
                 panel.get("font_size", 24), panel.get("label_color", "#1b1b1b"), "lm")

    for n in scene.get("nodes") or []:
        box = [n["x"] * scale, n["y"] * scale, (n["x"] + n["w"]) * scale, (n["y"] + n["h"]) * scale]
        fill, stroke = n.get("fill", "#ffffff"), n.get("stroke", "#222222")
        shape = n.get("shape", "rect")
        if shape == "ellipse":
            d.ellipse(box, fill=fill, outline=stroke, width=int(n.get("stroke_width", 2) * scale))
        elif shape == "diamond":
            pts = [(n["x"] + n["w"] / 2, n["y"]), (n["x"] + n["w"], n["y"] + n["h"] / 2),
                   (n["x"] + n["w"] / 2, n["y"] + n["h"]), (n["x"], n["y"] + n["h"] / 2)]
            d.polygon([(p[0] * scale, p[1] * scale) for p in pts], fill=fill, outline=stroke)
        else:
            radius = int(n.get("radius", 12) * scale) if shape == "roundrect" else 0
            d.rounded_rectangle(box, radius=radius, fill=fill, outline=stroke,
                                width=int(n.get("stroke_width", 2) * scale))
        size = n.get("font_size", 16)
        lines, lh, cx, top = _text_block(None, None, size, n, n.get("text_color", "#111111"))
        for i, line in enumerate(lines):
            text(cx, top + i * lh + size * 0.5, line, size, n.get("text_color", "#111111"), "mm")

    for i, it in enumerate(scene.get("legend") or []):
        x, y = c["width"] - 260, 24 + i * 26
        d.rectangle([x * scale, y * scale, (x + 18) * scale, (y + 18) * scale],
                    fill=it.get("color", "#cccccc"), outline="#333333")
        text(x + 26, y + 9, it.get("label", ""), 15, "#111111", "lm")

    for an in scene.get("annotations") or []:
        text(an.get("x", 24), an.get("y", 40), an.get("text", ""), an.get("font_size", 15),
             "#333333", "lm")

    img.save(path, dpi=(c.get("dpi", 300), c.get("dpi", 300)))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--basename", default="figure")
    ap.add_argument("--formats", default="svg,pdf,png")
    ap.add_argument("--scale", type=float, default=2.0)
    a = ap.parse_args()

    scene = json.load(open(a.scene, encoding="utf-8-sig"))
    os.makedirs(a.outdir, exist_ok=True)
    written = {}
    formats = [f.strip().lower() for f in a.formats.split(",") if f.strip()]
    for fmt in formats:
        path = os.path.join(a.outdir, "%s.%s" % (a.basename, fmt))
        if fmt == "svg":
            render_svg(scene, path)
        elif fmt == "pdf":
            render_pdf(scene, path)
        elif fmt == "png":
            render_png(scene, path, a.scale)
        else:
            continue
        written[fmt] = {"path": path, "bytes": os.path.getsize(path)}
    print(json.dumps({"scene": a.scene, "written": written,
                      "font": find_font() or "builtin", "ok": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
