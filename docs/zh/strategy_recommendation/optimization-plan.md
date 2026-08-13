---
title: MTA 归因到 Ad Group 预算策略
lang: zh-CN
---

# MTA 归因到 Ad Group 预算策略：问题定义与研究计划

## 1. 讨论目标

本计划只定义和分析一个问题，不在当前阶段提出具体算法、预算公式或技术解决方案：

> 如何利用 MTA 归因模型得到的触点归因结果，结合 Campaign、Keyword、SKU 及其他可用数据，
> 形成下一次 Campaign Group 中各 Campaign 的 Ad Group 数量与 Ad Group 级预算分配策略。

这里的“策略”主要指：

1. 每个 Campaign 需要多少个 Ad Group；
2. Campaign Group 总预算如何落到各 Campaign；
3. 每个 Campaign 的预算如何落到其内部的新 Ad Group；
4. 每项预算建议基于哪些历史证据，以及其可信程度。

## 2. 业务范围

当前业务层级为：

```text
Campaign Group
└── Campaign
    └── Ad Group
```

已确定的业务条件：

- 一个 Campaign Group 只服务一个广告平台；
- 一个 Campaign Group 中包含四个 Campaign；
- 每个 Campaign 只投放一种 Ad Product；
- 一个 Campaign 中可以包含多个 Ad Group；
- Keyword、SKU、Match Type、Target、Audience 等信息属于广告投放实体或策略信息；
- 下一次 Campaign 和 Ad Group 的 ID 可能与历史 ID 不同。

本问题关注下一次 Campaign Group 的初始预算策略。策略是否会在后续被继续优化，不改变本计划
对当前问题的定义。

## 3. 已有的 MTA 输出能说明什么

当前 MTA 触点主要由广告相关字段构成：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

每个触点可以得到多个 outcome 的归因结果，例如：

- `converted_users`；
- `purchase_count`；
- `revenue`。

这些结果说明的是：在历史观察窗口内，各类广告触点获得了多少结果信用。它能够描述不同
Ad Product、Placement、Creative 或 Interaction Type 在转化路径中的相对贡献。

但该输出本身不包含：

- Campaign 与 Ad Group 的业务结构；
- Keyword、Match Type、Target 和 Audience；
- SKU、ASIN、商品类别、价格和毛利；
- 库存、可售状态、促销和生命周期；
- 下一次 Campaign 中将建立哪些 Ad Group；
- 每个 Ad Group 增加预算后可能产生的新增结果。

因此，MTA 输出与最终预算对象之间存在明显的粒度断点。

## 4. 其他相关数据可能包含什么

除 MTA 外，当前问题涉及的数据可分为以下几类。这里仅整理其作用和缺口，不规定具体使用
方式。

| 数据类别 | 可能包含的内容 | 与预算问题的关系 |
| --- | --- | --- |
| 历史广告结构 | Campaign ID、Ad Group ID、Ad Product、平台 | 说明历史触点由哪些广告结构承载 |
| 投放实体 | Keyword、Match Type、Target、Audience | 说明 Ad Group 内部投放对象 |
| 商品实体 | SKU、ASIN、品类、品牌 | 说明广告实际推广的产品 |
| 商品经营数据 | 价格、毛利、库存、可售、促销 | 说明归因结果是否具备经营价值和继续投放条件 |
| 历史效果数据 | 曝光、点击、成本、购买、销售额 | 说明历史投放规模和结果 |
| 预算数据 | Budget、Spend、预算受限、Pacing | 说明预算设置与实际消耗的关系 |
| 下一期输入 | 候选 Keyword/SKU 数量或明细、总预算、Campaign 数量 | 定义下一次预算策略的对象和边界 |

目前最重要的数据事实是：MTA 有触点贡献，但缺少产品和投放实体；其他数据可能有实体信息，
但其结果是否能够与 MTA 触点稳定关联，仍需单独确认。

## 5. 从 MTA 触点到 Ad Group 预算的主要断点

### 5.1 触点粒度与 Ad Group 粒度不同

MTA 的归因对象是由广告属性组合而成的触点，预算的接收对象却是下一次新建的 Ad Group。
同一种触点可能出现在多个历史 Ad Group 中，一个历史 Ad Group 也可能包含多个 Keyword、SKU
或 Target。两者不是天然的一对一关系。

如果无法说明一个触点的归因结果与哪些实体、哪些历史 Ad Group 有关，就无法判断该归因信用
应如何影响下一次的新 Ad Group。

### 5.2 历史结构与下一次结构不同

历史 Campaign ID 和 Ad Group ID 主要表示历史数据血缘。下一次投放可能重新创建 Campaign、
调整 Ad Group 数量、改变 Keyword/SKU 组合，因此历史 ID 不能直接代表未来预算对象。

这里的核心问题不是能否保留 ID，而是历史证据在未来结构变化后是否仍然具有可比较性。

### 5.3 MTA 归因不等于预算增量

MTA 解释的是历史结果信用，不直接回答边际预算问题：

```text
某个 Ad Group 的预算增加后，实际 Spend 会增加多少？
Spend 增加后，转化、购买或收入会增加多少？
```

一个触点拥有较高归因份额，可能是因为它历史预算较高、靠近转化、覆盖人数较多，或确实表现
较好。仅根据归因份额无法区分这些原因。

因此，需要明确区分：

- 历史信用分配；
- 历史相关性；
- 预算响应；
- 因果增量。

这四者不是同一个概念。

### 5.4 Campaign 级贡献与组内差异

如果同一个 Campaign 内的多个新 Ad Group 只有数量差异，而没有 Keyword、SKU、Target、
Audience 或其他特征差异，那么它们在数据上是不可区分的。

在这种情况下，即使可以判断四个 Campaign 之间的相对重要性，也不能从已有证据进一步判断
同一 Campaign 内哪个新 Ad Group 应得到更多预算。

### 5.5 Ad Group 数量与预算分配相互影响

Ad Group 数量是离散结构问题，预算金额是连续分配问题。候选 Keyword、SKU、Target 和
Audience 的数量会影响需要建立多少 Ad Group；Ad Group 数量变化又会改变预算最小单位、
组内数据密度和每组可获得的最低预算。

因此，需要先判断以下关系是否能够被现有数据识别：

- 数量是否只由容量和候选规模决定；
- 数量是否还应受到历史贡献、商品差异或数据稀疏度影响；
- 数量与预算是否应被视为两个独立问题；
- 不同 Ad Product 是否具有不同的 Ad Group 容量定义。

### 5.6 多个 outcome 的目标不完全一致

MTA 同时给出转化用户、购买次数和收入等结果。它们可能指向不同的预算倾向：

- 转化用户更偏向覆盖和转化人数；
- 购买次数更偏向交易频次；
- 收入更偏向销售规模；
- 如果未来加入毛利，排序还可能再次变化。

在没有明确业务目标和权重前，“较好的预算策略”没有唯一数学定义。

## 6. 产品信息缺失带来的具体问题

当前 MTA 触点字段全部是广告相关属性，产品信息缺失会直接造成以下不确定性：

1. 无法知道高归因触点具体推广了哪些 SKU；
2. 无法区分触点贡献来自商品吸引力还是广告触点本身；
3. 无法判断历史高贡献 SKU 在下一次是否仍然可售、有库存或有足够毛利；
4. 无法判断某 Keyword 与某 SKU 的关联是实际投放关系还是数据组合产生的表面关系；
5. 无法解释一个新 Ad Group 的预算证据究竟来自广告属性、Keyword、SKU 还是历史 Ad Group；
6. 无法处理新 SKU、新 Keyword 或新组合的冷启动问题。

产品数据并不是对 MTA 字段的简单补充。它改变了最终预算策略所依据的业务对象，因此产品数据
与广告触点之间是否存在稳定、可验证的关联，是本问题的核心前提之一。
