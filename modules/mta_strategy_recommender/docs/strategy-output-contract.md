# 预算策略输出契约

本模型的“策略”仅指新 Ad Group 数量和初始预算分配，不是具体广告投放计划。

## 必须回答

1. 每个 Campaign 的合格候选数量是否要求拆组；
2. 每个 Campaign 推荐多少个新 Ad Group；
3. MTA 三类 outcome 经 AMC bridge 后给该 Campaign 多少相对价值；
4. 每个匿名新组获得多少份额和金额；
5. 是否发生 bridge 降级或最低预算不足。

## 不得回答

- 哪个 Keyword、SKU、Match Type 应进入哪个组；
- 使用什么 Target、Audience、Placement 或投放动作；
- 哪个历史 Ad Group 就是未来新组；
- 最高 ROI、因果增量或优化后的预算。

## 数量依据

`count_rationale` 保存输入计数、每个维度的容量下限以及最终最大值。SP/SB 计算 Keyword
unit、SKU、合法 Pair；SD/DSP 计算 SKU、Target、Audience。当前样例输出 `1/1/1/1`。

## 预算依据

Campaign 预算使用全部 MTA 触点与 outcome 权重。AMC `assisted_*` 只把同一触点贡献分摊给
历史实体并汇总到 Campaign。新组没有稳定映射，因此 Campaign 内严格等分并保存
`allocation_basis=CAMPAIGN_MTA_EQUAL_SPLIT`。

若未来要求同一 Campaign 的新组获得不同预算，必须先补充稳定的候选/历史实体到新 slot
映射，再修改本契约；不能仅凭匿名组编号制造差异。
