---
stepsCompleted: [1, 2]
inputDocuments:
  - docs/research/amazon/research/amazon调研.docx
  - docs/research/amazon/research/Amazon_Attribution_Report_FULL.docx
workflowType: research
lastStep: 1
research_type: technical
research_topic: Amazon Attribution and an Amazon-only MTA demonstration
research_goals: Summarize two research reports, verify and supplement them with official Amazon material, and explain data, attribution boundaries, and implementation recommendations through examples.
user_name: ericson
date: 2026-07-06
web_research_enabled: true
source_verification: true
---

# Research Report: Technical

> Historical research snapshot: this page records research and implementation recommendations as of 2026-07-06. Some directories and input structures differ from current code. The [AMC MTA module](../../../attribution/amc-mta-module.md) and [data contract](../../../datasets/amc-data-contract.md) govern current behavior.

**Date:** 2026-07-06
**Author:** ericson
**Research type:** technical

## Research Overview

The original workflow left this section as a placeholder: `[Research overview and methodology will be appended here]`. The confirmed scope and methodology are preserved in the next section.

## Technical Research Scope Confirmation

**Research topic:** Amazon Attribution and an Amazon-only MTA demonstration

**Research goals:** summarize two research reports, verify and supplement them with official Amazon material, and explain data, attribution boundaries, and demonstration implementation through concrete examples.

**Technical research scope:**

- architecture analysis: responsibility boundaries among Amazon Attribution, AMC, the Ads API, and MTA;
- implementation approaches: demonstration data structures, attribution methods, result interpretation;
- technology stack: official Amazon measurement and data products;
- integration patterns: off-Amazon channels, Amazon conversion, AMC, and API connections;
- performance considerations: data grain, privacy thresholds, aggregation limits, reproducibility.

**Research methodology:**

- verify claims against then-current official Amazon public material;
- distinguish verified facts, reasonable interpretation, and unconfirmed statements in local reports;
- cross-check important attribution conclusions across sources;
- explain abstractions with specific paths and numeric examples.

**Scope confirmed:** 2026-07-06.

## Technology Stack Analysis

### Amazon Measurement and Data Platforms

The Amazon capabilities in this scenario should be treated as three different platforms, not one API:

1. **Amazon Attribution:** measures how off-Amazon search, social, display, video, email, affiliate, and influencer activity affects Amazon detail-page views, add-to-cart events, purchases, and sales. Official documentation describes Attribution tags connecting off-Amazon advertising with Amazon conversions, with results available through the console, downloadable reports, or the Amazon Attribution API.
2. **Amazon Marketing Cloud (AMC):** a privacy-safe data clean room based on AWS Clean Rooms that can analyze Amazon Ads signals and advertiser-provided pseudonymized signals. AMC can analyze event- and user-level signals internally but exports only aggregate anonymous results satisfying privacy thresholds.
3. **Amazon Ads API:** REST and OAuth 2.0 interfaces for managing and reporting Amazon advertising, including Sponsored Ads, Amazon DSP, AMC, and Amazon Marketing Stream. The project's OpenAPI snapshot mainly describes management entities—Campaigns, Ad Groups, ads, Targets, budgets, bids, and DSP forecasts—and cannot replace Attribution or AMC conversion paths.

Sources:

- [Amazon Attribution](https://advertising.amazon.com/en-us/solutions/products/amazon-attribution/)
- [Amazon Marketing Cloud](https://advertising.amazon.com/solutions/products/amazon-marketing-cloud)
- [Amazon Ads API](https://advertising.amazon.com/about-api)
- [AMC API availability through Amazon Ads API](https://advertising.amazon.com/resources/whats-new/amc-api-available-on-amazon-ads-api/)

### Demonstration Programming Technology at the Time of Research

The legacy demonstration reviewed on 2026-07-06 used the Python standard library:

- CSV exchanged model input and attribution output;
- Python modules implemented a Markov chain and simplified Shapley allocation;
- Scalable Vector Graphics (SVG) provided reproducible charts;
- a fixed random seed drove bootstrap stability analysis.

That stack was appropriate for a low-dependency, reproducible demonstration. The research recommended preserving the model interface and adding a data-adaptation layer before integrating real Amazon data. Amazon Attribution downloads or API data and AMC query aggregates would first be normalized for aggregate performance analysis; only privacy-compliant path aggregates would proceed through path construction to Markov and Shapley.

Current AMC MTA instead uses five-segment interactions, five CSV model/governance outputs, and a governance decision. It has no SVG or bootstrap-stability artifact. See the [current module](../../../attribution/amc-mta-module.md).

### Data and Storage Technology

The demonstration uses module-local CSV under `modules/mta_attribution/data/simulated/`.

The research distinguishes three data types:

| Data type | Recommended format | Purpose |
| --- | --- | --- |
| Amazon Attribution aggregate report | CSV | funnel and conversion analysis by channel, publisher, Campaign, Ad Group, ASIN |
| AMC-style anonymous aggregate path | CSV | five-segment Markov and path-level Shapley demonstration |
| model output | CSV | attribution, model differences, support, governance |

For production, immutable raw API snapshots should precede normalized analytical tables. AMC user-level signals cannot be exported directly; preserve query version, parameters, and aggregate results rather than assuming access to complete user logs.

### API and Authentication

The project OpenAPI snapshot describes:

- REST/JSON;
- OAuth 2.0 authorization-code flow;
- North America, Europe, and Far East regional endpoints;
- bulk query and management interfaces for Campaigns, Ad Groups, ads, and Targets.

Official Amazon material also states that API access requires application and approval. Possessing an OpenAPI file does not imply access to an advertising account or real data.

### Technology Adoption Recommendation

The research recommended Python, CSV snapshots, versioned configuration, and reproducible run scripts for the demonstration stage, without adding a database, microservice, or real-time stream.

After obtaining real Amazon Attribution reports, first build an aggregate-analysis adapter. After obtaining AMC access and privacy-compliant path aggregates, replace synthetic paths. Do not force Campaign Management data into attribution merely to demonstrate an API when that data cannot support MTA paths.

### Confidence and Open Verification

- **High confidence:** Amazon Attribution measures off-Amazon marketing effects on Amazon outcomes; official material listed a unified 14-day attribution window and click, detail-page view, add-to-cart, purchase, sales, and new-to-brand measures.
- **High confidence:** AMC supports privacy-safe analysis of event/user signals but exports only aggregate anonymous results.
- **Medium confidence:** a local report claimed a 14-day click window plus a seven-day view window. The official Attribution pages found during the research stated a 14-day attribution window but did not confirm the seven-day view rule, so the report did not adopt it as a default.
- **High confidence:** the project OpenAPI describes mainly advertising-management objects and cannot independently generate cross-touchpoint user paths.

## Integration Patterns Analysis

### Amazon Attribution Tag Integration

The basic pattern assigns a unique Attribution tag to every off-Amazon strategy to be measured and adds the tag parameters to the final landing URL. Official material states that each Ad Group receives a unique tag and that reporting can be organized by publisher, channel, Campaign, creative, Keyword, or product.

A user clicks a TikTok advertisement URL containing an Attribution tag and reaches an Amazon detail page or Store. Amazon can then aggregate the resulting detail-page view, add-to-cart, purchase, and product-sales events into an Amazon Attribution report.

Sources:

- [Amazon Attribution basics](https://advertising.amazon.com/zh-cn/library/guides/basics-of-amazon-attribution)
- [Amazon Attribution 14-day last-touch method](https://advertising.amazon.com/help/G4YK9L2G4NXDD7SC)

#### Example: Tags Determine Analytical Grain

Suppose a TikTok Campaign has two creatives:

For example, the `Summer Launch` Campaign can contain `TikTok-video-A` using `tag_A` and `TikTok-video-B` using `tag_B`.

If both creatives share one tag, reporting can reveal only TikTok's combined purchases. Separate tags permit a comparison between video A and B. Tag design is data-model design: detail lost through coarse tags cannot be reconstructed later.

### Downloaded Report and API Integration

Official Amazon Attribution offered:

- visual reports in the advertising console;
- on-demand or scheduled Excel reports;
- Amazon Attribution API integrated into Amazon Ads API.

The four principal report types described were:

1. Campaign report: daily Campaign and Ad Group performance;
2. Publisher report: aggregated channel and publisher performance;
3. Keyword/creative report: Keyword or creative performance for supported bulk-created activity;
4. Product report: promoted products, brand-halo products, and aggregate views.

Source: [Amazon Attribution reports and measures](https://advertising.amazon.com/zh-cn/library/guides/basics-of-amazon-attribution).

The recommended demonstration adapter maps and validates a downloaded Excel/CSV report, writes `amazon_attribution_performance.csv`, and uses that normalized aggregate table for funnel, ROAS, and Campaign comparisons.

This process creates an aggregate performance table and does not automatically generate a user-touchpoint sequence.

### AMC Query Integration

AMC can address path questions that Amazon Attribution aggregate reports cannot. Official material states that AMC can query event- and user-level signals across sources, but highly sensitive fields such as `user_id` cannot appear in final output, and results must satisfy aggregation thresholds.

Sources:

- [AMC product and privacy](https://advertising.amazon.com/solutions/products/amazon-marketing-cloud)
- [AMC aggregation thresholds](https://advertising.amazon.com/help/G6ZYAPTTTE54UQPP)

The correct pattern is therefore to aggregate paths inside AMC rather than export user logs:

An AMC SQL or analytical template should aggregate internal pseudonymous events by path. Example aggregates might contain `TikTok > Facebook > Google` with 180 users and 24 conversions, `Google` with 420 users and 63 conversions, and `Facebook > Google` with 250 users and 31 conversions. Only aggregates satisfying privacy thresholds should be exported as Markov MTA input.

The TikTok/Facebook/Google example is possible only if the advertiser supplies permitted pseudonymized first-party signals to AMC and those signals can connect to Amazon signals within policy. Amazon Attribution downloads alone cannot reconstruct such paths.

### MTA Model Adaptation at the Time of Research

The legacy code reviewed by the research expected `markov_user_paths.csv`, `shapley_user_channel_sets.csv`, and `channel_spend.csv`.

The recommendation was two adapters rather than direct algorithm edits:

| Adapter | Input | Output | Limitation |
| --- | --- | --- | --- |
| `AmazonAttributionAggregateAdapter` | Amazon Attribution aggregate report | Channel/Campaign funnel and ROI analysis | Does not create real MTA paths |
| `AmazonPathAggregateAdapter` | AMC aggregate paths or explicitly labeled synthetic paths | Path tables required by Markov/Shapley | Must record provenance and whether paths are synthetic |

Those names describe the legacy design. Current code uses the AMC aggregate and Amazon Ads contracts documented elsewhere.

### Attribution Time and Data Updates

Official material cited by the research stated:

- Amazon Attribution used 14-day last touch;
- conversions could take approximately 12 hours to appear;
- attributed measures for a report date could remain incomplete until the lookback window closed;
- Amazon could restate attribution, changing historical attributed results.

Sources:

- [14-day last-touch rule](https://advertising.amazon.com/help/G4YK9L2G4NXDD7SC)
- [Conversion delay and window completeness](https://advertising.amazon.com/help/GX7KDKHMWQYMJ385)
- [Attribution restatement](https://advertising.amazon.com/help/G22MA5YPN9KKT7TM)

The research therefore required snapshots to contain `report_date`, `data_as_of`, `attribution_window_days`, and `report_version`.

#### Example: Why Same-Day Conclusions Are Unsafe

A TikTok advertisement receives 100 clicks on July 1. The July 2 report shows three purchases; by July 10 it may backfill to eight. If a model overwrites old data daily without `data_as_of`, it cannot explain why the same Campaign's ROAS changed later.

### Integration Security and Permissions

- Amazon Ads API uses OAuth 2.0.
- API access requires application and approval.
- Advertising-account access, Attribution permission, and AMC-instance permission are separate prerequisites.
- Tokens, advertiser identifiers, and profile information must not be committed to the repository.
- Final AMC queries must not re-identify users.

### Integration Patterns Not Recommended

- Do not treat Campaign Management OpenAPI as an attribution-event source.
- Do not fabricate “real user paths” from aggregate Attribution reports.
- Do not treat Amazon last-touch output as the ground-truth label for Markov or Shapley.
- Do not claim that a demonstration can export raw AMC `user_id`.
- Do not introduce message queues, microservices, or real-time stream processing for the current scale.

The original workflow ended with a placeholder comment indicating that later research steps could append content. No additional substantive section was present in the legacy file.
