---
title: AMC MTA 双模型比较与可靠性规范
lang: zh-CN
---

# AMC MTA 双模型比较与可靠性规范

本文是 Markov 与 Path-level Shapley 当前比较输出的事实源。

## 模型定位

- Markov 是正式展示模型，衡量路径顺序和转移依赖。
- Path-level Shapley 是参照模型，衡量路径中唯一触点的参与贡献。
- 两者都不是因果增量模型，不取平均，也不能用一个 outcome 替代另一个。
- 三个 outcome 为 `converted_users`、`purchase_count`、`revenue`。

## 严格输入校验

比较前会对字段名和值执行首尾空白清理，字符串内部空格保持不变。清理后的
表头必须精确等于 18 列契约，且不得为空或重名；每行列数必须与表头一致。
触点集合必须一致且无重复行，
share 和归因值有限且非负，平台表现、成本和效率字段一致。每个非零 outcome 的
share 分别守恒为 1，归因值与 AMC 总量守恒；零 outcome 必须在两模型同时为零。
AMC 报告还必须只有一个合法日期窗口。任何非法输入都以 `ValueError` fail-fast，
不发布部分结果。文件发布失败继续抛出原始 `OSError`，原子发布层恢复整组旧产物。
五份正式输出的表头和值仍保持无首尾空白的规范格式。

## 触点差距

对同一触点和 outcome：

```text
gap_pp = 100 × |markov_share - shapley_share|
mean_share = (markov_share + shapley_share) / 2
relative_gap = 0                         if mean_share = 0
relative_gap = |markov_share - shapley_share| / mean_share  otherwise
```

展示值可以舍入，但模型一致性使用解析时保留的原始十进制 share，不增加 epsilon。

## 三项可靠性标准

可靠性只由以下三个布尔值按 AND 合成：

1. `calculation_valid`：全部严格校验通过后才生成正式行，因此当前产物中为 `true`。
2. `data_support_sufficient`：非零 outcome，且 `raw_purchase_count >= 30`、
   `raw_converted_users >= 20`、`raw_unique_paths >= 5`。
3. `models_consistent`：非零 outcome，且精确 `gap_pp <= 1.0`、
   `relative_gap <= 0.20`。

三项全真时 `reliability_status=RELIABLE`，原因是 `ALL_CRITERIA_PASSED`；否则为
`UNRELIABLE`。失败原因按 `CALCULATION_INVALID`、`INSUFFICIENT_DATA_SUPPORT`、
`MODELS_INCONSISTENT` 的固定顺序用 `|` 连接。零 outcome 的后两项为 `false`。

## 整体证据

摘要仅保留三项整体描述，不参与可靠性判断：

- `tvd = 0.5 × Σ|M-S|`；
- Spearman rho，并列使用平均排名；无法定义时为空；
- `top_k_overlap_rate`，其中 `k=min(5,touchpoint_count)`，并列用规范触点键排序。

摘要对同一 outcome 的所有触点分别 AND 三个基础布尔值，再复用相同可靠性合成。

## 精确输出契约

触点比较，14 列、当前样例 51 行：

```text
touchpoint,outcome,markov_share,shapley_share,gap_pp,relative_gap,raw_unique_paths,raw_converted_users,raw_purchase_count,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason
```

整体摘要，13 列、当前样例 3 行：

```text
outcome,report_start_date,report_end_date,max_touchpoint_gap_days,touchpoint_count,tvd,spearman_rho,top_k_overlap_rate,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason
```

推荐结果，15 列、当前样例 51 行：

```text
touchpoint,interaction_type,outcome,official_model,official_share,recommended_value,benchmark_model,benchmark_share,gap_pp,relative_gap,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason
```

推荐结果固定 `official_model=MARKOV`、`benchmark_model=PATH_LEVEL_SHAPLEY`。
非零 outcome 的 `official_share` 等于 Markov share，包括合法的 `0.0` 触点；零
outcome 的 `official_share` 为空。推荐与触点表中同一键的 share、gap 和五个
可靠性字段必须一致。两份单模型文件保持 18 列且不增加可靠性字段。

`recommended_value` 是由 `reliability_status` 判别的 CSV 文本联合类型。非零
outcome 的 `RELIABLE` 行输出 `official_share` 单点；`UNRELIABLE` 行输出两个
模型 share 的升序无空格闭区间 `[low,high]`。零 outcome 没有可解释分布，该字段
为空；非零 outcome 的两个 share 都为零时，允许退化区间 `[0.0,0.0]`。该区间是
模型结果范围，不是统计置信区间。

## 当前样例

当前 17 个五段触点 × 3 个 outcome 形成 51 条记录，全部计算有效、支持充分且
模型一致，因此为 `51 RELIABLE / 0 UNRELIABLE`；三个摘要也都是 `RELIABLE`。
三个 outcome 的 TVD 为 1.4066%、1.3891%、1.4266%，Spearman 为 0.7407、
0.7762、0.7966，Top 5 重合率为 40%、60%、40%。

这些结果只支持当前窗口的模型比较，不证明因果增量、长期稳定或自动预算可用性。

## 未来研究

滚动窗口、重采样和 3/7/14 天敏感性可作为后续研究，但它们不是当前可靠性条件，
也不是当前 CSV 字段。若未来需要决策审批或自动化治理，应设计独立产物，不扩宽
现有 14/13/15 契约。
