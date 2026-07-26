---
title: 'AMC MTA 输入忽略字段首尾空格'
type: 'feature'
created: '2026-07-22'
status: 'done'
baseline_commit: '290b7df205a3495487cb797b979148ec19a57318'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** AMC MTA 的普通 CSV 读取已经会清除部分首尾空格，但严格 AMC/模型读取器会拒绝相同输入，导致 `(one    )` 与 `(one)` 在不同入口表现不一致。手工排版或导出工具附带的字段首尾空格不应改变输入语义。

**Approach:** 所有 CSV 输入统一对字段名和值执行首尾空白清理；字符串内部空格保持原样。清理后继续执行完整 schema、数值、集合和守恒校验，程序输出仍使用规范无首尾空格格式。

## Boundaries & Constraints

**Always:** 只使用 `strip()` 语义清除字段名和值两端的空白；普通、AMC 严格、Markov/Shapley 严格读取入口行为一致；清理后表头必须非空且唯一；多余列、缺失列和业务非法值仍然失败；正式输出物理表头和值保持规范格式。

**Ask First:** 若实现需要改变五份正式输出 schema、触点键内部语义、数值阈值或可靠性逻辑，必须先获得用户批准。

**Never:** 不删除字符串内部空格；不把内部空格不同的两个业务值强行合并；不静默接受清理后重名的字段；不修改现有样例数值或任何 `log` 文件。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 字段值首尾空格 | `" one    "` | 读取为 `"one"` | 不报错 |
| 表头首尾空格 | `" outcome "` | 识别为 `outcome` | 清理后按正式 schema 校验 |
| 内部空格 | `"one value"` | 保持 `"one value"` | 后续业务校验按原值处理 |
| 清理后字段重名 | `"one", " one "` | 不产生覆盖或歧义 | 明确抛出 `ValueError` |
| 多余或缺失列 | 行宽与表头不一致 | 不补列、不丢列 | 明确抛出 `ValueError` |
| 正式输出 | 任意合法输入 | 生成无首尾空格的规范 CSV | 原子发布规则保持不变 |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/amc_mta_attribution.py` -- 公共 CSV 读取、字段说明行过滤和规范 CSV 写入。
- `modules/amc_mta/src/model_comparison.py` -- AMC 聚合路径严格读取入口。
- `modules/amc_mta/scripts/compare_attribution_models.py` -- Markov/Shapley 严格读取入口。
- `modules/amc_mta/tests/test_model_comparison.py` -- 严格读取、异常列和模型比较测试。
- `modules/amc_mta/tests/test_amc_mta_end_to_end.py` -- 公共读取与正式物理输出测试。
- `modules/amc_mta/docs/` -- 输入容错与输出严格边界的用户说明。

## Tasks & Acceptance

**Execution:**
- [x] `modules/amc_mta/src/amc_mta_attribution.py` -- 提供统一的 CSV 表头/值首尾清理与字段冲突检查，供全部入口复用。
- [x] `modules/amc_mta/src/model_comparison.py`、`modules/amc_mta/scripts/compare_attribution_models.py` -- 严格读取器改用统一规范化结果，同时保留 schema、行宽和业务校验。
- [x] `modules/amc_mta/tests/` -- 将旧的“拒绝首尾空格”断言改为“接受并规范化”，增加内部空格、清理后重名和异常列测试。
- [x] `modules/amc_mta/docs/` -- 明确输入忽略首尾空格、内部空格保留、正式输出仍无首尾空格。

**Acceptance Criteria:**
- Given 合法 CSV 的字段名或字段值带首尾空格，when 通过任一 AMC MTA CSV 入口读取，then 得到与无首尾空格输入相同的规范值和计算结果。
- Given 两个字段名清理后相同，when 读取 CSV，then 在任何数据被模型使用前抛出明确错误。
- Given 字符串包含内部空格，when 读取 CSV，then 内部空格不被删除或折叠。
- Given 合法输入完成流水线，when 检查五份正式输出，then 表头、字段值、行数和数值结果仍精确符合现有契约。

## Spec Change Log

## Verification

**Commands:**
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'` -- 全部模块测试通过。
- 从临时复制的 `amc_mta/` 执行 `python3 -B run_pipeline.py` 和对齐校验 -- 独立包运行成功且正式输出保持规范。
- 对五份输出执行物理表头、行宽和首尾空白检查 -- 全部通过。

## Dev Agent Record

### Implementation Plan

- 先为普通、AMC 严格和模型严格读取器增加失败测试。
- 在公共归因模块实现一次性表头、行宽和值规范化，两个严格入口复用该结果。
- 保留规范化之后的 schema、数值、集合和守恒校验，在临时独立包验证正式输出。

### Completion Notes

- 新增 `read_csv_normalized`：仅使用 `strip()` 处理字段名和值的两端，拒绝空/重名表头和行宽异常。
- AMC 与 Markov/Shapley 严格读取器已统一复用规范化层，内部空格保留且后续业务契约不放宽。
- 106 项模块测试通过；临时独立包流水线、对齐检查、五份输出物理检查和加空白输入结果等价检查全部通过。
- 未读取或更改任何文件名含 `log` 的文件，未覆盖工作区既有 Markdown 变更。

## File List

- `_bmad-output/implementation-artifacts/amc_mta/completed/spec-tolerate-csv-edge-whitespace.md`
- `modules/amc_mta/src/amc_mta_attribution.py`
- `modules/amc_mta/src/model_comparison.py`
- `modules/amc_mta/scripts/compare_attribution_models.py`
- `modules/amc_mta/tests/test_model_comparison.py`
- `modules/amc_mta/tests/test_amc_mta_end_to_end.py`
- `modules/amc_mta/docs/amc-data-requirements.md`
- `modules/amc_mta/docs/usage.md`
- `modules/amc_mta/docs/model-comparison-governance.md`
- `modules/amc_mta/docs/touchpoint-reliability-guide.md`
- `modules/amc_mta/docs/amc-mta-complete-guide.md`

## Change Log

- 2026-07-22：统一 CSV 输入首尾空白容错，保留严格结构和业务校验，补齐测试与文档。

## Status

done

## Suggested Review Order

**统一输入规范化**

- 单一入口清理边缘空白并拒绝结构歧义及畸形 CSV。
  [`amc_mta_attribution.py:87`](../../../../modules/amc_mta/src/amc_mta_attribution.py#L87)

- AMC 严格入口复用规范化层后继续执行精确 schema 校验。
  [`model_comparison.py:128`](../../../../modules/amc_mta/src/model_comparison.py#L128)

- 双模型严格入口保持相同的规范化与完整契约。
  [`compare_attribution_models.py:40`](../../../../modules/amc_mta/scripts/compare_attribution_models.py#L40)

**行为边界与说明**

- 数据契约明确输入宽容、内部空格保留和输出严格。
  [`amc-data-requirements.md:7`](../../../../modules/amc_mta/docs/amc-data-requirements.md#L7)

- 使用说明解释比较入口不会修复其他非法数据。
  [`usage.md:62`](../../../../modules/amc_mta/docs/usage.md#L62)

**回归保护**

- 普通读取覆盖清理、内部空格、重名及异常行宽。
  [`test_amc_mta_end_to_end.py:202`](../../../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L202)

- 严格读取覆盖畸形引号、边缘空白和 schema 异常。
  [`test_model_comparison.py:668`](../../../../modules/amc_mta/tests/test_model_comparison.py#L668)
