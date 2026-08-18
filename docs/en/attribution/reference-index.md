---
title: Detailed AMC MTA Documentation Index
compact: "Link-only hub pointing to the usage guide, output index, data contract, usage commands, reliability, Amazon Ads sample, and governance spec, plus the precedence rule that contract, code, and tests win. No technical content of its own."
lang: en-US
---

# Detailed AMC MTA Documentation Index

Only documentation for the currently runnable module is kept here:

- [Complete usage guide](complete-guide.md): one-stop written guidance for submission review, execution, demo, error handling, and limitations.
- [Current data-flow diagram](../introduction/amc-mta-architecture.md#current-data-flow): theme-aware Draw.io architecture showing canonical governance, standardized models, DNN, and isolated evaluation.
- [Canonical output index](output-reference.md): reading order, fields, granularity, and interpretation boundaries for the five CSV files.
- [Data contract](../market-simulation/amc-data-contract.md): the only complete source of truth for current fields and business rules.
- [Usage](../introduction/environment/amc-mta-usage.md): commands, parameters, and outputs.
- [Single-touchpoint attribution reliability](reliability.md): interpret a single-touchpoint result using calculation validity, sufficient data support, and model consistency.
- [Amazon Ads sample](../market-simulation/amazon-ads-sample.md): five-segment performance/cost input and billing assignment.
- [Dual-model difference quantification and output specification](model-governance.md): consumer-goods-oriented gap thresholds, evidence thresholds, and output state machine for Markov and path-level Shapley.

AMC platform background research and project-management documentation are external to the original project. They are not included with this standalone package and are not runtime dependencies.

See the [output index](output-reference.md) for a file-by-file description of the five canonical CSV files, and the [submission manifest](../reference/submission-manifest.md) for submission scope. If this documentation conflicts with historical design material, the current data contract, model-governance specification, runtime code, and tests take precedence.
