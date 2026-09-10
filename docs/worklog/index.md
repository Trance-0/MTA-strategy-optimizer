---
title: Work Log
description: Who is involved in this project, what they own, and where their day-by-day record lives
compact: "Roster of everyone involved, with each person's Git author identity: yao-LLL (Jiahao Yao) attribution and strategy models before 2026-08-08, Trance-0 (Zheyuan Wu) project manager since, tianlc6-design (Tianle Chen) SQL database, Willow-sakura (Yi Liu) evaluation, Yayu Yu knowledge base, kim383706382-ship-it (Chenghao Jin) Data Generator."
order: 1
---

# Work Log

This section records **who** did the work and **when**. It is the counterpart to the [version log](../version/), which records **what** changed in the repository.

Each person owns one page. Entries are reverse-chronological `## YYYY-MM-DD` sections with at most three bullet points each, following the scheme established by the project's original work log.

## People

### [`yao-LLL`](./JiahaoYao.md)

- Name: Jiahao Yao
- Git author: `yao-LLL <ericsonyao@outlook.com>`, with early commits as `YAO JIAHAO <yao@YAO-JIAHAOdeMacBook-Air-3.local>`
- Responsibility: Development of the Multi-Touch Attribution (MTA) models (Markov and Shapley) and the current strategy model
- Active period: Until 2026-08-08

### [`Trance-0`](./ZheyuanWu.md)

- Name: Zheyuan Wu
- Git author: `Zheyuan Wu <60459821+Trance-0@users.noreply.github.com>`
- Responsibility: Project manager. The MTA-SIM pipeline and `mta_common` canonical data model, the Deep Neural Network (DNN) attribution model and an ongoing review of the strategy model, the Vue dashboard and Flask backend, container and host deployment with the repository mirrors, and the English documentation set with its repository rules
- Active period: Since 2026-08-08

### [`tianlc6-design`](./TianleChen.md)

- Name: Tianle Chen
- Git author: none in this repository; the database work lives in external service schemas
- Responsibility: Structured Query Language (SQL) database creation; evaluation module with Yi Liu
- Active period: Ongoing

### [`Willow-sakura`](./YiLiu.md)

- Name: Yi Liu
- Git author: `Willow-sakura <2934356936@qq.com>`
- Responsibility: Evaluation module with Tianle Chen
- Active period: Ongoing

### [`Yayu Yu`](./YayuYu.md)

- Name: Yayu Yu
- Git author: `Yayu Yu <yyy688997@gmail.com>`
- Responsibility: Knowledge base building, ontology evaluation, and research
- Active period: Ongoing

### [`kim383706382-ship-it`](./ChenghaoJin.md)

- Name: Chenghao Jin
- Git author: `kim383706382-ship-it <kim383706382@gmail.com>`
- Responsibility: Data Generator configuration workflow and data simulation: the Guided/JSON configuration editor, the generator's backend preflight contract, and its run lifecycle
- Active period: Since 2026-09-06

The 2026-08-08 boundary marks the handover of development ownership from Jiahao Yao to Zheyuan Wu. Work recorded before that date under the attribution and strategy modules belongs to the earlier author; the Git history preserves the exact authorship.

## Areas and Owning Modules

### Attribution models: Markov, path-level Shapley

- Owner: Jiahao Yao
- Where the work lands: `modules/mta_attribution/`

### Strategy model, current version

- Owner: Jiahao Yao, under review by Zheyuan Wu
- Where the work lands: `modules/mta_strategy_recommendation/`

### Pipeline, integration, module-owned commands

- Owner: Zheyuan Wu
- Where the work lands: `modules/mta_standard/`, `backend/`, and each module's own `src/` entry points

### Data simulation

- Owner: Zheyuan Wu, with the earlier data-collection groups
- Where the work lands: `external/mta_sim_dataset/`, `modules/*/data/simulated/`

### Data Generator configuration workflow

- Owner: Chenghao Jin
- Where the work lands: `backend/services/data_generator.py`, `backend/api/data_generator.py`, `dashboard/src/generator/`, specified in [Data Generator](../en/dashboard/data-generator.md)

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

- One page per person, named in PascalCase after the person, for example `ZheyuanWu.md`. Its `title` is `Name (handle)`, so a reader matches the page to the account without opening it.
- Each page opens with the same metadata block: project, handle, Git author, role, active period. Record the Git author as `Name <email>` exactly as it appears in `git log`, listing any additional identity the same person has committed under, so a commit can be traced to a page without guessing. Say so plainly when a contributor has no commits in this repository.
- Reverse-chronological `## YYYY-MM-DD` sections, each with `### Completed` and optionally `### Next`.
- At most three bullet points per section. Merge related work rather than adding a fourth.
- A page belongs to its owner. Do not edit, restructure, or translate another person's page.
- An agent must propose today's entry and receive explicit confirmation from its owner before writing it, and may write only to its owner's page.
