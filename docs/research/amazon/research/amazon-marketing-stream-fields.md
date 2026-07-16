# Amazon Marketing Stream 字段调研

## 结论

Amazon 官方名称是 `Amazon Marketing Stream`，不是单独叫 `Amazon Advertisement Stream`。它是 Amazon Ads API 体系下的 push-based messaging system，用来把近实时的广告数据通过 AWS SQS 或 Amazon Data Firehose 推送给广告主、agency 或技术服务商。

目前公开资料可以确认三件事：

- Amazon Marketing Stream 可以订阅多个 `StreamDatasetId`，这些 dataset 覆盖 Sponsored Products、Sponsored Brands、Sponsored Display、Amazon DSP、budget usage、budget recommendations、campaign/ad group/ad/target 变更等。
- Amazon 公开产品页说明它提供 hourly campaign metrics、campaign changes、budget consumption，以及 sponsored ads 的 traffic 和 conversion 相关 hourly changes。
- Amazon Ads Advanced Tools Center 的 Marketing Stream dataset 页面包含 dataset 级别的 `Schema` 和 `Sample Payload`，可以查看某个 dataset 支持的具体 fields / metrics。比如 `adsp-traffic` 页面说明该 dataset 包含 Amazon DSP campaign 相关的 click、impression、cost 数据，并在 schema 表中列出 `dataset_id`、`idempotency_id`、`time_window_start` 等字段。

但需要注意：本文当前还没有逐页抽取每个 dataset 的完整 schema 表。下面的 dataset 列表和数据类别是官方可确认信息；后面的 normalized fields 是本项目为了 AMC MTA / Amazon Ads report 数据链路设计的落地字段层，不应被直接理解为 Marketing Stream 原始 payload 的全量官方字段。

- 官方公开可确认的 subscription dataset。
- 官方 dataset 页面能确认的数据类别和部分字段示例。
- 本项目建议落地的 normalized fields，用于和 AMC MTA / Amazon Ads report 数据链路对齐。

## 官方可订阅 dataset

下面的 `StreamDatasetId` 来自 Amazon 官方 `ads-advanced-tools-docs` GitHub 仓库中的 Amazon Marketing Stream CloudFormation template。它是目前公开资料里最明确的 dataset 列表。

| StreamDatasetId | 数据类别 | 适合用途 |
| --- | --- | --- |
| `sp-traffic` | Sponsored Products traffic | SP 小时级曝光、点击、流量表现分析 |
| `sp-conversion` | Sponsored Products conversion | SP 转化、销售、订单相关分析 |
| `budget-usage` | Sponsored ads budget usage | 预算消耗监控、预算 pacing、预算耗尽预警 |
| `sd-traffic` | Sponsored Display traffic | SD 小时级曝光、点击、流量表现分析 |
| `sd-conversion` | Sponsored Display conversion | SD 转化、销售、订单相关分析 |
| `sponsored-ads-campaign-diagnostics-recommendations` | Sponsored ads campaign diagnostics / recommendations | campaign health、诊断、优化建议 |
| `campaigns` | Sponsored ads campaign entity changes | campaign 创建、状态、配置变更流 |
| `adgroups` | Sponsored ads ad group entity changes | ad group 配置变更流 |
| `ads` | Sponsored ads ad entity changes | ad / creative / advertised product 相关变更流 |
| `targets` | Sponsored ads targeting entity changes | keyword、product targeting、audience targeting 等变更流 |
| `sb-traffic` | Sponsored Brands traffic | SB 小时级曝光、点击、流量表现分析 |
| `sb-conversion` | Sponsored Brands conversion | SB 转化、销售、订单相关分析 |
| `sb-clickstream` | Sponsored Brands clickstream | SB 点击行为事件流，通常比汇总 traffic 更接近 event stream |
| `sb-rich-media` | Sponsored Brands rich media | SB 视频、富媒体互动相关数据 |
| `adsp-campaigns` | Amazon DSP campaign changes | DSP campaign 变更流 |
| `adsp-campaign-flights` | Amazon DSP campaign flight changes | DSP flight / pacing / budget period 相关变更流 |
| `adsp-adgroups` | Amazon DSP ad group changes | DSP ad group / line item 相关变更流 |
| `adsp-adgroup-targets` | Amazon DSP ad group target changes | DSP target / audience / inventory 相关变更流 |
| `sp-budget-recommendations` | Sponsored Products budget recommendations | SP 预算建议，用于预算优化和机会识别 |

## 数据形态

Amazon Marketing Stream 不是 AMC 那种“提交 SQL 后返回聚合 report”的模式。它更像一个持续订阅的数据流：

- 通过 Amazon Ads API 创建 subscription。
- 指定 `StreamDatasetId`、realm / region 和 destination。
- destination 可以是 AWS SQS，也可以是 Amazon Data Firehose。
- Amazon 按 dataset 持续推送消息。
- 部分 performance dataset 是 hourly metrics，适合做近实时监控、dayparting、预算 pacing、投放异常检测。
- campaign / ad group / ad / target dataset 更像 entity change stream，适合做配置快照、变更审计和状态同步。

## 官方公开可确认的数据类别

| 类别 | 对应 dataset | 官方公开能确认的内容 | 是否适合 MTA |
| --- | --- | --- | --- |
| Traffic metrics | `sp-traffic`, `sb-traffic`, `sd-traffic` | hourly performance / traffic changes，通常围绕 impressions、clicks 等流量指标 | 适合作为 media exposure / engagement 的聚合输入 |
| Conversion metrics | `sp-conversion`, `sb-conversion`, `sd-conversion` | conversion changes，通常围绕 purchases、sales、units 等转化指标 | 可用于补充 outcome，但 MTA 仍需注意归因口径 |
| Budget usage | `budget-usage` | budget consumption | 适合 ROI / ROAS、预算 pacing，不是用户路径数据 |
| Recommendations | `sp-budget-recommendations`, `sponsored-ads-campaign-diagnostics-recommendations` | budget recommendations、campaign diagnostics / recommendations | 适合优化建议，不适合作为 MTA 主事实表 |
| Entity changes | `campaigns`, `adgroups`, `ads`, `targets` | campaign / ad group / ad / target 配置变更 | 适合维表和状态快照 |
| Sponsored Brands event / media | `sb-clickstream`, `sb-rich-media` | SB clickstream、rich media 相关流 | 可辅助细化 SB 触点，字段需按对应 dataset schema 页确认 |
| Amazon DSP changes | `adsp-campaigns`, `adsp-campaign-flights`, `adsp-adgroups`, `adsp-adgroup-targets` | DSP campaign / flight / ad group / target 变更 | 适合 DSP 维表和状态同步，不是转化路径表 |

## 项目建议 normalized fields

因为不同 dataset 的 raw payload schema 不一样，我建议项目里不要直接假设所有 stream payload 都能落成同一个固定 CSV。更稳妥的方式是建立一个 normalized layer：每个 raw stream dataset 先进入 bronze/raw，然后转换成统一的 analytics 表。

### Performance stream normalized table

这张表用于承接 `sp-traffic`、`sb-traffic`、`sd-traffic`、`sp-conversion`、`sb-conversion`、`sd-conversion`，也可以和 Amazon Ads report 做口径对齐。

| Field | Type | 来源/口径 | 说明 |
| --- | --- | --- | --- |
| `streamDatasetId` | string | Amazon Marketing Stream | 原始 dataset，例如 `sp-traffic`、`sb-conversion` |
| `eventDateTime` | timestamp | Amazon Marketing Stream | 消息或指标对应的时间 |
| `reportDate` | date | derived | 按广告账户时区或项目统一时区截取 |
| `reportHour` | int | derived | 0-23，用于 hourly / intraday 分析 |
| `marketplace` | string | Amazon Ads | marketplace，例如 `US` |
| `accountId` | string | Amazon Ads | Ads account / advertiser account id |
| `profileId` | string | Amazon Ads | Sponsored ads 常见 profile 级标识，具体是否出现取决于 dataset |
| `campaignId` | string | Amazon Ads | campaign identifier |
| `campaignName` | string | entity join | 可从 campaign entity stream 或 report 维表补齐 |
| `campaignState` | string | Amazon Ads API enum | `ENABLED`、`PAUSED`、`ARCHIVED` |
| `adGroupId` | string | Amazon Ads | ad group identifier |
| `adGroupName` | string | entity join | 可从 ad group entity stream 或 report 维表补齐 |
| `adId` | string | Amazon Ads | ad / creative / product ad identifier，取决于 dataset |
| `targetId` | string | Amazon Ads | keyword、product target、audience target 等 |
| `keywordId` | string | Amazon Ads | keyword 粒度数据可用时使用 |
| `asin` | string | Amazon Ads | advertised ASIN 或 purchased ASIN，取决于 report / dataset |
| `adProduct` | string | Amazon Ads API enum | `SPONSORED_PRODUCTS`、`SPONSORED_BRANDS`、`SPONSORED_DISPLAY`、`AMAZON_DSP` 等 |
| `adType` | string | Amazon Ads API enum | `PRODUCT_AD`、`VIDEO`、`DISPLAY`、`COMPONENT`、`AUDIO` 等 |
| `creativeType` | string | Amazon Ads API enum | `IMAGE`、`VIDEO` |
| `inventoryType` | string | Amazon Ads API enum | `DISPLAY`、`ONLINE_VIDEO`、`STREAMING_TV`、`AUDIO`、`PODCAST` 等 |
| `placement` | string | Amazon Ads API enum | `TOP_OF_SEARCH`、`PRODUCT_PAGE`、`REST_OF_SEARCH` 等 |
| `normalizedTouchpoint` | string | project derived | 本项目统一五段触点，例如 `SPONSORED_BRANDS:VIDEO:TOP_OF_SEARCH:VIDEO:CLICK` |
| `costType` | string | Amazon Ads API enum | `CPC`、`CPM`、`VCPM`、`FIXED_PRICE` |
| `currencyCode` | string | Amazon Ads | 例如 `USD` |
| `impressions` | integer | traffic dataset | 曝光次数 |
| `clicks` | integer | traffic dataset | 点击次数 |
| `cost` | decimal | traffic / spend related | 广告花费；具体是否在 stream payload 中出现需以订阅后的 raw payload 校验 |
| `purchases` | integer | conversion dataset | 购买/订单数，归因窗口取决于 Amazon 口径 |
| `sales` | decimal | conversion dataset | 销售额，归因窗口取决于 Amazon 口径 |
| `unitsSold` | integer | conversion dataset | 销售件数 |
| `rawMessageId` | string | ingestion metadata | SQS / Firehose 或自建 ingest 产生的消息 id |
| `rawIngestedAt` | timestamp | ingestion metadata | 数据进入本项目数据湖/仓库的时间 |

### Entity stream normalized table

这张表用于承接 `campaigns`、`adgroups`、`ads`、`targets`、`adsp-campaigns`、`adsp-campaign-flights`、`adsp-adgroups`、`adsp-adgroup-targets`。

| Field | Type | 来源/口径 | 说明 |
| --- | --- | --- | --- |
| `streamDatasetId` | string | Amazon Marketing Stream | 原始 dataset |
| `eventDateTime` | timestamp | Amazon Marketing Stream | 变更事件时间 |
| `marketplace` | string | Amazon Ads | marketplace |
| `accountId` | string | Amazon Ads | Ads account / advertiser account id |
| `profileId` | string | Amazon Ads | Sponsored ads profile id，如适用 |
| `entityType` | string | derived | `campaign`、`adGroup`、`ad`、`target`、`flight` |
| `entityId` | string | Amazon Ads | 当前实体 id |
| `parentEntityId` | string | Amazon Ads | 上级实体 id，例如 ad group 的 campaign id |
| `entityName` | string | Amazon Ads | 当前实体名称，如适用 |
| `state` | string | Amazon Ads API enum | `ENABLED`、`PAUSED`、`ARCHIVED` |
| `adProduct` | string | Amazon Ads API enum | 广告产品 |
| `adType` | string | Amazon Ads API enum | 广告类型，如适用 |
| `creativeType` | string | Amazon Ads API enum | 创意类型，如适用 |
| `inventoryType` | string | Amazon Ads API enum | DSP / video / audio 相关库存类型，如适用 |
| `placement` | string | Amazon Ads API enum | sponsored ads placement，如适用 |
| `costType` | string | Amazon Ads API enum | 计费方式，如适用 |
| `budgetAmount` | decimal | Amazon Ads | campaign / flight 预算，如适用 |
| `budgetType` | string | Amazon Ads | daily / lifetime 等预算类型，如适用 |
| `bidAmount` | decimal | Amazon Ads | target / keyword bid，如适用 |
| `targetType` | string | Amazon Ads API enum | `KEYWORD`、`PRODUCT`、`AUDIENCE`、`DEVICE` 等 |
| `rawPayload` | json | raw stream | 保留原始消息，便于后续字段追溯 |
| `rawMessageId` | string | ingestion metadata | 消息 id |
| `rawIngestedAt` | timestamp | ingestion metadata | 入库时间 |

### Budget stream normalized table

这张表用于承接 `budget-usage` 和 `sp-budget-recommendations`。

| Field | Type | 来源/口径 | 说明 |
| --- | --- | --- | --- |
| `streamDatasetId` | string | Amazon Marketing Stream | `budget-usage` 或 `sp-budget-recommendations` |
| `eventDateTime` | timestamp | Amazon Marketing Stream | 预算事件或建议产生时间 |
| `reportDate` | date | derived | 日期 |
| `marketplace` | string | Amazon Ads | marketplace |
| `accountId` | string | Amazon Ads | Ads account / advertiser account id |
| `profileId` | string | Amazon Ads | Sponsored ads profile id，如适用 |
| `campaignId` | string | Amazon Ads | campaign identifier |
| `campaignName` | string | entity join | campaign name |
| `adProduct` | string | Amazon Ads API enum | 广告产品 |
| `budgetAmount` | decimal | Amazon Ads | 当前预算 |
| `budgetUsage` | decimal | Amazon Marketing Stream | 已消耗预算或预算使用量 |
| `budgetRemaining` | decimal | derived | 可由预算和消耗计算，或由 payload 提供时直接取 |
| `recommendedBudgetAmount` | decimal | budget recommendations | 推荐预算，如适用 |
| `currencyCode` | string | Amazon Ads | 货币 |
| `rawPayload` | json | raw stream | 原始消息 |
| `rawMessageId` | string | ingestion metadata | 消息 id |
| `rawIngestedAt` | timestamp | ingestion metadata | 入库时间 |

## 和 MTA / ROI 的关系

Amazon Marketing Stream 本身更适合做近实时运营和聚合指标监控，不等同于 AMC 的用户路径数据。对于 MTA：

- `traffic` dataset 可以提供 ad product / format / placement / campaign / ad group 粒度的 impressions、clicks、cost 等聚合输入。
- `conversion` dataset 可以提供 purchases、sales、unitsSold 等转化聚合输入。
- `entity changes` dataset 可以补齐 campaign、ad group、ad、target 的维度和状态。
- 如果要做 user-level path attribution，仍然应优先依赖 AMC 输出的 privacy-safe aggregated path report，而不是把 Marketing Stream 当作用户路径表。
- 如果要做 ROI / ROAS，Marketing Stream 和 Amazon Ads reporting 都可以作为 cost / sales 的候选来源，但最终要以实际订阅 payload 和 report schema 校验字段可用性。

## 本项目建议

当前项目的 `modules/amc_mta` 使用以下两类核心分析输入：

- AMC path report：负责 MTA path 和 conversion outcome。
- Amazon Ads report / Marketing Stream normalized performance table：负责与 AMC 一致的 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 粒度的 cost、sales、impressions、clicks 等聚合指标；CPC 费用归 `CLICK`，CPM 费用归 `IMPRESSION`。

如果后续真的接入 Amazon Marketing Stream，建议新增一层：

```text
raw_stream_messages
normalized_stream_performance
normalized_stream_entities
normalized_stream_budget
```

然后再把 `normalized_stream_performance` 聚合到当前 `amazon_ads_report_sample.csv` 的字段口径。这样脚本不需要知道原始 SQS / Firehose payload 的细节，也能避免后续 Amazon payload 版本变化影响 MTA 主流程。

## Sources

- [Amazon Ads, `Amazon Marketing Stream` product page](https://advertising.amazon.com/solutions/products/amazon-marketing-stream)
- [Amazon Ads official GitHub, `ads-advanced-tools-docs`](https://github.com/amzn/ads-advanced-tools-docs)
- [Amazon Ads official GitHub, `amazon_marketing_stream` resources](https://github.com/amzn/ads-advanced-tools-docs/tree/main/amazon_marketing_stream)
- [Amazon Ads official GitHub, `Stream_SQS _CF_Template.yaml`](https://raw.githubusercontent.com/amzn/ads-advanced-tools-docs/main/amazon_marketing_stream/Stream_SQS%20_CF_Template.yaml)
- Local Amazon Ads API schema snapshot: `docs/research/amazon/research/AmazonAdsAPIALLMerged_prod_3p_formatted.json`
