# 三分钟上手

## 1. 一条命令

```bash
python scripts/run_case.py --input /input --work /app/work --output /app/output
```

它按材料自动选路线：有 `scene*.json` 画示意图；有 `*.csv` 加 `*spec*.json` 画图表；两者都没有但有 `*.svg` 加 `edits*.json` 则做保源编辑。打印一行摘要：

```json
{"case_id": "EXAMPLE-FIG", "status": "success", "route": "scene",
 "outputs": ["chart.png", "figure.svg", "figure.pdf", "figure.png", "ledger.csv"]}
```

## 2. 写场景（示意图路线）

```json
{"canvas": {"width": 1200, "height": 700},
 "layers": [{"id": "connectors", "z": 1}, {"id": "shapes", "z": 2}, {"id": "labels", "z": 3}],
 "nodes": [{"id": "n1", "layer": "shapes", "shape": "roundrect", "x": 80, "y": 120,
            "w": 220, "h": 90, "text": "刺激输入",
            "source": {"kind": "stated", "artifact": "source.xml", "quote": "原文句子"}}],
 "edges": [{"id": "e1", "from": "n1", "to": "n2", "label": "传导",
            "source": {"kind": "inferred", "note": "关系由上下文推断"}}]}
```

规则只有三条：`id` 唯一、边必须指向存在的节点、每个元素都要 `source`。想标"这是推断"就写 `kind: inferred` 并给 `note`，不要假装它来自原文。

## 3. 写图表规格（图表路线）

```json
{"x": "time_s", "series": [{"y": "signal_mV", "label": "记录信号"}],
 "style": "line", "xlabel": "时间 (s)", "ylabel": "幅度 (mV)"}
```

只写列名，不写数值——数值永远来自 `data.csv`，这样图可以随时重画。

## 4. 编辑既有 SVG（编辑路线）

```json
[{"op": "set-text", "id": "label-n1-0", "text": "新标签"},
 {"op": "move", "id": "node-n1", "dx": 40, "dy": -10},
 {"op": "recolor", "id": "node-n2", "fill": "#eef"}]
```

被点名的元素改，其余不动；找不到的 id 会被拒绝并记入 `edit_log.json`。

## 5. 交付前检查

```bash
python scripts/check_export.py --svg out/figure.svg --png out/figure.png --pdf out/figure.pdf
python selftest.py
python benchmark/run_benchmark.py
```

第一条给导出检查；后两条验证包本身可用，并给出自建基准的通过率（不是官方得分）。

## 材料不足时

若摘要里 `route` 为 `none`、`status` 为 `insufficient_evidence`，说明材料里既没有场景也没有数据表。正确做法是在 `result.json` 里写明缺什么，不要凭领域常识补出一张图。
