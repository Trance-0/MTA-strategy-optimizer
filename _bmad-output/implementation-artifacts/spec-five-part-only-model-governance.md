---
title: 'AMC MTA 治理输出仅保留五粒度'
type: 'refactor'
created: '2026-07-17'
status: 'done'
baseline_commit: '549d724'
context:
  - '{project-root}/modules/amc_mta/docs/model-comparison-governance.md'
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前 Markov、Shapley 主结果已经是五粒度，但比较模块仍生成四粒度摘要、四段父触点字段和父级原因码，导致最终输出仍混入用户不再考虑的四粒度信息。

**Approach:** 将模型比较、推荐和摘要契约统一为五粒度；删除所有四粒度投影、父触点诊断及其字段，只按完整 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 键计算支持度、差距、整体指标和治理状态。

## Boundaries & Constraints

**Always:** 保留 `interaction_type=IMPRESSION|CLICK`；保留 Markov 为正式展示模型、Path-level Shapley 为参照模型；三个 outcome 独立评估；触点比较和推荐仍各为 `17 × 3 = 51` 行；摘要改为三个 outcome 的 3 行五粒度结果；支持度直接从五段 AMC 路径重算；当前稳定性证据缺失时继续阻断 `decision_value` 和自动预算。

**Ask First:** 若需要重新引入任意聚合粒度、修改差距/支持度阈值、改变双模型主从关系、融合模型或开放自动预算，必须先征求用户确认。

**Never:** 不生成 `FOUR_PART` 行；不输出 `parent_touchpoint`、`parent_support_level`、`parent_difference_level`；不生成 `INTERACTION_ALLOCATION_*`、`PARENT_*` 或 `TOUCHPOINT_DIVERGENCE` 等依赖四段投影的原因码；不修改历史已完成规格中的原始记录；不改变 CPC/CPM 成本归属和五段主归因算法。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 默认样例 | 17 个五段触点、3 个 outcome | 比较 51 行、摘要 3 行、推荐 51 行，所有触点键均为五段 | N/A |
| 曝光和点击共享前四段 | 两个独立五段触点 | 分别评估，不进行四段合并或父级解释 | N/A |
| 小/中/大差距 | Markov 与 Shapley 五段 share 不同 | 原因码仅来自五段差距分类，如 `ALIGNED`、`MODEL_REVIEW`、`ABSOLUTE_GAP` | N/A |
| 非法模型或路径输入 | 集合错位、重复、非有限、负数或不守恒 | 不发布混合结果 | 抛出明确 `ValueError` |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/model_comparison.py` -- 当前四段投影、父级字段、摘要和推荐行的单一实现来源。
- `modules/amc_mta/tests/test_model_comparison.py` -- 父级诊断测试及比较行数、字段契约测试。
- `modules/amc_mta/tests/test_amc_mta_end_to_end.py` -- 五份产物、摘要行数和样例指标回归。
- `modules/amc_mta/outputs/attribution/` -- 需要重建的三份治理 CSV。
- `modules/amc_mta/README.md`、`modules/amc_mta/docs/`、`docs/amc-mta-*.md` -- 当前输出与治理说明。

## Tasks & Acceptance

**Execution:**
- [x] `modules/amc_mta/src/model_comparison.py` -- 移除四段聚合函数、父级诊断和父级字段；支持度函数固定为五粒度；摘要仅生成三个五段 outcome 行。
- [x] `modules/amc_mta/tests/` -- 删除父级行为断言，增加输出不含四粒度字段/状态、摘要仅 3 行且键均为五段的回归测试。
- [x] `modules/amc_mta/outputs/attribution/` -- 重新运行流水线，发布新的比较、摘要和推荐 CSV 契约。
- [x] 当前 README 与治理文档 -- 删除四段阅读、父级汇总和相关原因码说明，明确仅使用五粒度。

**Acceptance Criteria:**
- Given 默认流水线，when 生成全部五份输出，then 两份模型结果、51 行比较、3 行摘要和 51 行推荐均只表达五粒度。
- Given 任一治理 CSV，when 检查表头和值，then 不存在 `parent_*` 字段、`FOUR_PART` 值或依赖四粒度的原因码。
- Given 三个 outcome，when 核对摘要，then TVD、Spearman、Top K 和关键分歧数量沿用原五粒度计算结果。
- Given 当前证据状态，when 查看推荐输出，then 51 行仍为 `EVIDENCE_UNVERIFIED`、`decision_value` 为空且 `automation_allowed=false`。

## Design Notes

摘要保留 `grain` 字段并固定写入 `FIVE_PART`，使文件自描述且便于下游校验；删除的是四粒度计算和输出，不是五粒度标签。历史规格作为追溯记录不改写，当前代码、CSV、README 和现行治理文档必须无四粒度契约。

## Verification

**Commands:**
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 全部测试通过。
- `python3 modules/amc_mta/run_pipeline.py` -- expected: 五份输出确定性重建。
- `python3 modules/amc_mta/scripts/validate_data_alignment.py` -- expected: 17 个五段触点和 61 天范围对齐。
- `rg -n 'FOUR_PART|parent_touchpoint|parent_support_level|parent_difference_level|INTERACTION_ALLOCATION|PARENT_TOUCHPOINT|PARENT_AGGREGATE|TOUCHPOINT_DIVERGENCE' modules/amc_mta/src modules/amc_mta/scripts modules/amc_mta/outputs modules/amc_mta/README.md modules/amc_mta/docs README.md docs/amc-mta-architecture.md docs/amc-mta-capability-assessment.md docs/component-inventory.md docs/development-guide.md docs/index.md docs/source-tree-analysis.md` -- expected: 当前实现、输出和现行说明无残留；测试使用这些字面量锁定禁用契约，因此不纳入残留扫描。

**Results:**
- 75 项测试通过。
- 完整流水线确定性重建五份输出。
- 17 个 AMC/Amazon Ads 五段触点及 61 天范围对齐。
- 比较 51 行、摘要 3 行、推荐 51 行；摘要全部为 `FIVE_PART`。
- 51 行推荐全部为 `EVIDENCE_UNVERIFIED`，`decision_value` 为空，
  `automation_allowed=false`。
- 禁用字段、状态和原因码在当前实现、输出及现行说明中的残留扫描为零。

## Suggested Review Order

**五粒度治理实现**

- 从完整五段路径直接重算支持度，不再接受其他治理粒度。
  [`model_comparison.py:440`](../../modules/amc_mta/src/model_comparison.py#L440)

- 逐触点比较只生成五段字段、五段原因码和阻断状态。
  [`model_comparison.py:612`](../../modules/amc_mta/src/model_comparison.py#L612)

- 每个 outcome 仅追加一行 `FIVE_PART` 整体摘要。
  [`model_comparison.py:699`](../../modules/amc_mta/src/model_comparison.py#L699)

- 比较与推荐 CSV 契约已删除全部父级字段。
  [`model_comparison.py:47`](../../modules/amc_mta/src/model_comparison.py#L47)

**输出与阅读契约**

- 治理文档明确所有指标和状态只使用完整五段键。
  [`model-comparison-governance.md:256`](../../modules/amc_mta/docs/model-comparison-governance.md#L256)

- 使用说明锁定 51/3/51 行结构和五段摘要。
  [`usage.md:69`](../../modules/amc_mta/docs/usage.md#L69)

- 正式摘要产物仅保留三个五段 outcome。
  [`amc_mta_model_comparison_summary.csv:1`](../../modules/amc_mta/outputs/attribution/amc_mta_model_comparison_summary.csv#L1)

**契约回归**

- 端到端校验全行字段、五段键、互动类型和原因码。
  [`test_amc_mta_end_to_end.py:217`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L217)

- 单路径曝光与点击支持度始终独立计算。
  [`test_model_comparison.py:100`](../../modules/amc_mta/tests/test_model_comparison.py#L100)
