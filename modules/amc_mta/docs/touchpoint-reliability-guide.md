# AMC MTA 单触点归因可靠性判断

## 用途

本文用于判断一个五段触点在当前报告窗口、指定 outcome 下的归因结果是否可靠。

五段触点格式：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

`IMPRESSION` 和 `CLICK` 是两个独立触点，必须分别判断。三个 outcome 也分别形成
记录：`converted_users`、`purchase_count`、`revenue`。

可靠性只由以下三个布尔标准组成：

1. 计算是否有效；
2. 数据支撑是否充分；
3. Markov 与 Shapley 是否一致。

三个标准全部通过才是 `RELIABLE`；任一不通过就是 `UNRELIABLE`。不再使用
高、中、低等级，也不增加其他条件。

## 1. 计算是否有效

字段：

```text
calculation_valid
```

只有完整流程通过以下严格校验，才会生成新结果：

- AMC、Amazon Ads、Markov 和 Shapley 使用同一窗口、账户和五段触点集合；
- AMC `report_start_date` 与 `report_end_date` 是有效 ISO 日期，且起点不晚于终点；
- 输入字段完整，数值有限、非负且关系合法；
- 两个模型的 share 和 attributed outcome 分别守恒；
- 成本、平台表现和效率指标一致；
- 无重复触点，CSV 表头和值没有首尾空白。

校验通过的输出记录为 `true`。任一校验失败时流程 fail-fast，不发布新产物，
因此不会把无效预览写成正式结果。

## 2. 数据支撑是否充分

字段：

```text
data_support_sufficient
```

同一五段触点必须同时满足：

```text
raw_purchase_count >= 30
raw_converted_users >= 20
raw_unique_paths >= 5
```

三个条件均满足为 `true`，任一条件不足为 `false`。门槛值本身算通过。

支持量从原始 AMC 聚合路径计算。同一触点在一条规范化路径中重复出现只计一次
支持；一条路径可以同时支持多个触点，所以这些支持量不要求跨触点守恒。
既有 `FULL_SUPPORT` 与 `LIMITED_SUPPORT` 都达到最低门槛，`LOW_SUPPORT` 未达到。

## 3. 两个模型是否一致

字段：

```text
models_consistent
```

对非零 outcome：

```text
gap_pp = 100 × |markov_share - shapley_share|
mean_share = (markov_share + shapley_share) / 2
relative_gap = |markov_share - shapley_share| / mean_share
```

同时满足以下条件为 `true`：

```text
gap_pp <= 1.0
relative_gap <= 0.20
```

任一条件超界为 `false`。两个门槛值本身算通过。该判断直接使用数值，不受
`LONG_TAIL`、`SMALL`、`MEDIUM` 或 `LARGE` 的分类顺序影响；因此非零长尾触点
只要两个差距门槛均通过，也可以得到 `models_consistent=true`。门槛比较使用
解析时保留的未舍入原始十进制 share 精确计算，不先按输出显示值舍入，也不使用
容差放宽；任何严格大于 `1.0` 或 `0.20` 的值都不通过。

当整个 outcome 合法地为零时，`calculation_valid=true`，但
`data_support_sufficient=false`、`models_consistent=false`，最终结果不可靠。

## 最终状态与原因

输出字段：

```text
calculation_valid
data_support_sufficient
models_consistent
reliability_status
reliability_reason
```

合并规则：

```text
calculation_valid
AND data_support_sufficient
AND models_consistent
```

三项全真：

```text
reliability_status = RELIABLE
reliability_reason = ALL_CRITERIA_PASSED
```

任一项为假：

```text
reliability_status = UNRELIABLE
```

失败原因只使用以下三个代码，并按固定顺序连接：

```text
CALCULATION_INVALID
INSUFFICIENT_DATA_SUPPORT
MODELS_INCONSISTENT
```

例如支持不足且模型不一致：

```text
reliability_reason = INSUFFICIENT_DATA_SUPPORT|MODELS_INCONSISTENT
```

## 在哪里查看

五个字段写入三份双模型产物：

```text
amc_mta_model_comparison_touchpoints.csv
amc_mta_model_comparison_summary.csv
amc_mta_recommended_attribution.csv
```

推荐表和触点比较表中的同一 `touchpoint + outcome` 必须具有完全相同的五个值。
摘要表按 outcome 汇总：分别对该 outcome 下所有触点的
`calculation_valid`、`data_support_sufficient`、`models_consistent` 做 AND，
再使用完全相同的三项 AND 公式生成摘要可靠性。

触点表保留 `gap_pp`、`relative_gap` 和三个原始支持量；摘要保留 TVD、Spearman
和 Top-K 重合率。这些摘要指标不参与可靠性计算，旧状态与差距等级不在当前 schema。

原始 Markov、Shapley 单模型结果不包含可靠性字段，因为可靠性需要两个模型及
AMC 原始支持共同判断。

## 当前样例

当前样例共有 17 个五段触点和三个 outcome，即 51 条触点结果：

- 51 条 `calculation_valid=true`；
- 51 条 `data_support_sufficient=true`；
- 51 条 `models_consistent=true`；
- 最终 `51 RELIABLE / 0 UNRELIABLE`；
- 三条 outcome 摘要均为 `RELIABLE`。

`RELIABLE` 只表示当前窗口满足上述三项归因证据标准，不代表因果增量、长期稳定
贡献，也不表示结果适合自动预算或投放执行。
