---
title: '精简 AMC MTA 模型比较输出字段'
type: 'refactor'
created: '2026-07-21'
status: 'done'
baseline_commit: 'b9a8527aafcf87d8ff038cf671241a0b6a19adf8'
context:
  - '{project-root}/modules/amc_mta/docs/model-comparison-governance.md'
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 三份双模型 CSV 在新增三项可靠性判断后仍保留大量空列、可推导列、单模型重复数据及旧稳定性/自动决策治理字段，导致最终结果宽而且语义重复。

**Approach:** 保持 Markov、Shapley 两份单模型输出不变，将触点比较、摘要和推荐结果分别精简为可靠性判断所需的模型差距、原始支持证据、必要上下文和五个最终判断字段。

## Boundaries & Constraints

**Always:** 三份文件继续保持 `51 / 3 / 51` 行；可靠性仍只由 `calculation_valid`、`data_support_sufficient`、`models_consistent` 三项 AND 生成 `reliability_status` 和 `reliability_reason`。数据门槛、Decimal 模型一致性门槛、零 outcome、fail-fast、原子发布及当前 `0 RELIABLE / 51 UNRELIABLE` 结果不变。推荐表继续明确 Markov 为正式展示口径、Shapley 为参照。

**Ask First:** 修改可靠性门槛、改变 Markov/Shapley 主从关系、改文件名或行粒度、删除用于三项判断的原始证据、改变两份单模型 schema。

**Never:** 不保留整列空值、可由保留列直接推导的辅助字段、单模型性能/效率重复字段，或 `stability/status/decision/review/automation/reason_code` 旧治理字段；不让 TVD、Spearman、Top-K 或旧等级进入可靠性判断；不读取、哈希、移动或修改 `log.md`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 当前样例 | 17 触点 × 3 outcome | 三份精简文件为 51/3/51 行且保持 0/51 可靠 | N/A |
| 零 outcome | 两模型合法全零 | 五个可靠性字段按既有零 outcome 规则输出 | N/A |
| 非法模型/AMC 输入 | 错列、非有限、不守恒或发布失败 | 不发布新旧 schema 混合文件 | `ValueError`，恢复整组旧产物 |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/model_comparison.py` -- 三个公开 schema、触点/摘要/推荐行构造及旧诊断辅助逻辑。
- `modules/amc_mta/scripts/{run_amc_attribution.py,compare_attribution_models.py}` -- 三份精简产物的原子发布入口。
- `modules/amc_mta/tests/` -- schema、阈值、零 outcome、确定性和回滚覆盖。
- `modules/amc_mta/outputs/attribution/` -- 需要重建的三份双模型 CSV。
- `modules/amc_mta/docs/`, `docs/` -- 当前字段契约、架构、能力说明和派生清单。

## Tasks & Acceptance

**Execution:**
- [x] `modules/amc_mta/src/model_comparison.py` -- 将触点比较精简为 14 列：`touchpoint,outcome,markov_share,shapley_share,gap_pp,relative_gap,raw_unique_paths,raw_converted_users,raw_purchase_count,calculation_valid,data_support_sufficient,models_consistent,reliability_status,reliability_reason`；删除旧治理构造、无效 `reference_window_days` 参数及差距 helper 的未使用返回值。
- [x] `modules/amc_mta/src/model_comparison.py` -- 将摘要精简为 13 列：`outcome,report_start_date,report_end_date,max_touchpoint_gap_days,touchpoint_count,tvd,spearman_rho,top_k_overlap_rate` 加五个可靠性字段；整体指标只作证据展示。
- [x] `modules/amc_mta/src/model_comparison.py` -- 将推荐结果精简为 14 列：`touchpoint,interaction_type,outcome,official_model,official_share,benchmark_model,benchmark_share,gap_pp,relative_gap` 加五个可靠性字段；零 outcome 的 `official_share` 保持为空。
- [x] `modules/amc_mta/tests/` -- 更新精确表头与透传断言，增加禁用字段、零 outcome 空正式 share、阈值、Decimal 边界、fail-fast 和回滚覆盖。
- [x] 输出、全部当前文档与派生状态 -- 原子重建三份 CSV，同步根 README、产品/架构/治理文档并刷新扫描报告和工作区清单；不改写已完成历史规格。

**Acceptance Criteria:**
- Given 任一当前双模型产物，when 检查表头，then 精确等于 14/13/14 列契约且不存在旧治理、空占位或单模型重复字段。
- Given 同一非零 `touchpoint + outcome`，when 对照触点和推荐结果，then share、差距及五个可靠性字段一致；零 outcome 的推荐 `official_share` 为空且五个可靠性字段仍一致。
- Given 当前样例与边界夹具，when 运行完整 pipeline 和独立比较，then 两入口逐字节一致、连续运行确定，仍为 51/3/51 行及 `0/51` 可靠。
- Given 非法输入或发布中断，when 生成精简产物，then 不留下部分更新或新旧 schema 混合文件。

## Spec Change Log

- 2026-07-21（审查第 1 轮）：盲审发现非冻结验收把所有 outcome 的 share 透传
  写成同一规则，诱发零 outcome 的 `official_share` 从既有空值回归为 `0.0`。
  已为验收和测试增加非零限定及零 outcome 空值规则，并把无效窗口参数、差距 helper
  死返回值和全部当前文档同步纳入任务。避免已知错误状态“合法无 outcome 被展示为可消费
  的正式零份额”。KEEP：14/13/14 schema、18/18 单模型、三项可靠性算法、Decimal
  门槛、51/3/51、0/51、输入校验、原子回滚及确定性均须保留。

## Design Notes

本规格取代上一份可靠性规格中“旧字段保留但不参与可靠性”的输出策略，但不改变其三项判断算法。`_SHARED_PERFORMANCE_FIELDS` 和 `_EFFICIENCY_FIELDS` 即使不再写入比较表，仍可保留用于输入一致性校验。推荐文件名暂不改变，以避免路径级兼容破坏。

## Verification

**Commands:**
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 全部测试通过且不产生缓存。
- `python3 modules/amc_mta/run_pipeline.py` 与独立比较入口 -- expected: 两次运行字节稳定，三份文件精确匹配新 schema。
- `python3 modules/amc_mta/scripts/validate_data_alignment.py` -- expected: 17 个触点、61 天和账户/币种范围不变。
- 严格表头/禁用字段/计数/可靠性/清单检查与 `git diff --check`（排除 `log.md`）-- expected: 0 failures。

## Suggested Review Order

**输出契约**

- 从三个公开 schema 掌握 14/13/14 精简边界。
  [`model_comparison.py:49`](../../../../modules/amc_mta/src/model_comparison.py#L49)

- 查看触点、摘要和推荐结果如何共用三项可靠性。
  [`model_comparison.py:562`](../../../../modules/amc_mta/src/model_comparison.py#L562)

**零 outcome 与模型角色**

- 真实 outcome 总量决定正式 share 是否为空。
  [`model_comparison.py:584`](../../../../modules/amc_mta/src/model_comparison.py#L584)

- 混合夹具保护非零 outcome 的合法零份额。
  [`test_model_comparison.py:615`](../../../../modules/amc_mta/tests/test_model_comparison.py#L615)

**禁用字段与端到端保护**

- 负向契约阻止旧治理字段重新进入 schema。
  [`test_model_comparison.py:240`](../../../../modules/amc_mta/tests/test_model_comparison.py#L240)

- 完整流水线校验正式三文件不含重复字段。
  [`test_amc_mta_end_to_end.py:299`](../../../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L299)

**当前事实源**

- 治理说明集中记录精简字段和解释边界。
  [`model-comparison-governance.md:59`](../../../../docs/zh/attribution/model-governance.md#L59)

- 使用说明给出三份正式结果的消费方式。
  [`usage.md:70`](../../../../docs/zh/environment/amc-mta-usage.md#L70)
