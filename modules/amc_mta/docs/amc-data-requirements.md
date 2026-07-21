# AMC MTA 数据契约

本文是当前输入、路径规则和归因口径的事实源。

## 三类输入

| 数据 | 用途 |
| --- | --- |
| `amc_touchpoint_events_sample.csv` | 仅用于本地演示路径构建，不代表 AMC 可导出的用户明细 |
| `amc_mta_path_report_raw_sample.csv` | 匿名聚合路径，归因算法的直接输入 |
| `amazon_ads_report_sample.csv` | Amazon Ads 成本与表现，用于计算效率指标 |

真实应用应在 AMC clean room 内完成事件排序、路径构建与隐私聚合，只导出满足隐私门槛的聚合路径。

## 字段口径

概念事件的 `TOUCHPOINT` 必须提供 `journey_id`、`event_time`、`ad_product`、`format` 和 `interaction_type`；`placement` 和 `creative` 为空时归一为 `UNSPECIFIED`。`interaction_type` 只能是：

```text
IMPRESSION
CLICK
```

缺失、空值或其他值都会终止路径构建。这里的互动类型来自 AMC 事件标准化层；程序不会根据 Amazon Ads 报告中的汇总 `impressions`、`clicks` 数值反推用户路径。

`CONVERSION` 必须提供：

| 字段 | 含义 |
| --- | --- |
| `users` | 路径覆盖的去重用户数 |
| `converted_users` | 至少购买一次的去重用户数 |
| `purchase_count` | 订单/购买事件次数，可大于购买用户数 |
| `revenue` | 购买收入 |

归因使用的 AMC 聚合路径表只保留以上四个指标以及窗口、账户和 `path` 字段；`new_to_brand_purchases`、`avg_days_to_purchase` 不进入聚合路径输出。

计数字段必须是有限非负整数，收入必须是有限非负数，并满足：

```text
0 <= converted_users <= users
purchase_count >= converted_users
new_to_brand_purchases <= purchase_count
purchase_count 或 revenue 为正时 converted_users > 0
```

旧 AMC 字段 `purchases` 不再接受，避免把购买用户数与订单次数混为一谈。Amazon Ads 原生 `purchases` 仍保留，输出时命名为 `reported_purchases`。

## 五段互动键与 Ads 计费规则

AMC 路径和归因模型使用五段互动键：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

前置广告属性段转大写，仅允许字母、数字、下划线；`INTERACTION_TYPE` 只能是
`IMPRESSION` 或 `CLICK`。同一广告先曝光后点击时，两个事件会作为有序且不同的
五段触点保留在路径中。

Amazon Ads 报告也必须使用同一五段键，并提供 `interaction_type`、`cost_type`
和完全一致的 `normalizedTouchpoint`。DSP 的 `FORMAT` 来自
`inventoryType`，Sponsored Ads 来自 `adType`。

`cost_type` 只能是 `CPC` 或 `CPM`：CPC 计费行必须为 `CLICK`，CPM 计费行
必须为 `IMPRESSION`。同一广告的非计费互动可作为独立五段行参与对齐和
归因，但成本必须为 0。平台 `purchases`、`sales` 只归属
`CLICK` 行。程序不会复制成本、根据归因反向分摊成本，也不会从 Ads 汇总
指标反推 AMC 用户路径。

## 路径规则

默认报告窗口为 `2026-05-01` 至 `2026-06-30`。

- 从购买前最后一个触点开始向前回溯；触点顺序以时间戳为准。
- 相邻触点及最后触点到购买的间隔都必须 `<= 14 天`，正好 14 天有效。
- 首次遇到 `> 14 天` 时，排除其左侧触点及更早触点。
- 路径总时长无上限。
- 回溯后的最早触点必须严格晚于 `report_start_date`，否则整条路径不记录。
- 购买不得晚于 `report_end_date`；没有有效触点的购买不记录。
- 同一旅程多次购买时，后一次购买只使用前一次购买之后的新触点。

例如 `A --19天--> B --9天--> C --9天--> D --购买` 输出 `B > C > D`。

## 对齐要求

当前一次运行只接受一个 `marketplace + advertiser_id + currency` 范围。AMC 与 Ads 必须具备：

- 相同账户和 marketplace；
- 相同报告起止日期；AMC 起止日期必须是有效 ISO 日期，且起点不晚于终点；
- 完全相同的五段互动触点集合；
- 每个五段互动触点在窗口内每一天都有 Ads 数据。

任何缺失、额外日期、跨账户混合或键不匹配都会终止归因，不再静默补零。

## 模型与输出

Markov 分别建立购买用户、订单次数和收入三个 outcome 模型。购买用户模型以 `converted_users` 为转化终点、`users - converted_users` 为 Null；订单和收入模型分别使用 `purchase_count`、`revenue` 作为路径权重。

Shapley 对每条路径的唯一触点集合计算 unanimity game，并分别分配三个 outcome；重复触点在单条路径内只计一次。

两种模型都在五段互动粒度输出三套 share 和归因值，三项结果分别守恒：

```text
attributed_converted_users = converted_users 总量
attributed_purchase_count  = purchase_count 总量
attributed_revenue         = revenue 总量
```

每个模型仅输出一份五段主结果，包含 `touchpoint`、`interaction_type`、三套归因
指标、Amazon Ads 表现与成本及效率指标。Markov 与 Shapley 两份模型文件保持
独立。流程另生成三份治理产物：51 行五段全量比较、三个 outcome 的五段整体摘要，
以及 51 行管理层推荐记录。模型归因、支持度、差距诊断和推荐结果全部使用完整
五段键。

比较输入必须使用严格无空白表头，两个模型的触点集合、成本和平台表现完全一致，
且每个非零 outcome 的 share 与归因总量分别守恒。三份双模型产物固定为
14/13/14 列并包含五个
可靠性字段：`calculation_valid`、`data_support_sufficient`、
`models_consistent`、`reliability_status`、`reliability_reason`。计算有效、原始
支持同时达到 `30` 次购买、`20` 位购买用户、`5` 条唯一路径，且非零 outcome
的模型差距同时满足 `gap_pp<=1.0`、`relative_gap<=0.20` 时，结果才是
`RELIABLE`。摘要按 outcome 分别 AND 聚合所有触点的三个基础布尔值，再使用
相同公式生成摘要可靠性。TVD、Spearman、Top-K 重合率只作摘要描述，不参与
可靠性计算。两份单模型结果保持 18 列；旧稳定性、状态、决策、复核、自动化、
原因码和重复效率字段不再进入双模型产物。

零成本行的 ROAS、ROI、CPA 和每转化用户成本为空。

效率指标：

```text
ROAS = attributed_revenue / cost
ROI  = (attributed_revenue - cost) / cost
CPA  = cost / attributed_purchase_count
cost_per_converted_user = cost / attributed_converted_users
```
