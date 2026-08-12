---
title: Amazon Marketing Cloud
compact: "External platform background on the AMC clean room and how it differs from Amazon Ads reporting, Amazon Marketing Stream, and Amazon Attribution with its 14-day last-touch rule. Read when reasoning about data-source boundaries; not a build contract."
lang: en-US
---

# Amazon Marketing Cloud (AMC)

Amazon Marketing Cloud is a privacy-safe clean room for Amazon Ads. It permits controlled analysis of pseudonymized Amazon Ads signals, advertiser first-party data, and available extension signals. Accessible results are aggregated anonymous outputs satisfying privacy rules, not downloadable complete user-event logs.

## Boundary with Related Data Sources

- **AMC:** query touchpoints, conversions, and paths inside the clean room and export anonymous aggregates.
- **Amazon Ads reporting / Marketing Stream:** provide Campaign and advertising dimensions plus operational and cost measures such as impressions, clicks, cost, and sales.
- **Amazon Attribution:** measures the effect of off-Amazon marketing on Amazon outcomes; its 14-day last-touch rule is not the project's 14-day contiguous-path rule.

The project simulates AMC-style aggregate paths and joins cost from a separate Amazon Ads table. Event samples exist only for local algorithm demonstration. The [AMC MTA module](../../../attribution/amc-mta-module.md) defines current behavior and fields.

## Reading Entry Points

- [AMC, MTA, and ROI data flow](data-flow.md)
- [Current data contract](../../../datasets/amc-data-contract.md)
- [AMC MTA project introduction](../../../introduction/amc-mta-introduction.md)
- [Historical technical research from 2026-07-06](../research/technical-amazon-attribution-mta-2026-07-06.md)

## Reference Sources

- [Amazon Marketing Cloud](https://advertising.amazon.com/solutions/products/amazon-marketing-cloud)
- [Amazon Ads API: AMC overview](https://advertising.amazon.com/API/docs/en-us/guides/amazon-marketing-cloud/overview)
- [Amazon Attribution](https://advertising.amazon.com/solutions/products/amazon-attribution)
- [Amazon Marketing Stream](https://advertising.amazon.com/solutions/products/amazon-marketing-stream)
