---
title: '整理并建立工作区文件位置治理'
type: 'chore'
created: '2026-07-20'
status: 'done'
baseline_commit: '2c00f19fa640bb65d7ccf99714f11f912904a85a'
context:
  - '{project-root}/docs/source-tree-analysis.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 工作区主体结构稳定，但新增 AMC 指南未完整入索引，清单与扫描报告已过期，少量历史/研究文档的位置和入口命名不能准确表达职责。

**Approach:** 保持三层顶级结构，只整理审计确认的文档位置与命名；建立位置规则、补齐导航，最后重建机器清单和扫描报告。

## Boundaries & Constraints

**Always:** 保留现有未提交内容；`log.md` 原位且字节不变，不打开、不格式化、不重新哈希；保持 `.agents/`、`_bmad/`、`_bmad-output/`、`docs/.archive/` 及 AMC 运行结构；研究原件只做内容不变的更名；移动后同步更新全部路径、索引和清单。

**Ask First:** 删除普通文件，修改算法、输入或五份正式输出，改变工具配置路径，或移动规格外文件。

**Never:** 不删除研究、历史设计、完成规格或安装内容；不触碰 `.git`；不移动 AMC 运行路径；不运行会覆盖 CSV 的流水线；不修改冻结规格正文。

</frozen-after-approval>

## Code Map

- `docs/workspace-file-management.md` -- 位置与变更规则。
- `{README.md,docs/index.md,docs/README.md}` -- 工作区导航。
- `docs/product/`, `design-artifacts/` -- 当前事实与历史愿景边界。
- `docs/research/` -- 研究入口、命名和原件索引。
- `modules/amc_mta/docs/README.md` -- 模块文档索引。
- `docs/{project-overview.md,source-tree-analysis.md,component-inventory.md,architecture.md,workspace-file-inventory.json,project-scan-report.json}` -- 最终结构及派生状态。

## Tasks & Acceptance

**Execution:**
- [x] `docs/workspace-file-management.md` -- 定义分区、稳定路径、命名、归档、移动流程及 `log.md` no-touch 规则。
- [x] `docs/product/model-relationship-guide.md` → `design-artifacts/amc_mta/A-Product-Brief/model-relationship-guide.md` -- 历史愿景归位并修复引用。
- [x] `docs/research/{mta,ab-testing}/阅读顺序.md` → 各自 `README.md` -- 规范入口并链接原件。
- [x] MTA Shapley PDF -- 将文件名 `Methodsfor` 修正为 `Methods for`，保持二进制内容不变。
- [x] `docs/research/amazon/research/README.md` -- 索引该层六份原件并接入上级入口。
- [x] 模块与全局索引 -- 登记触点可靠性指南，确保所有非规格项目 Markdown 从根入口可达。
- [x] 工作区说明和两个 JSON 派生文件 -- 按最终树刷新职责、计数与基线；清单明确排除 `.git`、自身、ignored 个人配置及 `log.md` 内容哈希。

**Acceptance Criteria:**
- Given 最终工作区，when 清单与磁盘对账，then 除声明的排除项外，路径、大小、权限和 SHA-256 零差异。
- Given 根入口，when 检查项目自有 Markdown，then 零断链且所有非历史规格文档可达。
- Given 内容不应变化的研究原件（本次为 Shapley PDF），when 比较移动/更名前后摘要，then 内容完全相同；研究入口 Markdown 按任务要求增强导航。
- Given `log.md` 和现有 AMC 未提交变更，when 检查最终状态，then `log.md` 从未成为 patch/move/hash 目标，原有改动保留，四份 CSV 未被重写。
- Given 最终顶层树，when 按治理规则分类，then 每个文件有唯一职责区且无新增缓存、临时文件、空文件或符号链接。

## Spec Change Log

- 2026-07-20：完成已批准的文件归位、导航治理、派生清单刷新和全部验证。

## Design Notes

`docs/.archive/` 是 BMad 固定归档位置。ignored 的 `_bmad/custom/config.user.toml` 不移动、不提交。冻结规格内的旧路径只在实现产物索引说明时效性。

## Verification

**Commands:**
- `git status --short` 与定向 diff -- expected: 只有规格内变化及原有改动。
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 75 tests passed，且不生成字节码缓存。
- Markdown 链接与可达性检查 -- expected: 0 broken links，0 unintended orphans。
- JSON 解析及清单对账 -- expected: 0 mismatches；`log.md` 只用前后 `stat` 元数据确认本任务未触碰。
- task-scoped `git diff --check`（排除受保护 `log.md`、四份既有格式化 CSV 与迁移文档中原有的 Markdown 硬换行）并检查新编写文本 -- expected: 本任务新增内容无空白错误。

## Suggested Review Order

**位置治理与保护边界**

- 先确认所有文件的唯一职责区与稳定路径。
  [`workspace-file-management.md:7`](../../../../docs/workspace-file-management.md#L7)

- 再检查移动、归档与 `log.md` no-touch 流程。
  [`workspace-file-management.md:47`](../../../../docs/workspace-file-management.md#L47)

**导航与资料归位**

- 从总索引核对治理、可靠性与历史愿景入口。
  [`index.md:18`](../../../../docs/index.md#L18)

- 检查历史模型说明是否准确隔离当前能力。
  [`model-relationship-guide.md:1`](../../../../design-artifacts/amc_mta/A-Product-Brief/model-relationship-guide.md#L1)

- 检查 MTA、A/B 与 Amazon 原件的目录入口。
  [`README.md:1`](../../../../docs/research/mta/README.md#L1)
  [`README.md:1`](../../../../docs/research/ab-testing/README.md#L1)
  [`research/README.md:1`](../../../../docs/research/amazon/research/README.md#L1)

- 确认模块索引已登记触点可靠性指南。
  [`docs/README.md:1`](../../../../docs/zh/attribution/reference-index.md#L1)

**派生状态与后续风险**

- 核对最终规模、验证结论和分区评价。
  [`project-overview.md:24`](../../../../docs/project-overview.md#L24)

- 核对扫描范围、排除项和验证命令。
  [`project-scan-report.json:1`](../../../../docs/project-scan-report.json#L1)

- 最后查看未擅自修改的既有 AMC 问题。
  [`deferred-work.md:20`](../deferred/deferred-work.md#L20)
