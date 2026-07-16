# AMC MTA 项目介绍

AMC MTA 是一个面向 Amazon 广告场景的可复现多触点归因 Demo。它从 AMC 风格匿名聚合路径估算广告曝光与点击对购买用户、订单次数和收入的贡献，并在相同五段互动粒度关联 Amazon Ads 成本和计算效率指标。

模型结果表示特定归因方法下的贡献分配，不等同于广告的因果增量效果。

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

输入明确区分 `converted_users`（至少购买一次的去重用户）和 `purchase_count`（订单次数）。Markov 与 Shapley 分别归因这两个指标和收入；每个模型输出一份包含互动类型、贡献、成本与效率指标的五段结果，共两份结果。CPA 使用订单次数，另行输出每购买用户成本。完整边界见[数据契约](../../../modules/amc_mta/docs/amc-data-requirements.md)。

## 项目价值

- 从多触点视角补充 last-touch 报告无法展示的路径贡献。
- 对比 Markov 与 Shapley，观察结果对不同模型假设的敏感性。
- 分开观察曝光与点击贡献，并按 CPC/CLICK、CPM/IMPRESSION 规则唯一关联成本。
- 将归因收入与广告成本关联，统一查看 ROI、ROAS、订单 CPA 和每购买用户成本。
- 为预算讨论、广告组合分析和后续真实 AMC 聚合数据接入提供可复现基础。
