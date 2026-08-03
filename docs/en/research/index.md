---
title: Research Material Index
lang: en-US
---

# Research Material Classification Index

This section indexes external papers, platform research, and background material in the current research set. Explicitly retired material is not part of that set. Research does not equal current implementation and is not runtime input to `modules/amc_mta`.

The current internal business hierarchy is defined in [Campaign Group hierarchy and finest performance grain](campaign-data-hierarchy.md): `Campaign Group -> Campaign -> Ad Group -> Keyword/SKU`; `ad_product` is a Campaign field rather than a hierarchy level.

## Relevance to AMC MTA

| Level | Section | Purpose |
| --- | --- | --- |
| core method | [MTA reading entry](mta/) | Markov, Shapley, stability, and MTA methodology |
| core platform | [Amazon reading entry](amazon/) | AMC, Amazon Ads, advertising products, data boundaries |
| future validation | [A/B-testing reading entry](ab-testing/) | future validation of attribution/budget conclusions; not part of current calculations |
| background | [Ontology research](/research/ontology/本体论研究（最终）.pdf) | knowledge-organization research with no direct runtime dependency |
| background | [Cross-industry proposal](/research/industry/跨行业AI应用项目-营销场景AI应用与数据.pdf) | early marketing-AI proposal and project context |

### Core MTA Material

- [MTA reading order](mta/)
- [Data-driven Multi-touch Attribution Models](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf): emphasizes stability of attribution estimates; its research models differ from the implementation.
- [Mapping the Customer Journey](/research/mta/Mapping%20the%20customer%20journey.pdf): graph and higher-order Markov attribution research.
- [Shapley Value Methods for Attribution Modeling](/research/mta/Shapley%20Value%20Methods%20for%20Attribution%20Modeling%20in%20Online%20Advertising.pdf): Shapley attribution background.
- [Study notes](mta/data-driven-mta-models-study-note.md): personal reading notes, not a source of code facts.

### Amazon Platform Material

- [AMC background](amazon/amc/) and [data flow](amazon/amc/data-flow.md) support the clean-room boundary.
- `/research/amazon/research/amazon调研.docx` covers SP, SB, SD, DSP, CPC/CPM, and AMC background.
- `/research/amazon/research/Amazon_Attribution_Report_FULL.docx` mainly covers off-Amazon Amazon Attribution and ROAS and cannot replace AMC paths.
- The OpenAPI JSON, Marketing Stream fields, and format examples support upstream-data research and are not runtime inputs.
- [2026-07-06 technical research](amazon/research/technical-amazon-attribution-mta-2026-07-06.md) is a historical snapshot; module contracts govern current behavior.
- [Amazon source index](amazon/research/) describes the six originals and their boundaries.

### Future Validation and Background

- [Two A/B-testing papers](ab-testing/) support future causal validation and experiment design; they cannot prove that the current synthetic attribution is correct.
- Ontology and industry documents remain team background and should not enter the runtime chain or core reading order.

## Boundary

- MTA samples are in `modules/amc_mta/data/simulated/`; independent business-hierarchy samples are in `modules/mta_strategy_recommender/data/simulated/`.
- Current input/output contracts begin at the [AMC MTA reference index](../attribution/reference-index.md).
- The pipeline does not read research originals and does not infer AMC user paths from aggregate Amazon Attribution reports.
- Classify new material in this index as core, future validation, or background.
