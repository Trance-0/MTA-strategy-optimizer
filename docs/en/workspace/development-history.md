---
title: Development History
description: English translation of the preserved project work log
lang: en-US
---

# Development History

This page translates the complete project work log into English. The original Chinese record remains at the repository root in `log.md` and is mirrored under `docs/zh/workspace/development-history.md` as an unpublished source backup.

The entries record decisions and intentions at the time they were written. They are historical evidence, not a replacement for current source code, tests, contracts, or the [current project status](../introduction/progress.md).

## 2026-07-30

### Completed

- Expanded the underlying data and completed an initial version of Ad Group-level strategy generation.

### Next

- Review whether the generation method should be improved further.

## 2026-07-27

### Completed

- Held a project meeting.

### Next

- The overall proposed workflow was:
  1. Work backward from MTA attribution results to recommend concrete Ad Group advertising strategies and budgets.
  2. Use a prediction model to estimate Ad Group budget performance, then optimize iteratively.
  3. Validate the final version through A/B testing.

## 2026-07-25

### Next

- Extend MTA to the `Account × Ad Product × five-segment touchpoint` grain so attribution can be examined for a specific advertising product.
- Keep the existing MTA method unchanged, but aggregate its touchpoint evidence to describe attribution performance for each Ad Product. Continue predicting budget allocation at Ad Group level because a Campaign has one inherent Ad Product. This turns MTA output into statistical evidence, such as which placements or creatives receive higher attribution shares, while budget allocation remains a separate decision grain.
- Use the models at two stages: the prediction and optimization models allocate budget at Campaign initialization, while detailed MTA touchpoint evidence supports Ad Group advertising decisions after spending begins.
- Because attribution-model and prediction-model touchpoints may differ or overlap only partially, use Keyword and Stock Keeping Unit (SKU) features to build a separate machine-learning prediction model, then build the optimizer from that prediction model. The intended business chain was to derive each Ad Group budget from the optimizer and use detailed MTA evidence to support the Ad Group's concrete advertising strategy.
- The proposal depended on the assumption that different products respond similarly to advertising formats during promotion.

## 2026-07-22

### Completed

- Completed the visualization.
- Organized project files.
- Completed the overall MTA usage guide.
- Completed the final pre-upload check for the MTA milestone.

## 2026-07-21

### Completed

- Expanded the MTA model dataset to one year.
- Reduced the reliability judgment to three indicators.
- Updated the program so data can be extended without changing the code.

### Next

- Complete visualization work.
- Discuss model completeness with an agent-assisted review.

## 2026-07-17

### Completed

- Held a project meeting.

### Next

- Simplify reliability to three indicators: calculation validity, sufficient data support, and model consistency.
- Complete the MTA attribution model.
- Organize the visual process diagram.
- Prepare for the machine-learning model.

## 2026-07-16

### Completed

- Cleaned the complete workspace and consolidated navigation.
- Evaluated all AMC MTA dual-model outputs.
- Restored a reproducible Amazon Marketing Cloud conceptual-event sample.
- Confirmed that the legacy general MTA implementation had been intentionally removed and made `modules/amc_mta` the only formal implementation at that time.
- Audited all business files, research material, three inputs, five outputs, and 75 tests present at that time.
- Added the Amazon Marketing Cloud MTA architecture, capability assessment, and current documentation index.
- Marked prediction, budget optimization, experimentation, and AI question-answering documents as historical vision rather than delivered capability.

### Next

- Prepare for the next meeting.

## 2026-07-13

### Completed

- Improved the MTA algorithm and data structure and fixed the five-segment interaction grain.

### Next

- Review the design in a meeting.

## 2026-07-08

### Completed

- Organized the forms of data available from Amazon Marketing Cloud.
- Decided to perform MTA using Amazon Marketing Cloud and Amazon Ads report data.
- Selected the initial touchpoint representation.
- Completed simulated Amazon Marketing Cloud and Amazon Ads report data.
- Updated the model.
- Drafted an A/B-test approach. The meeting proposal could not guarantee audience isolation: even if each Ad Group spent budget proportionally, the same user could still see ads from both groups. Experimental assignment therefore needed to fix audiences at sample level.

### Next

- Align the content with the ontology team.
- Review and improve the simulated data.
- Freeze the grain at this stage and write a separate explanation requiring a Creative value.
- Review Amazon Marketing Stream fields.
- Write a concrete A/B-testing proposal.

## 2026-07-03

### Completed

- Studied how to combine the project framework with the ontology design.
- Completed initial research into Amazon Marketing Cloud and Amazon Attribution.
- Identified the intended data sources.

### Next

- Read the Amazon research report and understand Amazon Marketing Cloud and Amazon Attribution data formats.
- Adjust the MTA model to match advertising formats and available data.

## 2026-06-15 to 2026-07-02

### Completed

- Studied MTA.
- Studied A/B testing.
- Built the initial MTA model.
- Established the project-solution framework.
