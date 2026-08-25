---
title: Official Stream Datasets and Shapes
compact: "Publicly confirmed Amazon Marketing Stream subscription identifiers, delivery through AWS SQS or Firehose, envelope behavior, and available traffic, conversion, budget, recommendation, and entity-change categories without inventing undocumented payload fields."
lang: en-US
---

# Official Stream Datasets and Shapes

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
