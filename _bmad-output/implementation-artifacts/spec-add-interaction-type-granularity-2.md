---
title: 'AMC MTA 全链路升级为五段互动粒度'
type: 'feature'
created: '2026-07-14'
status: 'done'
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前 AMC 路径和互动明细虽已使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 五段键，但 Amazon Ads 输入、数据对齐、成本聚合、主归因产物、文档与测试仍保留四段基础键，导致最终内容仍表现为四粒度。

**Approach:** 将 AMC MTA 全链路统一为五段粒度，`INTERACTION_TYPE` 仅允许 `IMPRESSION` 或 `CLICK`。Amazon Ads 指标也按五段行输入和关联；CPC 成本唯一归属 `CLICK`，CPM 成本唯一归属 `IMPRESSION`，不再将归因结果降维到四段。

## Boundaries & Constraints

**Always:** 五段键严格为 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`；Ads 行必须提供互动类型和 `cost_type=CPC|CPM`；CPC 行只能是 `CLICK`，CPM 行只能是 `IMPRESSION`；同一笔成本只出现一次；非计费互动行成本为 0；平台购买量、销售额和售出件数归 `CLICK`；Markov/Shapley 的购买用户、订单次数、收入归因分别守恒；现有 14 天路径、报告起点、多购买不复用及账户/日期/币种边界保持不变。

**Ask First:** 若真实上游无法提供五段 Ads 行或 `cost_type`，或需采用 CPC/CPM 之外的成本类型、改变平台转化指标归属、保留四段兼容产物，必须先征求用户确认。

**Never:** 不复制四段成本到曝光与点击两行；不按归因结果反向分摊成本；不从 Ads 汇总曝光/点击数反推 AMC 用户路径；不静默接受缺失、未知或与计费类型冲突的互动类型；不继续输出四段归因或成本结果。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| CPC 广告 | `interaction_type=CLICK,cost_type=CPC` | 五段 CLICK 行保留点击、成本及平台转化指标 | N/A |
| CPM 广告 | `interaction_type=IMPRESSION,cost_type=CPM` | 五段 IMPRESSION 行保留曝光和成本；平台转化指标为 0 | N/A |
| 非计费互动 | 同一基础广告存在另一互动类型 | 五段行可参与归因，但成本为 0；CLICK 可承载平台转化指标 | N/A |
| 计费冲突 | CPC+IMPRESSION 或 CPM+CLICK | 不进入聚合、对齐或归因输出 | 明确指出行号和字段冲突 |
| 五段对齐 | AMC 与 Ads 互动集合或逐日覆盖不同 | 拒绝运行 | 报告缺失和额外五段键 |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/touchpoint_key.py` -- 五段 AMC/Ads 键的唯一构造和严格校验入口。
- `modules/amc_mta/src/amc_path_builder.py` -- 已按互动类型构造五段有序路径，需保持现有窗口语义。
- `modules/amc_mta/src/amc_mta_attribution.py` -- Ads 五段指标聚合、模型结果舍入、成本关联及效率指标。
- `modules/amc_mta/scripts/validate_data_alignment.py` -- 按完整五段键校验集合与逐日覆盖。
- `modules/amc_mta/scripts/run_amc_attribution.py`、`modules/amc_mta/run_pipeline.py`、`modules/amc_mta/config.py` -- 仅发布每模型一份五段主结果。
- `modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py`、`modules/amc_mta/data/simulated/` -- 生成 CPC/CPM 唯一成本归属的五段样例并同步 ZIP。
- `modules/amc_mta/tests/`、`modules/amc_mta/docs/`、`modules/amc_mta/README.md` -- 全量迁移契约、用法与回归断言。

## Tasks & Acceptance

**Execution:**
- [x] `src/touchpoint_key.py`、Ads 聚合与对齐脚本 -- 删除五转四投影依赖，要求 Ads 完整五段键、互动类型及计费类型一致。
- [x] `src/amc_mta_attribution.py` -- 将五段模型结果直接关联五段 Ads 指标，按全局守恒舍入并拒绝四段结果。
- [x] 运行脚本、配置与流水线 -- 合并互动/成本双层产物，每个模型仅输出一份包含 `interaction_type`、成本和效率指标的五段结果。
- [x] 模拟生成器与数据 -- 按 CPC/CLICK、CPM/IMPRESSION 生成唯一计费行，补充非计费互动行且不复制成本，重建输出与归档。
- [x] 测试与全部相关文档 -- 移除四段契约，覆盖合法、冲突、零成本、五段对齐和端到端守恒。

**Acceptance Criteria:**
- Given 默认样例，when 运行完整流水线，then 路径、Ads 输入、Markov 与 Shapley 主产物中的每个触点均为严格五段键且不再生成四段结果。
- Given CPC 与 CPM 混合数据，when 聚合成本，then CPC 成本只出现在 CLICK 行、CPM 成本只出现在 IMPRESSION 行，输出总成本与输入总成本一致。
- Given 同一基础广告同时出现曝光和点击，when 归因，then 两类互动分别获得贡献且不会因共享前四段而合并。
- Given 五段结果，when 检查三个 outcome 与效率指标，then 归因值分别守恒，零成本行的 ROAS/ROI 为空且成本不会重复。

## Spec Change Log

## Design Notes

Amazon Ads 输入不再把一条四段汇总记录复制成两条。模拟数据按计费类型创建唯一成本行：CPC 对应 CLICK，CPM 对应 IMPRESSION；若需要另一互动类型参与 AMC 归因，则使用成本为 0 的独立五段 Ads 行满足对齐。平台购买、销售与售出件数只落在 CLICK 行，避免跨互动重复。

## Verification

**Commands:**
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'` -- 全部单元与端到端测试通过。
- `python3 modules/amc_mta/run_pipeline.py` -- 生成五段路径及两份五段模型结果。
- `python3 modules/amc_mta/scripts/validate_data_alignment.py` -- 完整五段集合、账户、窗口、币种和逐日覆盖通过。
- `unzip -t modules/amc_mta/data/simulated.zip` -- 归档完整且包含最新五段样例。

## Suggested Review Order

**五段主流程**

- 入口直接关联五段归因与五段 Ads 指标，仅发布两份结果。
  [`run_amc_attribution.py:55`](../../modules/amc_mta/scripts/run_amc_attribution.py#L55)

- 成本结果严格保留互动类型并正确处理零成本效率指标。
  [`amc_mta_attribution.py:650`](../../modules/amc_mta/src/amc_mta_attribution.py#L650)

**计费与键约束**

- Ads 键要求完整第五段并核验存储键一致性。
  [`touchpoint_key.py:83`](../../modules/amc_mta/src/touchpoint_key.py#L83)

- CPC/CLICK 与 CPM/IMPRESSION 无条件匹配，阻止零成本冲突。
  [`amc_mta_attribution.py:551`](../../modules/amc_mta/src/amc_mta_attribution.py#L551)

- 完整五段集合与逐日覆盖直接对齐，不再降维。
  [`validate_data_alignment.py:72`](../../modules/amc_mta/scripts/validate_data_alignment.py#L72)

**样例与发布验证**

- 样例按互动类型写入唯一计费类型与成本归属。
  [`generate_simulated_amazon_ads_report.py:102`](../../modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py#L102)

- 流水线只认 Markov、Shapley 两份五段主产物。
  [`run_pipeline.py:103`](../../modules/amc_mta/run_pipeline.py#L103)

- 端到端验证五段输出、成本唯一性与守恒。
  [`test_amc_mta_end_to_end.py:36`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L36)
