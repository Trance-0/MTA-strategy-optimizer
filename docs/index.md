# 全工作区文档总索引

本索引覆盖整个工作区：当前业务实现、项目知识、研究原件、历史产物以及本地
Agent/BMad 工具链。当前业务链路由
[`modules/amc_mta`](../modules/amc_mta/README.md) 和
[`modules/mta_strategy_recommender`](../modules/mta_strategy_recommender/README.md)
组成；`.agents` 和 `_bmad` 是开发工具，不是营销产品功能。

## 推荐阅读顺序

1. [工作区总览与现状评价](project-overview.md)：查看全范围结论、健康度与风险。
2. [目录结构分析](source-tree-analysis.md)：理解所有顶层目录和边界。
3. [工作区文件位置管理](workspace-file-management.md)：新增、移动和归档文件。
4. [工作区级架构](architecture.md)：理解业务、知识和工具三层关系。
5. [组件与资产清单](component-inventory.md)：查看代码、数据、研究和技能资产。
6. [开发与验证指南](development-guide.md)：运行项目并复现验证。
7. [AMC MTA 能力评价](amc_mta/amc-mta-capability-assessment.md)：深入判断归因能力。

## 当前入口与权威层级

| 主题 | 推荐入口 |
| --- | --- |
| 全工作区现状 | [工作区总览与现状评价](project-overview.md) |
| 全量逐文件清单 | [工作区文件清单](workspace-file-inventory.json) |
| 顶层架构与分区 | [工作区级架构](architecture.md) |
| 用户维护的系统架构图 | [Draw.io 源文件](系统架构图-07.drawio) |
| 文件位置与移动规则 | [工作区文件位置管理](workspace-file-management.md) |
| 可运行模块与命令 | [`modules/amc_mta/README.md`](../modules/amc_mta/README.md) |
| Campaign Group 初始策略 | [策略初始化器](../modules/mta_strategy_recommender/README.md) |
| 初始策略计划与契约 | [整体模型计划](../modules/mta_strategy_recommender/docs/model-plan.md) |
| 输入字段、路径和成本规则 | [AMC MTA 数据契约](../modules/amc_mta/docs/amc-data-requirements.md) |
| Markov/Shapley 差距与决策状态 | [模型比较治理规范](../modules/amc_mta/docs/model-comparison-governance.md) |
| 单触点结果可靠性 | [触点可靠性指南](../modules/amc_mta/docs/touchpoint-reliability-guide.md) |
| 代码结构与数据流 | [AMC MTA 架构](amc_mta/amc-mta-architecture.md) |
| 项目成熟度与后续优先级 | [AMC MTA 能力评价](amc_mta/amc-mta-capability-assessment.md) |
| Campaign Group 数据层级 | [Campaign Group 顶层数据关系与最细效果粒度](research/campaign-data-hierarchy.md) |
| 尚未解决的 AMC MTA 技术问题 | [延期事项](../_bmad-output/implementation-artifacts/amc_mta/deferred/deferred-work.md) |

权威优先级为：运行代码与测试 → 模块数据/治理契约 → 可再生产物 → 本目录的架构与
能力评价 → 项目介绍 → 研究笔记 → 历史产品文档。架构与评价是从代码和产物派生的
当前说明，不替代源码契约。

## 工作区分区

```text
.
├── .agents/           # 119 个安装技能
├── _bmad/             # BMad 配置、清单与共享工具
├── _bmad-output/      # 已完成规格和延期事项
├── design-artifacts/  # 历史产品愿景
├── docs/              # 当前知识、研究和全量扫描结果
└── modules/           # AMC MTA + Campaign Group 初始策略模块

modules/amc_mta/
├── src/       # 路径键、路径构建、归因和模型比较
├── scripts/   # 独立命令行入口
├── tests/     # 107项自动化测试
├── data/      # 一份模拟事实源及四类派生数据
├── outputs/   # 五份正式、可再生 CSV
└── docs/      # 当前模块契约与使用说明

modules/mta_strategy_recommender/
├── data/      # strategy_request + candidate_pool 两个输入
├── outputs/   # 唯一正式初始预算 JSON
├── src/       # 数量/预算生成与跨模块校验
├── scripts/   # 生成和校验 CLI
├── tests/     # 合同、兼容与边界测试
└── docs/      # 模型计划与输出契约

docs/
├── index.md
├── amc_mta/          # AMC MTA 工作区架构与能力评价
├── workspace-file-management.md
├── product/   # 当前项目介绍
└── research/  # 外部研究原件，不是运行输入
```

完整注释见[目录结构分析](source-tree-analysis.md)。

## 内容状态

- **当前**：本索引、架构、能力评价、[产品文档状态](product/README.md)、
  AMC MTA 项目介绍及模块文档。
- **研究支撑**：`docs/research/mta/`、`docs/research/amazon/`。
- **后续验证**：`docs/research/ab-testing/`。
- **背景资料**：ontology、industry。
- **历史愿景**：`design-artifacts/`，包括
  [模型功能与关系说明](../design-artifacts/amc_mta/A-Product-Brief/model-relationship-guide.md)。
- **历史实现记录**：`_bmad-output/implementation-artifacts/`；冻结规格记录当时意图，
  不自动代表当前能力。
- **安装工具**：`.agents` 与 `_bmad`；保持安装结构，不按业务重复文件清理。

## 当前验证基线

截至 2026-07-30，基于统一用户事件主表及其四类派生数据，并运行
`python3 modules/amc_mta/run_pipeline.py` 的确定性输出：

- 107 项 AMC MTA 测试通过，策略初始化模块另有34项预算模型测试；
- 17 个五段触点与 Amazon Ads 报告完全对齐；
- 报告窗口为 2026-01-01 至 2026-03-31，共90天逐日覆盖；
- 主表有11,147条事件、2,400个合成用户和3,547个journey；
- 三项 AMC outcome 总量为920个购买用户、1,023次购买、87,802.83收入；
- 五份归因产物可确定性复现；
- 三份双模型产物的可靠性结果为 `51 RELIABLE / 0 UNRELIABLE`；
- 51 条推荐记录均为 `RELIABLE`；推荐表只保存正式/参照 share、差距和可靠性。

这些数字证明样例流水线的一致性，不证明真实投放中的模型有效性或因果增量。

全工作区另已确认：119个技能注册与安装目录一致、108个Python和7个
JavaScript 文件语法通过、项目自有 Markdown 无本地断链。工具层已知限制见
[工作区总览](project-overview.md)。
