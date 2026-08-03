---
title: AMC MTA 正式输出索引
lang: zh-CN
---

# AMC MTA 正式输出索引

五份正式 CSV 位于 `modules/amc_mta/outputs/attribution/`。它们共享五段触点语义，但承担
不同职责；不要把不同批次文件混用，也不要把 `RELIABLE` 解释为因果有效。

## 建议阅读顺序

| 顺序 | 文件 | 粒度与主键 | 用途 |
| --- | --- | --- | --- |
| 1 | `amc_markov_attribution_results.csv` | 每个五段 `touchpoint` 一行 | 正式展示模型的三套归因、Ads 表现、成本和效率 |
| 2 | `amc_shapley_attribution_results.csv` | 每个五段 `touchpoint` 一行 | 参照模型结果，用于判断模型敏感性 |
| 3 | `amc_mta_model_comparison_touchpoints.csv` | `touchpoint + outcome`，当前 51 行 | 比较 share、差距、原始支持和逐触点可靠性 |
| 4 | `amc_mta_model_comparison_summary.csv` | `outcome`，固定三行 | 汇总 TVD、Spearman、Top-K 和整体可靠性 |
| 5 | `amc_mta_recommended_attribution.csv` | `touchpoint + outcome`，当前 51 行 | 给出 Markov 正式值、Shapley 参照值和最终展示值 |

`touchpoint` 已包含互动类型，独立的 `interaction_type` 字段便于筛选；两个字段必须
一致。三个 outcome 为 `converted_users`、`purchase_count` 和 `revenue`。

## 字段分组

两份单模型文件各 18 列：

- 身份：`attribution_model`、`touchpoint`、`interaction_type`；
- share：`converted_user_share`、`purchase_count_share`、`revenue_share`；
- 归因值：`attributed_converted_users`、`attributed_purchase_count`、`attributed_revenue`；
- Ads：`impressions`、`clicks`、`cost`、`reported_purchases`、`reported_sales`；
- 效率：`roas`、`roi`、`cpa`、`cost_per_converted_user`。

触点比较文件 14 列，除主键和两模型 share 外，还包括 `gap_pp`、`relative_gap`、
三个原始支持量以及五个可靠性字段。摘要文件 13 列，包括报告窗口、最大路径间隔、
触点数、TVD、Spearman、Top-K 重合率和五个可靠性字段。推荐文件 15 列，包括
`official_model/share`、`recommended_value`、`benchmark_model/share`、差距和五个
可靠性字段。精确字段顺序见[治理规范](model-governance.md)。

## 解释限制

- `official_model` 固定为 Markov，Shapley 仅作参照；
- `RELIABLE` 仅表示当前窗口通过计算有效、数据支持和模型一致三项标准；
- `recommended_value` 的区间是两模型 share 范围，不是置信区间；
- 摘要中的 TVD、Spearman 和 Top-K 只作诊断，不参与可靠性计算；
- 零成本行的效率指标为空；CPA 类指标分母为 0 时也为空；非计费互动不复制成本；
- 五份输出都不是预算分配、自动投放或因果增量结论。

输入、守恒和成本规则见[数据契约](../datasets/amc-data-contract.md)，完整审阅流程见
[完整使用说明](complete-guide.md)。
