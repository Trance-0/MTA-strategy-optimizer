---
title: '精简 MTA 策略初始化模拟数据契约'
type: 'refactor'
created: '2026-07-30'
status: 'done'
baseline_commit: '2ad60f2c6a2fdb5cd8e749af13893176caa8b94c'
context:
  - '{project-root}/modules/mta_strategy_recommender/data/simulated/README.md'
  - '{project-root}/modules/mta_strategy_recommender/docs/model-plan.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前策略模拟目录用七个小型输入表和一个手写输出混合表达单个 Campaign Group、四个 Campaign、少量候选项与预算，重复范围字段多，且输入、历史参考和预期输出职责不清。

**Approach:** 将运行条件合并为 `strategy_request.json`，将 Keyword、SKU 和稀疏 Pair 规则合并为 `candidate_pool.json`；把手写推荐移到测试夹具。策略模块直接引用 AMC 的归因与实体聚合产物，不复制证据。

## Boundaries & Constraints

**Always:** 保留 `Campaign Group → 4 Campaign → Ad Group → Keyword/SKU` 业务层级；每个 Campaign 只有一个 `ad_product`；Pair 规则继续阻止 Keyword/SKU 笛卡尔积；总预算可省略，省略时只允许相对份额；候选池版本和 MTA 批次可追溯。

**Ask First:** 若必须改变推荐输出 schema、四个 Campaign 约束、AMC CSV/schema、五段触点或归因算法，暂停并征得批准。

**Never:** 不实现策略生成器或优化器；不把预期输出伪装成程序已生成结果；不复制 AMC 证据到策略模拟目录；不修改 `log.md` 或 `docs/系统架构图-07.drawio`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 标准样例 | 两个输入 JSON + 独立推荐夹具 | 校验四个 Campaign、候选引用、Pair、证据和预算守恒 | 返回摘要 |
| 无总预算 | 请求不含 `total_daily_budget`，夹具无绝对预算 | 只校验相对份额并返回 warning | 夹具含绝对预算则拒绝 |
| 候选非法 | 池外实体、BLOCKED Pair、非法 Match Type | 不接受推荐夹具 | 返回具体候选错误 |
| 文件职责错误 | 缺少两个输入之一或输出仍混入输入目录 | 不执行校验 | 返回缺失/位置错误 |

</frozen-after-approval>

## Code Map

- `modules/mta_strategy_recommender/data/simulated/` -- 精简后的两个输入和说明。
- `modules/mta_strategy_recommender/tests/fixtures/` -- 人工维护的预期输出样例。
- `modules/mta_strategy_recommender/src/hierarchy_validator.py` -- 解析嵌套 JSON 并校验输入与输出夹具。
- `modules/mta_strategy_recommender/tests/test_hierarchy_validator.py` -- 新契约正反例。
- `modules/mta_strategy_recommender/docs/` -- 输入、输出和模型计划说明。

## Tasks & Acceptance

**Execution:**
- [x] `data/simulated/{strategy_request.json,candidate_pool.json,README.md}` -- 合并 Group、Campaign、预算、候选与 Pair；删除七个被替代文件。
- [x] `tests/fixtures/expected_initial_recommendation.json` -- 将手写推荐明确移为预期输出夹具，内容 schema 保持不变。
- [x] `src/hierarchy_validator.py`、`scripts/validate_simulated_hierarchy.py` -- 读取两个输入与显式推荐路径，保留现有层级、候选、证据和预算校验。
- [x] `tests/test_hierarchy_validator.py` -- 改写19项回归，覆盖缺文件、版本不一致、BLOCKED Pair和无总预算。
- [x] `README.md`、`docs/*.md`、工作区清单 -- 清除现行旧文件引用并说明 AMC 证据直接读取边界。

**Acceptance Criteria:**
- Given 默认模拟目录，when 列出业务数据，then 只包含两个输入 JSON 和 README，预期推荐只存在于测试夹具。
- Given 标准样例，when 运行层级校验，then 4 Campaign、6 Keyword、4 SKU、9 Pair及6个推荐 Ad Group通过。
- Given 任一非法候选或预算状态，when 校验，then 在发布或策略实现前得到确定性错误。
- Given AMC MTA 与策略回归，when 完整运行，then AMC 107项测试和策略层测试通过且 AMC 产物不变。

## Spec Change Log

## Design Notes

两个 JSON 是当前小规模演示的平衡点：请求与可复用候选池仍分离，但不再为一组数据维护七张小表。若未来候选规模或上游来源显著扩大，可在不改变逻辑对象的前提下恢复表式存储。`expected_initial_recommendation.json` 在生成器实现前只证明输出契约，不代表模型已经计算。

## Verification

**Commands:**
- `python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py`
- `python3 -B -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'`
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'`
- `git diff --check`

## Suggested Review Order

**输入职责与边界**

- 先看两输入、一夹具及未来 MTA 生成器边界。
  [`README.md:3`](../../modules/mta_strategy_recommender/data/simulated/README.md#L3)

- Group、四个 Campaign、权重和容量约束集中在请求中。
  [`strategy_request.json:2`](../../modules/mta_strategy_recommender/data/simulated/strategy_request.json#L2)

- 候选实体与稀疏 Pair 规则集中且保持可追溯。
  [`candidate_pool.json:5`](../../modules/mta_strategy_recommender/data/simulated/candidate_pool.json#L5)

**确定性契约校验**

- 单一入口读取两个输入与显式输出夹具。
  [`hierarchy_validator.py:113`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L113)

- 必需容量约束控制每组及每 Campaign 规模。
  [`hierarchy_validator.py:178`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L178)

- 触点、候选分配、探索关系和预算逐层守恒。
  [`hierarchy_validator.py:271`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L271)

- 命令行明确区分输入目录与预期推荐路径。
  [`validate_simulated_hierarchy.py:16`](../../modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py#L16)

**模型边界与验收证据**

- 计划明确当前校验器与未来策略生成器的职责差异。
  [`model-plan.md:77`](../../modules/mta_strategy_recommender/docs/model-plan.md#L77)

- 十九项测试覆盖文件隔离、候选、探索、触点与预算反例。
  [`test_hierarchy_validator.py:45`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L45)
