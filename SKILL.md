---
name: figure-source-draw
description: 依据材料生成或编辑科研图稿，同时交付可编辑源文件（分层 SVG）、PDF/PNG 导出件与逐元素来源台账；支持示意图与机制图、数据图表、以及对既有 SVG 的保源修改，并在导出后自检文字可编辑性、越界元素与空白图。
---

# 科研绘图：出图，也保留可编辑来源

本 Skill 面向"依据固定材料产出可复用科研图稿"的任务：从材料里取出实体、关系、数据和图面约束，画成图，同时交付能被别人继续编辑的源文件、能直接使用的导出件，以及每个元素来自哪一句/哪一列的台账。它不负责美化排版，也不替材料补出原文没有的结构。

## 适用条件

材料满足下列任一情形即可调用：

- 需要把文字描述的实体与关系画成示意图、机制图或流程图（含分层与图例要求）。
- 有数据表（CSV/TSV/JSON）需要画成图，且要求图与数据对应、可重画。
- 已有 SVG 图稿需要按新要求修改，且必须保住原作者的布局。

不适用于：纯图像美化、照片修图、三维渲染，以及材料里没有任何结构与数据、只能凭空想象的场景——后者应报 `insufficient_evidence`。

## 输入

| 位置 | 内容 | 说明 |
|-|-|-|
| `/input/case.json` | 案例标识与 `output_contract` | 决定必须交哪些字段 |
| `/input/task.md` | 任务说明 | 图要回答的问题、图面约束 |
| `/input/artifacts/` | 原始材料 | 论文 PDF/XML、数据表、既有 SVG、编辑要求 |

脚本按文件名识别路线，不依赖领域标签：`scene*.json` 走示意图路线，`*.csv` 加 `*spec*.json` 走图表路线，`*.svg` 加 `edits*.json` 走编辑路线。同一案例可同时命中多条。

## 处理流程

1. **清点材料。** 列出 `artifacts` 下每个文件的类型与大小，判断有哪些能作为图面依据；PDF/XML 先抽出正文与图表说明，数据表先看列名与量纲。
2. **确定路线并建场景。** 示意图路线写 `scene.json`：`nodes` 记实体，`edges` 记关系，`legend` 记图例，`layers` 决定叠放顺序；每个元素必须带 `source`，取自原文的写 `{"kind":"stated","artifact":...,"quote":...}`，由推断得到的写 `{"kind":"inferred","note":"为什么推断"}`。图表路线写 `chart_spec.json`，只写列名与样式，不写数值。
3. **校验与出图。** `scene.py --validate` 先查 id 唯一性、边是否指向存在的节点、元素是否越界、来源是否缺失；通过后 `render.py` 一次产出 SVG、PDF、PNG 三份同坐标的文件。
4. **导出自检。** `check_export.py` 检查三件事：SVG 里文字仍是 `<text>`（不是路径，否则不可编辑）、没有元素落到画布外、PNG 不是空白、PDF 能打开且尺寸正确。
5. **建台账并装配结果。** `ledger.py` 为每个元素写一行来源；`run_case.py` 汇总 `result.json`，未填字段标 `insufficient_evidence` 并降级为 `partial`。

一条命令即可完成 2—5 步：

```bash
python scripts/run_case.py --input /input --work /app/work --output /app/output
```

## 三条路线的落地方式

**示意图。** 场景模型只有五种形状（矩形、圆角矩形、椭圆、菱形、六边形）与三类连线（实线、虚线、点线），这是刻意的限制：结构图的可核验性来自"实体—关系—来源"三元组，而不是形状数量。文字自动换行并按节点居中，SVG 中每个节点是 `id="node-*"` 的组，改文字不会破坏布局。

**图表。** 数据只来自 `artifacts` 里的表，`chart_spec.json` 指定哪一列作 x、哪些列作 y、风格（line/scatter/bar/barh/errorbar）。若某列全是非数值，脚本报错退出而不是画一张空图。`chart_mapping.json` 记录列名、点数与缺失值数量，台账据此写"这一条曲线来自哪一列"。

**编辑。** `edit_svg.py` 只改被点名的元素（`set-text`、`move`、`recolor`、`delete`），其余部分保持不变，并把每个操作的前后值写进 `edit_log.json`。找不到的元素或无法移动的标签会被拒绝并记录，而不是静默跳过。

## 异常处置

| 情形 | 识别方式 | 处置 |
|-|-|-|
| 材料没有任何结构或数据 | `run_case.py` 报告 `route: none` | 报 `insufficient_evidence`，列出缺什么，不凭空画 |
| 元素缺来源 | `scene.py --validate` 报 `missing source` | 补 `source`；若确为推断，标 `inferred` 并写理由 |
| 节点越界 | 校验给出 `extends outside the canvas` 警告 | 调坐标或加大画布，不裁切内容 |
| 文字溢出节点 | 换行后行数超出高度 | 放大节点或缩短文字；导出检查会提示空白与过小图 |
| 数据列不存在或非数值 | `chart.py` 退出并指出列名 | 回到数据表核对该列，不猜测替代列 |
| 编辑目标不存在 | `edit_svg.py` 记 `missing` 并返回非零 | 先列出现有 id 再改，不新建同名元素 |
| 字体缺中文 | 导出后文字显示为方框 | 报告缺字体并按无衬线回退；SVG 中文字仍为可编辑文本 |
| 导出空白或过小 | `check_export.py` 报 `blank` | 视为失败，检查场景坐标与格式参数 |

## 运行状态口径

- `success`：三份导出件与台账齐备，导出检查通过，契约字段全部填写。
- `partial`：图已产出但存在可说明的缺口（校验警告、部分编辑被拒、契约字段缺项）。
- `insufficient_evidence`：材料不支持出图，`result.json` 说明缺什么。
- `failed`：脚本报错未能出图，保留错误信息与已经完成的中间产物。

## 输出约定

```
/app/output/
  figure.svg        可编辑源文件（分层 <g id="layer-*">，文字为 <text>）
  figure.pdf        矢量导出件
  figure.png        位图导出件（默认 2 倍缩放，按 canvas.dpi 写入元数据）
  chart.svg/pdf/png 若走图表路线，另出同名三份
  ledger.csv        逐元素来源台账
  export_check.json 导出检查结果
  result.json       契约字段 + 状态 + 不确定性
```

`result.json` 至少含 `case_id`、`status`、`editable_source`、`exports`、`provenance`、`element_map`、`uncertainty`；`output_contract` 里要求的其他字段若材料不支持，写成 `{"status":"insufficient_evidence","reason":...}`，不用编造值占位。

## 失败处理

脚本失败时不要反复重试同一命令：先读 `work/run_report.json` 里的 `rc` 与 `stderr`，区分"参数错"（可修）与"材料缺"（应报状态）。已生成的 SVG 保留，后续可只重跑 `render.py` 与 `check_export.py`。

## 质量闸门

交付前逐条确认：

1. 每个节点与边都有 `source`，推断项标了 `inferred`。
2. SVG 中文字以 `<text>` 存在，图层命名为 `layer-*`。
3. 三份导出件同在，`export_check.json` 的 `ok` 为真。
4. 台账行数等于节点数 + 边数 + 标注数（图表路线另加图与系列行）。
5. `result.json` 的 `status` 与实际缺口一致。

## 预算分配

一次案例建议不超过 20 次模型调用：清点材料 2 次，写场景或图表规格 6 次，校验与出图 3 次，自检与台账 3 次，回改与复核 6 次。脚本执行本身不消耗模型请求，优先用脚本代替重复的人工比对。

## 输出片段示例

以下为合成示例（`examples/case`）的真实输出节选，**不是**任何正式案例的结果：

```json
{
 "case_id": "EXAMPLE-FIG",
 "status": "success",
 "route": "scene",
 "editable_source": "/app/output/figure.svg",
 "exports": {"/app/output/figure.png": "2x scale", "/app/output/figure.pdf": "vector"},
 "provenance": "/app/output/ledger.csv",
 "element_map": [{"element_id": "n-stim", "kind": "node", "source_kind": "stated",
                  "artifact": "notes.txt", "evidence": "a brief stimulus is applied"}],
 "uncertainty": "元素来源标为 inferred 的由推断得到，需人工确认"
}
```

## 资源

- `scripts/scene.py`：场景模型与校验，定义形状、连线与来源字段。
- `scripts/render.py`：同一坐标下产出 SVG/PDF/PNG，不依赖外部转换器。
- `scripts/chart.py`：从数据表按列名出图，输出列映射。
- `scripts/edit_svg.py`：保源编辑，记录前后值。
- `scripts/check_export.py`：导出检查（文字可编辑性、越界、空白、页面尺寸）。
- `scripts/ledger.py`：逐元素来源台账。
- `scripts/run_case.py`：一条命令跑完流程并装配 `result.json`。
- `templates/scene_template.json`：最小场景模板。
- `docs/quickstart.md`：三分钟上手。
- `benchmark/`：自建基准与通过率（自建，不等于官方案例得分）。
