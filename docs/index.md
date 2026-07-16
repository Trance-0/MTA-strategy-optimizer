# AMC MTA 当前文档总索引

本索引是工作区当前事实的统一入口。项目只有一个正式业务实现：
[`modules/amc_mta`](../modules/amc_mta/README.md)。旧通用 MTA 已由用户主动
删除；预测、预算优化、Dashboard、实验平台和 AI 问答仅存在于历史愿景文档，
不是当前能力。

## 推荐阅读顺序

1. [项目介绍](product/amc-mta/project-introduction.md)：先理解目标、使用场景和边界。
2. [能力评价](amc-mta-capability-assessment.md)：判断当前能做什么、不能做什么。
3. [架构说明](amc-mta-architecture.md)：理解代码组件、数据流和模型语义。
4. [数据契约](../modules/amc_mta/docs/amc-data-requirements.md)：查看输入、五段键、路径和指标规则。
5. [使用说明](../modules/amc_mta/docs/usage.md)：运行完整流程或独立步骤。
6. [双模型治理规范](../modules/amc_mta/docs/model-comparison-governance.md)：解释模型差距和输出阻断。

## 当前入口与权威层级

| 主题 | 推荐入口 |
| --- | --- |
| 可运行模块与命令 | [`modules/amc_mta/README.md`](../modules/amc_mta/README.md) |
| 输入字段、路径和成本规则 | [AMC MTA 数据契约](../modules/amc_mta/docs/amc-data-requirements.md) |
| Markov/Shapley 差距与决策状态 | [模型比较治理规范](../modules/amc_mta/docs/model-comparison-governance.md) |
| 代码结构与数据流 | [AMC MTA 架构](amc-mta-architecture.md) |
| 项目成熟度与后续优先级 | [AMC MTA 能力评价](amc-mta-capability-assessment.md) |
| 尚未解决的技术问题 | [延期事项](../_bmad-output/implementation-artifacts/deferred-work.md) |

权威优先级为：运行代码与测试 → 模块数据/治理契约 → 可再生产物 → 本目录的架构与
能力评价 → 项目介绍 → 研究笔记 → 历史产品文档。架构与评价是从代码和产物派生的
当前说明，不替代源码契约。

## 文件分区

```text
modules/amc_mta/
├── src/       # 路径键、路径构建、归因和模型比较
├── scripts/   # 独立命令行入口
├── tests/     # 75 项自动化测试
├── data/      # 三份可复现模拟输入
├── outputs/   # 五份正式、可再生 CSV
└── docs/      # 当前模块契约与使用说明

docs/
├── index.md
├── amc-mta-architecture.md
├── amc-mta-capability-assessment.md
├── product/   # 当前项目介绍与明确标记的历史愿景
└── research/  # 外部研究原件，不是运行输入
```

## 文档状态

- **当前**：本索引、架构、能力评价、AMC MTA 项目介绍及模块文档。
- **研究支撑**：`docs/research/mta/`、`docs/research/amazon/`。
- **后续验证**：`docs/research/ab-testing/`。
- **背景资料**：machine-learning、ontology、industry。
- **历史愿景**：`design-artifacts/` 与
  [模型功能与关系说明](product/model-relationship-guide.md)。
- **历史实现记录**：`_bmad-output/implementation-artifacts/`；冻结规格记录当时意图，
  不自动代表当前能力。

## 当前验证基线

截至 2026-07-16，基于基线提交 `734ff73`、当前三份模拟输入以及
`python3 modules/amc_mta/run_pipeline.py` 的确定性输出：

- 75 项 AMC MTA 测试通过；
- 17 个五段触点与 Amazon Ads 报告完全对齐；
- 报告窗口为 2026-05-01 至 2026-06-30，共 61 天逐日覆盖；
- 三项 AMC outcome 总量为 1,826 个购买用户、2,044 次购买、226,628 收入；
- 五份归因产物可确定性复现；
- 51 条治理推荐均为 `EVIDENCE_UNVERIFIED`，没有 `decision_value`。

这些数字证明样例流水线的一致性，不证明真实投放中的模型有效性或因果增量。
