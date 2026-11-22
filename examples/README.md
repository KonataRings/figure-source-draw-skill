# 示例（合成，非正式案例）

本目录只用于说明接口与字段，**不是**平台任何固定案例的结果。

| 文件 | 内容 |
|-|-|
| `case/case.json` | 合成案例的契约：`required` 含 `editable_source`、`exports`、`provenance`、`element_map`、`status` |
| `case/artifacts/scene.json` | 示范示意图：4 个实体、3 条关系、2 项图例、1 条标注，每个元素带来源 |
| `case/artifacts/data.csv` | 示范数据表：时间—幅度两组，含对照臂 |
| `case/artifacts/chart_spec.json` | 图表规格：只写列名与样式 |
| `expected_output/` | 由上面的输入实际跑出的结果，`result.json` 内已标 `"example": true` |

**只发文本资源。** 平台把 PNG/PDF 之类判为不支持的文件类型，会让整次提交在预检被拒；为避免扩展名白名单的差异，本包连示例 SVG 也不附带，只保留 JSON 与 CSV。三类产物都在运行时生成：

```bash
python scripts/render.py --scene examples/case/artifacts/scene.json \
    --outdir examples/expected_output --basename figure --formats svg,pdf,png
```

复现全流程：

```bash
python scripts/run_case.py --input examples/case --work /tmp/work --output /tmp/out
```

其中 `n-ctrl`（对照臂）的来源标为 `inferred`：原文提到存在对照，但没有说明它在通路中的位置，图上把它画在下方属于作者的推断。这类不确定必须留在台账里，读者才能判断该不该采信。
