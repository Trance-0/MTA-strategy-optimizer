# Campaign Group 策略初始化输入

本目录只保存一次策略初始化所需的业务输入，不保存历史 MTA 证据，也不保存推荐输出。
层级固定为：

```text
Campaign Group
└── Campaign（固定四个，每个只有一个 ad_product）
    └── Ad Group（未来由模型推荐）
        ├── Keyword
        └── SKU
```

| 文件 | 用途 |
| --- | --- |
| `strategy_request.json` | Group 范围、四个 Campaign、AMC 文件 SHA/窗口、17→6 选点口径、可选总预算、outcome 权重和容量约束 |
| `candidate_pool.json` | 六个 Keyword、四个 SKU、八条历史 Pair、两条补充 Pair 及两条 SD/DSP 信号规则 |

手写的推荐结果仅是输出契约夹具，位于
`../../tests/fixtures/expected_initial_recommendation.json`，不代表模型已经生成策略。

当前校验器只读以下历史 MTA 与实体证据：

- `modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv`
- `modules/amc_mta/data/simulated/amc_touchpoint_entity_aggregate_sample.csv`

`hierarchy_validator.py` 校验文件 SHA、账户/窗口、17 个触点、34 条实体、六个选中触点、
三类 outcome 数值、平台原生定向、实体选择和预算复算。它不会修改或重新生成 AMC。

策略输入通过 `mta_source`、`mta_batch_id` 和 `candidate_pool_id` 保持可追溯。`evidence_type`
记录历史或补充证据，`allocation_role` 记录用途，`policy_status` 单独记录允许或禁止；历史中
出现不等于当前允许投放，补充候选也不能伪装成直接 MTA 实体证据。

校验命令：

```bash
python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
```
