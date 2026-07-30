---
title: '整理工作区并统一预算模型当前入口'
type: 'chore'
created: '2026-07-30'
status: 'done'
baseline_commit: '7d521578b131447dc67a1daf6f1f13551e6089b8'
context:
  - '{project-root}/docs/workspace-file-management.md'
  - '{project-root}/modules/mta_strategy_recommender/docs/output-data-contract.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前业务代码已经实现 MTA 驱动的新 Ad Group 数量与预算生成，但根入口、架构、开发指南、现行业务层级文档和扫描报告仍混有旧的“只校验、分配具体 Keyword/SKU、19/28 项测试”话术；正式结果只放在测试 fixture，也导致输出位置不直观。工作区还保留四个 ignored `.DS_Store`。

**Approach:** 删除明确缓存，将策略预算结果迁到正式 `outputs/` 路径，统一包导入和当前文档，同时保留研究、安装工具、历史愿景和冻结规格作为追溯材料。

## Boundaries & Constraints

**Always:** `log.md` 与 `docs/系统架构图-07.drawio` 只原样纳入 Git，不读取或修改内容；`modules/amc_mta` 只读；当前事实统一描述为“一个 Campaign Group 服务一个平台、固定四个 Campaign、各自一个 SP/SB/SD/DSP、模型只推荐新组数量和预算”；刷新机器清单并复跑全部业务测试。

**Ask First:** 删除或移动除四个 `.DS_Store` 与预算输出 fixture 迁移之外的文件；修改 MTA/预算公式、输入数据、输出数值、Campaign 数量、候选容量或历史规格正文；处理安装工具测试缺口。

**Never:** 不删除 `.agents`、`_bmad`、研究原件、设计产物或已完成规格；不把旧规格问题陈述当作当前残留回写；不增加 Keyword/SKU/Match Type/Target/Audience 分配；不做 Decimal/币种舍入、优化或自动投放；不自动 push。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 正式预算结果 | 当前确定性生成结果在测试 fixture | 原样迁到 `modules/mta_strategy_recommender/outputs/initial_budget_recommendation.json`，CLI 和校验器默认使用该路径 | 生成结果不一致时失败 |
| CLI 兼容 | 历史命令使用 `--check-fixture` | 新文档使用 `--check-output`，旧参数作为兼容别名继续可用 | 未知参数失败 |
| 包与脚本导入 | 包导入或直接运行 CLI | 两种方式都能加载预算生成器与校验器 | 导入测试失败即阻断 |
| 保留资产 | 两个用户文件已有未提交内容 | 字节不变并纳入 Git | 任何内容变化立即阻断 |
| 历史旧话术 | 冻结规格含 `2/2/1/1` 等旧口径 | 历史正文保留，索引标明已被 budget-only v4 取代 | 当前入口仍宣称旧能力则失败 |

</frozen-after-approval>

## Code Map

- `.gitignore` -- 白名单保留策略模块的一份正式预算结果。
- `modules/mta_strategy_recommender/scripts/*.py` -- 正式输出路径、兼容 CLI 与包导入入口。
- `modules/mta_strategy_recommender/src/*.py` -- 可作为包或脚本依赖加载的预算实现。
- `modules/mta_strategy_recommender/tests/` -- 正式结果一致性、CLI 与包导入回归。
- `README.md`、`docs/*.md`、`docs/research/campaign-data-hierarchy.md` -- 当前能力、目录、层级与验证基线。
- `_bmad-output/{README.md,implementation-artifacts/README.md}` -- 当前与历史规格导航。
- `docs/project-scan-report.json`、`docs/workspace-file-inventory.json` -- 整理后的机器状态。

## Tasks & Acceptance

**Execution:**
- [x] 删除四个已确认的 `.DS_Store`；不清理安装骨架、历史区或研究资产。
- [x] 将确定性预算 JSON 从测试 fixture 迁到正式 `outputs/`，更新 `.gitignore`、CLI、校验器与测试引用，并保留旧 CLI 参数兼容。
- [x] 统一 `src` 包导入，使 package import 与两个 CLI 均可运行。
- [x] 修正根入口、当前 docs、现行业务层级文档、模块索引和 BMad 索引；历史规格正文不变。
- [x] 更新测试数字、扫描状态和全量文件清单；把两个用户文件原样加入 Git。

**Acceptance Criteria:**
- Given 整理后的工作区，when 从根入口阅读或运行推荐命令，then 能直接找到正式预算输出，当前文档不再宣称模型分配具体候选或尚未实现生成器。
- Given 当前模型输入，when 生成和校验，then 输出数值、`1/1/1/1`、17 触点、34 实体行与整理前完全一致。
- Given 两个保留资产，when 比较整理前后字节，then 内容不变且均被 Git 跟踪。
- Given 完整验证，when 运行策略 34 项与 AMC 107 项测试、包导入、CLI、链接和 inventory 校验，then 全部通过且 AMC 相对基线零变化。

## Spec Change Log

## Design Notes

正式输出与测试期望使用同一份提交文件，避免 `outputs/` 与 fixture 维护两份相同 JSON。历史参数只作为 CLI 别名保留，不继续出现在当前文档。浮点精度属于模型输出契约的后续议题，本轮保证字节与数值不变。

## Verification

**Commands:**
- `python3 -B modules/mta_strategy_recommender/scripts/generate_initial_budget.py --check-output`
- `python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py`
- `python3 -B -c 'import modules.mta_strategy_recommender.src.hierarchy_validator'`
- `python3 -B -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'`
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'`
- `git diff --exit-code 7907b101 -- modules/amc_mta`
- `git diff --check -- . ':(exclude)log.md' ':(exclude)docs/系统架构图-07.drawio'`

## Suggested Review Order

**当前入口与正式输出**

- 根入口直接呈现已实现的预算初始化能力。
  [`README.md:1`](../../README.md#L1)

- 模块说明统一正式结果、运行命令与兼容边界。
  [`mta_strategy_recommender/README.md:15`](../../modules/mta_strategy_recommender/README.md#L15)

- 唯一正式 JSON 同时承担确定性测试基准。
  [`initial_budget_recommendation.json:1`](../../modules/mta_strategy_recommender/outputs/initial_budget_recommendation.json#L1)

**生成与兼容**

- CLI 用字节级比较保护正式输出并兼容旧参数。
  [`generate_initial_budget.py:23`](../../modules/mta_strategy_recommender/scripts/generate_initial_budget.py#L23)

- 包相对导入支持 CLI 与标准 package import。
  [`hierarchy_validator.py:10`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L10)

- 回归同时覆盖新旧命令、模型边界和正式结果。
  [`test_hierarchy_validator.py:73`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L73)

**业务口径与工作区状态**

- 现行层级明确候选计数与具体实体分配的边界。
  [`campaign-data-hierarchy.md:85`](../../docs/research/campaign-data-hierarchy.md#L85)

- 主索引区分当前能力、研究资料和历史规格。
  [`index.md:19`](../../docs/index.md#L19)

- 扫描报告记录双基线、清理结果与验证证据。
  [`project-scan-report.json:7`](../../docs/project-scan-report.json#L7)
