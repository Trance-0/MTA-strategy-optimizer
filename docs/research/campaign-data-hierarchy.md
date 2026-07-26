# Campaign 数据关系与 Paid Search 最细效果粒度

本文根据 [`campaign-data-model.md`](../../modules/ML_predict/campaign-data-model.md) 和 [`product-data-model.md`](../../modules/ML_predict/product-data-model.md) 整理 Campaign、Ad Group、Keyword、SKU、Product 与日级效果指标之间的关系，供预测模型的数据设计使用。

## 1. 业务维度视图

下面是便于理解业务管理和投放范围的视图，不是数据库中逐层建立外键的严格实体树。Campaign Group通过关系表管理Campaign；`retailer_id`、`market_id`、`account_id` 和 `sponsored_ads` 实际上都直接保存在Campaign记录中，当前模型没有独立的Account或Ad Product主表。

```text
Campaign Group：Amazon US Running Shoes FY2026
│
├── Campaign Group属性
│   ├── campaign_group_id
│   ├── group_name
│   ├── parent_id
│   ├── group_status = Active
│   ├── rule_type
│   ├── sp_active
│   ├── auth_id
│   ├── primary_kpi
│   └── secondary_kpi
│
├── Campaign Group条件
│   ├── fiscal_year = FY2026
│   ├── retailer_id = Amazon
│   ├── market_id = US
│   ├── category_id = Running Shoes
│   ├── brand_id = Nike
│   └── segment_id
│
├── Campaign Group关系
│   ├── campaign_group_id
│   └── campaign_id
│
├── Campaign：SP Campaign 001
│   │
│   ├── Campaign属性
│   │   ├── campaign_id
│   │   ├── fiscal_year = FY2026
│   │   ├── retailer_id = Amazon
│   │   ├── market_id = US
│   │   ├── account_id = Account A
│   │   ├── sponsored_ads = sponsored product
│   │   ├── sponsored_ads_sub_type
│   │   ├── start_date
│   │   ├── end_date
│   │   ├── targeting = MANUAL
│   │   ├── target_object_type = KEYWORD
│   │   ├── status = enabled
│   │   ├── api_id
│   │   └── managed_by_search_planner
│   │
│   ├── Campaign范围说明
│   │   ├── Platform：Amazon
│   │   ├── Market：US
│   │   ├── Account：Account A
│   │   └── Ad Product：Sponsored Products（SP）
│   │
│   ├── Ad Group：AG-001
│   │   │
│   │   ├── Ad Group属性
│   │   │   ├── ad_group_id
│   │   │   ├── campaign_id
│   │   │   ├── api_id
│   │   │   ├── status = enabled
│   │   │   ├── min_cpc
│   │   │   ├── max_cpc
│   │   │   └── managed_by_search_planner
│   │   │
│   │   ├── Keyword：women running shoes
│   │   │   │
│   │   │   ├── Ad Group × Keyword关系
│   │   │   │   ├── ad_group_id
│   │   │   │   ├── keyword_id
│   │   │   │   ├── keyword_api_id
│   │   │   │   ├── match_type = EXACT
│   │   │   │   └── status = enabled
│   │   │   │
│   │   │   ├── Keyword属性
│   │   │   │   ├── keyword_id
│   │   │   │   ├── value = women running shoes
│   │   │   │   ├── paid_search_enabled
│   │   │   │   ├── search_volume
│   │   │   │   ├── search_volume_tag
│   │   │   │   ├── search_branding_tag
│   │   │   │   └── search_conquest_tag
│   │   │   │
│   │   │   ├── SKU：AMZ-US-PEG41-BLK-38
│   │   │   │   │
│   │   │   │   ├── Ad Group × SKU关系
│   │   │   │   │   ├── ad_group_id
│   │   │   │   │   ├── sku_id
│   │   │   │   │   ├── product_api_id
│   │   │   │   │   └── status = enabled
│   │   │   │   │
│   │   │   │   ├── SKU属性
│   │   │   │   │   ├── sku_id
│   │   │   │   │   ├── retailer_id = Amazon
│   │   │   │   │   ├── market_id = US（可空）
│   │   │   │   │   ├── value = ASIN/SKU
│   │   │   │   │   ├── product_id
│   │   │   │   │   ├── price
│   │   │   │   │   ├── specification_profit
│   │   │   │   │   ├── item_health
│   │   │   │   │   ├── scope_for_search_optimization
│   │   │   │   │   └── paid_search_enabled
│   │   │   │   │
│   │   │   │   ├── Product：Nike Pegasus 41
│   │   │   │   │   ├── product_id
│   │   │   │   │   ├── gtin
│   │   │   │   │   ├── brand = Nike
│   │   │   │   │   ├── category = Running Shoes
│   │   │   │   │   ├── segment
│   │   │   │   │   ├── source_system_code
│   │   │   │   │   └── tier
│   │   │   │   │
│   │   │   │   ├── Keyword × SKU属性
│   │   │   │   │   ├── mapping_priority
│   │   │   │   │   ├── eiroas
│   │   │   │   │   ├── incrementality_factor
│   │   │   │   │   ├── keyword_rank
│   │   │   │   │   └── item_spots
│   │   │   │   │
│   │   │   │   └── Date：2026-07-01
│   │   │   │       └── Paid Search最细历史效果记录
│   │   │   │           ├── campaign_id
│   │   │   │           ├── ad_group_id
│   │   │   │           ├── keyword_id
│   │   │   │           ├── sku_id
│   │   │   │           ├── date
│   │   │   │           ├── impressions
│   │   │   │           ├── clicks
│   │   │   │           ├── traffic_budget / traffic_spend
│   │   │   │           ├── sales
│   │   │   │           ├── unit_sales
│   │   │   │           ├── roas
│   │   │   │           ├── cvr
│   │   │   │           └── cpc
│   │   │   │
│   │   │   └── SKU：AMZ-US-PEG41-WHT-38
│   │   │       ├── Product：Nike Pegasus 41
│   │   │       └── Date
│   │   │           └── impressions / clicks / traffic_spend / sales
│   │   │
│   │   └── Keyword：lightweight running shoes
│   │       ├── match_type = PHRASE
│   │       ├── SKU：AMZ-US-PEG41-BLK-38
│   │       │   └── Date
│   │       │       └── impressions / clicks / traffic_spend / sales
│   │       └── SKU：AMZ-US-PEG41-WHT-38
│   │           └── Date
│   │               └── impressions / clicks / traffic_spend / sales
│   │
│   └── Ad Group：AG-002
│       ├── Ad Group属性
│       ├── Keywords
│       ├── SKUs
│       └── Date × Keyword × SKU指标
│
└── Campaign：SP Campaign 002
    ├── Campaign属性与范围
    ├── Ad Group：AG-003
    └── Ad Group：AG-004
```

图中的 Amazon、US、Account A、Campaign名称、Keyword、SKU 和 Product 都是说明关系的示例值，不表示数据库中只有这些取值。`price`、`item_health`、搜索量和 Keyword × SKU 特征来自关联的产品时序表，不是全部直接存放在 Campaign 或 Ad Group 主表中。

## 2. 各层主要任务

| 层级 | 主要任务 | 与下层关系 |
| --- | --- | --- |
| Campaign Group | 按财年、平台、市场、品类、品牌和Segment组织Campaign，并保存Group级KPI与状态 | 通过`campaign_group_relationship`关联一个或多个Campaign |
| Retailer | 标识 Amazon、Walmart 等平台 | 一个平台包含多个市场和账户 |
| Market | 标识 US、UK、DE 等市场 | 与 Retailer、Account 一起限定 Campaign 投放范围 |
| Account | 标识特定平台、市场中的广告账户 | 一个账户可包含多种 Ad Product 和多个 Campaign |
| Ad Product | 标识 SP、SB、SD 等广告产品类型 | 一条 Campaign 记录对应一个广告类型值 |
| Campaign | 定义一次广告活动的市场、类型、时间、Targeting 和状态 | 一个 Campaign 包含多个 Ad Group |
| Ad Group | 组织一组投放策略、Keyword 和 SKU | 与 Keyword、SKU 均为多对多关系 |
| Keyword | 表达广告面向的搜索需求及匹配方式 | 可与多个 SKU 形成历史效果组合 |
| SKU | 表达特定 Retailer 下的具体可售商品；`market_id` 可空 | 一个 SKU 属于一个 Product |
| Product | 表达跨销售环境的商品主体及品牌、品类属性 | 一个 Product 可以对应多个 SKU |
| Paid Search日级指标 | 记录实际投放表现 | 最细已描述的KPI聚合可达到 Date × Campaign × Ad Group × Keyword × SKU |

## 3. 核心关系

```text
Campaign Group N ── N Campaign
Campaign 1 ── N Ad Group
Ad Group N ── N Keyword
Ad Group N ── N SKU
Product  1 ── N SKU
Keyword  N ── N SKU（映射及历史效果关系）
```

Campaign 不直接关联 Product。完整商品关系为：

```text
Campaign
→ Ad Group
→ ad_group_sku
→ SKU
→ Product
```

## 4. 一条 Paid Search 最细效果记录

```text
date          = 2026-07-01
campaign_id   = C001
ad_group_id   = AG001
keyword_id    = K001
sku_id        = S001
impressions   = 10000
clicks        = 250
traffic_budget = 500
sales         = 2000
unit_sales    = 20
```

它表示：在指定日期、Campaign 和 Ad Group 中，某个 Keyword × SKU 组合产生的聚合投放结果。其中 `traffic_budget` 对应 `paid_search_traffic.budget`，不能与仅到 `date × campaign` 粒度的 `campaign_spend.budget` 混为同一口径。

## 5. “最细粒度”的边界

当前两份 Data Model 没有单次曝光、点击、搜索请求、竞价、用户或订单事件 ID。因此对于 `paid_search_traffic`、`paid_search_conversion` 和 `vw_sku_keyword_kpi_metrics`，最细已描述的效果粒度是聚合事实记录，不是用户事件：

```text
Paid Search最细已描述效果粒度
= Date × Campaign × Ad Group × Keyword × SKU

不支持继续下钻为
= User × Search × Impression × Click × Order
```

这不是两份 Data Model 中所有数据的统一最低粒度。其他表还存在 `date × sku`、`date × keyword × sku`、`date × campaign` 等平行粒度。

同时需要验证 `keyword_id` 和 `sku_id` 在 Paid Search事实表中是否始终存在。`vw_campaign_metadata` 关系视图展开出的 Keyword × SKU 笛卡尔组合不能自动视为真实投放触点；只有实际事实数据中存在的组合才可作为训练样本。

## 6. 对预测模型的意义

预测输入中的预算目前计划分配到 Ad Group，而历史效果可能细到 Keyword × SKU，两者存在粒度差异。第一版更稳妥的主预测单位是 Ad Group，并将其 Keyword 和 SKU 聚合为特征：

```text
Campaign环境与总预算
        ↓
Ad Group分配预算
        ↓
Keyword流量特征 + SKU转化特征
        ↓
预测Ad Group结果
        ↓
汇总为Campaign结果
```

如果以后下钻到 Keyword × SKU，应先建立“Ad Group 预计实际花费 → 触点份额 → 触点结果”的分层预测，并确认这些组合真实存在、互斥且能够无重复地汇总。
