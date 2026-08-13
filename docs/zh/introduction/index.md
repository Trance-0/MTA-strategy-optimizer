---
title: 项目概览
description: Marketing ROI Analysis 的目标、边界和端到端工作流
lang: zh-CN
---

# 项目概览

本项目面向需要把历史多触点归因（Multi-Touch Attribution，MTA）结果转化为下一期广告预算决策的营销分析、数据科学和工程团队。

## 总体目标 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

整体思路分为三个职责清晰的阶段：

1. **历史归因**：根据聚合客户路径，估计每个触点对转化用户、购买次数和收入的历史归因占比。
2. **策略初始化**：面对一个新的 Campaign，结合 MTA 占比、Campaign/Ad Group 实体关系、候选投放对象和预算约束，生成 Ad Group 数量及可解释的初始预算。
3. **预算优化**：在单独的 Ad Group 级模型中预测不同预算下的结果，并在业务约束内最大化预期收入。该阶段尚未实现。

```mermaid
flowchart LR
    A["聚合路径与广告表现"] --> B["MTA：Markov + Shapley"]
    B --> C["触点 × Outcome 历史归因占比"]
    C --> D["实体 Bridge 与 Campaign 得分"]
    E["候选对象、预算、容量规则"] --> D
    D --> F["Ad Group 数量与初始预算"]
    F --> G["未来：Ad Group 响应预测"]
    G --> H["未来：约束预算优化"]
```

## 当前交付边界 <span class="status-label status-verified" aria-label="Verified"></span>

| 组件 | 当前输出 | 当前不做 |
| --- | --- | --- |
| AMC MTA | Markov、Path-level Shapley、模型比较、可靠性状态、推荐归因占比 | 因果增量证明、自动投放 |
| MTA Strategy Recommender | 新 Ad Group 数量、Campaign 预算份额、组内等分的初始预算 | Ad Group 表现预测、边际收益估计、数学最优预算 |
| Strategy Optimizer | 尚未实现 | 当前不能宣称收入最大化或 ROI 最优 |

当前输出应理解为**历史证据和预算起点**，而不是生产级因果归因或自动预算优化。

## 继续阅读

- [项目结构与数据流](./project-structure.md)
- [进展与待办](./progress.md)
- [数据集与兼容性](../datasets/index.md)
- [归因模型总览](../attribution/index.md)
- [策略优化模型](../strategy_recommendation/index.md)
