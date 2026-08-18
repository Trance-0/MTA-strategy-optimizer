---
title: Composed Episodes and Evaluation Isolation
description: Model-facing campaign episodes and isolated evaluation ground truth
compact: "Routes to CampaignEpisode, EvaluationGroundTruth, and EvaluationEpisode: model-facing composition of campaign observations, simulator-known truth kept in evaluation-only code, and their evaluation wrapper."
order: 70
lang: en-US
---

# Composed Episodes and Evaluation Isolation

These classes compose campaign records for a future model while keeping simulator-known ground truth structurally unreachable from model-facing code. See the [Canonical Data Model](../index.md) for the complete relationship diagram and source-file contracts.

## Class Index

- [Campaign Episode](./campaign-episode.md): one campaign's decision-time and observed-after-treatment records.
- [Evaluation Ground Truth](./evaluation-ground-truth.md): simulator-known truth available only to evaluation code.
- [Evaluation Episode](./evaluation-episode.md): composition of a CampaignEpisode and its EvaluationGroundTruth.
