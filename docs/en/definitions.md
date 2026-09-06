---
title: Development Definitions
compact: "Defines SDD, RAG, JSON, and CI for specification retrieval and verification; links the maintained advertising, attribution, data, and model terminology glossary."
---

# Development Definitions

The [domain glossary](/en/reference/definitions) defines the project's marketing,
data, model, and deployment vocabulary. These terms describe how an agent works
with the specifications.

#### SDD (Specification-Driven Development)

Write the accepted behavior contract before implementation. Code and tests must
agree with it; drift is resolved explicitly using intent and change history.

#### RAG (Retrieval-Augmented Generation)

Select relevant external context before generating an answer or change. Here,
compact page summaries and source/test ownership route the agent to a few pages.

#### JSON (JavaScript Object Notation)

A text format for objects, arrays, strings, numbers, booleans, and null values.
The retrieval command emits it so agents can consume results without scraping prose.

#### CI (Continuous Integration)

Automatic verification of a proposed code revision. This repository's verification
workflow checks documentation ownership, product tests, and production builds.

#### USD (United States Dollar)

The default currency suggestion in a new product-economics draft. It does not
convert currencies or fill a missing observed price.

#### COGS (Cost of Goods Sold)

The cost of producing or acquiring a product. `unit_cogs` is its per-unit value;
a missing value remains null and must never be interpreted as a measured zero.
