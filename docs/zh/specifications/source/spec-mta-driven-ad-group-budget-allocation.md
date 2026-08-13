---
title: '实现 MTA 驱动的新 Ad Group 数量与预算模型'
type: 'refactor'
created: '2026-07-30'
status: 'done'
baseline_commit: '7907b101e3be0823e352ce51aae1bad5f204615d'
context:
  - '{project-root}/modules/mta_strategy_recommender/docs/output-data-contract.md'
  - '{project-root}/modules/amc_mta/data/simulated/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前模块固定 `2/2/1/1` 并输出具体投放计划，超出“根据 MTA 计算新 Ad Group 初始预算”的目标。

**Approach:** 候选数量与产品容量计算组数；MTA outcome 与 AMC `assisted_*` 桥接计算 Campaign 预算，再对同 Campaign 匿名新组等分。

## Boundaries & Constraints

**Always:** AMC 只读；保留一个 Group 和四个 Campaign；SP/SB 按 Keyword unit/SKU/合法 Pair，SD/DSP 按 SKU/Target/Audience 计数；`assisted_*` 仅作触点内权重；份额和金额逐层守恒；结果是非优化 initial seed。

**Ask First:** 修改 AMC、四个 Campaign、outcome 权重，或让同 Campaign 新组非等额分配前暂停；差异化必须先有稳定 slot 映射。

**Never:** 不输出候选 ID、Targeting、动作或策略角色；不复用历史组 ID；不声称最高 ROI/因果/优化；不反调容量保留旧数量；不碰 `log.md`、`docs/系统架构图-07.drawio`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 标准样例 | 17 触点、34 实体行、$1000 | 复算 `1/1/1/1` 与四组预算 | 返回摘要 |
| 候选扩大 | 计数跨容量边界 | 数量按 `ceil(count/capacity)` 增加 | 超过上限拒绝 |
| 无预算基线 | 省略 Group 总预算 | 保留 Campaign/Ad Group 相对份额，省略金额 | 返回 shares-only warning |
| 桥接分母为零 | outcome 的 `assisted_*` 全零 | clicks→impressions→users→等分并披露 | 无实体拒绝 |
| 预算不足 | 预算低于 `count × minimum` | 保留所需数量并标记不可执行 | 不静默减组 |

</frozen-after-approval>

## Code Map

- `modules/mta_strategy_recommender/data/simulated/*.json` -- 请求、容量和候选计数。
- `modules/mta_strategy_recommender/src/budget_recommender.py` -- 数量、桥接与预算的单一实现。
- `modules/mta_strategy_recommender/src/hierarchy_validator.py` -- 血缘和可复算校验。
- `modules/mta_strategy_recommender/tests/` -- 预算基准及边界回归。

## Tasks & Acceptance

**Execution:**
- [x] `data/simulated/*.json` -- 升级 budget-only v4，输入候选计数、容量和最低预算。
- [x] `src/budget_recommender.py` -- 生成数量、bridge、Campaign 分数与等分预算。
- [x] `src/hierarchy_validator.py`、`scripts/*.py` -- 生成并复算纯预算输出，拒绝旧字段和漂移。
- [x] `tests/` -- 重建基准与边界测试，覆盖动态数量、降级和守恒。
- [x] `README.md`、`docs/*.md`、工作区清单 -- 同步输入、公式、边界和命令。

**Acceptance Criteria:**
- Given 当前候选数量和容量，when 生成，then 四个 Campaign 数量均为 1，且修改任一计数跨容量边界会确定性增加对应数量。
- Given MTA 与 AMC 实体表，when 按 outcome 桥接，then各级份额可复算且和为 1。
- Given新组没有内容映射，when 分配预算，then同 Campaign 等分并标记 `CAMPAIGN_MTA_EQUAL_SPLIT`。
- Given $1000 总预算，when 输出，then Ad Group→Campaign→Group 金额守恒；无总预算时只输出 share。
- Given完整输出，when 检查 schema，then不存在候选 ID、Targeting、动作或历史组冒充新组。
- Given完整回归，when验收，then生成器确定性、策略测试通过、AMC 107 项测试通过且 `modules/amc_mta` 相对基线零变化。

## Spec Change Log

## Design Notes

历史组只在 bridge 内分摊触点贡献并汇总到 Campaign；候选数量只决定 `N`，因此匿名新组预算为 `campaign_share / N`。差异化需另加 `historical/candidate → new_slot` 映射。

## Verification

**Commands:**
- `python3 -B modules/mta_strategy_recommender/scripts/generate_initial_budget.py --check-fixture`
- `python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py`
- `python3 -B -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'`
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'`
- `git diff --exit-code 7907b101 -- modules/amc_mta`
- `git diff --check -- . ':(exclude)log.md' ':(exclude)docs/系统架构图-07.drawio'`

## Suggested Review Order

**预算生成主线**

- 从统一入口查看数量、MTA 份额与预算如何组合。
  [`budget_recommender.py:595`](../../modules/mta_strategy_recommender/src/budget_recommender.py#L595)

- 严格校验四 Campaign、v4 输入和产品容量规则。
  [`budget_recommender.py:135`](../../modules/mta_strategy_recommender/src/budget_recommender.py#L135)

**数量与归因**

- 用候选计数和容量上限确定新组数量。
  [`budget_recommender.py:298`](../../modules/mta_strategy_recommender/src/budget_recommender.py#L298)

- 将全部 MTA 触点经 AMC 实体桥接到 Campaign。
  [`budget_recommender.py:453`](../../modules/mta_strategy_recommender/src/budget_recommender.py#L453)

- 设计文档解释公式边界与同 Campaign 等分原因。
  [`model-plan.md:11`](../../docs/zh/strategy_recommendation/model-plan.md#L11)

**校验与交付**

- 独立检查 Ad Group、Campaign 与 Group 逐层守恒。
  [`hierarchy_validator.py:140`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L140)

- 命令行生成器支持写出结果或核对固定样例。
  [`generate_initial_budget.py:16`](../../modules/mta_strategy_recommender/scripts/generate_initial_budget.py#L16)

- 回归覆盖动态数量、桥接降级、严格 schema 和预算边界。
  [`test_hierarchy_validator.py:72`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L72)
