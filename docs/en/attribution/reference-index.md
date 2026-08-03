---
title: Detailed AMC MTA Documentation Index
lang: en-US
---

# Detailed AMC MTA Documentation Index

Only documentation for the currently runnable module is kept here:

- [Complete usage guide](complete-guide.md): one-stop written guidance for submission review, execution, demo, error handling, and limitations.
- [Data-flow diagram](../../assets/amc-mta/data-flow.png): standalone PNG showing inputs, dual models, reliability, and canonical outputs; use the [SVG source](../../assets/amc-mta/data-flow.svg) for maintenance.
- [Canonical output index](output-reference.md): reading order, fields, granularity, and interpretation boundaries for the five CSV files.
- [Data contract](../datasets/amc-data-contract.md): the only complete source of truth for current fields and business rules.
- [Usage](../environment/amc-mta-usage.md): commands, parameters, and outputs.
- [Single-touchpoint attribution reliability](reliability.md): interpret a single-touchpoint result using calculation validity, sufficient data support, and model consistency.
- [Amazon Ads sample](../datasets/amazon-ads-sample.md): five-segment performance/cost input and billing assignment.
- [Dual-model difference quantification and output specification](model-governance.md): consumer-goods-oriented gap thresholds, evidence thresholds, and output state machine for Markov and path-level Shapley.

AMC platform background research and project-management documentation are external to the original project. They are not included with this standalone package and are not runtime dependencies.

See the [output index](output-reference.md) for a file-by-file description of the five canonical CSV files, and the [submission manifest](../reference/submission-manifest.md) for submission scope. If this documentation conflicts with historical design material, the current data contract, model-governance specification, runtime code, and tests take precedence.
