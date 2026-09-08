---
title: Development Definitions
compact: "Defines PRD, FR, NFR, UX, UI, CLI, QA, API, CSV, SDD, RAG, JSON, CI, ECS, YAML, HTTPS and URL for specification, verification and deployment configuration; links the maintained advertising, attribution, data, and model terminology glossary."
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
The mirror validates generator configuration as an object in this format before publication.

#### CI (Continuous Integration)

Automatic verification of a proposed code revision. This repository's verification
workflow checks deployment inputs, product tests, and production builds; documentation ownership is reviewed against the owning pages.

#### ECS (Elastic Compute Service)

Alibaba Cloud's virtual-machine hosting service. This project's existing
Yunxiao host job runs commands on an already provisioned machine and restarts
the `mta-backend.service` service without building a container.

#### YAML (YAML Ain't Markup Language)

A text format using indentation to describe configuration. Yunxiao's pipeline
file defines jobs and embeds the host bootstrap command as a multiline value.

#### HTTPS (Hypertext Transfer Protocol Secure)

Encrypted web transport with server-certificate validation. The Gitea clone
address uses it without embedding a password in the address.

#### URL (Uniform Resource Locator)

An address naming a resource and how to access it. Deployment configuration
uses one address for the Gitea repository and another optional public health check.

#### USD (United States Dollar)

The default currency suggestion in a new product-economics draft. It does not
convert currencies or fill a missing observed price.

#### COGS (Cost of Goods Sold)

The cost of producing or acquiring a product. `unit_cogs` is its per-unit value;
a missing value remains null and must never be interpreted as a measured zero.

#### PRD (Product Requirements Document)

The accepted user outcomes, scope and testable requirements for a release.

#### FR (Functional Requirement)

A stable numbered statement of behavior the product must provide; stories map
back to these identifiers to show coverage.

#### API (Application Programming Interface)

A defined request and response boundary. The Dashboard calls backend routes;
external callers can push the same documented dataset contract.

#### CSV (Comma-Separated Values)

A text format with a header and rows, using commas between fields and doubled
quotes inside quoted fields. Dataset templates define exact column names.

#### NFR (Non-Functional Requirement)

A measurable operating constraint such as responsiveness, persistence or accessibility.

#### UX (User Experience)

The observable interaction and recovery behavior through which a person completes an analysis.

#### UI (User Interface)

The visible controls, labels, tables and charts through which a person operates the application.

#### CLI (Command-Line Interface)

A command and arguments executed by the backend or a terminal to run an existing product module.

#### QA (Quality Assurance)

Verification that implemented behavior meets the accepted requirements and preserves evidence of what was tested.
