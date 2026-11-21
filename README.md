# 科研绘图 Skill：figure-source-draw

依据材料生成或修改科研图稿，交付**可分层的可编辑源文件**、PDF/PNG 导出件，以及**逐元素来源台账**。三条路线：示意图/机制图、数据图表、既有 SVG 的保源编辑。

## 为什么这样设计

绘图任务最容易糊弄的地方是把图画得好看但无法核验：元素来自哪一句、哪一列查不到，导出的图不能改。本 Skill 把"可编辑"和"可核验"做成硬约束：

- 一张图先写成 `scene.json`（实体、关系、来源），再由**同一份坐标**渲染出 SVG、PDF、PNG，三者不会互相矛盾。
- SVG 里文字保持 `<text>`，图层命名 `layer-*`；导出检查会验证这一点，而不是只看文件存不存在。
- 每个元素必须有 `source`：取自原文标 `stated` 并给出处，推断得到标 `inferred` 并写理由。缺来源直接校验失败。

## 目录

```
SKILL.md                  调用说明、流程、异常处置、质量闸门
scripts/scene.py          场景模型与校验（形状、连线、来源）
scripts/render.py         SVG / PDF / PNG 三后端，同一坐标，不依赖外部转换器
scripts/chart.py          数据表 → 图表，输出列映射
scripts/edit_svg.py       保源编辑，记录前后值
scripts/check_export.py   导出检查：文字可编辑、越界、空白、页面尺寸
scripts/ledger.py         逐元素来源台账
scripts/run_case.py       一条命令跑完并装配 result.json
templates/                场景模板
examples/                 合成示例案例与示意输出（已标注为示例）
benchmark/                自建基准：6 个合成场景，检验文档声明的行为
docs/quickstart.md        三分钟上手
```

## 依赖

- Python 3.9+
- 必需：`lxml`、`Pillow`、`numpy`、`reportlab`（PDF 后端）、`matplotlib`（图表路线）、`PyMuPDF`（PDF 检查，缺失时跳过该项）
- 不依赖 LibreOffice、Inkscape、ImageMagick；没有外部二进制依赖
- 字体：优先使用系统里的中文无衬线字体（`msyh.ttc`、`Noto Sans CJK` 等），找不到则回退，并在导出说明里指出可能的缺字

## 用法

```bash
# 一条命令跑完：清点 → 校验/出图 → 导出检查 → 台账 → result.json
python scripts/run_case.py --input /input --work /app/work --output /app/output

# 也可以分步
python scripts/scene.py --validate my_scene.json
python scripts/render.py --scene my_scene.json --outdir out --basename figure --formats svg,pdf,png
python scripts/check_export.py --svg out/figure.svg --png out/figure.png --pdf out/figure.pdf --min-text 3
python scripts/ledger.py --scene my_scene.json --output out/ledger.csv
```

安装到平台约定位置：

```bash
python install.py            # 复制到 /app/submission，幂等
python install.py --force    # 覆盖已有 SKILL.md
```

## 自检与基准

```bash
python selftest.py                    # 三条路线 + 三类拒绝路径
python benchmark/run_benchmark.py     # 6 个合成场景，输出 report.md
```

自检覆盖：示意图与图表同例并出、编辑路线（改名/移动/改色/删除/不存在的 id）、缺来源被拒、材料不足降级、空白图被检出。基准覆盖：四种形状组合、长文本换行、中文标签、越界警告、缺来源拒绝、三系列图表。

基准是**自建**的合成场景，不是平台官方三个固定案例，通过率不能当作官方得分。

## 适用范围与限制

- 适用：机制图、流程图、结构示意、由数据表生成的常见二维图、按指令修改既有 SVG。
- 不适用：照片修图、三维渲染、需要自由曲线/渐变的插画级绘制。场景模型只有五种形状与直线连线，这是为可核验性做的取舍。
- 字体缺中文时，SVG 文字仍可编辑（可换字体），PDF/PNG 可能显示方框，此时应报告而不假装正常。
- 场景坐标需要人（或 Agent）给出；本 Skill 不做自动布局，避免用自动排版掩盖结构关系。

## 版本

- 1.0.0：场景模型 + 三后端渲染 + 图表路线 + 保源编辑 + 导出检查 + 台账 + 一条命令驱动；自检与 6 例基准。
