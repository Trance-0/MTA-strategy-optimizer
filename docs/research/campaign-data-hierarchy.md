# Campaign Group 顶层数据关系与最细效果粒度

本文定义策略初始化器使用的现行业务口径。实体关系树只有四层：

```text
Campaign Group
└── Campaign
    └── Ad Group
        ├── Keyword
        └── SKU
```

`ad_product` 是 Campaign 记录中的单值固有字段，不是 Campaign 与 Ad Group 之间的独立层级。
Keyword 与 SKU 并列挂载到实际投放的 Ad Group；它们不是彼此的父子节点。当前初始化器
只输出新组数量和预算，不决定这些实体的具体分配。

## 1. 顶层业务视图

```text
Campaign Group：Amazon US Running Shoes FY2026
├── Group 范围
│   ├── campaign_group_id = CG001
│   ├── retailer/platform = Amazon
│   ├── marketplace = US
│   ├── advertiser/account = Account A
│   ├── category = Running Shoes
│   ├── brand = Nike
│   └── segment = Running
│
├── Campaign：C001
│   ├── ad_product = SPONSORED_PRODUCTS
│   ├── targeting = MANUAL
│   ├── status = enabled
│   ├── Ad Group：AG001
│   │   ├── Keyword：women running shoes / EXACT
│   │   ├── Keyword：lightweight running shoes / PHRASE
│   │   ├── SKU：AMZ-US-PEG41-BLK-38
│   │   └── SKU：AMZ-US-PEG41-WHT-38
│   └── Ad Group：AG002
│       ├── Keyword 集合
│       └── SKU 集合
│
├── Campaign：C002
├── Campaign：C003
└── Campaign：C004
```

示例中的 Amazon、US、Campaign 名称、Keyword 和 SKU 只用于说明关系，不限制实际取值。
一次当前推荐任务固定一个 Campaign Group 服务一个平台，并固定包含四个 Campaign，分别
承载 SP、SB、SD、DSP。

## 2. 业务职责

| 层级 | 主要职责 | 与下一层关系 |
| --- | --- | --- |
| Campaign Group | 确定单一平台、市场、账户、品类、品牌和 Segment 范围，过滤本次有限候选池 | 当前推荐任务固定包含四个 Campaign |
| Campaign | 保存投放活动配置；`ad_product` 是其中一个必填单值字段 | 一个 Campaign 包含多个 Ad Group |
| Ad Group | 承载实际投放配置；初始化器只推荐新组数量和预算槽位 | 在投放系统中与 Keyword、SKU 分别为多对多 |
| Keyword | 表达搜索需求和 Match Type | 可进入多个 Ad Group，但同一 Campaign 内应控制重复 |
| SKU | 表达平台和市场中的具体可售商品 | 属于 Product，可进入多个策略组 |
| Product | 表达跨销售环境的商品主体 | 一个 Product 可对应多个 SKU |

当前推荐任务的关系为：

```text
Campaign Group 1 ── 4 Campaign
Campaign       1 ── N Ad Group
Ad Group       N ── N Keyword
Ad Group       N ── N SKU
Product        1 ── N SKU
```

Campaign 和 Campaign Group 都不直接拥有 SKU。完整商品链路是：

```text
Campaign Group
→ campaign_group_relationship
→ Campaign
→ Ad Group
→ ad_group_sku
→ SKU
→ Product
```

## 3. 有限候选池与实际分配

Campaign Group 的上游数据准备先按平台、市场、账户、品牌、品类、库存、可售状态和合规
规则形成有限候选池。当前模型接收按 Campaign 聚合后的数量：

- SP/SB：Keyword unit、SKU、合法 Keyword–SKU Pair 数量；
- SD/DSP：SKU、Target、Audience 数量。

Campaign 根据自身广告产品进一步过滤可用内容。策略初始化器用这些数量和容量上限决定
每个 Campaign 的新 Ad Group 数量，但不选择候选、不决定 Match Type，也不把实体分配到
具体新组。实际分配属于下游投放准备流程。

允许的组合来源为：

```text
EXISTING    已有真实投放关系
VALIDATED   已通过规则或人工验证
EXPLORATION 受限测试组合
BLOCKED     禁止分配
```

## 4. Paid Search 最细效果记录

```text
date           = 2026-07-01
campaign_id    = C001
ad_group_id    = AG001
keyword_id     = K001
sku_id         = S001
impressions    = 10000
clicks         = 250
traffic_budget = 500
sales          = 2000
unit_sales     = 20
```

它表示某天在指定 Campaign 和 Ad Group 中，一个真实 Keyword × SKU 组合产生的聚合结果。当前最细已描述效果粒度是：

```text
Date × Campaign × Ad Group × Keyword × SKU
```

它不是用户事件粒度，也不能继续下钻为 `User × Search × Impression × Click × Order`。其他事实表仍可能存在 `date × sku`、`date × keyword × sku`、`date × campaign` 等平行粒度；不同预算字段不能因名称相近而混用。

关系视图展开出的 Keyword × SKU 笛卡尔组合不能自动视为真实触点。只有事实数据中存在、
业务验证或明确标记为受限探索的组合才可计入合法候选数量。

## 5. 对策略初始化器的意义

MTA 五段键是归因观察维度，不是业务实体树。初始化器采用以下链路：

```text
Campaign Group 范围与有限候选计数
              ↓
四个固定 Campaign
              ↓
按候选容量推荐新 Ad Group 数量
              ↓
全部 MTA 触点经 AMC bridge 形成 Campaign 份额
              ↓
同 Campaign 的匿名新组等分 INITIAL_SEED 预算
              ↓
交给后续优化团队
```

本模块只提供可解释的数量与预算初始点，不分配具体投放实体，不预测全局最优，也不承担
持续预算优化。
