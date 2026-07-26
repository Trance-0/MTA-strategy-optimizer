---
title: '在 AMC 推荐输出中增加最终推荐值'
type: 'feature'
created: '2026-07-22'
status: 'done'
baseline_commit: 'b05a57a24559992dbe9210fcb1a932c6be1ef8f4'
context:
  - '{project-root}/modules/amc_mta/docs/model-comparison-governance.md'
  - '{project-root}/modules/amc_mta/docs/touchpoint-reliability-guide.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 推荐表同时展示 Markov official 和 Shapley benchmark，但使用者仍需自行根据可靠性判断采用单点还是区间。

**Approach:** 在推荐表增加 `recommended_value`：可靠时直接给 Markov `official_share`，不可靠时给两个模型 share 构成的升序闭区间。

## Boundaries & Constraints

**Always:** `RELIABLE` 行输出 official 单点；`UNRELIABLE` 行输出 `[min(markov_share,shapley_share),max(...)]`，使用无空格格式。outcome 总量为零时没有可解释分布，保持空值；非零 outcome 的两个 share 都为零时允许 `[0.0,0.0]`。仅推荐表从 14 列变为 15 列，其余表 schema 不变。可靠性三项标准、Markov official 身份及现有精度不变。

**Ask First:** 改 official 模型、用置信区间替代模型区间、增加第二个类型字段、把该字段加入其他输出或改变区间文本格式。

**Never:** 不用区间掩盖计算无效原因；不把 zero outcome 伪装为零归因；不改变模型、门槛、行数或已有字段；不读取、哈希、移动或修改 `log.md`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 可信归因 | `RELIABLE` 且 outcome 非零 | `recommended_value=official_share` | N/A |
| 不可信归因 | `UNRELIABLE` 且 outcome 非零 | 输出两个 share 的升序闭区间 | N/A |
| 模型顺序反转 | Shapley 高于 Markov | 区间仍先小后大 | N/A |
| 零 outcome | 没有可解释 share 分布 | `recommended_value` 为空 | N/A |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/model_comparison.py` -- 推荐 schema 与逐行构建逻辑。
- `modules/amc_mta/tests/test_model_comparison.py` -- 单点、区间、排序和零 outcome 契约。
- `modules/amc_mta/tests/test_amc_mta_end_to_end.py` -- 正式 CSV schema 与值一致性。
- `modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv` -- 15 列正式产物。
- 当前 README、数据契约和治理文档 -- 推荐字段说明。

## Tasks & Acceptance

**Execution:**
- [x] `model_comparison.py` -- 添加 `recommended_value` 并集中实现单点/区间/空值选择。
- [x] `tests/` -- 覆盖 reliable、unreliable、反向区间、退化区间、zero outcome 和精确 schema。
- [x] 推荐 CSV -- 通过正式流水线重建，不手工编辑派生值。
- [x] 当前文档与工作区清单 -- 同步 15 列契约和字段解释；历史完成规格不改写。

**Acceptance Criteria:**
- Given 任意推荐行，when 检查可靠性与 outcome，then `recommended_value` 严格符合单点、区间或空值规则。
- Given 完整流水线，when 生成推荐表，then 保持 51 行且只有推荐表新增一列。
- Given 当前全年样例全部可靠，when 重建输出，then 51 行 `recommended_value` 均等于 `official_share`。

## Spec Change Log

## Design Notes

`recommended_value` 是 CSV 文本联合类型：单点沿用现有数字格式，区间格式固定为 `[low,high]`。`reliability_status` 已承担类型判别，无需增加重复字段。

## Verification

实际结果：100/100 测试通过；推荐表保持 51 行并变为 15 列；当前 51 行
`recommended_value` 均等于 `official_share`；流水线双跑哈希、数据对齐和清单校验通过。

**Commands:**
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 全部通过。
- `python3 -B modules/amc_mta/run_pipeline.py` -- expected: 推荐表 51 行、15 列并可重复生成。
- schema、字段语义、文档、清单与 `git diff --check` -- expected: 0 failures。

## Suggested Review Order

**推荐值生成**

- 推荐 schema 只增加一个最终值字段。
  [`model_comparison.py:82`](../../../../modules/amc_mta/src/model_comparison.py#L82)

- 可靠单点、模型区间和空值在一个函数中统一选择。
  [`model_comparison.py:478`](../../../../modules/amc_mta/src/model_comparison.py#L478)

- 推荐行复用已有 share 与可靠性，不改变模型计算。
  [`model_comparison.py:677`](../../../../modules/amc_mta/src/model_comparison.py#L677)

**边界验证**

- 不可靠正反区间及真实 CSV 回读锁定文本契约。
  [`test_model_comparison.py:345`](../../../../modules/amc_mta/tests/test_model_comparison.py#L345)

- 全年正式输出验证 51 个可靠值等于 official。
  [`test_amc_mta_end_to_end.py:371`](../../../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L371)

**使用说明**

- 治理规范定义 15 列顺序和三种推荐值形态。
  [`model-comparison-governance.md:71`](../../../../modules/amc_mta/docs/model-comparison-governance.md#L71)

- 使用文档解释如何按可靠性读取单点或区间。
  [`usage.md:109`](../../../../modules/amc_mta/docs/usage.md#L109)
