---
title: Amazon Marketing Stream Field Research
compact: "External research on Amazon Marketing Stream: the 19 StreamDatasetId subscriptions such as sp-traffic, sb-clickstream, budget-usage, adsp-campaigns, SQS and Firehose delivery, plus proposed-only normalized performance, entity, and budget tables. Design proposal, not implemented schema."
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

### `sp-traffic`

- **Data category:** Sponsored Products traffic
- **Suitable use:** hourly SP impressions, clicks, and traffic performance

### `sp-conversion`

- **Data category:** Sponsored Products conversion
- **Suitable use:** SP conversions, sales, and orders

### `budget-usage`

- **Data category:** sponsored-ads budget usage
- **Suitable use:** spend monitoring, pacing, budget-exhaustion warnings

### `sd-traffic`

- **Data category:** Sponsored Display traffic
- **Suitable use:** hourly SD impressions, clicks, traffic performance

### `sd-conversion`

- **Data category:** Sponsored Display conversion
- **Suitable use:** SD conversions, sales, orders

### `sponsored-ads-campaign-diagnostics-recommendations`

- **Data category:** Campaign diagnostics/recommendations
- **Suitable use:** Campaign health, diagnostics, optimization suggestions

### `campaigns`

- **Data category:** sponsored-ads Campaign entity changes
- **Suitable use:** Campaign creation, status, configuration changes

### `adgroups`

- **Data category:** sponsored-ads Ad Group changes
- **Suitable use:** Ad Group configuration changes

### `ads`

- **Data category:** sponsored-ads ad changes
- **Suitable use:** ad, creative, advertised-product changes

### `targets`

- **Data category:** sponsored-ads targeting changes
- **Suitable use:** Keyword, product, Audience Targeting changes

### `sb-traffic`

- **Data category:** Sponsored Brands traffic
- **Suitable use:** hourly SB impressions, clicks, traffic performance

### `sb-conversion`

- **Data category:** Sponsored Brands conversion
- **Suitable use:** SB conversions, sales, orders

### `sb-clickstream`

- **Data category:** Sponsored Brands clickstream
- **Suitable use:** SB click-event stream, generally closer to events than aggregate traffic

### `sb-rich-media`

- **Data category:** Sponsored Brands rich media
- **Suitable use:** SB video and rich-media interaction data

### `adsp-campaigns`

- **Data category:** Amazon DSP Campaign changes
- **Suitable use:** DSP Campaign change stream

### `adsp-campaign-flights`

- **Data category:** Amazon DSP flight changes
- **Suitable use:** flight, pacing, budget-period changes

### `adsp-adgroups`

- **Data category:** Amazon DSP Ad Group changes
- **Suitable use:** DSP Ad Group/line-item changes

### `adsp-adgroup-targets`

- **Data category:** Amazon DSP target changes
- **Suitable use:** DSP Target, Audience, inventory changes

### `sp-budget-recommendations`

- **Data category:** Sponsored Products budget recommendations
- **Suitable use:** SP budget optimization and opportunity identification

## Data Shape

Amazon Marketing Stream is not an AMC submit-SQL-and-return-an-aggregate-report pattern. It is a continuous subscription:

- create a subscription through the Amazon Ads API;
- specify `StreamDatasetId`, realm/region, and destination;
- choose AWS SQS or Amazon Data Firehose as destination;
- receive ongoing messages for the dataset;
- use hourly performance datasets for near-real-time monitoring, dayparting, pacing, and anomaly detection;
- use Campaign/Ad Group/ad/target datasets as entity-change streams for configuration snapshots, auditing, and state synchronization.

## Publicly Confirmable Data Categories

### traffic metrics

- **Dataset:** `sp-traffic`, `sb-traffic`, `sd-traffic`
- **Publicly confirmable content:** hourly performance/traffic changes, generally including impressions and clicks
- **Suitability for MTA:** aggregate media exposure/engagement input

### conversion metrics

- **Dataset:** `sp-conversion`, `sb-conversion`, `sd-conversion`
- **Publicly confirmable content:** conversion changes, generally purchases, sales, units
- **Suitability for MTA:** supplemental Outcomes; attribution semantics still require care

### budget usage

- **Dataset:** `budget-usage`
- **Publicly confirmable content:** budget consumption
- **Suitability for MTA:** ROI/ROAS and pacing, not user paths

### recommendations

- **Dataset:** `sp-budget-recommendations`, `sponsored-ads-campaign-diagnostics-recommendations`
- **Publicly confirmable content:** budget recommendations and Campaign diagnostics
- **Suitability for MTA:** optimization input, not the principal MTA fact table

### entity changes

- **Dataset:** `campaigns`, `adgroups`, `ads`, `targets`
- **Publicly confirmable content:** Campaign/Ad Group/ad/target configuration changes
- **Suitability for MTA:** dimensions and state snapshots

### Sponsored Brands event/media

- **Dataset:** `sb-clickstream`, `sb-rich-media`
- **Publicly confirmable content:** clickstream and rich-media activity
- **Suitability for MTA:** potential SB touchpoint detail; confirm fields against each schema

### Amazon DSP changes

- **Dataset:** `adsp-campaigns`, `adsp-campaign-flights`, `adsp-adgroups`, `adsp-adgroup-targets`
- **Publicly confirmable content:** Campaign/flight/Ad Group/target changes
- **Suitability for MTA:** DSP dimensions and state synchronization, not conversion paths

## Project-Proposed Normalized Fields

Raw payload schemas differ by dataset. The recommendation is not to force every payload into one fixed CSV, but to land each dataset in a bronze/raw layer and transform it into common analytics tables.

### Performance Stream Normalized Table

This table can receive `sp-traffic`, `sb-traffic`, `sd-traffic`, `sp-conversion`, `sb-conversion`, and `sd-conversion` and align them with Amazon Ads reporting.

#### `streamDatasetId`

- **Type:** string
- **Source/semantics:** Marketing Stream
- **Description:** raw dataset such as `sp-traffic` or `sb-conversion`

#### `eventDateTime`

- **Type:** timestamp
- **Source/semantics:** Marketing Stream
- **Description:** message or metric time

#### `reportDate`

- **Type:** date
- **Source/semantics:** derived
- **Description:** date in the account or project-standard timezone

#### `reportHour`

- **Type:** integer
- **Source/semantics:** derived
- **Description:** 0-23 for hourly/intraday analysis

#### `marketplace`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** marketplace such as `US`

#### `accountId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** Ads/advertiser account identifier

#### `profileId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** common sponsored-ads profile identifier when the dataset provides it

#### `campaignId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** Campaign identifier

#### `campaignName`

- **Type:** string
- **Source/semantics:** entity join
- **Description:** filled from Campaign change stream or report dimension

#### `campaignState`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `ENABLED`, `PAUSED`, `ARCHIVED`

#### `adGroupId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** Ad Group identifier

#### `adGroupName`

- **Type:** string
- **Source/semantics:** entity join
- **Description:** filled from Ad Group change stream/report dimension

#### `adId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** ad, creative, or product-ad identifier depending on dataset

#### `targetId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** Keyword, product, or Audience target

#### `keywordId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** used when Keyword-grain data is available

#### `asin`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** advertised or purchased Amazon Standard Identification Number depending on data

#### `adProduct`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `SPONSORED_PRODUCTS`, `SPONSORED_BRANDS`, `SPONSORED_DISPLAY`, `AMAZON_DSP`, etc.

#### `adType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `PRODUCT_AD`, `VIDEO`, `DISPLAY`, `COMPONENT`, `AUDIO`, etc.

#### `creativeType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `IMAGE`, `VIDEO`

#### `inventoryType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `DISPLAY`, `ONLINE_VIDEO`, `STREAMING_TV`, `AUDIO`, `PODCAST`, etc.

#### `placement`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `TOP_OF_SEARCH`, `PRODUCT_PAGE`, `REST_OF_SEARCH`, etc.

#### `normalizedTouchpoint`

- **Type:** string
- **Source/semantics:** project-derived
- **Description:** five-segment key such as `SPONSORED_BRANDS:VIDEO:TOP_OF_SEARCH:VIDEO:CLICK`

#### `costType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `CPC`, `CPM`, `VCPM`, `FIXED_PRICE`

#### `currencyCode`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** for example `USD`

#### `impressions`

- **Type:** integer
- **Source/semantics:** traffic dataset
- **Description:** impression count

#### `clicks`

- **Type:** integer
- **Source/semantics:** traffic dataset
- **Description:** click count

#### `cost`

- **Type:** decimal
- **Source/semantics:** traffic/spend
- **Description:** ad spend; confirm its presence from subscribed raw payloads

#### `purchases`

- **Type:** integer
- **Source/semantics:** conversion dataset
- **Description:** purchases/orders under Amazon's attribution window

#### `sales`

- **Type:** decimal
- **Source/semantics:** conversion dataset
- **Description:** sales under Amazon's attribution window

#### `unitsSold`

- **Type:** integer
- **Source/semantics:** conversion dataset
- **Description:** units sold

#### `rawMessageId`

- **Type:** string
- **Source/semantics:** ingestion metadata
- **Description:** identifier created by SQS, Firehose, or ingestion layer

#### `rawIngestedAt`

- **Type:** timestamp
- **Source/semantics:** ingestion metadata
- **Description:** data-lake/warehouse ingestion time

### Entity Stream Normalized Table

This table can receive `campaigns`, `adgroups`, `ads`, `targets`, `adsp-campaigns`, `adsp-campaign-flights`, `adsp-adgroups`, and `adsp-adgroup-targets`.

#### `streamDatasetId`

- **Type:** string
- **Source/semantics:** Marketing Stream
- **Description:** raw dataset

#### `eventDateTime`

- **Type:** timestamp
- **Source/semantics:** Marketing Stream
- **Description:** entity-change time

#### `marketplace`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** marketplace

#### `accountId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** Ads/advertiser account identifier

#### `profileId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** sponsored-ads profile when applicable

#### `entityType`

- **Type:** string
- **Source/semantics:** derived
- **Description:** `campaign`, `adGroup`, `ad`, `target`, `flight`

#### `entityId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** current entity identifier

#### `parentEntityId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** parent such as Campaign ID for an Ad Group

#### `entityName`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** entity name where applicable

#### `state`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `ENABLED`, `PAUSED`, `ARCHIVED`

#### `adProduct`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** advertising product

#### `adType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** ad type where applicable

#### `creativeType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** creative type where applicable

#### `inventoryType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** DSP/video/audio inventory type where applicable

#### `placement`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** sponsored-ads placement where applicable

#### `costType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** billing method where applicable

#### `budgetAmount`

- **Type:** decimal
- **Source/semantics:** Amazon Ads
- **Description:** Campaign/flight budget where applicable

#### `budgetType`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** daily/lifetime budget type where applicable

#### `bidAmount`

- **Type:** decimal
- **Source/semantics:** Amazon Ads
- **Description:** target/Keyword bid where applicable

#### `targetType`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** `KEYWORD`, `PRODUCT`, `AUDIENCE`, `DEVICE`, etc.

#### `rawPayload`

- **Type:** JSON
- **Source/semantics:** raw stream
- **Description:** retained message for field traceability

#### `rawMessageId`

- **Type:** string
- **Source/semantics:** ingestion metadata
- **Description:** message identifier

#### `rawIngestedAt`

- **Type:** timestamp
- **Source/semantics:** ingestion metadata
- **Description:** ingestion time

### Budget Stream Normalized Table

This table can receive `budget-usage` and `sp-budget-recommendations`.

#### `streamDatasetId`

- **Type:** string
- **Source/semantics:** Marketing Stream
- **Description:** `budget-usage` or `sp-budget-recommendations`

#### `eventDateTime`

- **Type:** timestamp
- **Source/semantics:** Marketing Stream
- **Description:** budget event/recommendation time

#### `reportDate`

- **Type:** date
- **Source/semantics:** derived
- **Description:** date

#### `marketplace`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** marketplace

#### `accountId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** Ads/advertiser account identifier

#### `profileId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** sponsored-ads profile where applicable

#### `campaignId`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** Campaign identifier

#### `campaignName`

- **Type:** string
- **Source/semantics:** entity join
- **Description:** Campaign name

#### `adProduct`

- **Type:** string
- **Source/semantics:** API enumeration
- **Description:** advertising product

#### `budgetAmount`

- **Type:** decimal
- **Source/semantics:** Amazon Ads
- **Description:** current budget

#### `budgetUsage`

- **Type:** decimal
- **Source/semantics:** Marketing Stream
- **Description:** consumed budget or usage

#### `budgetRemaining`

- **Type:** decimal
- **Source/semantics:** derived/payload
- **Description:** calculated from budget and usage or read directly if supplied

#### `recommendedBudgetAmount`

- **Type:** decimal
- **Source/semantics:** recommendations
- **Description:** recommended budget where applicable

#### `currencyCode`

- **Type:** string
- **Source/semantics:** Amazon Ads
- **Description:** currency

#### `rawPayload`

- **Type:** JSON
- **Source/semantics:** raw stream
- **Description:** original message

#### `rawMessageId`

- **Type:** string
- **Source/semantics:** ingestion metadata
- **Description:** message identifier

#### `rawIngestedAt`

- **Type:** timestamp
- **Source/semantics:** ingestion metadata
- **Description:** ingestion time

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

If Marketing Stream is integrated, add four explicit layers: `raw_stream_messages`, `normalized_stream_performance`, `normalized_stream_entities`, and `normalized_stream_budget`.

Then aggregate `normalized_stream_performance` to the current Amazon Ads input contract. This keeps SQS/Firehose payload details out of the attribution scripts and isolates Amazon payload-version changes from the MTA pipeline.

## Sources

- [Amazon Marketing Stream product page](https://advertising.amazon.com/solutions/products/amazon-marketing-stream)
- [Amazon Ads official `ads-advanced-tools-docs`](https://github.com/amzn/ads-advanced-tools-docs)
- [Amazon Marketing Stream resources](https://github.com/amzn/ads-advanced-tools-docs/tree/main/amazon_marketing_stream)
- [Stream SQS CloudFormation template](https://raw.githubusercontent.com/amzn/ads-advanced-tools-docs/main/amazon_marketing_stream/Stream_SQS%20_CF_Template.yaml)
- Local Amazon Ads API snapshot: `/research/amazon/research/AmazonAdsAPIALLMerged_prod_3p_formatted.json`
