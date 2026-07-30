# 策略初始化器输出数据契约

本文说明策略初始化器当前输出的 JSON 结构和字段含义。输出是供后续优化团队使用的
`INITIAL_SEED`，不是最优解，也不是可直接提交给广告平台的执行请求。

模型后续应输出的 Ad Group 数量依据、MTA 数值证据和具体投放动作，见
[模型策略输出契约](strategy-output-contract.md)。

## 1. 输出文件

```text
modules/mta_strategy_recommender/tests/fixtures/expected_initial_recommendation.json
```

当前样例包含：

| 数据 | 结果 |
| --- | ---: |
| Campaign Group | 1 个 |
| Campaign | 4 个 |
| 推荐 Ad Group | 6 个 |
| 总日预算基线 | 1,000 USD |

输出层级为：

```text
Campaign Group
└── Campaign
    └── Ad Group
        ├── MTA 触点证据
        ├── Keyword
        ├── SKU
        ├── Keyword–SKU–Match Type pairing
        └── 初始预算
```

## 2. JSON 结构片段

下面只展示一个 Campaign 和一个 Ad Group，用于认识字段；它省略了其余 Campaign、
Ad Group 和部分分配，不能直接作为校验输入。可运行的完整结果见文末链接。

```json
{
  "campaign_group_id": "CG_DEMO_001",
  "candidate_pool_id": "pool_demo_2026_07",
  "mta_batch_id": "mta_demo_2026_07",
  "recommendation_type": "INITIAL_SEED",
  "handoff_status": "READY_FOR_OPTIMIZATION",
  "is_optimized": false,
  "budget_seed_total": 1000.0,
  "campaigns": [
    {
      "campaign_id": "C_DEMO_SP",
      "budget_seed_share": 0.45,
      "campaign_budget_seed": 450.0,
      "recommended_ad_groups": [
        {
          "ad_group_id": "C_DEMO_SP_AG_01",
          "strategy_name": "high_intent_top_search",
          "strategy_role": "CORE_CONVERSION",
          "source_candidate_pool_id": "pool_demo_2026_07",
          "mta_evidence": [
            {
              "touchpoint": "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK",
              "outcomes": ["converted_users", "purchase_count", "revenue"]
            }
          ],
          "reason_codes": [
            "RELIABLE_MTA_TOUCHPOINT",
            "HIGH_INTENT_KEYWORD_SKU_PAIR"
          ],
          "confidence": 0.91,
          "budget_seed_share": 0.25,
          "initial_daily_budget": 250.0,
          "keywords": [
            {"keyword_id": "K_RUNNING_EXACT", "match_type": "EXACT"}
          ],
          "skus": [
            {"sku_id": "SKU_PEG_BLACK"}
          ],
          "pairings": [
            {
              "keyword_id": "K_RUNNING_EXACT",
              "sku_id": "SKU_PEG_BLACK",
              "match_type": "EXACT"
            }
          ]
        }
      ]
    }
  ]
}
```

## 3. 顶层字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `campaign_group_id` | string | 本次推荐所属的 Campaign Group |
| `candidate_pool_id` | string | 本次冻结候选池版本 |
| `mta_batch_id` | string | 使用的 MTA 批次 |
| `recommendation_type` | string | 固定为 `INITIAL_SEED` |
| `handoff_status` | string | 固定为 `READY_FOR_OPTIMIZATION` |
| `is_optimized` | boolean | 固定为 `false` |
| `budget_seed_total` | number | Group 绝对预算基线；无基线时省略 |
| `campaigns` | array | 四个 Campaign 的推荐结果 |

三个状态字段共同表示：结果可以交给优化团队，但本身没有经过持续优化。

## 4. Campaign 字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `campaign_id` | string | 输入中已有的 Campaign |
| `budget_seed_share` | number | Campaign 占整个 Group 预算的比例 |
| `campaign_budget_seed` | number | Campaign 绝对预算；无基线时省略 |
| `recommended_ad_groups` | array | 推荐的一个或多个 Ad Group |

输出不重复保存 Campaign 的 `ad_product`，调用方通过 `campaign_id` 回查
`strategy_request.json` 中的 `campaigns`。

当前预算结果为：

| Campaign | `ad_product` | Ad Group | 预算份额 | 日预算 |
| --- | --- | ---: | ---: | ---: |
| `C_DEMO_SP` | `SPONSORED_PRODUCTS` | 2 | 0.45 | 450 |
| `C_DEMO_SB` | `SPONSORED_BRANDS` | 2 | 0.30 | 300 |
| `C_DEMO_SD` | `SPONSORED_DISPLAY` | 1 | 0.15 | 150 |
| `C_DEMO_DSP` | `AMAZON_DSP` | 1 | 0.10 | 100 |

## 5. Ad Group 字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `ad_group_id` | string | 推荐 Ad Group 的唯一标识 |
| `strategy_name` | string | 非空的机器可读策略名称；校验器强制提供 |
| `strategy_role` | string | 非空策略角色；`EXPLORATION` 组数量受请求约束 |
| `source_candidate_pool_id` | string | 必须与顶层候选池版本一致 |
| `mta_evidence` | array | 支持该策略的 MTA 五段触点 |
| `reason_codes` | array[string] | 推荐原因码 |
| `confidence` | number | 0 至 1 的证据充分程度，不是成功概率 |
| `budget_seed_share` | number | Ad Group 占整个 Group 预算的比例 |
| `initial_daily_budget` | number | Ad Group 绝对日预算；无基线时省略 |
| `keywords` | array | Keyword 与 Match Type 分配 |
| `skus` | array | SKU 分配 |
| `pairings` | array | 明确允许的 Keyword–SKU–Match Type 组合 |

除注明“无基线时省略”的金额字段外，当前结构中的其他字段均应提供。校验器要求
`campaigns` 覆盖四个 Campaign，并要求 `recommended_ad_groups`、`mta_evidence`、
`reason_codes`、`keywords`、`skus` 和 `pairings` 都是非空数组。

## 6. MTA 证据与候选分配

MTA 证据格式：

```json
{
  "touchpoint": "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK",
  "outcomes": ["converted_users", "purchase_count", "revenue"]
}
```

触点继续使用 AMC MTA 五段键：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

第一段必须与所属 Campaign 的 `ad_product` 一致。outcome 只能是：

- `converted_users`
- `purchase_count`
- `revenue`

Keyword/SKU不写入MTA结果，而是通过相同五段触点回查
`amc_touchpoint_entity_aggregate_sample.csv`中的历史实体关联。只有同时存在于本次冻结
候选池中的实体才能进入推荐；历史出现不等于当前可投放，辅助转化也不等于实体级因果
贡献。

实际 Keyword/SKU 组合必须在 `pairings` 中明确列出：

```json
{
  "keyword_id": "K_RUNNING_EXACT",
  "sku_id": "SKU_PEG_BLACK",
  "match_type": "EXACT"
}
```

Keyword 和 SKU 同时进入一个 Ad Group，不代表可以形成任意笛卡尔积。pairing 必须存在于
冻结候选关系中，且不能是 `BLOCKED`。

此外，当前校验还要求：

- 每个已分配 Keyword 和 SKU 至少出现在一个 pairing 中；
- pairing 的 Match Type 与 Keyword 分配一致，并受候选池允许；
- 同一 Ad Group 不重复 SKU 或 pairing；
- 同一 Campaign 不重复 `Keyword + Match Type`；
- 每组 Keyword/SKU 数量、每 Campaign Ad Group 数量和探索组数量满足请求约束；
- `EXPLORATION` Pair 必须放入受控探索组并携带对应原因码，不能伪装成核心实体证据。

## 7. 预算口径

所有 `budget_seed_share` 都是 Campaign Group 级份额：

```text
Ad Group 份额之和 = 所属 Campaign 份额
Campaign 份额之和 = 1
```

存在预算基线时：

```text
Ad Group 日预算 = Group 总预算 × Ad Group 份额
Campaign 预算 = 所属 Ad Group 日预算之和
Group 总预算 = 所有 Campaign 预算之和
```

当前样例：

```text
SP:  0.25 + 0.20 = 0.45 = 450 USD
SB:  0.16 + 0.14 = 0.30 = 300 USD
SD:  0.15        = 0.15 = 150 USD
DSP: 0.10        = 0.10 = 100 USD
Group              1.00 = 1,000 USD
```

没有预算基线时，只保留相对份额，并省略：

- 顶层 `budget_seed_total`
- Campaign `campaign_budget_seed`
- Ad Group `initial_daily_budget`

校验摘要会返回 `NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY`。

## 8. ID 回查关系

| 输出 ID | 回查文件 | 获取信息 |
| --- | --- | --- |
| `campaign_group_id` | `strategy_request.json` | 平台、市场、账户、币种和可选总预算 |
| `campaign_id` | `strategy_request.json` 的 `campaigns` | Campaign 名称、`ad_product` 和状态 |
| `keyword_id` | `candidate_pool.json` 的 `keywords` | Keyword 文本、意图和允许 Match Type |
| `sku_id` | `candidate_pool.json` 的 `skus` | Product、品牌、品类、库存和投放资格 |
| Keyword/SKU | `candidate_pool.json` 的 `pair_rules` | 关系类型与是否可分配 |

候选文件和输出必须使用同一个 `candidate_pool_id`，避免混用不同版本的数据。

## 9. 当前边界

当前已经实现的是输出契约、模拟数据和确定性校验。尚未实现：

- 自动读取正式MTA输出和触点实体聚合；
- outcome 加权评分；
- 策略聚类和自动生成推荐；
- 持续预算优化或自动投放。

生产输出应遵守表格中的严格 JSON 类型。当前校验器仍兼容部分布尔和数字字符串，这是
输入兼容行为，不应作为新数据生产规范。

Keyword、SKU 和 Match Type 是跨广告产品的归一化策略表达，不是所有广告产品都能直接
使用的平台 targeting payload。后续 adapter 必须根据 Campaign 的 `ad_product` 做平台
映射；无法映射时必须拒绝。

## 10. 验证

```bash
python3 modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python3 -m unittest discover \
  -s modules/mta_strategy_recommender/tests \
  -p 'test_*.py'
```

校验实现见 [`hierarchy_validator.py`](../src/hierarchy_validator.py)，完整结果见
[`expected_initial_recommendation.json`](../tests/fixtures/expected_initial_recommendation.json)。
