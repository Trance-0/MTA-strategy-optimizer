# 策略初始化器输出数据契约

当前输出是与仓库内 AMC 样例逐条对齐的 `INITIAL_SEED` 测试夹具，不是优化结果、因果结论
或可直接提交广告平台的请求。完整文件位于
`tests/fixtures/expected_initial_recommendation.json`。

## 1. 当前样例

| 数据 | 数量或口径 |
| --- | ---: |
| Campaign Group | 1 |
| Campaign | 4 |
| 推荐 Ad Group | 6（2/2/1/1） |
| AMC 可用五段触点 | 17 |
| 预算入选触点 | 6 |
| AMC 实体聚合行 | 34 |
| 历史 Keyword–SKU–Match Type Pair | 8 |
| Group 日预算基线 | 1,000 USD |

## 2. 顶层字段

| 字段 | 含义 |
| --- | --- |
| `campaign_group_id` | 本次推荐所属 Group |
| `candidate_pool_id` | 冻结候选池版本 |
| `mta_batch_id` | 人类可读批次别名 |
| `mta_source_snapshot` | AMC 窗口、账户、市场及两张文件 SHA-256 |
| `touchpoint_selection` | `17 → 6` 选点和实体选择方法 |
| `budget_derivation` | outcome 权重、公式版本、六点综合分总和及归一化范围 |
| `recommendation_type` | 固定为 `INITIAL_SEED` |
| `handoff_status` | 固定为 `READY_FOR_OPTIMIZATION` |
| `is_optimized` | 固定为 `false` |
| `budget_seed_total` | 可选 Group 绝对预算；无基线时省略 |
| `campaigns` | 四个 Campaign 的结果 |

血缘不再只依赖 `mta_batch_id`。校验器必须将 `mta_source_snapshot` 与
`strategy_request.mta_source` 比较，并对实际 AMC 文件重新计算 SHA。

## 3. 触点选择与预算口径

当前固定口径为：

```text
normalization_universe = SELECTED_RECOMMENDED_TOUCHPOINTS
available_touchpoint_count = 17
selected_touchpoint_count = 6
excluded_touchpoint_count = 11
```

每个入选触点按请求权重计算：

```text
CompositeScore
= 0.4 × converted_users.recommended_value
+ 0.3 × purchase_count.recommended_value
+ 0.3 × revenue.recommended_value

AdGroupShare
= CompositeScore / 六个入选触点 CompositeScore 之和
```

六个当前结果为：

| Campaign | 触点简写 | 综合分 | Group 份额 | 1,000 USD 日预算 |
| --- | --- | ---: | ---: | ---: |
| SP | Top Search Click | 0.0705870 | 0.205115524 | 205.115524 |
| SP | Rest Search Click | 0.0516523 | 0.150094048 | 150.094048 |
| SB | Component Top Click | 0.0561855 | 0.163266866 | 163.266866 |
| SB | Display Rest Impression | 0.0491124 | 0.142713469 | 142.713469 |
| SD | Product Page Image Click | 0.0600666 | 0.174544776 | 174.544776 |
| DSP | Display Image Impression | 0.0565291 | 0.164265317 | 164.265317 |

这些份额不是 17 个触点各自的原始归因 share，而是六个策略入选触点内部的预算归一化。
如果改变六点范围，必须先重新确认规格。

## 4. Campaign 字段

| 字段 | 含义 |
| --- | --- |
| `campaign_id` | 输入中已有的 Campaign |
| `recommended_ad_group_count` | 当前固定为 SP=2、SB=2、SD=1、DSP=1 |
| `count_rationale` | 稳定策略簇、容量下限与最终数量说明 |
| `budget_seed_share` | 该 Campaign 所有 Ad Group 的 Group 级份额之和 |
| `campaign_budget_seed` | 可选绝对预算；无 Group 基线时省略 |
| `recommended_ad_groups` | 具体初始策略 |

输出不重复保存 `ad_product`；通过 `campaign_id` 回查 `strategy_request.json`。

## 5. Ad Group 与 MTA 证据

每组至少保存：

```json
{
  "ad_group_id": "C_DEMO_SP_AG_01",
  "strategy_name": "top_search_lightweight_trail",
  "strategy_role": "CORE_CONVERSION",
  "mta_evidence": [
    {
      "touchpoint": "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK",
      "outcomes": {
        "converted_users": {
          "official_share": 0.070755,
          "recommended_value": 0.070755,
          "benchmark_share": 0.069927,
          "reliability_status": "RELIABLE"
        }
      },
      "composite_score": 0.070587
    }
  ],
  "entity_evidence": {
    "source_ad_group_id": "C_DEMO_SP_AG01",
    "selection_rank": 1,
    "assisted_revenue": 9581.89
  },
  "budget_seed_share": 0.20511552368285625
}
```

三个 outcome 都必须存在，数值和可靠性必须与
`amc_mta_recommended_attribution.csv` 完全一致。`entity_evidence.source_ad_group_id` 是历史
证据的可读标识，不要求等于新推荐 `ad_group_id`。

## 6. 平台适配的定向结构

```json
{
  "targeting_assignment": {
    "native_targets": {
      "keywords": [],
      "skus": [],
      "target_ids": [],
      "audience_ids": []
    },
    "strategy_signals": {
      "keyword_ids": [],
      "sku_ids": []
    },
    "pairings": []
  }
}
```

| 广告产品 | `native_targets` | Keyword 规则 |
| --- | --- | --- |
| Sponsored Products | Keyword + Match Type + Target + SKU/ASIN | 原生定向，Pair 必须是允许的 `HISTORICAL` |
| Sponsored Brands | Keyword + Match Type + Target + SKU/ASIN | 原生定向，Pair 必须是允许的 `HISTORICAL` |
| Sponsored Display | SKU/ASIN + Target + Audience | Keyword 只能进入 `strategy_signals` |
| Amazon DSP | SKU/ASIN + Target + Audience | Keyword 只能进入 `strategy_signals` |

当前 v3.0 样例以“一条 AMC 实体对应一个初始 Ad Group”为边界：SP/SB 必须恰好包含
1 个 Keyword、1 个 SKU 和 1 个 Pair；SD/DSP 必须恰好包含 1 个 SKU、1 个 Target、
1 个 Audience 和 1 个 Keyword 信号。不能在正确实体后追加未验证候选；未来若支持多实体，
需要升级版本并逐项回查，而不是放宽当前校验。

SD/DSP 信号必须命中候选池 `signal_rules`，并保存
`direct_mta_entity_evidence=false`。这表示它是候选语义信号，不是该 Keyword 的直接 MTA
实体归因。

## 7. 实体选择规则

同一 Campaign/触点可能有多条历史实体。当前确定性规则为：

1. 按 `assisted_revenue` 降序；
2. SP/SB 跳过同一 Campaign 已使用的 `Keyword + Match Type`；
3. 选择首条仍可执行且在冻结候选池中的实体；
4. 保存原始收入排序 `selection_rank`。

这只是可复算的初始点，不表示实体级 MTA 贡献或因果最优。AMC 实体表的
`assisted_revenue` 不能跨实体相加。

## 8. 预算与无基线规则

所有 share 都是 Campaign Group 级份额：

```text
Ad Group share 之和 = 1
Campaign share = 所属 Ad Group share 之和
Ad Group budget = Group budget × Ad Group share
```

没有 `campaign_group.total_daily_budget` 时仍复算并输出相对 share，但省略：

- `budget_seed_total`
- `campaign_budget_seed`
- `initial_daily_budget`

摘要返回 `NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY`。

## 9. 校验

```bash
python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python3 -B -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'
```

校验器只读 AMC 文件，覆盖 SHA/范围、17/34 行数、六点 MTA 数值、八条历史 Pair、
SD/DSP 原生字段、实体选择、综合分、份额和绝对预算守恒。
