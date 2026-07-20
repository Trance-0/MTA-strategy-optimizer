# Amazon 研究原件索引

本目录保存 Amazon Ads、Amazon Attribution 和 AMC 的外部原件与历史调研，不是
`modules/amc_mta` 的运行输入。六份原件如下：

| 原件 | 类型 | 用途与边界 |
| --- | --- | --- |
| [Amazon Ads API schema](AmazonAdsAPIALLMerged_prod_3p_formatted.json) | JSON | 上游 API 字段研究，不是本地输入 schema |
| [Amazon Attribution 报告](Amazon_Attribution_Report_FULL.docx) | DOCX | 站外 Amazon Attribution 研究，不可替代 AMC 路径 |
| [Advertising 数据格式示例](amazon-advertising-data-format-examples.txt) | TXT | 上游格式样例 |
| [Marketing Stream 字段研究](amazon-marketing-stream-fields.md) | Markdown | 流式指标和维度参考 |
| [Amazon 调研原件](amazon调研.docx) | DOCX | 广告产品、计费与 AMC 背景材料 |
| [2026-07-06 技术调研](technical-amazon-attribution-mta-2026-07-06.md) | Markdown | 历史技术快照，当前行为以模块契约为准 |

推荐先阅读上级 [Amazon 研究入口](../README.md)和 [AMC 概览](../amc/README.md)，
再按问题查阅原件。当前字段与计算规则只看
[AMC MTA 数据契约](../../../../modules/amc_mta/docs/amc-data-requirements.md)。
