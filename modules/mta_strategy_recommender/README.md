# MTA-Informed Strategy Initializer

本模块以 Campaign Group 为顶层，当前交付与 AMC MTA 逐条对齐的初始投放数据契约、
运行条件样例和确定性校验。校验器只读推荐归因与触点实体聚合，复算六组策略证据和预算；
自动生成策略的 adapter/generator 仍未实现。

```text
Campaign Group
└── Campaign
    └── Ad Group（推荐数量与策略）
        ├── Keyword
        └── SKU
```

每个 Campaign 记录保存一个 `ad_product`；它不是独立业务层级。模型推荐 Ad Group 数量、Keyword/SKU 分配和预算初始点，不寻找最高 ROI，不执行持续优化或自动投放。

## 当前交付

- `strategy_request.json` 中一个 Group、四个 Campaign、AMC SHA/范围和 `17 → 6` 选点口径；
- `candidate_pool.json` 中冻结的 Keyword/SKU、八条历史 Pair、补充 Pair 与 SD/DSP 信号规则；
- 独立测试夹具中的 `INITIAL_SEED` 预期输出，不冒充生成结果；
- 可选 Group 总预算、MTA 批次和版本化候选池；
- AMC SHA/范围、17 个触点、34 条实体、MTA 数值、历史 Pair、平台定向和预算复算；
- AMC MTA 五段输出继续作为上游归因证据，schema 不变；
- SP/SB 原生使用 Keyword/Match Type/SKU；SD/DSP 原生使用 SKU/Target/Audience，Keyword 只作非直接证据的策略信号；
- 历史 Ad Group ID 仅用于证据可读性，不要求等于新推荐 ID。

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
- [预期输出夹具](tests/fixtures/expected_initial_recommendation.json)
- [层级校验器](src/hierarchy_validator.py)
- [AMC MTA 上游输出](../amc_mta/outputs/attribution/)
