---
title: Campaign Identity
description: Canonical Campaign and AdGroup identity classes
compact: "Routes to Campaign and AdGroup, including the campaign's provider and ReportingScope fields and the AdGroup-to-Campaign identifier relationship."
order: 30
lang: en-US
---

# Campaign Identity

These classes identify a provider-independent campaign and its ad groups. `Campaign` carries typed provider and reporting-scope fields; `AdGroup` links to it by `campaign_id`. See the [Canonical Data Model](../index.md) for the complete relationship diagram and source-file contracts.

## Class Index

- [Campaign](./campaign.md): one advertising campaign, independent of product count.
- [Ad Group](./ad-group.md): one ad group linked to exactly one campaign by identifier.
