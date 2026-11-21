#!/usr/bin/env python3
"""Chart from the case's own data: CSV or JSON in, SVG + PDF + PNG out.

    python chart.py --data data.csv --spec chart_spec.json --outdir out --basename fig2

The spec names the columns, never the values, so the figure is regenerated from
the source table instead of being redrawn by hand. Every series keeps a column
mapping in the returned JSON, which is what the ledger records.
"""
import argparse
import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

STYLES = ("line", "scatter", "bar", "barh", "errorbar")


def load_table(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".tsv", ".txt"):
        delim = "\t" if ext == ".tsv" else ","
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=delim))
        if not rows:
            raise SystemExit("data file has no rows: %s" % path)
        cols = list(rows[0].keys())
    elif ext == ".json":
        obj = json.load(open(path, encoding="utf-8-sig"))
        if isinstance(obj, dict) and "rows" in obj:
            rows, cols = obj["rows"], list(obj["rows"][0].keys())
        elif isinstance(obj, list):
            rows, cols = obj, list(obj[0].keys())
        else:
            raise SystemExit("JSON data must be a list of rows or {\"rows\": [...]}")
    else:
        raise SystemExit("unsupported data type: %s" % ext)
    return rows, cols


def as_number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--basename", default="chart")
    ap.add_argument("--formats", default="svg,pdf,png")
    a = ap.parse_args()

    rows, cols = load_table(a.data)
    spec = json.load(open(a.spec, encoding="utf-8-sig"))
    xcol = spec.get("x")
    if xcol not in cols:
        sys.exit("x column %r not in data columns %s" % (xcol, cols))

    series = spec.get("series") or []
    if not series:
        sys.exit("spec.series is empty")
    mapping = []
    for s in series:
        if s["y"] not in cols:
            sys.exit("series column %r not in data columns %s" % (s["y"], cols))
        vals = [as_number(r.get(s["y"])) for r in rows]
        if all(v is None for v in vals):
            sys.exit("series column %r holds no numbers" % s["y"])
        mapping.append({"label": s.get("label", s["y"]), "column": s["y"],
                        "points": sum(1 for v in vals if v is not None),
                        "missing": sum(1 for v in vals if v is None)})

    xs = [as_number(r.get(xcol)) for r in rows]
    x_numeric = all(v is not None for v in xs)
    xvals = xs if x_numeric else [r.get(xcol, "") for r in rows]

    style = spec.get("style", "line")
    if style not in STYLES:
        sys.exit("unknown style %r, choose from %s" % (style, STYLES))

    fig, ax = plt.subplots(figsize=tuple(spec.get("figsize", [6.4, 4.2])),
                           dpi=spec.get("dpi", 300))
    for s, m in zip(series, mapping):
        y = [as_number(r.get(s["y"])) for r in rows]
        y = [float("nan") if v is None else v for v in y]
        kw = {"label": m["label"], "color": s.get("color"), "linewidth": s.get("linewidth", 2),
              "marker": s.get("marker", "o" if style == "scatter" else None),
              "markersize": s.get("markersize", 5)}
        if style == "bar":
            ax.bar(xvals, y, label=m["label"], color=s.get("color"))
        elif style == "barh":
            ax.barh(xvals, y, label=m["label"], color=s.get("color"))
        elif style == "scatter":
            ax.scatter(xvals, y, label=m["label"], color=s.get("color"),
                       s=s.get("markersize", 30))
        elif style == "errorbar":
            err = s.get("err")
            yerr = [as_number(r.get(err)) for r in rows] if err in cols else None
            ax.errorbar(xvals, y, yerr=yerr, label=m["label"], color=s.get("color"),
                        capsize=3, linewidth=s.get("linewidth", 2))
        else:
            order = sorted(range(len(xvals)), key=lambda i: (xvals[i] if x_numeric else str(xvals[i])))
            ax.plot([xvals[i] for i in order], [y[i] for i in order], **kw)

    ax.set_xlabel(spec.get("xlabel", xcol))
    ax.set_ylabel(spec.get("ylabel", series[0]["y"]))
    if spec.get("title"):
        ax.set_title(spec["title"])
    if spec.get("ylim"):
        ax.set_ylim(*spec["ylim"])
    if spec.get("xlim"):
        ax.set_xlim(*spec["xlim"])
    ax.grid(spec.get("grid", True), alpha=0.3, linewidth=0.6)
    if len(series) > 1 or spec.get("legend", True):
        ax.legend(frameon=False, fontsize=spec.get("legend_size", 9))
    fig.tight_layout()

    os.makedirs(a.outdir, exist_ok=True)
    written = {}
    for fmt in [f.strip().lower() for f in a.formats.split(",") if f.strip()]:
        path = os.path.join(a.outdir, "%s.%s" % (a.basename, fmt))
        fig.savefig(path, format=fmt, dpi=spec.get("dpi", 300),
                    bbox_inches="tight", facecolor="white")
        written[fmt] = {"path": path, "bytes": os.path.getsize(path)}
    plt.close(fig)

    info = {"data": os.path.abspath(a.data), "rows": len(rows), "x": xcol,
            "x_numeric": x_numeric, "style": style, "series": mapping,
            "written": written, "columns": cols}
    json.dump(info, open(os.path.join(a.outdir, "chart_mapping.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: info[k] for k in ("rows", "x", "style", "series", "written")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
