# Amazon Marketing Cloud（AMC）

AMC 是 Amazon Ads 的 privacy-safe clean room。它允许在受控环境内分析 pseudonymized Amazon Ads signals、广告主一方数据及可用扩展信号，但最终可访问的是满足隐私规则的 aggregated anonymous outputs，而不是可下载的完整用户事件日志。

## 与相关数据源的边界

- **AMC**：在 clean room 内查询触点、转化和路径，输出匿名聚合结果。
- **Amazon Ads reporting / Marketing Stream**：提供 campaign、广告维度、impressions、clicks、cost、sales 等运营和成本数据。
- **Amazon Attribution**：衡量站外营销对 Amazon 站内结果的影响；其 14 天 last-touch 规则不等同于本项目的 14 天连续路径规则。

本项目当前模拟 AMC 风格聚合路径，并用独立 Amazon Ads 表补充成本。事件样例仅用于本地算法演示；当前实现和字段以 [`modules/amc_mta`](../../../../modules/amc_mta/README.md) 为准。

## 阅读入口

- [AMC、MTA 与 ROI 数据流](data-flow.md)
- [当前数据契约](../../../../modules/amc_mta/docs/amc-data-requirements.md)
- [AMC MTA 项目介绍](../../../product/amc-mta/project-introduction.md)
- [2026-07-06 历史技术研究](../research/technical-amazon-attribution-mta-2026-07-06.md)

## 参考来源

- [Amazon Marketing Cloud](https://advertising.amazon.com/solutions/products/amazon-marketing-cloud)
- [Amazon Ads API: AMC overview](https://advertising.amazon.com/API/docs/en-us/guides/amazon-marketing-cloud/overview)
- [Amazon Attribution](https://advertising.amazon.com/solutions/products/amazon-attribution)
- [Amazon Marketing Stream](https://advertising.amazon.com/solutions/products/amazon-marketing-stream)
