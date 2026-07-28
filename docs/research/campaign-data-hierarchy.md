# Campaign Group 顶层数据关系与最细效果粒度

本文定义策略初始化器使用的现行业务口径。业务树只有四层：

```text
Campaign Group
└── Campaign
    └── Ad Group
        ├── Keyword
        └── SKU
```

`ad_product` 是 Campaign 记录中的单值固有字段，不是 Campaign 与 Ad Group 之间的独立层级。Keyword 与 SKU 并列挂载到 Ad Group；它们不是彼此的父子节点。

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

示例中的 Amazon、US、Campaign 名称、Keyword 和 SKU 只用于说明关系，不限制实际取值。一次当前推荐任务固定一个 Campaign Group 和四个 Campaign；这项运行规则不改变底层 Group–Campaign 关系表的物理基数。

## 2. 业务职责

| 层级 | 主要职责 | 与下一层关系 |
| --- | --- | --- |
| Campaign Group | 确定平台、市场、账户、品类、品牌和 Segment 范围，过滤本次冻结候选池 | 通过 `campaign_group_relationship` 关联 Campaign |
| Campaign | 保存投放活动配置；`ad_product` 是其中一个必填单值字段 | 一个 Campaign 包含多个 Ad Group |
| Ad Group | 承载单一清晰的初始策略以及具体 Keyword/SKU 分配 | 与 Keyword、SKU 分别为多对多 |
| Keyword | 表达搜索需求和 Match Type | 可进入多个 Ad Group，但同一 Campaign 内应控制重复 |
| SKU | 表达平台和市场中的具体可售商品 | 属于 Product，可进入多个策略组 |
| Product | 表达跨销售环境的商品主体 | 一个 Product 可对应多个 SKU |

物理关系保持为：

```text
Campaign Group N ── N Campaign
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

Campaign Group 先按平台、市场、账户、品牌、品类、库存、可售状态和合规规则冻结：

- Keyword 候选池；
- SKU 候选池；
- 明确审核过的 Keyword–SKU 组合。

Campaign 根据自身配置进一步过滤可用内容；策略初始化器再决定每个 Campaign 的 Ad Group 数量，并把候选 Keyword、SKU 和 Match Type 分配到具体 Ad Group。候选内容可以不使用，不要求穷举或形成笛卡尔积。

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

关系视图展开出的 Keyword × SKU 笛卡尔组合不能自动视为真实触点。只有事实数据中存在、业务验证或明确标记为受限探索的组合才可进入策略候选。

## 5. 对策略初始化器的意义

MTA 五段键是归因观察维度，不是业务实体树。初始化器采用以下链路：

```text
Campaign Group 范围与冻结候选池
              ↓
四个固定 Campaign
              ↓
按 MTA 策略差异推荐 Ad Group 数量
              ↓
为 Ad Group 分配 Keyword / SKU / Match Type
              ↓
生成 INITIAL_SEED 相对份额或预算种子
              ↓
交给后续优化团队
```

本模块只提供可解释的初始点，不预测全局最优，也不承担持续预算优化。
