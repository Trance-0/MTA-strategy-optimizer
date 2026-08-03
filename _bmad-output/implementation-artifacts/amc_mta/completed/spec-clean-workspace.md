---
title: '全工作区清理与一致性修复'
type: 'chore'
created: '2026-07-16'
status: 'done'
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/README.md'
  - '{project-root}/modules/amc_mta/README.md'
  - '{project-root}/modules/mta/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 工作区包含 macOS 元数据、重复导航、过期实现记录、未开展阶段的占位目录和多处失效引用；同时 AMC MTA 缺少概念事件样例，导致默认流水线及 3 个端到端测试无法运行。

**Approach:** 以当前未提交工作区为唯一基线，删除可证明无效或被取代的内容，合并导航并修复文档；恢复确定性的 AMC 事件样例，使仓库结构、说明、代码入口和测试重新一致。

## Boundaries & Constraints

**Always:** 保留可运行源码、有效模块输入、当前五段归因实现、5 份契约定义的 AMC 输出、Product Brief/PRD/技术补充、外部研究原件和仍有效的完成规格；删除前检查引用，修改后同步所有入口文档。

**Ask First:** 只有发现需要删除外部研究原件、改变归因公式/阈值、移除任一正式输出契约、删除 `.agents`/`_bmad` 工具资产或改写原始业务数据语义时才暂停确认。

**Never:** 不清理 `.git/objects`，不重建 Git 历史，不移动 `src/`、`scripts/` 或模块入口，不把 Markov 与 Shapley 合并成平均值，不掩盖仍存在的模型证据限制。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 工作区卫生清理 | 系统元数据、重复导航、过期规格和纯占位目录存在 | 删除明确冗余项，主要内容由根 README 和分区 README 可达 | 仍有引用时先修复引用或保留文件 |
| AMC 完整流程 | 聚合路径存在但概念事件样例缺失 | 恢复确定性事件样例，重新生成的聚合路径与已存样例逐字段一致 | 无法精确复现时不覆盖正式样例 |
| 输出清理 | `outputs/attribution` 含当前 5 份契约输出 | 保留 5 份各司其职的输出，不保留额外临时/旧格式文件 | 发现非契约文件时确认无引用后删除 |
| 文档校验 | 文档包含旧路径、旧状态或矛盾描述 | 所有本地 Markdown 链接有效，运行说明与实际文件一致 | 外部历史报告中的快照描述不强行改写 |

</frozen-after-approval>

## Code Map

- `.gitignore` -- 工作区卫生和可追踪工作流产物规则。
- `README.md` -- 合并 `WORKSPACE.md` 的有效导航和维护约定。
- `WORKSPACE.md` -- 与根 README 重复，合并后删除。
- `modules/amc_mta/data/simulated/` -- 恢复缺失事件样例并验证三份输入闭环。
- `modules/amc_mta/{README.md,docs/,tests/}` -- AMC 输入输出与完整流程契约。
- `modules/mta/{README.md,docs/}` -- 修复不存在压缩包及原始/派生数据角色说明。
- `docs/` -- 修复 Amazon、研究目录和产品说明中的失效引用与矛盾表述。
- `design-artifacts/` -- 删除未开展阶段占位，修复并公开决策日志路径。
- `_bmad-output/implementation-artifacts/amc_mta/` -- 删除被取代或失效记录，保留有效实现证据。
- `log.md` -- 清除空日期段、修复断句并记录本轮整理。

## Tasks & Acceptance

**Execution:**
- [x] 清除 6 个 `.DS_Store`，扩充 `.gitignore` 的 Python、编辑器、临时文件规则，并允许追踪有价值的 BMad 说明/规格。
- [x] 将有效工作区导航合并到 `README.md` 后删除 `WORKSPACE.md`；删除 B–E 设计占位及空 planning/test 产物目录。
- [x] 删除已被五段全链路规格取代的旧互动粒度规格，以及未核验且被正式文档替代的调查记录；同步产物索引。
- [x] 将 `.decision-log.md` 改为可见的 `decision-log.md`，修复设计材料、研究文档、模块 README 和日志中的失效内容。
- [x] 恢复 `amc_touchpoint_events_sample.csv`，确保默认 AMC 流水线、路径重建和端到端测试闭环。
- [x] 重新生成或校验 5 份 AMC 输出，确认没有额外输出文件且推荐结果仍保持证据未验证的治理状态。

**Acceptance Criteria:**
- Given 整理后的工作区，when 扫描缓存、临时文件和纯占位目录，then 不再发现本规格列明的冗余项。
- Given 所有项目 Markdown，when 校验本地链接，then 不存在失效路径。
- Given AMC 模拟输入，when 运行完整流水线和测试，then 聚合路径可精确复现且 75 项 AMC 测试全部通过。
- Given 当前五份正式输出，when 执行严格数据对齐与输出检查，then 文件集合与配置契约一致，51 条推荐记录仍禁止自动预算。

## Spec Change Log

## Design Notes

`.agents` 与 `_bmad` 内的重复模板属于已安装工具包结构，不按业务文件重复项逐个删除。外部 PDF、DOCX、JSON 未发现内容重复，全部保留。AMC 五份输出分别承担模型原始结果、触点诊断、整体摘要和治理推荐，不视为重复。

## Verification

**Commands:**
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 75 项通过。
- `python3 modules/amc_mta/run_pipeline.py` -- expected: 完整流程成功发布契约内 5 份输出。
- `python3 modules/amc_mta/scripts/validate_data_alignment.py` -- expected: AMC 与 Ads 五段触点、窗口和覆盖一致。
- 本地 Markdown 链接检查、冗余文件扫描及 `git diff --check` -- expected: 全部通过。

## Suggested Review Order

**工作区结构**

- 从统一入口理解清理后的目录边界和内容导航。
  [`README.md:5`](../../../../README.md#L5)

- 设计目录只保留已经形成的产品决策材料。
  [`design-artifacts/README.md:1`](../../../../design-artifacts/README.md#L1)

- BMad 索引只展示有效规格与延期事项。
  [`README.md:1`](../README.md#L1)

**AMC 数据闭环**

- 概念事件夹具确定性复现现有匿名聚合路径。
  [`amc_touchpoint_events_sample.csv:1`](../../../../modules/amc_mta/data/simulated/amc_touchpoint_events_sample.csv#L1)

- 模块入口明确五份输出及其不可自动预算状态。
  [`README.md:16`](../../../../docs/zh/attribution/amc-mta-module.md#L16)

- 端到端测试逐字段验证存储路径可复现。
  [`test_amc_mta_end_to_end.py:64`](../../../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L64)

- 边界测试锁定精确14天和多购买不复用语义。
  [`test_amc_path_builder.py:84`](../../../../modules/amc_mta/tests/test_amc_path_builder.py#L84)

**治理与资料边界**

- 正式AMC输出可追踪，其他模块输出仍保持可再生。
  [`.gitignore:41`](../../../../.gitignore#L41)

- 决策日志同步当前campaign与AMC两类样例状态。
  [`decision-log.md:4`](../../../../design-artifacts/amc_mta/A-Product-Brief/decision-log.md#L4)

- 数据限制只在两类路径证据都缺失时降级。
  [`addendum.md:55`](../../../../design-artifacts/amc_mta/A-Product-Brief/addendum.md#L55)

- 研究资料与模块运行样例保持物理分区。
  [`README.md:9`](../../../../docs/research/README.md#L9)

**维护记录**

- 工作日志记录本轮清理和AMC样例恢复。
  [`log.md:8`](../../../../log.md#L8)

- 延期清单只保留仍未解决的工程与模型问题。
  [`deferred-work.md:1`](../deferred/deferred-work.md#L1)
