---
title: '为 AMC 路径样例增加中文字段注释行'
type: 'feature'
created: '2026-07-14'
status: 'done'
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 第一份 Amazon Ads 样例 CSV 在英文表头下提供中文字段说明，而第二份 `amc_mta_path_report_raw_sample.csv` 直接进入数据行，阅读体验不一致。

**Approach:** 为 AMC 路径样例增加同式中文字段说明行，并让通用 CSV 读取逻辑可靠识别、跳过两类样例的说明行，确保归因与对齐不把注释当数据。

## Boundaries & Constraints

**Always:** 英文字段名继续作为第一行机器表头；中文说明固定为第二行；所有字段说明非空且列数、顺序与表头完全一致；流水线重建路径样例后仍保留说明行；读取结果不包含说明行；现有五段路径、归因和成本规则不变。

**Ask First:** 若需要为第三份事件级样例或模型输出也增加说明行，需先确认范围。

**Never:** 不用伪造合法日期或数值的方式隐藏说明行；不依赖只匹配 `报告日期` 的单一硬编码；不改变路径数据字段、类型或业务值。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 人工查看 | 打开路径样例 CSV | 第一行英文表头，第二行中文说明，第三行开始为数据 | N/A |
| 程序读取 | CSV 含中文说明行 | `read_csv` 自动跳过说明，仅返回业务数据 | N/A |
| 流水线重建 | 运行 `run_pipeline.py` | 发布后的路径样例仍含说明行且归因成功 | N/A |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/scripts/build_amc_path_report.py` -- 生成并写出路径样例，应插入中文字段说明。
- `modules/amc_mta/src/amc_mta_attribution.py` -- 通用 CSV 读取入口，应识别两种说明行。
- `modules/amc_mta/data/simulated/amc_mta_path_report_raw_sample.csv` -- 第二份待注释样例。
- `modules/amc_mta/tests/test_amc_mta_end_to_end.py` -- 验证物理第二行与读取/流水线行为。
- `modules/amc_mta/data/simulated.zip` -- 需同步更新归档。

## Tasks & Acceptance

**Execution:**
- [x] `scripts/build_amc_path_report.py` -- 定义与表头同序的中文说明并随路径结果写出。
- [x] `src/amc_mta_attribution.py` -- 将说明行识别从单一文案扩展为明确、可复用的规则。
- [x] 测试、样例和 ZIP -- 覆盖说明行格式、解析跳过和流水线重建一致性。

**Acceptance Criteria:**
- Given 默认路径事件样例，when 运行完整流水线，then 路径 CSV 第二行包含九项非空中文说明且模型结果不变。
- Given Ads 和 AMC 路径两种带说明 CSV，when 使用 `read_csv`，then 两者均只返回业务数据行。

## Spec Change Log

- 2026-07-14: 实施完成；增加路径字段说明、通用说明行识别、回归测试，并重建样例与归档。

## Verification

**Commands:**
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'` -- 全部测试通过。
- `python3 modules/amc_mta/run_pipeline.py` -- 路径说明行保留且两模型输出成功。
- `unzip -t modules/amc_mta/data/simulated.zip` -- 归档完整并包含最新路径样例。

## Suggested Review Order

**注释生成与读取**

- 路径生成入口固定把九项说明写在业务数据之前。
  [`build_amc_path_report.py:27`](../../modules/amc_mta/scripts/build_amc_path_report.py#L27)

- 两套说明定义集中管理，避免生成与解析发生漂移。
  [`amc_mta_attribution.py:22`](../../modules/amc_mta/src/amc_mta_attribution.py#L22)

- 只精确匹配完整说明行，避免误删中文业务数据。
  [`amc_mta_attribution.py:83`](../../modules/amc_mta/src/amc_mta_attribution.py#L83)

**回归保护**

- 验证流水线重建后第二行说明仍可正确跳过。
  [`test_amc_mta_end_to_end.py:76`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L76)

- 验证任意全中文合法数据不会被错误过滤。
  [`test_amc_mta_end_to_end.py:90`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L90)

**Results (2026-07-14):**
- 单元测试：56/56 通过。
- 完整流水线：成功，路径样例与 Markov、Shapley 输出均已发布。
- ZIP 完整性：通过，归档内路径样例第二行为九项中文说明。
