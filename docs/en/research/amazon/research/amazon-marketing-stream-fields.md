---
title: Amazon Marketing Stream Field Research
lang: en-US
---

# Amazon Marketing Stream Field Research

## Conclusion

The official name is `Amazon Marketing Stream`, not `Amazon Advertisement Stream`. It is a push-based messaging system in the Amazon Ads API ecosystem that sends near-real-time advertising data to advertisers, agencies, or technology providers through Amazon Web Services Simple Queue Service (AWS SQS) or Amazon Data Firehose.

Public material confirms three points:

- Amazon Marketing Stream supports multiple `StreamDatasetId` subscriptions covering Sponsored Products, Sponsored Brands, Sponsored Display, Amazon DSP, budget usage, budget recommendations, and Campaign/Ad Group/ad/target changes.
- The public product page describes hourly Campaign metrics, Campaign changes, budget consumption, and hourly sponsored-ads traffic and conversion changes.
- Marketing Stream dataset pages in the Amazon Ads Advanced Tools Center include dataset-specific schema and sample payload information. For example, `adsp-traffic` describes Amazon DSP Campaign click, impression, and cost data and lists fields such as `dataset_id`, `idempotency_id`, and `time_window_start`.

The source research did not extract the complete schema table for every dataset. The dataset list and data categories below are publicly confirmable; the proposed normalized fields are a project design for connecting Marketing Stream with AMC MTA and Amazon Ads reporting and must not be interpreted as the complete official raw payload schema.

This page separates:

- publicly confirmable subscription datasets;
- data categories and selected examples confirmed by official dataset pages;
- project-proposed normalized fields for the AMC MTA/Amazon Ads data chain.

## Official Subscription Datasets

The following `StreamDatasetId` values came from the Amazon Marketing Stream CloudFormation template in Amazon's public `ads-advanced-tools-docs` repository.

| StreamDatasetId | Data category | Suitable use |
| --- | --- | --- |
| `sp-traffic` | Sponsored Products traffic | hourly SP impressions, clicks, and traffic performance |
| `sp-conversion` | Sponsored Products conversion | SP conversions, sales, and orders |
| `budget-usage` | sponsored-ads budget usage | spend monitoring, pacing, budget-exhaustion warnings |
| `sd-traffic` | Sponsored Display traffic | hourly SD impressions, clicks, traffic performance |
| `sd-conversion` | Sponsored Display conversion | SD conversions, sales, orders |
| `sponsored-ads-campaign-diagnostics-recommendations` | Campaign diagnostics/recommendations | Campaign health, diagnostics, optimization suggestions |
| `campaigns` | sponsored-ads Campaign entity changes | Campaign creation, status, configuration changes |
| `adgroups` | sponsored-ads Ad Group changes | Ad Group configuration changes |
| `ads` | sponsored-ads ad changes | ad, creative, advertised-product changes |
| `targets` | sponsored-ads targeting changes | Keyword, product, Audience Targeting changes |
| `sb-traffic` | Sponsored Brands traffic | hourly SB impressions, clicks, traffic performance |
| `sb-conversion` | Sponsored Brands conversion | SB conversions, sales, orders |
| `sb-clickstream` | Sponsored Brands clickstream | SB click-event stream, generally closer to events than aggregate traffic |
| `sb-rich-media` | Sponsored Brands rich media | SB video and rich-media interaction data |
| `adsp-campaigns` | Amazon DSP Campaign changes | DSP Campaign change stream |
| `adsp-campaign-flights` | Amazon DSP flight changes | flight, pacing, budget-period changes |
| `adsp-adgroups` | Amazon DSP Ad Group changes | DSP Ad Group/line-item changes |
| `adsp-adgroup-targets` | Amazon DSP target changes | DSP Target, Audience, inventory changes |
| `sp-budget-recommendations` | Sponsored Products budget recommendations | SP budget optimization and opportunity identification |

## Data Shape

Amazon Marketing Stream is not an AMC submit-SQL-and-return-an-aggregate-report pattern. It is a continuous subscription:

- create a subscription through the Amazon Ads API;
- specify `StreamDatasetId`, realm/region, and destination;
- choose AWS SQS or Amazon Data Firehose as destination;
- receive ongoing messages for the dataset;
- use hourly performance datasets for near-real-time monitoring, dayparting, pacing, and anomaly detection;
- use Campaign/Ad Group/ad/target datasets as entity-change streams for configuration snapshots, auditing, and state synchronization.

## Publicly Confirmable Data Categories

| Category | Dataset | Publicly confirmable content | Suitability for MTA |
| --- | --- | --- | --- |
| traffic metrics | `sp-traffic`, `sb-traffic`, `sd-traffic` | hourly performance/traffic changes, generally including impressions and clicks | aggregate media exposure/engagement input |
| conversion metrics | `sp-conversion`, `sb-conversion`, `sd-conversion` | conversion changes, generally purchases, sales, units | supplemental Outcomes; attribution semantics still require care |
| budget usage | `budget-usage` | budget consumption | ROI/ROAS and pacing, not user paths |
| recommendations | `sp-budget-recommendations`, `sponsored-ads-campaign-diagnostics-recommendations` | budget recommendations and Campaign diagnostics | optimization input, not the principal MTA fact table |
| entity changes | `campaigns`, `adgroups`, `ads`, `targets` | Campaign/Ad Group/ad/target configuration changes | dimensions and state snapshots |
| Sponsored Brands event/media | `sb-clickstream`, `sb-rich-media` | clickstream and rich-media activity | potential SB touchpoint detail; confirm fields against each schema |
| Amazon DSP changes | `adsp-campaigns`, `adsp-campaign-flights`, `adsp-adgroups`, `adsp-adgroup-targets` | Campaign/flight/Ad Group/target changes | DSP dimensions and state synchronization, not conversion paths |

## Project-Proposed Normalized Fields

Raw payload schemas differ by dataset. The recommendation is not to force every payload into one fixed CSV, but to land each dataset in a bronze/raw layer and transform it into common analytics tables.

### Performance Stream Normalized Table

This table can receive `sp-traffic`, `sb-traffic`, `sd-traffic`, `sp-conversion`, `sb-conversion`, and `sd-conversion` and align them with Amazon Ads reporting.

| Field | Type | Source/semantics | Description |
| --- | --- | --- | --- |
| `streamDatasetId` | string | Marketing Stream | raw dataset such as `sp-traffic` or `sb-conversion` |
| `eventDateTime` | timestamp | Marketing Stream | message or metric time |
| `reportDate` | date | derived | date in the account or project-standard timezone |
| `reportHour` | integer | derived | 0-23 for hourly/intraday analysis |
| `marketplace` | string | Amazon Ads | marketplace such as `US` |
| `accountId` | string | Amazon Ads | Ads/advertiser account identifier |
| `profileId` | string | Amazon Ads | common sponsored-ads profile identifier when the dataset provides it |
| `campaignId` | string | Amazon Ads | Campaign identifier |
| `campaignName` | string | entity join | filled from Campaign change stream or report dimension |
| `campaignState` | string | API enumeration | `ENABLED`, `PAUSED`, `ARCHIVED` |
| `adGroupId` | string | Amazon Ads | Ad Group identifier |
| `adGroupName` | string | entity join | filled from Ad Group change stream/report dimension |
| `adId` | string | Amazon Ads | ad, creative, or product-ad identifier depending on dataset |
| `targetId` | string | Amazon Ads | Keyword, product, or Audience target |
| `keywordId` | string | Amazon Ads | used when Keyword-grain data is available |
| `asin` | string | Amazon Ads | advertised or purchased Amazon Standard Identification Number depending on data |
| `adProduct` | string | API enumeration | `SPONSORED_PRODUCTS`, `SPONSORED_BRANDS`, `SPONSORED_DISPLAY`, `AMAZON_DSP`, etc. |
| `adType` | string | API enumeration | `PRODUCT_AD`, `VIDEO`, `DISPLAY`, `COMPONENT`, `AUDIO`, etc. |
| `creativeType` | string | API enumeration | `IMAGE`, `VIDEO` |
| `inventoryType` | string | API enumeration | `DISPLAY`, `ONLINE_VIDEO`, `STREAMING_TV`, `AUDIO`, `PODCAST`, etc. |
| `placement` | string | API enumeration | `TOP_OF_SEARCH`, `PRODUCT_PAGE`, `REST_OF_SEARCH`, etc. |
| `normalizedTouchpoint` | string | project-derived | five-segment key such as `SPONSORED_BRANDS:VIDEO:TOP_OF_SEARCH:VIDEO:CLICK` |
| `costType` | string | API enumeration | `CPC`, `CPM`, `VCPM`, `FIXED_PRICE` |
| `currencyCode` | string | Amazon Ads | for example `USD` |
| `impressions` | integer | traffic dataset | impression count |
| `clicks` | integer | traffic dataset | click count |
| `cost` | decimal | traffic/spend | ad spend; confirm its presence from subscribed raw payloads |
| `purchases` | integer | conversion dataset | purchases/orders under Amazon's attribution window |
| `sales` | decimal | conversion dataset | sales under Amazon's attribution window |
| `unitsSold` | integer | conversion dataset | units sold |
| `rawMessageId` | string | ingestion metadata | identifier created by SQS, Firehose, or ingestion layer |
| `rawIngestedAt` | timestamp | ingestion metadata | data-lake/warehouse ingestion time |

### Entity Stream Normalized Table

This table can receive `campaigns`, `adgroups`, `ads`, `targets`, `adsp-campaigns`, `adsp-campaign-flights`, `adsp-adgroups`, and `adsp-adgroup-targets`.

| Field | Type | Source/semantics | Description |
| --- | --- | --- | --- |
| `streamDatasetId` | string | Marketing Stream | raw dataset |
| `eventDateTime` | timestamp | Marketing Stream | entity-change time |
| `marketplace` | string | Amazon Ads | marketplace |
| `accountId` | string | Amazon Ads | Ads/advertiser account identifier |
| `profileId` | string | Amazon Ads | sponsored-ads profile when applicable |
| `entityType` | string | derived | `campaign`, `adGroup`, `ad`, `target`, `flight` |
| `entityId` | string | Amazon Ads | current entity identifier |
| `parentEntityId` | string | Amazon Ads | parent such as Campaign ID for an Ad Group |
| `entityName` | string | Amazon Ads | entity name where applicable |
| `state` | string | API enumeration | `ENABLED`, `PAUSED`, `ARCHIVED` |
| `adProduct` | string | API enumeration | advertising product |
| `adType` | string | API enumeration | ad type where applicable |
| `creativeType` | string | API enumeration | creative type where applicable |
| `inventoryType` | string | API enumeration | DSP/video/audio inventory type where applicable |
| `placement` | string | API enumeration | sponsored-ads placement where applicable |
| `costType` | string | API enumeration | billing method where applicable |
| `budgetAmount` | decimal | Amazon Ads | Campaign/flight budget where applicable |
| `budgetType` | string | Amazon Ads | daily/lifetime budget type where applicable |
| `bidAmount` | decimal | Amazon Ads | target/Keyword bid where applicable |
| `targetType` | string | API enumeration | `KEYWORD`, `PRODUCT`, `AUDIENCE`, `DEVICE`, etc. |
| `rawPayload` | JSON | raw stream | retained message for field traceability |
| `rawMessageId` | string | ingestion metadata | message identifier |
| `rawIngestedAt` | timestamp | ingestion metadata | ingestion time |

### Budget Stream Normalized Table

This table can receive `budget-usage` and `sp-budget-recommendations`.

| Field | Type | Source/semantics | Description |
| --- | --- | --- | --- |
| `streamDatasetId` | string | Marketing Stream | `budget-usage` or `sp-budget-recommendations` |
| `eventDateTime` | timestamp | Marketing Stream | budget event/recommendation time |
| `reportDate` | date | derived | date |
| `marketplace` | string | Amazon Ads | marketplace |
| `accountId` | string | Amazon Ads | Ads/advertiser account identifier |
| `profileId` | string | Amazon Ads | sponsored-ads profile where applicable |
| `campaignId` | string | Amazon Ads | Campaign identifier |
| `campaignName` | string | entity join | Campaign name |
| `adProduct` | string | API enumeration | advertising product |
| `budgetAmount` | decimal | Amazon Ads | current budget |
| `budgetUsage` | decimal | Marketing Stream | consumed budget or usage |
| `budgetRemaining` | decimal | derived/payload | calculated from budget and usage or read directly if supplied |
| `recommendedBudgetAmount` | decimal | recommendations | recommended budget where applicable |
| `currencyCode` | string | Amazon Ads | currency |
| `rawPayload` | JSON | raw stream | original message |
| `rawMessageId` | string | ingestion metadata | message identifier |
| `rawIngestedAt` | timestamp | ingestion metadata | ingestion time |

## Relationship to MTA and ROI

Marketing Stream is suited to near-real-time operations and aggregate-metric monitoring, not AMC user-path data:

- traffic datasets can provide aggregate impressions, clicks, cost, and dimensions such as ad product, format, placement, Campaign, and Ad Group;
- conversion datasets can provide purchases, sales, and units;
- entity-change datasets can fill Campaign, Ad Group, ad, Target, and state dimensions;
- user-path attribution should rely on AMC privacy-safe aggregate path output rather than treating Marketing Stream as a user-path table;
- Marketing Stream and Amazon Ads reporting are both possible cost/sales sources for ROI and ROAS, but actual subscribed payloads and report schemas must confirm field availability.

## Project Recommendation

Current `modules/mta_attribution` uses two analytical input types:

- AMC path report for paths and conversion Outcomes;
- Amazon Ads report—or a normalized Marketing Stream performance table—for five-segment cost, sales, impressions, and clicks, with CPC assigned to `CLICK` and CPM assigned to `IMPRESSION`.

If Marketing Stream is integrated, add:

```text
raw_stream_messages
normalized_stream_performance
normalized_stream_entities
normalized_stream_budget
```

Then aggregate `normalized_stream_performance` to the current Amazon Ads input contract. This keeps SQS/Firehose payload details out of the attribution scripts and isolates Amazon payload-version changes from the MTA pipeline.

## Sources

- [Amazon Marketing Stream product page](https://advertising.amazon.com/solutions/products/amazon-marketing-stream)
- [Amazon Ads official `ads-advanced-tools-docs`](https://github.com/amzn/ads-advanced-tools-docs)
- [Amazon Marketing Stream resources](https://github.com/amzn/ads-advanced-tools-docs/tree/main/amazon_marketing_stream)
- [Stream SQS CloudFormation template](https://raw.githubusercontent.com/amzn/ads-advanced-tools-docs/main/amazon_marketing_stream/Stream_SQS%20_CF_Template.yaml)
- Local Amazon Ads API snapshot: `/research/amazon/research/AmazonAdsAPIALLMerged_prod_3p_formatted.json`
