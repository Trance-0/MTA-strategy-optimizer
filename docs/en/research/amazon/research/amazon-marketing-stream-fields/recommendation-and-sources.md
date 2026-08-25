---
title: Stream Recommendation and Sources
compact: "Explains how near-real-time Marketing Stream records complement rather than replace delayed MTA evidence, recommends raw payload retention plus stable normalized cores, and lists the external sources supporting the research."
lang: en-US
---

# Stream Recommendation and Sources

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
