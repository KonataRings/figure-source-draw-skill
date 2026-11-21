# 自建基准报告（科研绘图）

说明：本基准由本题作品自行构建，使用合成场景，**不是**平台官方的三个固定案例，
通过率不能当作官方得分。它检验的是：文档里声明的每条行为（出图、换行、中文、
越界警告、缺来源拒绝、图表路线）是否真的成立。

| 案例 | 期望 | 结果 | 标签数 | 台账行 | 说明 |
|-|-|-|-:|-:|-|
| shapes-four | success | ✓ | 7 | 7 | exports checked, 7 labels, 7 ledger rows |
| long-label-wrap | success | ✓ | 4 | 3 | exports checked, 4 labels, 3 ledger rows |
| cjk-label | success | ✓ | 3 | 3 | exports checked, 3 labels, 3 ledger rows |
| off-canvas | warning | ✓ | 2 | 3 | warned and still exported |
| missing-source | invalid | ✓ | - | - | validation rejected the scene |
| panelled-overview | success | ✓ | 3 | 5 | exports checked, 3 labels, 5 ledger rows |
| font-too-small | invalid | ✓ | - | - | validation rejected the scene |
| three-series-chart | chart | ✓ | - | - | chart rendered |

通过 **8/8**。
