---
title: Work Log
description: Who is involved in this project, what they own, and where their day-by-day record lives
compact: "Roster of everyone involved: yao-LLL (Jiahao Yao) attribution and strategy models before 2026-08-08, Trance-0 (Zheyuan Wu) project manager since, tianlc6-design (Tianle Chen) SQL database, Willow-sakura (Yi Liu) evaluation, Yayu Yu knowledge base. Read to find who owns an area."
order: 1
---

# Work Log

This section records **who** did the work and **when**. It is the counterpart to the [version log](../version/), which records **what** changed in the repository.

Each person owns one page. Entries are reverse-chronological `## YYYY-MM-DD` sections with at most three bullet points each, following the scheme established by the project's original work log.

## People

### [`yao-LLL`](./JiahaoYao.md)

- Name: Jiahao Yao
- Responsibility: Development of the Multi-Touch Attribution (MTA) models (Markov and Shapley) and the current strategy model
- Active period: Until 2026-08-08

### [`Trance-0`](./ZheyuanWu.md)

- Name: Zheyuan Wu
- Responsibility: Project manager. Pipeline development, data simulation with the earlier data-collection groups, integration, and algorithm testing: the Deep Neural Network (DNN) attribution model, and an ongoing review of the strategy model
- Active period: Since 2026-08-08

### [`tianlc6-design`](./TianleChen.md)

- Name: Tianle Chen
- Responsibility: Structured Query Language (SQL) database creation; evaluation module with Yi Liu
- Active period: Ongoing

### [`Willow-sakura`](./YiLiu.md)

- Name: Yi Liu
- Responsibility: Evaluation module with Tianle Chen
- Active period: Ongoing

### [`Yayu Yu`](./YayuYu.md)

- Name: Yayu Yu
- Responsibility: Knowledge base building, ontology evaluation, and research
- Active period: Ongoing

The 2026-08-08 boundary marks the handover of development ownership from Jiahao Yao to Zheyuan Wu. Work recorded before that date under the attribution and strategy modules belongs to the earlier author; the Git history preserves the exact authorship.

## Areas and Owning Modules

### Attribution models: Markov, path-level Shapley

- Owner: Jiahao Yao
- Where the work lands: `modules/mta_attribution/`

### Strategy model, current version

- Owner: Jiahao Yao, under review by Zheyuan Wu
- Where the work lands: `modules/mta_strategy_recommendation/`

### Pipeline, integration, script centralization

- Owner: Zheyuan Wu
- Where the work lands: `script/`, `modules/mta_standard/`

### Data simulation

- Owner: Zheyuan Wu, with the earlier data-collection groups
- Where the work lands: `external/mta_sim_dataset/`, `modules/*/data/simulated/`

### Algorithm testing, DNN attribution

- Owner: Zheyuan Wu
- Where the work lands: `modules/mta_attribution/src/dnn_attribution_model.py`

### SQL database

- Owner: Tianle Chen
- Where the work lands: External service schemas; see [campaign](../en/market-simulation/campaign-data-model.md) and [product](../en/market-simulation/product-data-model.md) data models

### Evaluation module

- Owner: Tianle Chen, Yi Liu
- Where the work lands: `modules/mta_strategy_evaluation/`, specified in [strategy evaluation](../en/strategy-evaluation/)

### Knowledge base, ontology, research

- Owner: Yayu Yu
- Where the work lands: [Research](../en/research/)

## Conventions

- One page per person, named in PascalCase after the person, for example `ZheyuanWu.md`.
- Reverse-chronological `## YYYY-MM-DD` sections, each with `### Completed` and optionally `### Next`.
- At most three bullet points per section. Merge related work rather than adding a fourth.
- A page belongs to its owner. Do not edit, restructure, or translate another person's page.
- An agent must propose today's entry and receive explicit confirmation from its owner before writing it, and may write only to its owner's page.
