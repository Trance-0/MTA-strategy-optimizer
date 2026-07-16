---
title: '将项目整理为单一 AMC MTA 归因能力'
type: 'chore'
created: '2026-07-16'
status: 'done'
baseline_commit: '734ff73b4f2c3e841fedee33311a2eecf704d888'
context:
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
  - '{project-root}/modules/amc_mta/docs/model-comparison-governance.md'
  - '{project-root}/_bmad-output/implementation-artifacts/deferred-work.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 旧 `modules/mta` 已由用户主动删除，但主导航和早期产品文档仍把通用 MTA、预测、预算优化与 AI 问答描述为当前能力，导致唯一可运行的 AMC MTA 被过时范围稀释，也缺少完整现状评价。

**Approach:** 将 `modules/amc_mta` 确定为唯一正式实现，清除当前导航中的旧引用，将未实现平台内容标为历史愿景，并建立 AMC MTA 架构、能力评价和文档总索引。

## Boundaries & Constraints

**Always:** 不恢复 `modules/mta`；保留 AMC MTA 源码、三份输入、五份输出、75 项测试、研究原件和历史规格；明确区分已实现归因诊断、未验证稳定性、无因果增量和自动预算能力；主导航只把 `modules/amc_mta` 标为当前模块。

**Ask First:** 修改算法、治理阈值、五段粒度、路径窗口、输出契约，或删除外部 PDF/DOCX/JSON 原件。

**Never:** 不评价旧通用 MTA；不平均两个模型；不把样例当生产证据或把 Amazon Attribution 报告当 AMC 路径；不篡改冻结历史意图。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 当前入口 | 从 README 或索引进入 | 只把 AMC MTA 标为当前能力，可到达架构、评价、契约和运行说明 | 修复旧链接或标为历史 |
| 历史愿景 | PRD 等包含未实现能力 | 保留原文，但不再代表当前交付范围 | 不删除追溯内容 |
| 研究与输出 | 外部资料及五份 CSV | 按相关性分类，五份输出全部保留 | 不删除原件或契约输出 |

</frozen-after-approval>

## Code Map

- `README.md`, `modules/README.md`, `docs/README.md` -- 统一当前主导航。
- `data/README.md` -- 删除不再成立的共享数据占位。
- `design-artifacts/README.md`, `docs/product/` -- 将广义平台内容标为历史愿景。
- `docs/research/` -- 分类资料相关性并修复旧运行路径。
- `docs/index.md`, `docs/amc-mta-architecture.md`, `docs/amc-mta-capability-assessment.md` -- 新增当前事实源、架构与成熟度评价。
- `docs/project-scan-report.json`, `log.md` -- 完成全量扫描状态与整理记录。

## Tasks & Acceptance

**Execution:**
- [x] 主导航、产品入口和空共享数据占位 -- 统一为 AMC MTA 单模块口径。
- [x] 研究与历史资料索引 -- 保留原件并标注核心、辅助和背景。
- [x] 三份当前文档 -- 固化架构、能力边界、成熟度、风险和路线。
- [x] 扫描状态与日志 -- 记录整理范围和最终验证。

**Acceptance Criteria:**
- Given 整理后的工作区，when 查看当前导航，then 不再把旧 MTA 或预测/优化描述为可运行能力。
- Given 新开发者只阅读文档入口，when 理解项目，then 能明确五段输入、双模型、五份输出、证据阻断及主要风险。
- Given 默认样例，when 运行流水线、对齐和测试，then 75 项测试通过、17 个触点对齐、输出可复现且 51 条推荐无决策值。
- Given 全部 Markdown，when 校验本地链接，then 除冻结历史文字快照外无失效链接。

## Spec Change Log

## Design Notes

评价采用工程、方法、数据、决策四层成熟度。项目定位为“工程完整的 AMC MTA 归因与双模型诊断 Demo”，不是生产级因果归因或预算优化系统。研究原件不移动，只调整索引优先级。

## Verification

**Commands:**
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 75 tests pass.
- `python3 modules/amc_mta/run_pipeline.py` -- expected: 路径及五份归因产物发布成功。
- `python3 modules/amc_mta/scripts/validate_data_alignment.py` -- expected: 17 个触点与 61 天覆盖一致。
- `rg -n 'modules/mta' README.md modules docs design-artifacts` -- expected: 无当前能力引用，历史文字有明确标签。
- `git diff --check` -- expected: no whitespace errors.

## Suggested Review Order

**当前项目边界**

- 根入口先明确唯一正式能力及不可自动决策边界。
  [`README.md:3`](../../README.md#L3)

- 文档入口定义当前、研究和历史材料的权威层级。
  [`index.md:17`](../../docs/index.md#L17)

- 模块索引只保留 AMC MTA 运行入口。
  [`modules/README.md:7`](../../modules/README.md#L7)

**能力与方法评价**

- 总体评价区分 Demo 完成度和生产就绪度。
  [`amc-mta-capability-assessment.md:3`](../../docs/amc-mta-capability-assessment.md#L3)

- 样例结果明确绑定当前输入、运行命令和证据阻断。
  [`amc-mta-capability-assessment.md:62`](../../docs/amc-mta-capability-assessment.md#L62)

- 架构文档解释单模块数据流与真实 AMC 边界。
  [`amc-mta-architecture.md:3`](../../docs/amc-mta-architecture.md#L3)

- 模型语义区分 Markov removal 与 Path-level Shapley。
  [`amc-mta-architecture.md:76`](../../docs/amc-mta-architecture.md#L76)

**历史与研究分层**

- 研究原件按核心方法、平台、验证和背景分级。
  [`research/README.md:1`](../../docs/research/README.md#L1)

- 历史设计入口防止未实现平台愿景被误读。
  [`design-artifacts/README.md:3`](../../design-artifacts/README.md#L3)

**审计与验证**

- 扫描报告记录基线、工作区状态和复验命令。
  [`project-scan-report.json:13`](../../docs/project-scan-report.json#L13)
