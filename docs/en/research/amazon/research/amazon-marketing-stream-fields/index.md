---
title: Amazon Marketing Stream Field Research
compact: "External research on Amazon Marketing Stream subscriptions, delivery and data shape, plus project-proposed normalized performance, entity, and budget fields. Research proposal only; it does not define an implemented database schema."
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

The evidence divides into [official subscriptions and publicly confirmed shapes](./official-datasets-and-shapes.md), the [project-proposed normalized fields](./proposed-normalized-fields.md), and [MTA relationship, recommendation, and sources](./recommendation-and-sources.md). The proposal remains non-binding until an owning implementation specification adopts it.
