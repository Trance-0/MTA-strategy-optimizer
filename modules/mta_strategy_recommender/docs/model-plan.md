# MTA-Informed Strategy Initializer 整体模型计划

## 1. 定位与边界

本模型的目标是以 Campaign Group 为一次推荐单元，将 AMC MTA 触点归因转换为可解释的初始投放方案；当前阶段先落实数据契约、样例和校验：

```text
Campaign Group
└── Campaign（固定 4 个）
    └── Ad Group（模型推荐数量与策略）
        ├── Keyword
        └── SKU
```

`ad_product` 只保存在 Campaign 记录中。Ad Group 通过 `campaign_id` 继承该属性，不能保存另一份可能冲突的值。

模型负责：

- 综合 `converted_users`、`purchase_count` 和 `revenue` 三类 MTA outcome；
- 根据候选池规模与策略差异推荐每个 Campaign 的 Ad Group 数量；
- 为 Ad Group 分配触点策略、Keyword、SKU 和 Match Type；
- 输出相对预算份额，存在预算基线时输出绝对预算种子；
- 标记为 `INITIAL_SEED` 并交给优化团队。

模型不负责最高 ROI、全局优化、因果增量证明、长期调参或自动执行。

## 2. 初始条件

一次运行由 `strategy_request.json` 给定：

```yaml
candidate_pool_id: pool_2026_07
  mta_batch_id: mta_demo_2026_q1
  mta_source:
    report_start_date: 2026-01-01
    report_end_date: 2026-03-31
    attribution_sha256: df47aac7...
    entity_sha256: 208f0383...
campaign_group:
  campaign_group_id: CG001
  platform: AMAZON
  marketplace: US
  advertiser_id: adv_001
  currency: USD
  total_daily_budget: 1000  # 可省略
campaigns:
  - {campaign_id: C001, ad_product: SPONSORED_PRODUCTS, status: enabled}
  - {campaign_id: C002, ad_product: SPONSORED_BRANDS, status: enabled}
  - {campaign_id: C003, ad_product: SPONSORED_DISPLAY, status: enabled}
  - {campaign_id: C004, ad_product: AMAZON_DSP, status: enabled}
outcome_weights:
  converted_users: 0.4
  purchase_count: 0.3
  revenue: 0.3
```

当前业务规则要求恰有四个唯一 Campaign。它们直接嵌套在本次 Group 请求中，因此不再维护
独立关系表。

必需的结构约束：

```yaml
ad_group_constraints:
  min_keywords: 1
  max_keywords: 50
  min_skus: 1
  max_skus: 20
  max_ad_groups_per_campaign: 10
  max_exploration_groups_per_campaign: 1
```

## 3. 有限候选池

一次运行开始时在 `candidate_pool.json` 中冻结四组版本化数据：

1. Keyword 候选：现有有效词、审核后的 harvesting 结果及允许的 Match Type；
2. SKU 候选：符合 Group 范围、可售、有库存且允许搜索投放的商品；
3. Keyword–SKU 合法组合：分别保存 `evidence_type`、`allocation_role` 和 `policy_status`；
4. SD/DSP 信号规则：Keyword 只作非原生信号，并固定 `direct_mta_entity_evidence=false`。

模型只能从候选池选择，不能生成全量笛卡尔积。Keyword 和 SKU 并列分配到 Ad Group，每项实际分配还必须有明确合法 pairing。

## 4. MTA 信号

上游保持使用：

- `modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv`
- `modules/amc_mta/outputs/attribution/amc_markov_attribution_results.csv`

MTA 五段键保持不变：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

这是 Group 范围内的归因观察维度，不是业务实体树，也不携带 Campaign、Ad Group、Keyword 或 SKU ID。第一段用于把触点策略路由到相容 Campaign，但不会在业务树中新增一层。

当前跨模块校验器会只读同批模拟事实派生的
`modules/amc_mta/data/simulated/amc_touchpoint_entity_aggregate_sample.csv`。该表把五段
触点连接到历史Campaign/Ad Group/Keyword/SKU表现；MTA输出本身仍保持原schema。
策略只在实体同时属于本次冻结候选池时使用这份历史证据，未观察候选不能伪装成有
MTA效果。

当前层级校验器会打开两张 AMC 表，验证 SHA、范围、触点/outcome 数值、实体关联、平台
定向和预算复算，但不会修改或重生成 AMC。夹具仍是人工准备的预期输出，不代表自动生成器
已经实现；自动选点、分组和输出生产仍属于下一阶段。

每个触点的初始优先级可按配置计算：

```text
TouchpointScore
= w_converted × converted_user_share
+ w_purchase  × purchase_count_share
+ w_revenue   × revenue_share
```

权重表达业务偏好，不是优化目标。`interaction_type` 只能作为证据，不能直接翻译成“增加点击”等不可执行动作。

## 5. 触点到 Ad Group 策略

转换规则使用：

```text
Platform × Campaign 配置 × Touchpoint Dimension
→ Control Level × Supported Action × Constraints
```

流程如下：

1. 依据 Campaign 配置筛选相容 MTA 触点和 Group 候选内容；
2. 按 Placement、Format、Creative、Keyword 意图、Match Type、SKU 相似度和策略角色形成稳定策略簇；
3. 超过容量的簇拆分，证据不足的小簇合并或进入探索组；
4. 每个稳定可执行簇形成一个推荐 Ad Group；
5. 为每组分配并列的 Keyword/SKU 清单和明确 pairing。

当前样例已按 `ad_product` 区分原生 targeting：SP/SB 使用 Keyword、Match Type 和 SKU；
SD/DSP 使用 SKU、Target 和 Audience，Keyword 只能进入 `strategy_signals`。结果仍不是可直接
提交平台的 API payload；后续 adapter 必须完成平台字段映射，无法映射时拒绝。

```text
RecommendedAdGroupCount(Campaign)
= Count(StableExecutableStrategyClusters)
```

同一 Campaign 内默认不重复分配相同 `Keyword + Match Type`。SKU 可以因不同策略出现在多个 Ad Group，但不能复制完整的 Keyword/SKU 策略。

## 6. 初始预算种子

预算仅用于初始化：

```text
AdGroupScore = Σ TouchpointScore
MtaSeedShare = AdGroupScore / Σ SelectedRecommendedTouchpointScore
```

当前样例从 17 个可靠触点中选出六个形成 `2/2/1/1` Ad Group，并只在这六个触点内归一化；
输出明确保存 `SELECTED_RECOMMENDED_TOUCHPOINTS`、`17 → 6` 和 11 个未选触点口径。本阶段
不读取历史 Campaign 预算，也不做新旧预算优化。有绝对 Group 总预算时：

```text
Ad Group budget seed = Group budget baseline × Ad Group group-level share
Campaign budget seed = Σ its Ad Group budget seeds
Group budget seed = Σ Campaign budget seeds
```

没有 Group 总预算时，只输出相对份额和 `NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY` warning，不输出绝对金额。

## 7. 输出契约

```yaml
campaign_group_id: CG001
candidate_pool_id: pool_demo_2026_07_amc_aligned
mta_batch_id: mta_demo_2026_q1
recommendation_type: INITIAL_SEED
handoff_status: READY_FOR_OPTIMIZATION
is_optimized: false
touchpoint_selection:
  normalization_universe: SELECTED_RECOMMENDED_TOUCHPOINTS
  available_touchpoint_count: 17
  selected_touchpoint_count: 6
campaigns:
  - campaign_id: C001
    recommended_ad_group_count: 2
    recommended_ad_groups:
      - ad_group_id: C001_AG01
        strategy_name: high_intent_top_search
        strategy_role: CORE_CONVERSION
        mta_evidence:
          - touchpoint: SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK
            outcomes:
              converted_users: {recommended_value: 0.070755, reliability_status: RELIABLE}
            composite_score: 0.070587
        targeting_assignment:
          native_targets:
            keywords: [{keyword_id: K_LIGHTWEIGHT, match_type: PHRASE}]
            skus: [{sku_id: SKU_TRAIL_BLUE}]
          strategy_signals: {keyword_ids: [], sku_ids: []}
          pairings: [{keyword_id: K_LIGHTWEIGHT, sku_id: SKU_TRAIL_BLUE, match_type: PHRASE}]
        budget_seed_share: 0.20511552368285625
```

输出 Campaign 和 Ad Group 不重复保存 `ad_product`；调用方通过输入 Campaign 表获取。每项策略还应保存 MTA 来源、候选池版本、原因码和置信度。

## 8. 模块结构与阶段

```text
modules/mta_strategy_recommender/
├── data/simulated/             # 两个独立输入 JSON
├── docs/model-plan.md
├── scripts/validate_simulated_hierarchy.py
├── src/hierarchy_validator.py
├── tests/
│   ├── fixtures/               # 人工维护的预期输出契约
│   └── test_hierarchy_validator.py
└── README.md
```

当前阶段实现输入契约、独立预期输出夹具和确定性校验。后续阶段再接入正式候选数据、
MTA adapter、策略聚类与推荐生成，但仍不在本模块中实现优化器。

## 9. 验收规则

- 一次样例只有一个 Campaign Group 和四个唯一 Campaign；
- 每个 Campaign 有且仅有一个非空标量 `ad_product`；
- 每个推荐 Ad Group 归属一个已知 Campaign，且不重复保存 `ad_product`；
- 所有 Keyword/SKU 均来自本次冻结候选池；
- pairing 必须有真实证据或明确补充来源，且 `policy_status=ALLOWED`；
- Ad Group → Campaign → Campaign Group 的相对份额和绝对预算守恒；
- 无预算基线时不得输出绝对预算；
- 输出明确是 `INITIAL_SEED`、`READY_FOR_OPTIMIZATION` 且 `is_optimized=false`；
- AMC MTA 五段键、17 触点、CSV schema 与正式输出保持不变。

详细输出字段、JSON 格式、预算口径和关联规则见
[输出数据契约](output-data-contract.md)；Ad Group 数量依据、MTA 数值证据和具体投放动作见
[模型策略输出契约](strategy-output-contract.md)；可运行样例及命令见 [模块 README](../README.md)。
