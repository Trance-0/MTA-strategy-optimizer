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
| `strategy_request.json` | Group 范围、四个 Campaign、候选池/MTA 版本、可选总预算、outcome 权重和容量约束 |
| `candidate_pool.json` | 六个 Keyword、四个 SKU 及九条明确 Pair 规则；不使用笛卡尔积 |

手写的推荐结果仅是输出契约夹具，位于
`../../tests/fixtures/expected_initial_recommendation.json`，不代表模型已经生成策略。

后续策略生成器将直接读取历史 MTA 与实体证据：

- `modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv`
- `modules/amc_mta/data/simulated/amc_touchpoint_entity_aggregate_sample.csv`

当前的 `hierarchy_validator.py` 不读取上述两张历史结果表；它只验证输出夹具中的
`mta_batch_id`、五段触点格式、Campaign `ad_product` 相容性和 outcome 名称。等策略生成器
实现后，才会用真实归因数值计算分组和预算种子。

策略输入通过 `mta_batch_id` 和 `candidate_pool_id` 保持可追溯。历史中观察过的实体不自动
等于本次允许投放的候选，候选池中的探索项也不能伪装成具有直接 MTA 实体证据。

校验命令：

```bash
python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
```
