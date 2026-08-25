---
title: Proposed Normalized Stream Fields
compact: "Project proposal for normalized Marketing Stream performance, entity, budget-usage, budget-recommendation, and change-event records, including identity, timing, metric, currency, status, and raw-payload retention fields; not an implemented schema."
lang: en-US
---

# Proposed Normalized Stream Fields

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
