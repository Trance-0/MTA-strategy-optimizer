# Ad Group 初始预算输出数据契约（v4）

## 1. 当前样例

| 数据 | 数量或口径 |
| --- | ---: |
| Campaign Group | 1 |
| Campaign | 4 |
| 推荐新 Ad Group | 4（1/1/1/1） |
| AMC MTA 触点 | 17（全部使用） |
| AMC 实体聚合行 | 34 |
| Group 日预算基线 | 1,000 USD |

## 2. 顶层字段

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 固定为 `4.0` |
| `campaign_group_id`、`candidate_pool_id`、`mta_batch_id` | 输入血缘 |
| `mta_source_snapshot` | AMC 窗口、市场、账户与两张文件 SHA |
| `budget_derivation` | bridge 公式、权重、行数、降级顺序和总分 |
| `recommendation_type` | `INITIAL_SEED` |
| `handoff_status` | `READY_FOR_OPTIMIZATION` |
| `is_optimized` | `false` |
| `warnings` | shares-only 或预算不足等状态 |
| `budget_seed_total` | 有 Group 预算基线时存在 |
| `campaigns` | 四个 Campaign 的数量与预算 |

预算归一化范围固定为 `ALL_AVAILABLE_MTA_TOUCHPOINTS`，不再人为选六个触点。

## 3. Campaign 输出

```json
{
  "campaign_id": "C_DEMO_SP",
  "recommended_ad_group_count": 1,
  "count_rationale": {
    "eligible_keyword_unit_count": 3,
    "eligible_sku_count": 3,
    "eligible_legal_pair_count": 3,
    "keyword_capacity_count": 1,
    "sku_capacity_count": 1,
    "legal_pair_capacity_count": 1,
    "final_recommended_count": 1
  },
  "outcome_contributions": {
    "converted_users": 0.242017,
    "purchase_count": 0.24183,
    "revenue": 0.23492
  },
  "campaign_mta_score": 0.2398318,
  "budget_seed_share": 0.2398318,
  "campaign_budget_seed": 239.8318,
  "execution_status": "EXECUTABLE"
}
```

`bridge_summary.historical_ad_group_count` 只披露参与 bridge 的历史组数量，不输出历史 ID；
`method_counts` 披露每个触点/outcome 使用的 `assisted_*` 或降级权重。

`budget_derivation.mta_value_policy` 固定为
`RELIABLE_POINT_OR_UNRELIABLE_RANGE_MIDPOINT`：可靠行使用单点；不可靠行使用 AMC
`[low,high]` 范围的中点并输出 `UNRELIABLE_MTA_RANGE_MIDPOINT_USED`。中点只是初始预算
代表值，不是最优值或统计置信结论。

## 4. Ad Group 输出

```json
{
  "ad_group_slot_id": "C_DEMO_SP_NEW_AG_01",
  "allocation_basis": "CAMPAIGN_MTA_EQUAL_SPLIT",
  "budget_seed_share": 0.2398318,
  "initial_daily_budget": 239.8318
}
```

新组只是一组匿名预算接收槽位。输出不得出现具体候选 ID、Targeting、Audience、投放动作、
策略角色或历史 Ad Group ID。

## 5. 守恒与缺省

```text
Σ Ad Group share = Campaign share
Σ Campaign share = 1
每个 MTA outcome 的 recommended_value 之和 = 1
Σ Ad Group budget = Campaign budget
Σ Campaign budget = Group budget
```

没有 `total_daily_budget` 时省略所有绝对金额，保留 share，并输出
`NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY`。预算不足时输出
`INSUFFICIENT_BUDGET_FOR_MINIMUMS`，不改变容量所需数量。
