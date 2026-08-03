---
title: 术语与缩写
description: 归因、广告层级、数据和优化术语
lang: zh-CN
---

# 术语与缩写

本页定义术语在本项目中的具体含义，面向熟悉基础营销或数据分析、但不一定熟悉广告归因系统的读者。

## 核心业务术语 <span class="status-label status-verified" aria-label="Verified"></span>

### AMC（Amazon Marketing Cloud）

Amazon Marketing Cloud 是一个隐私安全的分析环境。项目中的 AMC 风格路径是聚合演示数据，不代表可以导出用户级明细。

### MTA（Multi-Touch Attribution，多触点归因）

在多个历史营销触点之间分配 Outcome 信用的方法。本项目运行 Markov 与 Path-level Shapley。

### Touchpoint（触点）

一次可归类的广告互动。本项目使用五段标准化键：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

### Customer Path（客户路径）

在观察窗口内按顺序排列的触点序列，使用 ` > ` 分隔。

### Outcome（结果指标）

模型分配信用的业务结果。本项目包括去重转化用户、购买次数和收入。

### Campaign Group、Campaign、Ad Group

项目采用 `Campaign Group → Campaign → Ad Group → Keyword/SKU/Target/Audience` 层级。`ad_product` 是 Campaign 属性，不是独立层级。

## 归因术语 <span class="status-label status-verified" aria-label="Verified"></span>

### Attribution Share（归因份额）

某个 Outcome 在所有触点之间分配后，一个触点获得的比例。同一 Outcome 下份额合计为 1。

### Markov Chain（马尔可夫链）

根据状态转移概率描述路径的模型。本项目使用移除触点前后的转化概率下降计算信用。

### Removal Effect（移除效应）

从转移网络删除某触点后，估计转化概率相对基准的非负下降。

### Shapley Value（夏普利值）

合作博弈论中的公平信用分配。本项目的路径一致性实现把单条路径 Outcome 在其唯一触点间等分。

### Causal Incrementality（因果增量）

相对于“不投广告”反事实，由广告实际造成的额外 Outcome。观察性 MTA 归因份额不自动等于因果增量。

## 策略与优化术语 <span class="status-label status-verified" aria-label="Verified"></span>

### Budget Seed（预算起点）

用于后续评审或优化的可解释初始预算。当前输出是 Seed，不是最优解。

### Response Curve（响应曲线）

预算或 Spend 与预期 Outcome 之间的函数。饱和表示新增预算的边际收益逐步下降。

### Marginal Revenue（边际收入）

增加一个预算单位时预期增加的收入。它是预算优化需要估计的量，不等同于历史归因收入。

### Constraint（约束）

优化方案必须满足的规则，如总预算、最低预算、库存、投放资格和预算步长。

### ROAS（Return on Ad Spend，广告支出回报率）

归因收入除以广告花费。ROAS 是比率，不应与总收入最大化或利润最大化混为同一个目标。

## 数据治理术语 <span class="status-label status-verified" aria-label="Verified"></span>

### Ground Truth（真实值/答案表）

用于评估模型的参考答案。MTA-SIM 的 `simulation_ground_truth` 仅对合成机制有效，禁止作为训练特征。

### Data Leakage（数据泄漏）

训练时使用决策时不可获得的信息，例如把 Ground Truth 作为输入，会导致不诚实的评估结果。

### Repository Fact / External / Inference / Recommendation

- <span class="status-label status-verified" aria-label="Verified"></span> **Verified**：直接由本仓库代码或数据确认。
- <span class="status-label status-external" aria-label="External"></span> **External**：来自注明来源的外部仓库或资料。
- <span class="status-label status-inference" aria-label="Inference"></span> **Inference**：基于证据的解释，不是直接测量。
- <span class="status-label status-recommendation" aria-label="Recommendation"></span> **Recommendation**：待评审的设计或下一步。
