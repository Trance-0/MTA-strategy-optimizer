---
stepsCompleted: [1, 2]
inputDocuments:
  - docs/research/amazon/research/amazon调研.docx
  - docs/research/amazon/research/Amazon_Attribution_Report_FULL.docx
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Amazon Attribution 与 Amazon-only MTA Demo'
research_goals: '总结两份调研报告，使用 Amazon 官方资料核验和补充，并通过示例解释数据、归因边界及 Demo 实现建议'
user_name: 'ericson'
date: '2026-07-06'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

> 历史研究快照：本文记录 2026-07-06 当时的调研和实现建议，部分目录、输入结构与当前代码不同。当前行为以 [AMC MTA 模块文档](../../../attribution/amc-mta-module.md) 和其[数据契约](../../../datasets/amc-data-contract.md)为准。

**Date:** 2026-07-06
**Author:** ericson
**Research Type:** technical

---

## Research Overview

[Research overview and methodology will be appended here]

---

## Technical Research Scope Confirmation

**Research Topic:** Amazon Attribution 与 Amazon-only MTA Demo

**Research Goals:** 总结两份调研报告，使用 Amazon 官方资料核验和补充，并通过示例解释数据、归因边界及 Demo 实现建议。

**Technical Research Scope:**

- Architecture Analysis - Amazon Attribution、AMC、Ads API 与 MTA 的职责边界
- Implementation Approaches - Demo 数据结构、归因方法和结果解释
- Technology Stack - Amazon 官方测量与数据产品
- Integration Patterns - 站外渠道、Amazon 转化、AMC 和 API 数据连接
- Performance Considerations - 数据粒度、隐私阈值、聚合限制和可复现性

**Research Methodology:**

- 使用当前 Amazon 官方公开资料进行事实核验
- 将本地报告观点区分为已核验事实、合理解释和待确认说法
- 对关键归因结论进行多来源交叉验证
- 使用具体路径和数字案例说明抽象概念

**Scope Confirmed:** 2026-07-06

---

## Technology Stack Analysis

### Amazon 测量与数据平台

当前场景不需要把 Amazon 相关能力理解成一个单一 API，而应区分三类平台：

1. **Amazon Attribution**：用于测量搜索、社交、展示、视频、邮件、联盟和达人等 Amazon 站外营销活动对 Amazon 站内商品浏览、加购、购买和销售的影响。官方说明其通过 Attribution tag 连接站外投放与 Amazon 转化，并可通过控制台、下载报告或 Amazon Attribution API 获取结果。
2. **Amazon Marketing Cloud（AMC）**：基于 AWS Clean Rooms 的隐私安全数据净室，可查询 Amazon Ads 信号以及广告主上传的匿名化信号。AMC 可以分析事件级和用户级信号，但只能输出达到隐私门槛的聚合匿名结果。
3. **Amazon Ads API**：使用 REST API 和 OAuth 2.0 管理及报告 Amazon 广告活动，可访问 Sponsored Ads、Amazon DSP、AMC 和 Amazon Marketing Stream 等产品。项目中的 OpenAPI 文件主要描述 Campaign、Ad Group、Ad、Target、预算、出价及 DSP forecast 等管理实体，不能替代 Attribution 或 AMC 的转化路径数据。

来源：

- [Amazon Attribution 官方产品说明](https://advertising.amazon.com/en-us/solutions/products/amazon-attribution/)
- [Amazon Marketing Cloud 官方产品说明](https://advertising.amazon.com/solutions/products/amazon-marketing-cloud)
- [Amazon Ads API 官方说明](https://advertising.amazon.com/about-api)
- [AMC API 纳入 Amazon Ads API](https://advertising.amazon.com/resources/whats-new/amc-api-available-on-amazon-ads-api/)

### 研究时的 Demo 编程技术

2026-07-06 研究时的旧 Demo 使用 Python 标准库实现：

- CSV 作为模型输入与归因结果交换格式；
- Python 模块实现 Markov Chain 和简化的 Shapley 归因；
- SVG 作为可复现的图表输出；
- 固定随机种子执行 Bootstrap 稳定性分析。

这个技术栈适合 Demo，因为依赖少、结果容易复算，也能清晰展示归因算法。若以后接入真实 Amazon 数据，建议保持模型接口不变，在模型前增加独立的数据适配层：

```text
Amazon Attribution 下载报告 / API
                   ├──> 数据标准化层 ──> 聚合效果分析
AMC 查询聚合结果 ──┘
                                   └──> 路径构造 ──> Markov / Shapley
```

当前 AMC MTA 已改为五段互动粒度、五份 CSV 输出和治理阻断；没有 SVG 或
Bootstrap 稳定性产物。当前实现见
[AMC MTA 模块文档](../../../attribution/amc-mta-module.md)。

### 数据与存储技术

当前 Demo 使用模块内 CSV：

```text
modules/amc_mta/data/simulated/
```

但需要区分三类数据：

| 数据类型 | 推荐格式 | 用途 |
| --- | --- | --- |
| Amazon Attribution 聚合报告 | CSV | 渠道、publisher、campaign、ad group、ASIN 的漏斗和转化分析 |
| AMC 风格匿名聚合路径 | CSV | 演示五段 Markov 和 Path-level Shapley |
| 模型输出 | CSV | 归因结果、模型差异、支持度和治理状态 |

生产化后，原始 API 响应宜以不可变快照保存，标准化表再进入分析数据库；AMC 原始用户级信号不能直接导出，系统应保存查询版本、参数和聚合结果，而不是假设可以下载完整用户日志。

### API 与认证

项目内 OpenAPI 文件表明 Amazon Ads API 使用：

- REST/JSON；
- OAuth 2.0 authorization code flow；
- NA、EU、FE 三个区域 endpoint；
- Campaign、Ad Group、Ad、Target 等批量查询和管理接口。

Amazon 官方同时说明 API 访问需要申请和审批。Demo 不应把“已经拥有 OpenAPI 文件”等同于“已经获得可调用的广告账户与真实数据权限”。

### 技术采用建议

当前阶段不需要数据库、微服务或实时流式处理。建议采用：

```text
Python + CSV 快照 + 版本化配置 + 可复现运行脚本
```

当获得真实 Amazon Attribution 报告后，先构建聚合分析适配器；当获得 AMC 权限和满足隐私门槛的路径聚合结果后，再替换模拟路径。这样可以避免为了展示 API 而把并不支持 MTA 的 Campaign Management 数据硬塞进归因模型。

### 可信度与待核验点

- **高可信度**：Amazon Attribution 用于测量站外营销对 Amazon 站内结果的影响；官方列出统一的 14 天归因窗口和点击、DPV、加购、购买、销售、新客等指标。
- **高可信度**：AMC 支持隐私安全的事件级/用户级信号分析，但仅输出聚合匿名结果。
- **中等可信度**：本地报告声称“14 天点击窗口 + 7 天浏览窗口”。当前找到的 Amazon 官方 Attribution 页面只写 14 天归因窗口，因此 7 天浏览窗口在本报告中标记为未核验，不作为 Demo 默认规则。
- **高可信度**：项目 OpenAPI 主要提供广告管理对象，不能单独生成跨触点用户路径。

---

## Integration Patterns Analysis

### Amazon Attribution 标签集成

Amazon Attribution 的基础集成方式是给每个需要测量的站外广告策略生成唯一 Attribution tag，并把标签参数加入广告最终落地 URL。官方说明每个 ad group 获得唯一标签，标签可以按 publisher、channel、campaign、creative、keyword 或产品组织报告。

```text
TikTok 广告
   ↓ 点击带 Attribution tag 的 URL
Amazon 商品详情页或 Store
   ↓
DPV → Add to Cart → Purchase → Product Sales
   ↓
Amazon Attribution 聚合报告
```

来源：

- [Amazon Attribution 完整官方指南](https://advertising.amazon.com/zh-cn/library/guides/basics-of-amazon-attribution)
- [Amazon Attribution 14 天 last-touch 方法](https://advertising.amazon.com/help/G4YK9L2G4NXDD7SC)

#### 示例：标签如何决定分析粒度

假设 TikTok 有两个素材：

```text
Campaign: Summer Launch
├── Ad group: TikTok-video-A → tag_A
└── Ad group: TikTok-video-B → tag_B
```

如果两个素材共用一个标签，报告只能告诉你 TikTok 合计带来多少购买；如果每个素材使用独立标签，就能比较 video-A 和 video-B。标签设计实际上就是数据模型设计，后期无法从粗粒度标签中恢复更细粒度信息。

### 下载报告与 API 集成

Amazon Attribution 官方提供：

- 广告平台中的可视化报告；
- 可按需或定时生成的 Excel 报告；
- 集成到 Amazon Ads API 的 Amazon Attribution API。

官方列出四类主要报告：

1. Campaign report：campaign 和 ad group 的每日效果；
2. Publisher report：channel 和 publisher 聚合效果；
3. Keyword/creative report：部分批量创建活动的关键词或素材效果；
4. Product report：推广产品、品牌光环产品及其汇总视图。

来源：[Amazon Attribution 报告与指标官方指南](https://advertising.amazon.com/zh-cn/library/guides/basics-of-amazon-attribution)

Demo 的推荐适配流程：

```text
下载的 Excel/CSV
   ↓
列名映射与类型校验
   ↓
amazon_attribution_performance.csv
   ↓
漏斗、ROAS、Campaign 对比
```

注意：这个流程产生的是聚合效果表，不会自动生成用户触点序列。

### AMC 查询集成

AMC 适合解决 Amazon Attribution 聚合报告无法回答的路径问题。官方说明 AMC 可以查询跨来源的事件级和用户级信号，但 `user_id` 等高敏感字段不能出现在最终输出；查询结果必须满足聚合阈值。

来源：

- [AMC 官方产品与隐私说明](https://advertising.amazon.com/solutions/products/amazon-marketing-cloud)
- [AMC aggregation thresholds 官方说明](https://advertising.amazon.com/help/G6ZYAPTTTE54UQPP)

因此，AMC 的正确集成方式不是导出真实用户日志，而是在 AMC 内部完成路径聚合：

```text
AMC 内部 pseudonymous events
   ↓ SQL / 分析模板
按路径聚合：
TikTok > Facebook > Google | users=180 | conversions=24
Google                     | users=420 | conversions=63
Facebook > Google          | users=250 | conversions=31
   ↓ 仅导出达到阈值的聚合路径
Markov MTA 输入
```

这里的 `TikTok/Facebook/Google` 只有在广告主把相应匿名化第一方信号接入 AMC，并且能够和 Amazon 信号在允许范围内连接时才成立；不能仅凭 Amazon Attribution 下载报告反推出这些用户路径。

### 当前 MTA 模型适配

现有代码需要三类输入：

```text
markov_user_paths.csv
shapley_user_channel_sets.csv
channel_spend.csv
```

推荐引入两个适配器，而不是直接修改算法：

```text
AmazonAttributionAggregateAdapter
  输入：Amazon Attribution 聚合报告
  输出：渠道/Campaign 漏斗与 ROI 分析表
  限制：不生成真实 MTA 路径

AmazonPathAggregateAdapter
  输入：AMC 导出的聚合路径，或明确标记的模拟路径
  输出：Markov/Shapley 所需路径表
  限制：必须记录数据来源和路径是否模拟
```

### 归因时间与数据更新

Amazon 官方说明：

- Amazon Attribution 使用 14 天 last-touch 模型；
- 转化可能需要最多约 12 小时才出现在报告中；
- 报告日期上的归因指标在回溯窗口结束前仍可能不完整；
- Amazon 可能进行 attribution restatement，历史归因结果因此可能更新。

来源：

- [14 天 last-touch 规则](https://advertising.amazon.com/help/G4YK9L2G4NXDD7SC)
- [转化延迟与窗口完整性](https://advertising.amazon.com/help/GX7KDKHMWQYMJ385)
- [Attribution restatement](https://advertising.amazon.com/help/G22MA5YPN9KKT7TM)

这意味着数据快照必须带：

```text
report_date
data_as_of
attribution_window_days
report_version
```

#### 示例：为什么不能当天立即下结论

7 月 1 日 TikTok 广告获得 100 次点击。7 月 2 日报告显示 3 次购买，7 月 10 日可能已经回填为 8 次购买。若模型每天覆盖旧数据而不保留 `data_as_of`，就无法解释为什么同一个 Campaign 的 ROAS 后来发生变化。

### 集成安全与权限

- Amazon Ads API 使用 OAuth 2.0；
- API 权限需要申请和审批；
- 广告账户访问、Attribution 权限和 AMC instance 权限是不同前提；
- Token、广告主 ID 和 profile 信息不得写入仓库；
- AMC 不允许通过最终查询输出重识别用户。

### 不推荐的集成方式

- 不把 Campaign Management OpenAPI 当作归因事件源；
- 不从聚合 Attribution 报告伪造“真实用户路径”；
- 不把 Amazon last-touch 结果当作 Markov/Shapley 的真实标签答案；
- 不在 Demo 中声称能够导出 AMC 原始 `user_id`；
- 不为当前规模引入消息队列、微服务或实时流处理。

---

<!-- Content will be appended sequentially through research workflow steps -->
