# 研究资料分级索引

这里保存外部论文、平台调研和背景材料。所有文件均保留，但研究资料不等于当前实现，
也不是 `modules/amc_mta` 的运行输入。

## 与 AMC MTA 的相关性

| 等级 | 目录 | 用途 |
| --- | --- | --- |
| 核心方法 | [MTA 阅读入口](mta/README.md) | Markov、Shapley、稳定性和 MTA 方法依据 |
| 核心平台 | [Amazon 阅读入口](amazon/README.md) | AMC、Amazon Ads、广告产品和数据边界 |
| 后续验证 | [A/B 测试阅读入口](ab-testing/README.md) | 未来验证归因/预算结论，不参与当前模型计算 |
| 背景 | [机器学习论文](machine-learning/cacm12.pdf) | 通用机器学习常识，不直接支撑当前算法 |
| 背景 | [本体论研究](ontology/本体论研究（最终）.pdf) | 知识组织研究，与当前归因运行无直接依赖 |
| 背景 | [行业方案](industry/跨行业AI应用项目-营销场景AI应用与数据.pdf) | 早期跨行业营销 AI 方案和项目背景 |

### 核心 MTA 资料

- [MTA 阅读顺序](mta/README.md)
- [Data-driven Multi-touch Attribution Models](mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)：强调归因估计稳定性，研究模型与当前实现不同。
- [Mapping the customer journey](mta/Mapping%20the%20customer%20journey.pdf)：图与高阶 Markov 归因研究。
- [Shapley Value Methods for Attribution Modeling](mta/Shapley%20Value%20Methods%20for%20Attribution%20Modeling%20in%20Online%20Advertising.pdf)：Shapley 归因背景。
- [学习笔记](mta/Data-driven_MTA_Models_study_note.md)：个人学习记录，不作为代码事实源。

### Amazon 平台资料

- [AMC 背景](amazon/amc/README.md)与[数据流](amazon/amc/data-flow.md)直接支撑 clean room 边界。
- `amazon/research/amazon调研.docx` 对 SP、SB、SD、DSP、CPC/CPM 和 AMC 边界有直接参考价值。
- `amazon/research/Amazon_Attribution_Report_FULL.docx` 主要讨论站外 Amazon Attribution 与 ROAS，不可替代 AMC 路径。
- OpenAPI JSON、Marketing Stream 字段和格式示例用于上游数据研究，不是当前运行输入。
- [2026-07-06 技术调研](amazon/research/technical-amazon-attribution-mta-2026-07-06.md)是历史快照，当前行为以模块契约为准。
- [Amazon 研究原件索引](amazon/research/README.md)列出该层全部六份原件及用途。

### 后续验证与背景

- [两篇 A/B 测试论文](ab-testing/README.md)用于未来因果验证和实验设计，不能验证当前样例归因是否正确。
- machine-learning、ontology 和 industry 文件保留为团队背景资料；它们不应出现在当前运行链路或核心阅读顺序中。

## 边界

- 可运行样例只放在 [`modules/amc_mta/data/simulated/`](../../modules/amc_mta/data/simulated/)。
- 当前输入输出契约只看 [`modules/amc_mta/docs/`](../../modules/amc_mta/docs/)。
- 研究原件不由流水线读取，不从 Amazon Attribution 聚合报告反推 AMC 用户路径。
- 新增研究资料时，应在本索引标注“核心、后续验证或背景”。
