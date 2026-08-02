# MTA-Driven Ad Group Budget Initializer

本模块只生成新 Ad Group 的**数量与初始预算**，不生成 Keyword/SKU 分配、Targeting、动作或
策略角色，也不做优化、因果增量判断或自动投放。

```text
候选数量 + 产品容量 → 每个 Campaign 的新 Ad Group 数量
MTA outcome + AMC 实体桥接 → Campaign 预算份额
Campaign 份额 ÷ 匿名新组数量 → 每个 Ad Group 初始预算
```

当前 Campaign Group 固定包含四个 Campaign，每个分别使用 SP、SB、SD、DSP。v4 样例的
真实容量计算结果为 `1/1/1/1`，不是为了保留旧结果而写死。

## 当前交付

- `strategy_request.json`：Group 范围、四个 Campaign、AMC 血缘、outcome 权重、容量和最低预算；
- `candidate_pool.json`：每个 Campaign 的合格候选计数，不保存具体候选 ID；
- `budget_recommender.py`：数量、AMC bridge、Campaign 分数和匿名组等分的单一纯函数；
- `outputs/initial_budget_recommendation.json`：确定性生成的正式预算结果，也是测试唯一基准；
- budget-only 确定性校验器；
- AMC 文件只读，`assisted_*` 只在触点内部作为分摊权重。

可靠 MTA 行使用推荐单点；不可靠 `[low,high]` 行只取中点作为可披露的初始预算代表值。

## 运行

```bash
python3 -B modules/mta_strategy_recommender/scripts/generate_initial_budget.py --check-output
python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python3 -B -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'
```

不带 `--check-output` 时，生成器把结果写到标准输出，方便下游另行保存。旧
`--check-fixture` 参数仍是兼容别名；当前文档和新调用统一使用 `--check-output`。

## 文档

- [整体模型计划](docs/model-plan.md)
- [当前 Ad Group 初始预算计算详解](docs/current-ad-group-budget-calculation.md)
- [MTA 到 Ad Group 预算问题定义与研究计划](docs/mta-to-ad-group-budget-optimization-plan.md)
- [输出数据契约](docs/output-data-contract.md)
- [预算策略输出契约](docs/strategy-output-contract.md)
- [模拟输入说明](data/simulated/README.md)
- [正式初始预算结果](outputs/initial_budget_recommendation.json)
