---
title: Amazon Ads Five-Segment Cost Sample
lang: en-US
---

# Amazon Ads Five-Segment Cost Sample

`data/simulated/amazon_ads_report_sample.csv` is Amazon Ads-style performance and cost data aggregated daily from `synthetic_user_events_sample.csv`. The sample window is `2026-01-01` through `2026-03-31`: 90 days and 1,530 rows. The first CSV row contains field names, and the second contains Chinese field descriptions that the reader skips automatically.

## Fields and Join Key

- Scope: `reportDate`, `marketplace`, `accountId`, `currencyCode`.
- Advertising dimensions: `adProduct`, `adType`, `creativeType`, `inventoryType`, `placement`.
- Interaction and billing: `interaction_type`, `cost_type`.
- Derived join key: `normalizedTouchpoint`.
- Performance: `impressions`, `clicks`, `cost`, `purchases`, `sales`.

`normalizedTouchpoint` must exactly equal the key recomputed by the program from the raw dimensions and `interaction_type`:

`AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`

`INTERACTION_TYPE` may only be `IMPRESSION` or `CLICK`. Run `uv run python -X utf8 -B script/validate_data_alignment.py` from the repository root to validate the account, currency, window, five-segment touchpoint set, and daily coverage.

This file is a five-segment summary for attribution cost joins within the Campaign Group scope; it is not a Campaign/Ad Group management-structure sample. `AD_PRODUCT` in the five-segment key is an attribution observation dimension. The business tree remains `Campaign Group → Campaign → Ad Group → Keyword/SKU`, and `ad_product` is stored only on Campaign. See [strategy simulated inputs](strategy-simulated-data.md) for the hierarchy sample.

## Cost and Platform-Conversion Assignment

- Positive `CPC` cost is allowed only on `CLICK` rows.
- Positive `CPM` cost is allowed only on `IMPRESSION` rows.
- Non-billable interaction rows have zero cost; the base ad's cost is not copied to them.
- Platform `purchases` and `sales` are assigned only to `CLICK` rows.

Sample impressions, clicks, and costs are aggregated directly from user events. Platform `purchases` and `sales` derive from the last eligible CLICK in each journey. The Amazon Ads aggregate table is still not used to reconstruct AMC paths; the two merely share the same simulated fact source. `reported_purchases` does not replace the AMC Outcome definition. Efficiency metrics are calculated on the same five-segment row and are empty when cost is zero.
