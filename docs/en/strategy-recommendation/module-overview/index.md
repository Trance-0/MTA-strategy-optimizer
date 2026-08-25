---
title: MTA-Driven Ad Group Budget Initializer
description: Deterministic Campaign and Ad Group budget seed derived from governed MTA evidence and capacity constraints
compact: "Implemented strategy contract: canonical touchpoint parsing, evidence pinning, MTA-to-Campaign bridge, weighted Campaign scores, capacity-derived Ad Group counts, equal budget split, validation invariants, and source-file API reference."
lang: en-US
provenance:
  original_author: Jiahao Yao
  original_handle: yao-LLL
  source_branch: codex/yao-friday-reference
  source_commit: 3c4aa9e64d270b5be670c5b23fa4a8cc50bb5434
---

# MTA-Driven Ad Group Budget Initializer

The initializer turns governed Multi-Touch Attribution (MTA) evidence and a
candidate pool into a deterministic Campaign and Ad Group budget seed. Its
parts are separated by reader intent: the [implemented calculation](./current-implementation.md)
specifies the algorithm and invariants, [running and documentation](./running-and-documentation.md)
locates the commands and related pages, and [source files](./source-files.md)
defines the code-level contracts. Together they are one implementation
specification; none may redefine the formula independently.