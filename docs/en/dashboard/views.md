---
title: Dashboard Views and Visual Contract
compact: "Shared presentation topics and preserved KnowledgeBase, ontologyReviewFixtures, WillowGmvForecast and willowGmvModel contracts. The common views, tables, Settings and charts are specified in linked topic pages."
lang: en-US
source_files: dashboard/src/views/KnowledgeBase.vue, dashboard/src/lib/ontologyReviewFixtures.js, dashboard/src/lib/willowGmvModel.js, dashboard/src/components/WillowGmvForecast.vue
---

# Dashboard Views and Visual Contract

The dashboard presents pipeline evidence through shared views, tables, charts,
and navigation. The [shared presentation topics](./views/index.md) specify
those components in smaller pages. Contributor-owned view contracts remain
here at their existing location.

Optimization Log is backed by run provenance and pipeline stage state.
Knowledge Base exposes four operational-reference tabs derived only from the
current Dashboard snapshot: Touchpoint vocabulary, Rules, Entities, and Data
sources. They describe the data already in use and do not claim to be a
backend-owned ontology or recompute attribution, budgets, or verdicts. The
separate fifth Ontology Review tab remains a display-only exception: it reads
five checksum-verified canonical R5 fixtures prepared by the
[static delivery process](./deployment.md#canonical-ontology-review-fixtures).
It never calls a Review Application Programming Interface (API), calculates a
ratio, compares a threshold, or infers a verdict.

The default Touchpoint vocabulary tab sends no fixture requests. Entering Ontology Review
starts a bounded load with retry after failure. It has loading, unavailable/error,
defensive empty, and ready states. A valid release always reaches ready with
exactly five cases; empty is a defensive rendering state, not a sixth canonical
release. The ready state
offers the canonical in-band, exact-boundary, conflict, zero-baseline, and
missing-policy cases in manifest order. It displays plan, release, review, and
rule identity; current and recommended budget, currency, the canonical absolute
change ratio, authorization limit, policy source, verdict, evidence,
limitations, availability, and next step. `UNVERIFIED` never means approval,
and `CONFLICT` means human authorization is required rather than optimizer
failure. An unavailable or altered bundle displays no verdict.

All five Knowledge Base tabs use roving focus with ArrowLeft,
ArrowRight, Home, and End. Unmounting aborts unfinished fixture requests, and a request that exceeds ten seconds fails closed.
Identity, meaning, verdict, and next step remain readable in the narrow layout.

## Running a Stage from the Dashboard

### Willow Sakura forecast is a native panel

The evaluation tab embeds Willow Sakura's contributed Gross Merchandise Value
(GMV) forecast as dashboard widgets, not as a plain HyperText Markup Language
(HTML) page in an `iframe`. The panel includes all four ad-product budgets,
marketplace, day of week, weekend state, all seven placement and creative cost
shares, placement-type count, the run control, predicted attributed revenue,
total daily budget, the all-budgets-plus-ten-percent scenario, revenue delta,
and held-out model metrics.

`WillowGmvForecast.vue` owns the inputs and accessible labels.
`willowGmvModel.js` owns only pure Extended-27 feature construction and forward
inference using the contributor's exported JSON weights. Editing any input or
pressing **Run prediction** recomputes both scenarios. The panel names the
prediction as Amazon-attributed sales rather than organic GMV and reports the
held-out error alongside it; it never feeds this forecast into the project's
optimizer or presents it as realized uplift.


## Source Files

### Knowledge Base view

Source: `dashboard/src/views/KnowledgeBase.vue`, `dashboard/src/lib/ontologyReviewFixtures.js`

#### `KnowledgeBase.vue`

Four snapshot-backed operational references and the separately sourced canonical R5 Ontology Review. Touchpoint vocabulary reads the observed attribution keys; Rules combines the fixed reliability/outcome vocabulary with the current strategy request; Entities reads the Campaign Group, Campaigns, and eligible candidate counts; Data sources identifies the active snapshot source and its declared artifacts. These panels are presentation of current Dashboard data, not a backend-owned ontology. `ontologyReviewFixtures.js` continues to own the deployment-base asset path, byte and identity checks, display-only normalization, and immutable five-case result.

- Inputs: A validated route `section`; the route-scoped `shell`, `attribution`, or `budget` resource needed by the selected operational-reference tab; and, only for Ontology Review, the generated release manifest plus five fixture payloads below the deployment-base `data/ontology-review/` path. The component passes only an abort signal to the fixture adapter and owns no fetch implementation, local path, Structured Query Language (SQL) statement, credential, or Review API client.
- Outputs: The rendered page. Nothing is returned and nothing is written.
- Behavior contract: The four operational-reference tabs only group, label, and format existing snapshot fields; absent capacity rules or entities use their declared empty explanations. Ontology Review remains isolated and fails closed until every payload passes the pinned manifest, SHA-256, release, client, plan/review-link, and R5 identity checks. It copies policy strings and verdicts without calculation or inference, exposes the specified fail-closed states and five canonical meanings, loads only after its route is selected, supports retry and a ten-second timeout, aborts on unmount, and preserves the declared keyboard and narrow-layout behavior across all five tabs.
- Dependencies: Vue 3, `src/lib/useDashboard.js`, `src/lib/common.js`, the shared table and key/value components, `src/theme.js`, and `src/lib/ontologyReviewFixtures.js`; the view does not use Plotly or a Review API.
- Verification: `dashboard/tests/ontology_review_fixtures.test.js`, `dashboard/tests/dashboard.test.js`, `backend/tests/test_snapshot.py`, the clean normal/static builds, and the live GitHub Pages smoke test.


### The shared components

Source: `dashboard/src/components/WillowGmvForecast.vue`

`WillowGmvForecast.vue` renders the contributed forecast inside the evaluation
tab using the dashboard's cards, fields, and metric treatments. It contains no
`iframe`, `srcdoc`, global event handler, or copied navigation shell. Every
control has a stable label and every output updates through Vue state while
remaining independent from the production strategy artifacts.

### `src/lib/willowGmvModel.js`

Source: `dashboard/src/lib/willowGmvModel.js`

- Responsibility: Build the contributor's 27-feature vector and run its two
  hidden rectified-linear layers and capped output entirely in the browser.
- Inputs: The exported model JSON and Willow forecast form values.
- Outputs: Deterministic predicted attributed revenue for the requested budget
  scale, plus the exact feature vector for verification.
- Behavior contract: Budget inputs are non-negative; day and marketplace are
  one-hot encoded in the model's declared order; zero standard deviations are
  treated as one; matrix dimensions must match or throw a named error. The
  ten-percent comparison changes only the four budgets.
- Dependencies: JavaScript standard library only.
- Verification: `dashboard/tests/willow_gmv_model.test.js` and the production
  Vue build.
