---
title: '整理 AMC MTA Markdown 提交包'
type: 'chore'
created: '2026-07-22'
status: 'done'
baseline_commit: '9f600c0531b704d9abde4ff23705ded2743e9fcf'
context:
  - '{project-root}/docs/workspace-file-management.md'
  - '{project-root}/modules/amc_mta/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** AMC MTA 已可完整运行，但模块说明分散，五份输出缺少统一阅读入口，历史设计产物和 BMad 实施规格的目录职责也不够直观，不利于形成可审阅、可演示、可追溯的提交包。

**Approach:** 以 `modules/amc_mta` 作为唯一核心提交物，保持运行路径和 CSV 契约不变；新增一份中文 Markdown 总使用说明、输出索引和提交清单，并把设计附件与实施档案整理为有明确状态和入口的辅助材料。

## Boundaries & Constraints

**Always:** 只生成 Markdown 文档；保持 AMC MTA 源码、脚本、测试、数据和五份正式输出的现有路径及内容；移动辅助文档后同步更新有效链接；保留全部完成规格；明确 `official` 是项目正式展示口径、`RELIABLE` 不是因果有效；最终运行 100 项模块测试并校验 Markdown 链接。

**Ask First:** 删除任何普通文件，修改模型算法、可靠性阈值、CSV schema、模拟数据或正式输出，或者发现目录移动会影响外部工具路径。

**Never:** 不生成 `.docx`；不把 `_bmad-output` 当成运行依赖或核心提交物；不把历史预算优化愿景描述为当前能力；不读取、哈希、移动、格式化或修改任何 `log` 文件；不运行会覆盖正式 CSV 的流水线。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 正常提交 | 当前 AMC 模块、设计产物和完成规格 | 核心提交入口、完整使用说明、输出索引、提交清单和辅助材料索引全部可达 | 不适用 |
| 历史愿景 | 设计文档包含预测、预算优化和 AI 问答 | 保留追溯价值并醒目标记未实现，不混入当前能力 | 发现冲突时以 AMC 当前契约为准 |
| 受保护文件 | 任意 `log` 文件存在或有用户改动 | 完全排除在扫描、补丁、移动和验证目标外 | 立即跳过，不尝试读取或修复 |
| 路径迁移 | 辅助 Markdown 移入分类目录 | 所有非冻结有效文档链接更新，冻结历史规格保持原文并由索引解释时效性 | 链接检查失败则不完成任务 |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/README.md` -- 核心提交入口和快速运行。
- `modules/amc_mta/docs/` -- 当前模型事实源与新增完整使用说明。
- `modules/amc_mta/outputs/attribution/` -- 五份正式输出。
- `modules/amc_mta/SUBMISSION_MANIFEST.md` -- 必交、选交、不提交内容及验收状态。
- `design-artifacts/` -- 历史产品愿景和设计追溯附件。
- `_bmad-output/implementation-artifacts/` -- 已完成规格与延期事项。

## Tasks & Acceptance

**Execution:**
- [x] `modules/amc_mta/docs/amc-mta-complete-guide.md` -- 汇总范围、数据、路径、模型、指标、可靠性、输出、运行、错误、Demo、限制和后续验证。
- [x] `modules/amc_mta/{README.md,docs/README.md,SUBMISSION_MANIFEST.md}` -- 建立简洁入口、文档导航和提交边界。
- [x] `modules/amc_mta/docs/output-reference.md` -- 说明五份 CSV 的用途、顺序、主键、字段和解释限制，并避开输出目录忽略规则。
- [x] `design-artifacts/{README.md,A-Product-Brief/}` -- 保持 WDS 固定产品材料路径，由 README 原位分类并维持历史愿景标签。
- [x] `_bmad-output/{README.md,implementation-artifacts/README.md}` -- 保持规格与延期正文原位，在 README 中分类并刷新索引。
- [x] 全局有效索引和链接 -- 更新受目录调整影响的非冻结 Markdown 引用，不改冻结完成规格正文。

**Acceptance Criteria:**
- Given 提交审阅者从 `modules/amc_mta/README.md` 进入，when 按导航阅读，then 可找到完整使用说明、五份输出说明、运行命令、测试方法、Demo流程、模型边界和提交清单。
- Given 新 AMC 与 Ads 数据放入既定输入位置，when 按总说明运行，then 文档明确无需修改日期配置且六份派生产物只在整组校验成功后发布。
- Given 辅助目录整理完成，when 检查职责，then `modules/amc_mta` 是唯一核心提交物，`design-artifacts` 是可选设计附件，`_bmad-output` 是不随核心包提交的过程档案。
- Given 最终文件树，when 执行测试和链接检查，then 100 项测试通过、有效 Markdown 零断链、正式 CSV 未被重写且所有 `log` 文件未被触碰。

## Spec Change Log

- 2026-07-22：完成核心提交入口、完整指南、五份输出索引和提交清单。
- 2026-07-22：采用现有 README 原位分组，保留已配置的历史产品目录、冻结规格和延期正文路径。
- 2026-07-22：对 42 个有效 Markdown 的 210 个相对链接执行检查，排除冻结规格和受保护路径，结果零断链。
- 2026-07-22：运行 100 项模块测试，99 项通过；可复现性测试发现已存 Shapley 正式输出多一行异常记录。因正式 CSV 属于冻结区，本次不修复，规格保持 `in-review`。
- 2026-07-22：用户删除异常尾行后重新验证，100 项测试全部通过；完整指南加入最终数据流 Mermaid 流程图。
- 2026-07-22：最终审阅明确区分 Demo 六产物与真实 AMC 五结果发布，并恢复两份曾被视觉对齐的 CSV 至批准基线的严格物理契约；所有业务值保持不变。

## Design Notes

辅助目录允许移动 Markdown 以改善分类，但核心运行目录不移动。冻结的历史完成规格可能保留旧相对路径；实现产物索引必须说明其快照属性，避免为修链接而改写已批准意图。

实现时确认历史产品目录被现有工具配置引用，且实现产物正文具有稳定历史链接；
因此使用现有 README 内的 `product`、`completed`、`deferred` 分组表达职责，
不创建迁移目录，也不物理移动正文。

## Verification

**Commands:**
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'` -- expected: 100 tests pass，且不写入正式输出。
- Markdown 相对链接检查 -- expected: 排除历史冻结规格和所有 `log` 文件后零断链。
- 定向文件清单与 CSV 元数据检查 -- expected: 目录职责正确，五份正式输出路径、行数和内容保持不变。

## Suggested Review Order

**核心提交入口**

- 从唯一提交入口理解范围、运行方式和材料导航。
  [`README.md:1`](../../modules/amc_mta/README.md#L1)

- 核对核心、选交和不提交内容及最终验收状态。
  [`SUBMISSION_MANIFEST.md:1`](../../modules/amc_mta/SUBMISSION_MANIFEST.md#L1)

**数据流与结果解释**

- 查看 Demo、真实 AMC、双模型、可靠性和发布边界。
  [`amc-mta-complete-guide.md:30`](../../modules/amc_mta/docs/amc-mta-complete-guide.md#L30)

- 按正确顺序理解五份输出及字段限制。
  [`output-reference.md:1`](../../modules/amc_mta/docs/output-reference.md#L1)

**辅助材料边界**

- 确认历史产品愿景不冒充当前实现。
  [`design-artifacts/README.md:1`](../../design-artifacts/README.md#L1)

- 检查完成规格、当前整理和延期事项导航。
  [`implementation-artifacts/README.md:1`](README.md#L1)

- 查看本轮审阅发现但不阻塞提交的模型边界。
  [`deferred-work.md:15`](deferred-work.md#L15)
