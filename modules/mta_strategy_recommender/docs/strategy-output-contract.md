# 模型策略输出契约

本文专门定义模型应输出的“策略”。目标是让下游清楚知道：四个 Campaign 各需要多少
Ad Group、为什么需要这些 Ad Group，以及每个 Ad Group 具体应该采用什么投放策略。

本文描述目标契约。当前模块已经具备模拟结果和结构校验，但尚未实现从正式 MTA 输出
自动生成这些策略的 adapter、评分和聚类逻辑。

## 1. 策略输出必须回答的问题

模型输出不能只给出 Ad Group 名称。每次推荐必须回答：

1. 每个 Campaign 推荐多少个 Ad Group？
2. 为什么是这个数量？
3. 每个 Ad Group 依据哪些 MTA 触点归因结果？
4. 每个 Ad Group 承担什么业务角色？
5. 应采用哪些平台可支持的投放动作？
6. 应分配哪些给定 Keyword、SKU 和 Match Type？
7. 哪些候选不得使用？
8. 推荐的置信度和风险是什么？

策略输出分为两层：

```text
Campaign 策略
├── 推荐 Ad Group 数量
├── 数量形成原因
└── Ad Group 策略列表
    ├── MTA 数值证据
    ├── 策略角色与目标
    ├── 具体投放动作
    ├── Keyword/SKU 分配
    └── 原因、置信度与约束
```

不同策略字段有不同计算来源：

| 策略结果 | 主要来源 |
| --- | --- |
| 触点贡献、可靠性和优先级 | MTA 直接字段与 outcome 综合规则 |
| MTA 策略簇 | MTA 触点维度与聚类配置 |
| 候选容量型拆组 | 初始 Keyword/SKU/pair 数量与容量约束 |
| 每组分配多少 Keyword/SKU | 初始数量、组数、复用和余数分配规则 |
| 具体分配哪个 Keyword/SKU | 候选元数据、合法 pairing 和确定性排序 |
| 平台具体投放动作 | MTA 策略方向与平台支持规则 |
| 初始预算 | MTA 策略分数、历史份额和预算基线 |

## 2. Campaign 层策略

每个 Campaign 的策略结果至少包含：

| 字段 | 含义 |
| --- | --- |
| `campaign_id` | 输入中给定的 Campaign |
| `recommended_ad_group_count` | 模型推荐的 Ad Group 数量 |
| `count_rationale` | 为什么需要这个数量 |
| `strategy_coverage` | 本次策略覆盖了哪些主要 MTA 信号和候选内容 |
| `unassigned_signals` | 未进入任何 Ad Group 的信号及原因 |
| `recommended_ad_groups` | 具体 Ad Group 策略列表 |

`count_rationale` 建议使用结构化字段：

```json
{
  "stable_strategy_cluster_count": 2,
  "required_keyword_target_count": 18,
  "required_sku_assignment_count": 6,
  "required_pair_count": 24,
  "keyword_capacity_count": 2,
  "sku_capacity_count": 1,
  "pair_capacity_count": 2,
  "capacity_required_count": 2,
  "merged_low_evidence_cluster_count": 1,
  "final_recommended_count": 2,
  "summary": "形成核心转化组和受限探索组"
}
```

Ad Group 数量同时由 MTA 策略差异和候选池容量决定。对 Campaign `c`：

```text
M_c = MTA 形成的稳定可执行策略簇数量

K_c = 该 Campaign 本次必须分配的 Keyword + Match Type 数量
S_c = 该 Campaign 本次必须分配的 SKU 数量
P_c = 该 Campaign 本次必须落地的 pairing 数量

CapacityCount_c
= max(
    ceil(K_c / max_keywords_per_ad_group),
    ceil(S_c / max_skus_per_ad_group),
    ceil(P_c / max_pairs_per_ad_group)
  )

RecommendedAdGroupCount_c
= max(M_c, CapacityCount_c)
```

计算后还必须应用 `max_ad_groups_per_campaign`、各广告产品的最小内容要求和复用规则。
如果策略簇数量超过候选内容可支持的最大组数，应合并低证据近似策略；如果候选内容超过
单组容量，应拆分相同策略角色。约束互相冲突时返回 `INFEASIBLE_INPUT_CONSTRAINT`，不能
为了凑数量产生空 Ad Group。

因此，Ad Group 数量不是预先写死，也不只由 MTA 决定：MTA 决定策略差异，初始条件中的
Keyword/SKU/pair 数量和容量上限决定是否需要进一步拆组。

“可用候选数量”不一定等于“必须分配数量”。初始条件必须明确：

| 策略 | 含义 |
| --- | --- |
| `USE_ALL_ELIGIBLE` | 所有合格 Keyword/SKU 都必须至少分配一次 |
| `SELECT_SUBSET` | 允许先筛选子集，再按筛选后的数量计算容量 |

pairing 同样需要 `USE_ALL_REQUIRED_PAIRS` 或 `VALIDITY_EDGES_ONLY`。如果 pairing 只用于证明
组合合法，就不能把合法边的总数全部计入容量；只有本次要求实际落地的 pairing 才进入
`P_c`。

### Group 候选池如何分到四个 Campaign

如果 Keyword/SKU 候选池只在 Campaign Group 层给定，模型先按以下初始条件过滤或分配：

- `eligible_campaign_ids` 或 `eligible_ad_products`；
- 每个 Campaign 的 Keyword/SKU 最小与最大数量；
- Keyword 和 SKU 是否允许跨 Campaign 或跨 Ad Group 复用；
- Keyword–SKU 合法 pairing；
- 平台与 `ad_product` 支持规则。

如果允许按数量自动分配，可使用 Campaign 的 MTA 策略权重计算配额，再用最大余数法确保
整数总量守恒。只有 Group 总数量、但没有 Campaign 适用范围或分配规则时，只能计算整体
容量下限，不能唯一确定每个 Campaign 应获得哪些具体候选。

## 3. Ad Group 策略字段

每个推荐 Ad Group 至少包含：

| 字段 | 含义 |
| --- | --- |
| `ad_group_id` | 推荐 Ad Group 的唯一 ID |
| `strategy_name` | 机器可读策略名称 |
| `strategy_role` | 转化、增长、认知或探索等角色 |
| `primary_objective` | 该组优先支持的业务 outcome |
| `source_touchpoints` | 支持该策略的 MTA 数值证据 |
| `recommended_actions` | 平台可执行或可配置的具体动作 |
| `targeting_assignment` | 从给定候选池选择的 Keyword/SKU 等对象 |
| `exclusions` | 明确不能使用的对象或动作 |
| `reason_codes` | 结构化推荐原因 |
| `confidence` | 0 至 1 的证据充分程度 |
| `constraints` | 容量、平台、合规和执行限制 |
| `budget_seed_share` | 初始预算份额；详细规则见输出数据契约 |

策略结果还应保存 `allocation_basis`，说明该组是因为 MTA 策略差异形成，还是因为候选
数量超过容量而拆分，或同时由两者形成。

## 4. MTA 数值证据

策略不能只保存触点名称，还应保留该触点的归因数值：

```json
{
  "touchpoint": "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK",
  "outcomes": {
    "converted_users": {
      "official_share": 0.08,
      "recommended_value": 0.08,
      "benchmark_share": 0.079,
      "reliability_status": "RELIABLE"
    },
    "purchase_count": {
      "official_share": 0.10,
      "recommended_value": 0.10,
      "benchmark_share": 0.098,
      "reliability_status": "RELIABLE"
    },
    "revenue": {
      "official_share": 0.12,
      "recommended_value": 0.12,
      "benchmark_share": 0.118,
      "reliability_status": "RELIABLE"
    }
  },
  "composite_score": 0.10
}
```

其中：

- `touchpoint` 保持 AMC MTA 五段键；
- `official_share`、`recommended_value`、`benchmark_share` 和可靠性字段来自给定 MTA 批次；
- `reliability_status` 用于阻止不可靠证据直接成为核心策略；
- `composite_score` 是三类 outcome 按配置综合后的初始优先级；
- 权重代表业务偏好，不代表模型在寻找全局最优。

## 5. 具体投放动作

`recommended_actions` 必须说明“建议做什么”，而不只是重复 MTA 触点：

```json
[
  {
    "dimension": "PLACEMENT",
    "action": "INITIAL_EMPHASIS",
    "value": "TOP_OF_SEARCH",
    "control_level": "PLACEMENT_ADJUSTMENT",
    "evidence_type": "ATTRIBUTION_BASED",
    "causal_claim": false
  },
  {
    "dimension": "MATCH_TYPE",
    "action": "USE",
    "value": "EXACT",
    "control_level": "TARGET"
  }
]
```

每项动作至少需要：

- `dimension`：动作针对的位置、形式、创意、受众或定向维度；
- `action`：建议优先、使用、限制、排除或仅作为证据；
- `value`：具体建议值；
- `control_level`：平台实际可以在哪一层执行。
- `evidence_type`：说明动作由归因证据、候选规则还是平台规则支持；
- `causal_claim`：当前必须为 `false`，因为 MTA 不是增量因果证明。

不能把 `CLICK` 直接翻译成“增加点击”，也不能把不可控制的触点维度伪装成可配置动作。

## 6. 不同广告产品的策略差异

四个 Campaign 的 `ad_product` 已给定。模型必须按广告产品输出不同的可执行策略：

| `ad_product` | 主要策略控制项 | Keyword 的角色 | SKU 的角色 |
| --- | --- | --- | --- |
| Sponsored Products | Keyword、Match Type、商品定向、Placement | 可作为原生定向 | 广告商品或商品定向对象 |
| Sponsored Brands | Keyword、商品定向、Placement、创意形式 | 可作为原生定向 | 品牌展示商品或商品定向对象 |
| Sponsored Display | 商品定向、Audience、Creative、支持的位置 | 通常作为意图信号，不一定是原生定向 | 广告商品或商品定向对象 |
| Amazon DSP | Audience、Inventory、Format、Creative、Line Item | 作为策略信号，不是 Keyword Match Type 指令 | 商品范围或受众构建信号 |

因此，给定 Keyword 和 SKU 不代表四个广告产品都使用相同的 targeting payload。模型应：

```text
给定 Keyword/SKU
        ↓
选择与 MTA 策略相符的候选
        ↓
根据 Campaign 的 ad_product
映射为平台支持的控制项
        ↓
无法映射则拒绝，不生成虚假动作
```

## 7. Keyword/SKU 策略分配

`targeting_assignment` 建议分成原生定向和策略信号：

```json
{
  "native_targets": {
    "keywords": [
      {"keyword_id": "K_RUNNING_EXACT", "match_type": "EXACT"}
    ],
    "skus": [
      {"sku_id": "SKU_PEG_BLACK", "target_role": "ADVERTISED_PRODUCT"}
    ]
  },
  "strategy_signals": {
    "keyword_ids": [],
    "sku_ids": []
  },
  "pairings": [
    {
      "keyword_id": "K_RUNNING_EXACT",
      "sku_id": "SKU_PEG_BLACK",
      "match_type": "EXACT"
    }
  ],
  "allocation_basis": {
    "method": "CAPACITY_BALANCED_WITH_MTA_PRIORITY",
    "keyword_count": 1,
    "sku_count": 1,
    "pair_count": 1,
    "remainder_priority": 1
  }
}
```

当某 Campaign 最终得到 `N` 个 Ad Group 时，候选数量可以确定每组的基础分配量：

```text
KeywordBase = floor(K_c / N)
KeywordRemainder = K_c mod N

SkuBase = floor(S_c / N)
SkuRemainder = S_c mod N
```

每组先获得基础数量，余数优先分配给MTA策略分数更高且仍有容量的Ad Group。具体对象
必须先通过候选池与pairing校验；随后可用
`amc_touchpoint_entity_aggregate_sample.csv`中的历史触点—Keyword/SKU关联，判断某个
候选过去出现在哪些五段触点及其观察量。实体表与MTA表通过五段触点连接，但辅助转化
不是实体自身的因果归因，不能直接称为“该Keyword/SKU的MTA贡献”。没有历史关联时，
退回候选intent/segment、合法pairing和确定性轮转。

必须满足：

- 所有对象来自本次冻结候选池；
- pairing 明确存在且不是 `BLOCKED`；
- 同一 Campaign 不重复 `Keyword + Match Type`；
- Keyword/SKU 是平台原生定向还是策略信号必须明确区分；
- 未选择的候选可以保留，不要求穷举整个候选池。

因此需要区分两个结论：

- 候选数量、容量和复用规则足以计算“需要拆成几组、每组放多少个”；
- 具体哪个Keyword/SKU进入哪个策略组，先由候选资格和合法pairing限定，再由同批历史
  实体聚合、候选元数据和确定性规则排序；MTA输出本身仍不需要增加Keyword/SKU ID。

## 8. 推荐原因与置信度

建议使用机器可读的原因码，例如：

```json
{
  "reason_codes": [
    "RELIABLE_MTA_TOUCHPOINT",
    "DISTINCT_EXECUTABLE_STRATEGY_CLUSTER",
    "HIGH_INTENT_KEYWORD_SKU_PAIR"
  ],
  "confidence": 0.91
}
```

`confidence` 表示证据充分程度，不是转化概率、ROI 预测或成功保证。它可以综合：

- MTA 可靠性；
- 三个 outcome 的一致性；
- 触点数据支持度；
- 候选关系类型和相关性；
- 策略是否可以映射成平台原生动作。

## 9. 完整策略片段

下面是单个 Campaign 的目标输出片段，省略预算计算明细：

```json
{
  "campaign_id": "C_DEMO_SP",
  "recommended_ad_group_count": 2,
  "count_rationale": {
    "stable_strategy_cluster_count": 2,
    "required_keyword_target_count": 6,
    "required_sku_assignment_count": 4,
    "required_pair_count": 8,
    "capacity_required_count": 1,
    "merged_low_evidence_cluster_count": 0,
    "final_recommended_count": 2,
    "summary": "高意图 Top of Search 与受限探索形成两个可执行策略簇"
  },
  "recommended_ad_groups": [
    {
      "ad_group_id": "C_DEMO_SP_AG_01",
      "strategy_name": "high_intent_top_search",
      "strategy_role": "CORE_CONVERSION",
      "primary_objective": "BALANCED_CONVERSION_AND_REVENUE",
      "source_touchpoints": ["见第 4 节结构"],
      "recommended_actions": [
        {
          "dimension": "PLACEMENT",
          "action": "INITIAL_EMPHASIS",
          "value": "TOP_OF_SEARCH",
          "control_level": "PLACEMENT_ADJUSTMENT",
          "evidence_type": "ATTRIBUTION_BASED",
          "causal_claim": false
        }
      ],
      "targeting_assignment": {
        "native_targets": {
          "keywords": [
            {"keyword_id": "K_RUNNING_EXACT", "match_type": "EXACT"}
          ],
          "skus": [
            {"sku_id": "SKU_PEG_BLACK", "target_role": "ADVERTISED_PRODUCT"}
          ]
        },
        "allocation_basis": {
          "method": "CAPACITY_BALANCED_WITH_MTA_PRIORITY",
          "keyword_count": 1,
          "sku_count": 1,
          "pair_count": 1
        }
      },
      "reason_codes": [
        "RELIABLE_MTA_TOUCHPOINT",
        "DISTINCT_EXECUTABLE_STRATEGY_CLUSTER"
      ],
      "confidence": 0.91,
      "budget_seed_share": 0.25
    }
  ]
}
```

这是结构片段，不是可以直接通过当前校验器的完整 JSON。

## 10. 策略验收规则

策略生成器完成后，结果应满足：

1. 每个 Campaign 都输出 `recommended_ad_group_count`；
2. 数量等于实际输出的 Ad Group 数量；
3. 每个数量都能同时追溯到 MTA 策略簇和候选容量计算；
4. 每个 Ad Group 至少引用一项带数值的 MTA 触点证据；
5. 每个具体动作都能映射到所属 `ad_product` 的支持项；
6. 所有 Keyword/SKU 来自给定候选池；
7. 不可靠触点不能单独支撑核心策略；
8. 每个策略包含原因码、置信度和约束；
9. 未分配的重要信号必须给出原因；
10. Keyword/SKU 数量在分配前后守恒，允许复用时必须遵守显式复用规则；
11. 所有分配均满足每组容量和合法 pairing；
12. 容量计算只使用本次必须分配的候选与 pairing，不把可选合法边错误计入；
13. 归因支持的动作标记 `causal_claim=false`；
14. 输出明确是初始策略，不宣称最高 ROI 或全局最优。

## 11. 当前实现差距

当前模拟输出已经包含策略名称、策略角色、MTA 触点名称、Keyword/SKU、原因码、置信度和
预算种子，但还缺少：

- MTA outcome 的实际数值；
- `recommended_ad_group_count` 的自动计算；
- `count_rationale`；
- 候选数量、容量和 MTA 策略簇的联合计数；
- Group 候选池到四个 Campaign 的配额与确定性分配；
- 触点到策略簇的自动形成过程；
- 平台原生 `recommended_actions`；
- 原生定向与策略信号的区分；
- 未分配信号及原因。

因此当前文件是策略输出的模拟样例，而本文定义的是后续生成器应达到的目标策略契约。

通用 JSON 层级、预算和关联规则见 [输出数据契约](output-data-contract.md)，整体计算流程见
[模型计划](model-plan.md)。
