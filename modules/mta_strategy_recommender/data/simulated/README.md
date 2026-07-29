# Campaign Group 层级模拟数据

本目录独立演示策略初始化器的业务输入与输出，层级固定为：

```text
Campaign Group
└── Campaign
    └── Ad Group（模型推荐）
        ├── Keyword
        └── SKU
```

样例包含一个 Campaign Group、四个 Campaign、冻结的 Keyword/SKU 候选池、明确审核的合法组合、历史预算基线和一份 `INITIAL_SEED` 推荐。`ad_product` 只保存于 Campaign 记录，Ad Group 通过 `campaign_id` 继承该属性。

Keyword/SKU/Match Type 在此是跨广告产品的归一化策略分配，不是可直接提交的平台
targeting payload；后续 adapter 必须按 Campaign 的 `ad_product` 做支持项映射或拒绝。

| 文件 | 用途 |
| --- | --- |
| `campaign_group.json` | Group 运行范围、候选池版本、MTA 批次和可选预算基线 |
| `campaigns.csv` | 四个 Campaign 及其单值 `ad_product` |
| `campaign_group_relationships.csv` | Group–Campaign N:N 关系的本次管理范围 |
| `candidate_keywords.csv` | 本次冻结的 Keyword 候选池 |
| `candidate_skus.csv` | 本次冻结的 SKU 候选池 |
| `eligible_keyword_sku_pairs.csv` | 已有、验证、探索或禁止的明确组合；不使用笛卡尔积 |
| `historical_budgets.csv` | 可选的历史 Campaign 预算基线 |
| `initial_recommendation.json` | Ad Group 数量、策略、Keyword/SKU 分配和预算种子样例 |

校验命令：

```bash
python3 modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
```

本目录仍负责策略运行时给定的Campaign、候选池、约束和预算基线，不由历史行为自动
生成。`modules/amc_mta/data/simulated/amc_touchpoint_entity_aggregate_sample.csv`则从
统一用户事件主表提供历史触点—Keyword/SKU关联。两者通过实体ID连接，但观察过的
历史实体不自动等于本次允许投放的候选池。
