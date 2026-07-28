# 工作区组件与资产清单

## 业务组件

| 组件 | 入口 | 责任 |
| --- | --- | --- |
| 五段触点键 | `modules/amc_mta/src/touchpoint_key.py` | 统一广告产品、形式、位置、创意、互动类型 |
| 路径构建 | `modules/amc_mta/src/amc_path_builder.py` | 将事件转为 AMC 风格匿名聚合路径 |
| 归因引擎 | `modules/amc_mta/src/amc_mta_attribution.py` | Markov、Shapley、成本和效率指标 |
| 模型治理 | `modules/amc_mta/src/model_comparison.py` | 五段支持度、差距、三项可靠性、整体指标和推荐状态 |
| 完整入口 | `modules/amc_mta/run_pipeline.py` | 重建输入派生物与五份输出 |
| 命令行脚本 | `modules/amc_mta/scripts/` | 分步生成、归因、比较与校验 |
| 测试 | `modules/amc_mta/tests/` | 106 项单元、契约和端到端验证 |
| Campaign Group 层级校验 | `modules/mta_strategy_recommender/src/hierarchy_validator.py` | 校验四个 Campaign、候选引用、合法 pairing 和预算守恒 |
| 初始策略样例 | `modules/mta_strategy_recommender/data/simulated/` | 展示 Group→Campaign→Ad Group→Keyword/SKU 与 `INITIAL_SEED` |

## 数据资产

| 类型 | 数量 | 位置 |
| --- | ---: | --- |
| 模拟输入 CSV | 3 | `modules/amc_mta/data/simulated/` |
| 正式输出 CSV | 5 | `modules/amc_mta/outputs/attribution/` |
| 策略初始化模拟文件 | 9 | `modules/mta_strategy_recommender/data/simulated/` |
| 外部 PDF | 7 | `docs/research/` |
| 外部 DOCX | 2 | `docs/research/amazon/research/` |
| Amazon Ads OpenAPI JSON | 1 | `docs/research/amazon/research/` |
| 研究说明与笔记 | 多份 | `docs/research/**` |

## 文档资产

- 当前项目入口与评价：`docs/index.md`、`docs/project-overview.md`。
- 文件位置与移动规则：`docs/workspace-file-management.md`。
- 当前业务架构与契约：`docs/amc_mta/`、`modules/amc_mta/docs/`。
- AMC MTA 历史产品愿景：`design-artifacts/amc_mta/A-Product-Brief/`。
- 已完成实现规格：`_bmad-output/implementation-artifacts/amc_mta/`。
- 全量机器清单：`docs/workspace-file-inventory.json`。
- 研究分级与原件索引：`docs/research/README.md` 及各子目录 `README.md`。

## Agent/BMad 组件

| 模块 | 版本/渠道 | 主要作用 |
| --- | --- | --- |
| Core | 6.8.0 | 通用审查、索引、规格、协作 |
| BMM | 6.8.0 | 产品、架构、开发、文档工作流 |
| TEA | v1.19.0 | 测试架构与质量治理 |
| BMB | v2.0.0 | Agent、工作流和模块构建 |
| Automator | main/next | Story 自动化 |
| CIS | v0.2.1 | 创意与问题解决 |
| GDS | v0.6.0 | 游戏开发工作流 |
| WDS | v0.4.3 | Web/UX 设计工作流 |

注册清单包含 119 个技能，`.agents/skills/` 也包含 119 个一级技能目录，名称完全
对应。安装目录另含一个嵌套 setup skill 模板，因此全局共有 120 个 `SKILL.md`。

## 代码与可执行文件

- Python：94 个，语法检查全部通过。
- JavaScript：7 个，Node.js 语法检查全部通过。
- Bash：1 个 Story Automator 入口，`bash -n` 通过。
- Git 可执行文件：15 个，均位于安装工具脚本区域。
- AMC MTA 业务代码没有第三方 Python 依赖。

## 重复文件解释

全工作区有 127 组按 SHA-256 完全相同的文件，共涉及 621 个文件。大部分位于
`bmad-tea` 与各 `bmad-testarch-*` 技能的 `resources/knowledge/` 中。每个技能
复制所需知识以便独立加载和分发，因此：

- 不删除；
- 不改成符号链接；
- 不移动到业务文档目录；
- 只有在升级或重新打包 BMad 模块时统一处理。
