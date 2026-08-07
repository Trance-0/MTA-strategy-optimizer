---
title: MTA 驱动的 Ad Group 数量与预算模型
lang: zh-CN
---

# MTA 驱动的 Ad Group 数量与预算模型

## 1. 目标与边界

模型以一个 Campaign Group 为推荐单元，回答两个问题：每个给定 Campaign 需要多少个新
Ad Group，以及每个新组获得多少初始预算。

模型不输出具体 Keyword、SKU、Match Type、Target、Audience、动作或策略角色；结果固定为
`INITIAL_SEED`、`is_optimized=false`，交给后续团队迭代。

## 2. 数量计算

SP/SB：

```text
N = max(
  min_ad_groups,
  ceil(keyword_units / keyword_capacity),
  ceil(skus / sku_capacity),
  ceil(legal_pairs / pair_capacity)
)
```

SD/DSP：

```text
N = max(
  min_ad_groups,
  ceil(skus / sku_capacity),
  ceil(targets / target_capacity),
  ceil(audiences / audience_capacity)
)
```

若 `N > max_ad_groups` 则拒绝输入。当前样例按广告产品过滤后的计数均未跨越容量边界，
所以四个 Campaign 都得到一个组。修改任一相关计数跨边界会确定性增加对应数量。
输入采用严格 v4 字段和 JSON 数字类型；SP/SB 的合法 Pair 数不得超过 Keyword unit 与 SKU
数量的笛卡尔上限，且每组最低日预算必须为正数。

## 3. MTA 与 AMC bridge

每个触点和 outcome 使用 MTA `recommended_value`。AMC 实体表将该值在触点内部按对应的
`assisted_converted_users`、`assisted_purchase_count` 或 `assisted_revenue` 分摊，再汇总到
历史 Ad Group，之后才汇总到 Campaign；历史 ID 不进入输出。分母为零时依次降级为
clicks、impressions、unique_users、equal，并在输出披露。

归因和实体 bridge 都要求非空五段触点键；重复实体行、归因中不存在的孤儿实体触点，以及
与广告产品不一致的 Campaign 关联都会被拒绝。

`RELIABLE` 行直接使用 `recommended_value`；`UNRELIABLE` 行采用 AMC `[low,high]`
区间中点并输出 warning。该中点只是非优化初始点。

```text
CampaignOutcome = Σ TouchpointMTAValue × EntityBridgeShare
CampaignScore = Σ OutcomeWeight × CampaignOutcome
CampaignShare = CampaignScore / Σ CampaignScore
```

`assisted_*` 仅用于桥接权重，不能跨实体相加，也不代表实体级归因或因果效果。

## 4. 新组预算

候选输入只有数量，没有稳定的“历史实体/候选 → 新组 slot”映射，因此同一 Campaign 内的新组
不可区分。模型诚实采用：

```text
AdGroupShare = CampaignShare / N
allocation_basis = CAMPAIGN_MTA_EQUAL_SPLIT
```

若提供 Group 日预算，则金额等于份额乘以总预算；否则只输出相对份额。Campaign 获得的金额
低于 `N × minimum_daily_budget_per_ad_group` 时保留 N，并标记不可执行，不静默减少组数。

## 5. 输出

输出包含血缘、预算公式、Campaign 容量依据、MTA 分数、bridge 摘要、预算份额，以及匿名
`ad_group_slot_id` 的份额/金额。Campaign 和 Group 预算由 Ad Group 自下而上汇总并守恒。
