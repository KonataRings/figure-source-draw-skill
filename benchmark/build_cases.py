#!/usr/bin/env python3
"""Build the self-made benchmark cases for this skill.

    python build_cases.py > cases.json

Six synthetic scenes, each aimed at one failure mode the skill claims to handle:
shape variety, long labels that must wrap, CJK labels, a deliberately off-canvas
node, a deliberately missing source, and a three-series chart. Expected outcomes
are declared here, so a pass means the skill behaved as documented rather than
"something was produced".
"""
import json

def node(i, shape, x, y, w, h, text, kind="stated", **kw):
    n = {"id": "n%d" % i, "layer": "shapes", "shape": shape, "x": x, "y": y,
         "w": w, "h": h, "text": text}
    n["source"] = ({"kind": "stated", "artifact": "source.txt", "quote": text[:40]}
                   if kind == "stated" else {"kind": kind, "note": "derived from the text order"})
    n.update(kw)
    return n


def scene(nodes, edges=(), width=1200, height=800, panels=(), constraints=None):
    s = {"canvas": {"width": width, "height": height, "background": "#ffffff", "dpi": 300},
         "meta": {"title": "benchmark scene", "description": "", "case_id": "BENCH"},
         "layers": [{"id": "connectors", "z": 1}, {"id": "shapes", "z": 2},
                    {"id": "labels", "z": 3}],
         "nodes": list(nodes), "edges": list(edges), "legend": [], "annotations": [],
         "panels": list(panels)}
    if constraints:
        s["constraints"] = constraints
    return s


def edge(i, a, b, label=None, style="solid"):
    e = {"id": "e%d" % i, "from": a, "to": b, "style": style,
         "source": {"kind": "stated", "artifact": "source.txt", "quote": "relation"}}
    if label:
        e["label"] = label
    return e


CASES = [
    {"id": "shapes-four", "expect": "success",
     "scene": scene([node(1, "rect", 80, 100, 200, 100, "A"),
                     node(2, "roundrect", 360, 100, 200, 100, "B"),
                     node(3, "ellipse", 640, 80, 220, 140, "C"),
                     node(4, "diamond", 300, 320, 200, 120, "D")],
                    [edge(1, "n1", "n2", "then"), edge(2, "n2", "n3", "then"),
                     edge(3, "n4", "n2", "inhibits", "dashed")]),
     "min_text": 4},
    {"id": "long-label-wrap", "expect": "success",
     "scene": scene([node(1, "rect", 100, 100, 240, 140,
                          "a long caption that has to wrap over several lines inside the box"),
                     node(2, "rect", 500, 100, 240, 140, "short")],
                    [edge(1, "n1", "n2")]),
     "min_text": 2},
    {"id": "cjk-label", "expect": "success",
     "scene": scene([node(1, "roundrect", 100, 120, 260, 120, "刺激输入"),
                     node(2, "ellipse", 520, 110, 260, 140, "记录电极")],
                    [edge(1, "n1", "n2", "传导")]),
     "min_text": 2},
    {"id": "off-canvas", "expect": "warning",
     "scene": scene([node(1, "rect", 60, 60, 200, 100, "inside"),
                     node(2, "rect", 1100, 700, 260, 160, "sticks out")],
                    [edge(1, "n1", "n2")]),
     "min_text": 2, "expect_warning": "outside the canvas"},
    {"id": "missing-source", "expect": "invalid",
     "scene": {"canvas": {"width": 800, "height": 600},
               "layers": [{"id": "shapes", "z": 1}],
               "nodes": [{"id": "n1", "shape": "rect", "x": 50, "y": 50, "w": 200, "h": 100,
                          "text": "no provenance"}],
               "edges": [], "legend": [], "annotations": []},
     "min_text": 0},
    {"id": "panelled-overview", "expect": "success", "min_text": 3,
     "scene": scene([node(1, "roundrect", 90, 300, 200, 100, "sensor"),
                     node(2, "rect", 420, 300, 220, 100, "amplifier"),
                     node(3, "ellipse", 720, 285, 220, 130, "recorder")],
                    [edge(1, "n1", "n2"), edge(2, "n2", "n3")],
                    panels=[{"label": "A", "x": 50, "y": 260, "w": 300, "h": 190},
                            {"label": "B", "x": 380, "y": 260, "w": 620, "h": 190}],
                    constraints={"min_font_size": 12, "max_colors": 10})},
    {"id": "font-too-small", "expect": "invalid", "expect_error": "below the declared minimum",
     "scene": scene([node(1, "rect", 80, 80, 200, 100, "tiny", font_size=8)],
                    constraints={"min_font_size": 14})},
    {"id": "three-series-chart", "expect": "chart",
     "chart": {"x": "t",
               "series": [{"y": "a", "label": "A"}, {"y": "b", "label": "B"},
                          {"y": "c", "label": "C"}],
               "style": "line", "xlabel": "t", "ylabel": "value"},
     "rows": [{"t": i, "a": i, "b": 2 * i, "c": i * i} for i in range(9)],
     "min_text": 0},
]

if __name__ == "__main__":
    print(json.dumps(CASES, ensure_ascii=False, indent=1))

