# Ad Group 数量与预算模拟输入

本目录只有两个 v4 输入 JSON 和本说明，不保存 AMC 数据或模型输出。

| 文件 | 用途 |
| --- | --- |
| `strategy_request.json` | Group、四个 Campaign、AMC 文件 SHA/范围、outcome 权重、各广告产品容量与最低预算 |
| `candidate_pool.json` | 每个 Campaign 的合格 Keyword unit、SKU、合法 Pair、Target、Audience 数量 |

计数口径：

- SP/SB 使用 Keyword unit、SKU、合法 Pair 三个容量下限的最大值；
- SD/DSP 使用 SKU、Target、Audience 三个容量下限的最大值；
- `candidate_usage_policy=USE_ALL_ELIGIBLE`，所有给定计数都进入容量计算；
- 输入只含数量，不含具体候选 ID，因此输出也不构成投放计划。

当前样例按广告产品过滤后的数量为：SP 的 Keyword/SKU/Pair=`3/3/3`，SB=`4/4/4`，
SD 的 SKU/Target/Audience=`4/4/2`，DSP=`4/8/2`。

预算证据只读以下 AMC 文件：

- `modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv`
- `modules/amc_mta/data/simulated/amc_touchpoint_entity_aggregate_sample.csv`

历史 `campaign_id`/`ad_group_id` 只存在于 AMC bridge 内。输出使用新的匿名 slot ID，不把历史
组当作未来新组。
