---
title: '从 AMC MTA 全链路删除售出件数字段'
type: 'refactor'
created: '2026-07-14'
status: 'done'
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `unitsSold` / `units_sold` 不参与 Markov、Shapley、ROI、ROAS 或 CPA 计算，却仍存在于事件样例、Ads 输入、内部聚合、主结果、文档和测试中，增加数据契约与使用者理解成本。

**Approach:** 从 AMC MTA 全链路删除售出件数字段，只保留实际参与归因、成本或效率分析的字段；重新生成样例与产物，并证明归因结果及效率指标不受影响。

## Boundaries & Constraints

**Always:** 同时删除 camelCase `unitsSold` 与 snake_case `units_sold`；更新中文说明行且列数、顺序与机器表头一致；AMC 路径三项 outcome、五段触点、CPC/CPM 成本规则、ROI/ROAS/CPA 公式与结果保持不变；重建样例、两份模型输出和 ZIP。

**Ask First:** 若发现其他不参与计算的字段也应删除，或外部兼容性要求必须保留售出件数，先征求用户确认。

**Never:** 不用空列或固定 0 代替删除；不把售出件数并入 `purchase_count`；不改变 `purchases`、`purchase_count`、`sales`、`revenue` 的现有语义。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| AMC 事件样例 | 原表含 `units_sold` | 新表头、说明与业务行均不再包含该列 | N/A |
| Ads 样例 | 原表含 `unitsSold` | 新表头、中文说明与业务行均不再包含该列 | N/A |
| 模型输出 | 原结果含 `units_sold` | Markov/Shapley 输出删除该列，其余指标不变 | N/A |
| 外部旧输入 | 仍额外携带售出件数 | 核心计算忽略该非契约字段，不重新输出 | N/A |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/amc_path_builder.py` -- 移除事件转换对 `units_sold` 的读取和校验依赖。
- `modules/amc_mta/src/amc_mta_attribution.py` -- 移除 Ads 说明、Spend 数据结构、聚合和结果序列化字段。
- `modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py` -- 删除 Ads 样例字段及生成逻辑。
- `modules/amc_mta/scripts/run_amc_attribution.py` -- 删除模型输出列。
- `modules/amc_mta/data/simulated/`、`modules/amc_mta/outputs/` -- 重建输入、路径和结果产物。
- `modules/amc_mta/tests/`、`modules/amc_mta/docs/`、项目说明 -- 清理契约及回归断言。

## Tasks & Acceptance

**Execution:**
- [x] AMC 事件处理与样例 -- 删除 `units_sold` 输入列、读取和验证依赖。
- [x] Ads 聚合、生成器与样例 -- 删除 `unitsSold` 契约、内部状态和平台指标限制分支。
- [x] 模型输出与流水线产物 -- 删除 `units_sold` 列并保持所有计算值不变。
- [x] 文档、测试与 ZIP -- 全库清理字段引用，验证重建一致性和归因守恒。

**Acceptance Criteria:**
- Given 完成整改，when 扫描 `modules/amc_mta` 运行代码、CSV、文档和测试，then 不再出现 `unitsSold` 或 `units_sold`。
- Given 默认样例，when 运行完整流水线，then 57 项既有行为及新增删除断言通过，Markov/Shapley 三项归因总量和效率指标保持不变。
- Given 更新后的 CSV，when 检查英文表头与中文说明，then 列数和顺序完全一致且无售出件数列。

## Spec Change Log

- 2026-07-14：按批准规格完成实现；删除事件、Ads、内部聚合和模型输出字段，重建样例、结果与 ZIP，进入审查。

## Verification

**Commands:**
- `rg -n 'unitsSold|units_sold' modules/amc_mta` -- 无运行代码、数据、文档或测试残留。
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'` -- 全部测试通过。
- `python3 modules/amc_mta/run_pipeline.py` -- 路径与两份模型结果成功重建。
- `unzip -t modules/amc_mta/data/simulated.zip` -- 归档完整且包含最新无冗余字段样例。

**Results (2026-07-14):**

- 字段扫描无残留；ZIP 内样例扫描同样无残留。
- 58/58 单元测试通过，完整流水线成功。
- Markov/Shapley 均为 17 行，三项归因总量分别为 `1826`、`2044`、`226628.00`；成本均为 `338944.15`。
- Ads 英文表头与中文说明均为 17 列且顺序一致；ZIP 完整性检查通过。

## Suggested Review Order

**输入与内部模型**

- Ads 聚合状态只保留实际参与报表和效率分析的指标。
  [`amc_mta_attribution.py:588`](../../modules/amc_mta/src/amc_mta_attribution.py#L588)

- 事件路径仅校验三项归因 outcome，不再读取售出件数。
  [`amc_path_builder.py:154`](../../modules/amc_mta/src/amc_path_builder.py#L154)

- Ads 模拟输入表头与说明同步移除冗余列。
  [`generate_simulated_amazon_ads_report.py:18`](../../modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py#L18)

**输出与回归保护**

- 主结果字段列表删除冗余列，计算字段保持原序。
  [`run_amc_attribution.py:72`](../../modules/amc_mta/scripts/run_amc_attribution.py#L72)

- 结果序列化继续使用原归因、成本和效率计算。
  [`amc_mta_attribution.py:682`](../../modules/amc_mta/src/amc_mta_attribution.py#L682)

- 公共 CSV schema 显式阻止已删除字段回归。
  [`test_amc_mta_end_to_end.py:38`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L38)
