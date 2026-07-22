# AMC MTA 当前文档

这里仅保存当前可运行模块的说明：

- [完整使用说明](amc-mta-complete-guide.md)：提交审阅、运行、Demo、错误处理和限制的一站式文字说明。
- [数据流流程图](assets/amc-mta-data-flow.png)：独立 PNG 图像，展示输入、双模型、可靠性和正式输出；[SVG 源文件](assets/amc-mta-data-flow.svg)用于后续维护。
- [正式输出索引](output-reference.md)：五份 CSV 的阅读顺序、字段、粒度和解释边界。
- [数据契约](amc-data-requirements.md)：当前字段与业务规则的唯一完整事实源。
- [使用说明](usage.md)：运行命令、参数和输出。
- [单触点归因可靠性判断](touchpoint-reliability-guide.md)：按计算有效、数据支撑充分、模型一致三个标准解释单触点结果。
- [Amazon Ads 样例](amazon-ads-report-sample.md)：五段表现与成本输入及计费归属方式。
- [双模型差异量化与输出规范](model-comparison-governance.md)：面向快消品的 Markov 与 Path-level Shapley 差距阈值、证据门槛和输出状态机。

平台背景见 [Amazon AMC 研究](../../../docs/research/amazon/amc/README.md)，项目概览见 [AMC MTA 项目介绍](../../../docs/product/amc-mta/project-introduction.md)。

五份正式 CSV 的逐文件说明见[输出索引](output-reference.md)，提交范围见
[提交清单](../SUBMISSION_MANIFEST.md)。若本文档与历史设计材料冲突，以当前数据契约、
模型治理规范、运行代码和测试为准。
