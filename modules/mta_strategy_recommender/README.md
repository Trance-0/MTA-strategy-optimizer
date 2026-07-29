# MTA-Informed Strategy Initializer

本模块以 Campaign Group 为顶层，当前交付带 AMC MTA 触点证据的初始投放数据契约、
运行条件样例和确定性校验。上游现已提供由同一模拟事实源生成的触点实体聚合，但
自动读取归因与实体证据并生成方案的adapter/generator尚未实现。

```text
Campaign Group
└── Campaign
    └── Ad Group（推荐数量与策略）
        ├── Keyword
        └── SKU
```

每个 Campaign 记录保存一个 `ad_product`；它不是独立业务层级。模型推荐 Ad Group 数量、Keyword/SKU 分配和预算初始点，不寻找最高 ROI，不执行持续优化或自动投放。

## 当前交付

- 一个 Group、四个 Campaign 的运行条件模拟数据；
- 冻结 Keyword/SKU 候选池与明确合法 pairing；
- 历史预算基线和 `INITIAL_SEED` 推荐样例；
- Group–Campaign N:N 管理范围与版本化候选池；
- 层级、候选引用、触点证据、pair、预算守恒和无基线规则校验；
- AMC MTA 五段输出继续作为上游归因证据，schema 不变；
- 触点实体聚合提供历史Campaign/Ad Group/Keyword/SKU关联，但不替代冻结候选池。

## 验证

```bash
python3 modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python3 -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'
```

## 入口

- [整体模型计划](docs/model-plan.md)
- [输出数据契约](docs/output-data-contract.md)
- [模型策略输出契约](docs/strategy-output-contract.md)
- [模拟数据说明](data/simulated/README.md)
- [层级校验器](src/hierarchy_validator.py)
- [AMC MTA 上游输出](../amc_mta/outputs/attribution/)
