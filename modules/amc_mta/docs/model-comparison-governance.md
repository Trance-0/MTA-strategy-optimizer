# AMC MTA 双模型比较与可靠性规范

本文是 Markov 与 Path-level Shapley 当前比较输出的事实源。

## 模型定位

- Markov 是正式展示模型，衡量路径顺序和转移依赖。
- Path-level Shapley 是参照模型，衡量路径中唯一触点的参与贡献。
- 两者都不是因果增量模型，不取平均，也不能用一个 outcome 替代另一个。
- 三个 outcome 为 `converted_users`、`purchase_count`、`revenue`。

## 严格输入校验

比较前必须确认两模型物理表头均精确等于 18 列契约，触点集合一致、无重复行，
share 和归因值有限且非负，平台表现、成本和效率字段一致。每个非零 outcome 的
share 分别守恒为 1，归因值与 AMC 总量守恒；零 outcome 必须在两模型同时为零。
AMC 报告还必须只有一个合法日期窗口。任何非法输入都以 `ValueError` fail-fast，
不发布部分结果。文件发布失败继续抛出原始 `OSError`，原子发布层恢复整组旧产物。

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

推荐结果，14 列、当前样例 51 行：

```text
touchpoint,interaction_type,outcome,official_model,official_share,benchmark_model,benchmark_share,gap_pp,relative_gap,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason
```

推荐结果固定 `official_model=MARKOV`、`benchmark_model=PATH_LEVEL_SHAPLEY`。
非零 outcome 的 `official_share` 等于 Markov share，包括合法的 `0.0` 触点；零
outcome 的 `official_share` 为空。推荐与触点表中同一键的 share、gap 和五个
可靠性字段必须一致。两份单模型文件保持 18 列且不增加可靠性字段。

## 当前样例

当前 17 个五段触点 × 3 个 outcome 形成 51 条记录：51 条计算有效，3 条数据支持
充分，但这 3 条均未通过模型一致性，因此为 `0 RELIABLE / 51 UNRELIABLE`；三个
摘要也都是 `UNRELIABLE`。TVD 约为 9%–10%，Spearman 高，Top 5 重合率为
100%、100%、80%。这表示两个模型整体排名接近但份额仍有实质差异。

这些结果只支持当前窗口的模型比较，不证明因果增量、长期稳定或自动预算可用性。

## 未来研究

滚动窗口、重采样和 3/7/14 天敏感性可作为后续研究，但它们不是当前可靠性条件，
也不是当前 CSV 字段。若未来需要决策审批或自动化治理，应设计独立产物，不扩宽
现有 14/13/14 契约。
