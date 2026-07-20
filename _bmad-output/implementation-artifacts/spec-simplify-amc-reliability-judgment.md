---
title: '简化 AMC MTA 可靠性判断并写入输出'
type: 'feature'
created: '2026-07-20'
status: 'done'
baseline_commit: '1000bcc06086acac99680997ac5abbece0c621b1'
context:
  - '{project-root}/modules/amc_mta/docs/model-comparison-governance.md'
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前可靠性说明混入稳定性、差距等级和跨 outcome 条件，正式 CSV 又未直接给出可靠与否。

**Approach:** 只保留“计算有效、数据支撑充分、模型一致”三个布尔判断，以 AND 生成状态和原因并写入三份双模型产物。

## Boundaries & Constraints

**Always:** `calculation_valid` 表示严格输入、集合、守恒和效率校验通过；失败继续 fail-fast。`data_support_sufficient` 要求购买次数 `>=30`、购买用户 `>=20`、唯一路径 `>=5` 同时满足。`models_consistent` 要求非零 outcome 且 `gap_pp<=1.0`、`relative_gap<=0.20`，不受 LONG_TAIL 分类顺序影响。三项全真为 `RELIABLE`，否则 `UNRELIABLE`；原因按 `CALCULATION_INVALID|INSUFFICIENT_DATA_SUPPORT|MODELS_INCONSISTENT` 排序，全通过为 `ALL_CRITERIA_PASSED`。布尔值写小写。

**Ask First:** 修改门槛、增加第四项、删除既有字段、改变模型主从关系或开放自动预算。

**Never:** 不用稳定性、跨 outcome、重要性、关键分歧或高/中/低等级决定可靠性；不平均模型；不把可靠等同因果或自动决策；不触碰 `log.md`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 三项通过 | 校验、支持、模型差距均通过 | `RELIABLE` + `ALL_CRITERIA_PASSED` | N/A |
| 多项失败 | 支持不足且模型超界 | `UNRELIABLE`，固定顺序连接失败原因 | N/A |
| 长尾一致 | 非零长尾且两个差距门槛通过 | `models_consistent=true` | N/A |
| 零 outcome | 两模型合法全零 | 计算有效，但支持与一致性为 false | 最终不可靠 |
| 非法计算 | 非有限、错位或不守恒 | 不发布新输出 | `ValueError`，保留旧产物 |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/model_comparison.py` -- 判断、原因与三份 CSV schema 的单一来源。
- `modules/amc_mta/tests/` -- 阈值、真值表、零 outcome、表头和样例回归。
- `modules/amc_mta/outputs/attribution/` -- 流水线重建的五份正式输出。
- `modules/amc_mta/README.md`, `modules/amc_mta/docs/` -- 可靠性契约和解释边界。
- `docs/{workspace-file-inventory.json,project-scan-report.json}` -- 工作区派生状态。

## Tasks & Acceptance

**Execution:**
- [x] `modules/amc_mta/src/model_comparison.py` -- 实现三项判断、原因组合，并向触点/摘要/推荐 schema 追加五个字段；旧字段保留但不参与可靠性。
- [x] `modules/amc_mta/tests/` -- 覆盖真值、门槛、长尾、零 outcome、字段透传和样例。
- [x] `modules/amc_mta/outputs/attribution/` -- 原子重建五份 CSV；新字段只进入三份双模型产物。
- [x] AMC MTA 当前文档 -- 重写指南并同步 README、usage、数据契约和治理 schema。
- [x] 派生状态与延期说明 -- 标记旧多级规则被取代，刷新扫描报告和清单。

**Acceptance Criteria:**
- Given 任一非零触点/outcome，when 查看三份比较产物，then 五个字段规则一致，推荐与触点行一致，单模型表不含这些字段。
- Given 支持值正好为 `30/20/5`，when 判断数据支撑，then 结果为 true；任一项低于门槛则为 false。
- Given 非零长尾触点两模型份额相同，when 判断一致性，then 为 true；任一门槛超界则为 false。
- Given 当前 17×3 样例，when 重建输出，then 51 行计算有效、3 行支持通过但模型不一致，最终 `0 RELIABLE / 51 UNRELIABLE`；三行摘要均不可靠。
- Given 当前指南，when 查看判断步骤，then 仅有三个标准和二元状态，无高/中/低或稳定性/跨 outcome 门槛。
- Given 非法输入或发布失败，when 执行比较，then 不发布无效结果或部分更新。

## Spec Change Log

- 2026-07-20：完成三项二元可靠性实现、五份输出重建、当前文档同步和全量验证。
- 2026-07-20（审查第 2 轮）：验收反例发现摘要复用旧 `comparison_status`
  会在触点差距超界时仍输出 `models_consistent=true`。已将摘要规则修正为对该
  outcome 的触点级三个基础布尔值分别执行 AND 聚合，避免 TVD、排名、Top-K、
  关键分歧或支持等级进入可靠性。已知错误状态是“触点不可靠但摘要可靠”；
  KEEP：保留已批准的触点门槛、固定原因顺序、零 outcome、五字段输出范围、
  fail-fast 和当前样例 `0/51` 结论。
- 2026-07-20（审查第 2 轮完成）：摘要已改为逐字段 AND 触点布尔值；门槛改用
  十进制精确比较且没有 epsilon；补齐整体诊断反例、Spearman 未定义反例、
  nextafter/精确边界和 AMC 非法日期不发布测试，并重新通过全部验证。
- 2026-07-20（审查第 2 轮边界补丁）：模型解析保留未舍入原始字符串/Decimal
  share 供一致性门槛判断；NaN、无穷和负差距安全返回 false；内部辅助值不进入
  任何正式 schema。

## Design Notes

可靠性只评价当前窗口三项标准；`stability_level`、`decision_status`、
`automation_allowed`、`support_status` 和 `comparison_status` 都是独立诊断或治理
字段。摘要对同一 outcome 的触点级 `calculation_valid`、
`data_support_sufficient`、`models_consistent` 分别执行 AND 聚合，再使用同一个
三项 AND 公式生成状态与原因；零 outcome 仍按冻结矩阵处理。

## Verification

**Commands:**
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 全部测试通过且不产生缓存。
- `python3 modules/amc_mta/run_pipeline.py` -- expected: 原子重建五份 CSV，三份比较产物含可靠性结果。
- `python3 modules/amc_mta/scripts/validate_data_alignment.py` -- expected: 17 个五段触点、61 天和账户/币种范围一致。
- 严格表头、行数、计数和确定性检查 -- expected: 51/3/51 行，`0/51` 可靠，无首尾空白。
- Markdown 链接、工作区清单对账和 `git diff --check`（排除 `log.md`）-- expected: 0 failures。

**Results:** 审查第 2 轮修正完成。86 项测试全部通过；原始文本 share 在显示舍入
为边界值但实际微量超界时，触点、摘要和推荐均保持 `UNRELIABLE`，内部 Decimal
辅助键未进入输出。流水线连续两次生成的 6 份
产物 SHA-256 完全一致；数据对齐为 17 个触点、61 天、单一账户币种范围；严格
CSV 检查确认 17/17/51/3/51 行、摘要与触点布尔 AND 一致、`0/51` 为可靠；41 份
当前项目 Markdown 全部可达，0 断链、0 孤儿；工作区清单按声明排除项刷新并完成
双向对账。全过程未读取、哈希、移动或修改 `log.md`。

## Suggested Review Order

**三项可靠性契约**

- 从统一合成函数理解三项 AND、状态和固定原因顺序。
  [`model_comparison.py:541`](../../modules/amc_mta/src/model_comparison.py#L541)

- 核对最低数据门槛与严格十进制模型一致性门槛。
  [`model_comparison.py:490`](../../modules/amc_mta/src/model_comparison.py#L490)

- 查看触点判断及摘要逐字段 AND 的完整数据流。
  [`model_comparison.py:721`](../../modules/amc_mta/src/model_comparison.py#L721)

**输出契约**

- 确认五个字段只追加到三份双模型 schema。
  [`model_comparison.py:49`](../../modules/amc_mta/src/model_comparison.py#L49)

- 查看业务说明、零 outcome 和结果文件边界。
  [`touchpoint-reliability-guide.md:14`](../../modules/amc_mta/docs/touchpoint-reliability-guide.md#L14)

- 核对旧治理指标与可靠性判断的隔离规则。
  [`model-comparison-governance.md:208`](../../modules/amc_mta/docs/model-comparison-governance.md#L208)

**边界与回归**

- 覆盖精确门槛、非法数值和固定原因真值表。
  [`test_model_comparison.py:166`](../../modules/amc_mta/tests/test_model_comparison.py#L166)

- 复现旧摘要误判并验证逐触点 AND 修正。
  [`test_model_comparison.py:366`](../../modules/amc_mta/tests/test_model_comparison.py#L366)

- 验证原始十进制微超界不会被 float 吞掉。
  [`test_model_comparison.py:451`](../../modules/amc_mta/tests/test_model_comparison.py#L451)

- 端到端确认正式 CSV、透传、重建与原子保护。
  [`test_amc_mta_end_to_end.py:157`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L157)
