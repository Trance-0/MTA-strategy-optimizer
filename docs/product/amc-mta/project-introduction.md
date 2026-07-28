# AMC MTA 项目介绍

AMC MTA 是本仓库可运行的归因实现：一个面向 Amazon 广告场景的可复现多触点归因与双模型诊断 Demo。它从 AMC 风格匿名聚合路径估算广告曝光与点击对购买用户、订单次数和收入的贡献，并在相同五段互动粒度关联 Amazon Ads 成本和计算效率指标。其输出可作为 [MTA Strategy Initializer](../../../modules/mta_strategy_recommender/README.md) 的上游证据。

模型结果表示特定归因方法下的贡献分配，不等同于广告的因果增量效果。

当前阅读入口：

- [文档总索引](../../index.md)
- [架构说明](../../amc_mta/amc-mta-architecture.md)
- [能力评价](../../amc_mta/amc-mta-capability-assessment.md)
- [模块运行说明](../../../modules/amc_mta/README.md)

## 项目如何工作

```text
AMC 风格匿名聚合路径，区分曝光与点击
        ↓
Markov 与 Shapley 多触点归因
        ↓
按广告产品、形式、位置、创意和互动类型分配贡献
        ↓
按完整五段键关联 Amazon Ads 成本
        ↓
输出五段 ROI、ROAS、CPA
```

项目不导出或处理真实 AMC 用户级行为明细。真实应用应在 AMC clean room 内完成事件排序、路径构建和隐私聚合，只向本项目提供满足隐私门槛的匿名聚合结果。

AMC 路径触点表示为：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

`INTERACTION_TYPE` 只能是 `IMPRESSION` 或 `CLICK`。这使同一个广告的曝光和点击可以在路径与成本结果中分别出现并获得贡献。Amazon Ads 报告同样使用五段键：CPC 成本只归 `CLICK`，CPM 成本只归 `IMPRESSION`；非计费互动行成本为 0，避免重复成本。

Amazon Ads 报告中的 `impressions` 和 `clicks` 是汇总表现指标，不用于反推客户路径。AMC 互动事件必须由上游明确提供互动类型。

路径从购买向前回溯。相邻触点以及最后触点到购买的间隔最多为 14 天；正好 14 天有效，首次超过 14 天时截断更早触点。只要每一段合格，路径总长度不设上限。

输入明确区分 `converted_users`（至少购买一次的去重用户）和 `purchase_count`（订单次数）。Markov 与 Shapley 分别归因这两个指标和收入；每个模型输出一份包含互动类型、贡献、成本与效率指标的五段结果。流程还生成触点比较、整体摘要和治理推荐，共五份正式输出。CPA 使用订单次数，另行输出每购买用户成本。完整边界见[数据契约](../../../modules/amc_mta/docs/amc-data-requirements.md)。

当前全年样例的 51 条推荐记录采用精简 15 列契约，保留 Markov 正式展示值、Shapley
参照值、差距与可靠性，并由 `recommended_value` 在可靠时给出 Markov 单点、不可靠
时给出两个模型 share 的升序闭区间；当前全部为 `RELIABLE`。详细规则见
[模型比较治理规范](../../../modules/amc_mta/docs/model-comparison-governance.md)。

独立的当前窗口可靠性只检查计算有效、最低数据支持和模型一致三个标准。当前
全年样例 51 条记录全部通过三项，因此为 `51 RELIABLE / 0 UNRELIABLE`；
摘要按 outcome 分别 AND 聚合全部触点的三个布尔值，整体差异指标只保留为诊断；
详细解释见[触点可靠性指南](../../../modules/amc_mta/docs/touchpoint-reliability-guide.md)。

## 项目价值

- 从多触点视角补充 last-touch 报告无法展示的路径贡献。
- 对比 Markov 与 Shapley，观察结果对不同模型假设的敏感性。
- 分开观察曝光与点击贡献，并按 CPC/CLICK、CPM/IMPRESSION 规则唯一关联成本。
- 将归因收入与广告成本关联，统一查看 ROI、ROAS、订单 CPA 和每购买用户成本。
- 为人工预算讨论、广告组合分析和后续真实 AMC 聚合数据接入提供可复现诊断基础。

本项目当前不提供效果预测、预算优化、投放执行、因果增量估计或 AI 问答能力。
