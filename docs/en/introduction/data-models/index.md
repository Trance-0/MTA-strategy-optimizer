---
title: Canonical Data Model
description: Provider-independent domain model foundation shared across attribution, strategy, and dashboard modules
compact: "Provider-independent canonical dataclasses (Touchpoint, Campaign, Product, Budget, Outcome, AttributionEvidence, CampaignEpisode) replacing the five-segment string key as ground truth, with a legacy compatibility bridge. Foundation only: no optimizer, incrementality estimation, or similarity calculation implemented."
lang: en-US
source_files: modules/mta_common/src/enums.py, modules/mta_common/src/provider_capabilities.py, modules/mta_common/src/touchpoint.py, modules/mta_common/src/reporting_scope.py, modules/mta_common/src/campaign.py, modules/mta_common/src/product.py, modules/mta_common/src/budget.py, modules/mta_common/src/delivery.py, modules/mta_common/src/outcome.py, modules/mta_common/src/attribution_evidence.py, modules/mta_common/src/lineage.py, modules/mta_common/src/episode.py, modules/mta_common/src/evaluation_only.py, modules/mta_common/src/presentation/similarity.py, modules/mta_common/src/legacy_adapters.py
---

# Canonical Data Model

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`modules/mta_common/` defines a provider-independent domain model for a Campaign, its Products, its Touchpoints, and every observation (budget, delivery, outcome, historical attribution) that can be recorded against them. It exists because the current implementation ties campaign and touchpoint identity to two Amazon-specific shapes: the `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` five-segment string key in `modules/mta_attribution`, and the hardcoded four-Campaign, four-product `strategy_request.json` schema in `modules/mta_strategy_recommendation`. Neither shape distinguishes `provider` from `ad_product`, neither can express that a field is missing for five different reasons rather than one, and neither has a `Product`, `ProductEconomics`, or `CampaignProductLink` concept at all.

Every canonical class here is a `@dataclass(frozen=True)` with explicit validation in `__post_init__`, so an invalid record cannot be constructed rather than being caught later by a downstream consumer. The five-segment string key remains fully supported, but only as a backward-compatible serialization of a `Touchpoint`, produced and parsed by `legacy_adapters.py`, never redefined as the canonical form itself.

## Scope and Non-Goals <span class="status-label status-verified" aria-label="Verified"></span>

This module is a data model and a compatibility bridge. It deliberately does not implement:

- A budget optimizer that reads `StrategyObjective` and `BudgetUsagePolicy` and produces an allocation.
- Causal-incrementality estimation that would populate `OutcomeObservation`'s `incremental_units`/`incremental_revenue` fields.
- The similarity calculation that would produce a `SimilarityReference`.
- A real adapter for any advertising platform other than Amazon Ads. `Provider.GENERIC` and `GENERIC_CAPABILITIES` exist only to prove the contract is not Amazon-specific; no adapter reads real data shaped like it.
- A rewrite of `modules/mta_attribution`, `modules/mta_standard`, or `modules/mta_strategy_recommendation` to consume these classes directly. Those modules keep reading and writing their native shapes; `legacy_adapters.py` is the only bridge, and nothing outside `modules/mta_common/tests/test_legacy_adapters.py` currently calls it.

## Data Flow <span class="status-label status-verified" aria-label="Verified"></span>

The model-facing flow runs in one direction:

1. A provider or raw source (today, Amazon Ads AMC paths, Amazon Ads reports, or `strategy_request.json`) is read by provider-specific normalization code that already exists in `modules/mta_attribution` and `modules/mta_standard`.
2. `legacy_adapters.py` adapts that provider-specific shape into canonical observations: a `Touchpoint`, a `ReportingScope`, a `Campaign`, an `AdGroup`.
3. Those canonical observations combine into historical attribution evidence (`AttributionEvidence`) and campaign, product, and economic observations (`BudgetObservation`, `DeliveryObservation`, `OutcomeObservation`, `ProductEconomics`).
4. `CampaignEpisode` composes one campaign's decision-time and observed-after-treatment records into the shape a future response model would consume.
5. A future response model and a future strategy optimizer would read `CampaignEpisode` (and, for evaluation only, `EvaluationEpisode`). Neither is implemented in this module.

A second, separate path does not feed back into the flow above: canonical product and campaign information may in the future feed a similarity process, whose output is a `SimilarityReference` consumed only by the dashboard for display. `SimilarityReference` lives in the separate `presentation` namespace precisely so this one-way path cannot be mistaken for model input. See [Similarity Reference](./similarity-reference.md) for the isolation guarantee and its tests.

## Class Index <span class="status-label status-verified" aria-label="Verified"></span>

### Vocabularies

Seven `StrEnum` classes in `enums.py`, the repository's only use of `Enum` outside this module — see each page's Known Limitations for why.

- [Provider](./provider.md): which advertising platform a record came from, independent of `ad_product`.
- [Field Availability](./field-availability.md): the five explicit reasons a field may not carry a value.
- [Strategy Objective](./strategy-objective.md): what a future optimizer would maximize.
- [Budget Usage Policy](./budget-usage-policy.md): whether a future optimizer must exhaust an authorized budget.
- [Assignment Type](./assignment-type.md): how a budget was assigned, reserved for a future intervention study.
- [Record Classification](./record-classification.md): when in the decision cycle a record's fields became available.
- [Margin Source](./margin-source.md): whether a `ProductEconomics` margin was given directly or derived.

### Touchpoint and Provider Contract

- [Provider Capabilities](./provider-capabilities.md): a provider-level ceiling declaring which `Touchpoint` fields a provider can supply at all.
- [Touchpoint](./touchpoint.md): the canonical, typed replacement for the five-segment string key.
- [Touchpoint Field Availability](./touchpoint-field-availability.md): the per-record realization of `ProviderCapabilities` for one `Touchpoint` instance.
- [Reporting Scope](./reporting-scope.md): the account, market, currency, and date window an observation covers.

### Campaign Identity

- [Campaign](./campaign.md): one advertising campaign, independent of provider or product count.
- [Ad Group](./ad-group.md): one ad group belonging to exactly one Campaign.

### Product Identity and Economics

- [Product](./product.md): a business product, identified independently of any ad platform.
- [Product Economics](./product-economics.md): a product's price and cost structure, with missing cost-of-goods-sold kept missing rather than zero-filled.
- [Campaign Product Link](./campaign-product-link.md): the explicit many-to-many relationship between Campaign and Product.

### Budget, Delivery, and Outcome Observations

- [Budget Constraints](./budget-constraints.md): forward-looking budget bounds and usage policy for one campaign.
- [Budget Observation](./budget-observation.md): configured budget versus actual spend, kept as two independent fields.
- [Delivery Observation](./delivery-observation.md): impressions, clicks, and cost observed for one Touchpoint.
- [Outcome Observation](./outcome-observation.md): total, organic, and incremental outcomes, kept distinct.

### Historical Evidence and Lineage

- [Attribution Evidence](./attribution-evidence.md): one touchpoint's attributed share of one outcome, free of any optimization claim.
- [Data Lineage](./data-lineage.md): where a record came from, without coupling to a local file path.

### Composed Episodes and Evaluation Isolation

- [Campaign Episode](./campaign-episode.md): one campaign's decision-time and observed-after-treatment fields, composed for a future response model.
- [Evaluation Ground Truth](./evaluation-ground-truth.md): simulator-known truth, isolated to evaluation-only code.
- [Evaluation Episode](./evaluation-episode.md): a `CampaignEpisode` paired with its `EvaluationGroundTruth`, by composition rather than inheritance.

### Presentation-Only Similarity

- [Similarity Reference](./similarity-reference.md): a dashboard-facing "similar items" pointer, structurally isolated from every model-facing class.

## Legacy Compatibility Direction <span class="status-label status-verified" aria-label="Verified"></span>

`legacy_adapters.py` is the only module in `modules/mta_common/src/` that imports from `modules.mta_attribution` or `modules.mta_standard`. It bridges in both directions:

- **Legacy schema to canonical model**: it adapts the five-segment touchpoint key, the four-segment MTA-SIM key, `AttributionResult`, `TouchpointSpend`, `StandardAttributionRow`, and the relevant `strategy_request.json` and `initial_budget_recommendation.json` shapes into `Touchpoint`, `AttributionEvidence`, `DeliveryObservation`, `OutcomeObservation`, `ReportingScope`, `Campaign`, `AdGroup`, `BudgetConstraints`, and `BudgetObservation`.
- **Canonical model to legacy projection**: `touchpoint_to_five_segment_key` projects a canonical `Touchpoint` back to the string key the existing attribution algorithms require, so those algorithms do not need to be rewritten to consume the canonical model directly.

Every lossy conversion this bridge performs is documented once in `legacy_adapters.py`'s module docstring and repeated on the specific class page it affects, in that page's own `## Legacy Mapping` section, rather than in one separate table-based document.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Attribution Documentation

The five-segment key this model wraps is specified in [Attribution Model Overview](/en/attribution/index.md) and canonicalized by `touchpoint_key.py`, described there under its Source Files section. [Touchpoint](./touchpoint.md) and [Attribution Evidence](./attribution-evidence.md) reference that existing contract rather than restating its validation rules.

### Relationship to Market Simulation Documentation

The four-segment MTA-SIM key, `AttributionResult`, and `TouchpointSpend` this model adapts are specified in [Market Simulation and Compatibility](/en/market-simulation/index.md), [Campaign data model](/en/market-simulation/campaign-data-model.md), and [Product data model](/en/market-simulation/product-data-model.md). `simulation_ground_truth`'s existing isolation, documented there, is the precedent [Evaluation Ground Truth](./evaluation-ground-truth.md) follows for the canonical model.

### Relationship to Strategy Recommendation

`strategy_request.json`'s Campaign, Ad Group, and budget fields, adapted by `legacy_adapters.py` into [Campaign](./campaign.md), [Ad Group](./ad-group.md), [Budget Constraints](./budget-constraints.md), and [Budget Observation](./budget-observation.md), are specified in [Strategy Recommendation](/en/strategy-recommendation/index.md).

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for every maintained implementation file under `modules/mta_common/src/`, except `__init__.py`. This section is consolidated here rather than split across the 26 class pages above, since most of these files each back multiple class pages.

### `enums.py`

Source: `modules/mta_common/src/enums.py`

- Responsibility: Define the seven controlled vocabularies every other canonical class references.
- Inputs: None; pure declarations.
- Outputs: `Provider`, `FieldAvailability`, `StrategyObjective`, `BudgetUsagePolicy`, `AssignmentType`, `RecordClassification`, `MarginSource`.
- Dependencies: Python standard library only (`enum.StrEnum`).
- Verification: `modules/mta_common/tests/test_enums_and_capabilities.py`.

### `provider_capabilities.py`

Source: `modules/mta_common/src/provider_capabilities.py`

- Responsibility: Declare, per provider, which `Touchpoint` fields exist and are supplied, as a static ceiling.
- Inputs: None; declares `ProviderCapabilities` plus the `AMAZON_ADS_CAPABILITIES` and `GENERIC_CAPABILITIES` constants.
- Outputs: `ProviderCapabilities` instances for callers to validate a `Touchpoint` against.
- Dependencies: `enums.py`.
- Verification: `modules/mta_common/tests/test_enums_and_capabilities.py`.

### `touchpoint.py`

Source: `modules/mta_common/src/touchpoint.py`

- Responsibility: Define the canonical, typed `Touchpoint` and its per-record `TouchpointFieldAvailability`, replacing the five-segment string key as the fundamental type.
- Inputs: A provider-specific loader's fields, or `legacy_adapters.py`'s adaptation of an existing key.
- Outputs: `Touchpoint`, `TouchpointFieldAvailability`.
- Dependencies: `enums.py`.
- Verification: `modules/mta_common/tests/test_touchpoint.py`.

### `reporting_scope.py`

Source: `modules/mta_common/src/reporting_scope.py`

- Responsibility: Compose the account, market, currency, and date window shared by every observation record into one reusable value object.
- Inputs: A provider's account/market/currency/window fields, today scattered across `strategy_request.json`'s `mta_source` and `campaign_group`.
- Outputs: `ReportingScope`.
- Dependencies: Python standard library only.
- Verification: `modules/mta_common/tests/test_budget_and_delivery.py`.

### `campaign.py`

Source: `modules/mta_common/src/campaign.py`

- Responsibility: Define the canonical `Campaign` and `AdGroup`, independent of platform or product count.
- Inputs: A provider's campaign/ad-group fields, or `legacy_adapters.py`'s adaptation of `strategy_request.json` and `initial_budget_recommendation.json`.
- Outputs: `Campaign`, `AdGroup`.
- Dependencies: `enums.py`, `reporting_scope.py`.
- Verification: `modules/mta_common/tests/test_campaign.py`, with adapter-path coverage in `modules/mta_common/tests/test_legacy_adapters.py`.

### `product.py`

Source: `modules/mta_common/src/product.py`

- Responsibility: Define `Product` (business identity separated from provider-specific advertising identities), `ProductEconomics` (price and cost structure, with unfilled fields kept `None`), and `CampaignProductLink` (the explicit many-to-many relationship).
- Inputs: A future product-data integration; no current data source populates any of the three.
- Outputs: `Product`, `ProductEconomics`, `CampaignProductLink`.
- Dependencies: `enums.py`.
- Verification: `modules/mta_common/tests/test_product_and_economics.py`.

### `budget.py`

Source: `modules/mta_common/src/budget.py`

- Responsibility: Define `BudgetConstraints` (forward-looking bounds and usage policy) and `BudgetObservation` (configured budget versus actual spend, as independent fields).
- Inputs: A provider's budget fields, or `legacy_adapters.py`'s adaptation of `strategy_request.json` and `initial_budget_recommendation.json`.
- Outputs: `BudgetConstraints`, `BudgetObservation`.
- Dependencies: `enums.py`, `reporting_scope.py`.
- Verification: `modules/mta_common/tests/test_budget_and_delivery.py`.

### `delivery.py`

Source: `modules/mta_common/src/delivery.py`

- Responsibility: Define `DeliveryObservation`, the canonical counterpart to today's `TouchpointSpend`, with the non-billed impressions/clicks metric left `None` instead of zero.
- Inputs: `legacy_adapters.delivery_observation_from_touchpoint_spend`'s adaptation of `TouchpointSpend`.
- Outputs: `DeliveryObservation`.
- Dependencies: `reporting_scope.py`, `touchpoint.py`.
- Verification: `modules/mta_common/tests/test_budget_and_delivery.py`.

### `outcome.py`

Source: `modules/mta_common/src/outcome.py`

- Responsibility: Define `OutcomeObservation`, keeping total-observed outcomes distinct from organic-baseline and incremental-attributable outcomes, never fabricating the latter two from the former.
- Inputs: Today's total-observed path-report and Ads-report fields, via `legacy_adapters.py`; a future incrementality model for the organic/incremental fields.
- Outputs: `OutcomeObservation`.
- Dependencies: `reporting_scope.py`, `touchpoint.py`.
- Verification: `modules/mta_common/tests/test_outcome_and_attribution_evidence.py`.

### `attribution_evidence.py`

Source: `modules/mta_common/src/attribution_evidence.py`

- Responsibility: Define `AttributionEvidence`, adapting today's two attribution-result shapes into one canonical, pure-historical-evidence type with no marginal-return, causal-incrementality, optimal-budget, or product-contribution-profit field.
- Inputs: `legacy_adapters.py`'s adaptation of `AttributionResult` and `StandardAttributionRow`.
- Outputs: `AttributionEvidence`.
- Dependencies: `reporting_scope.py`, `touchpoint.py`.
- Verification: `modules/mta_common/tests/test_outcome_and_attribution_evidence.py`.

### `lineage.py`

Source: `modules/mta_common/src/lineage.py`

- Responsibility: Define `DataLineage`, generalizing today's content-hash-only provenance into a reusable, logical-source-referencing value object.
- Inputs: None populated by any current adapter; defines the type for gradual adoption.
- Outputs: `DataLineage`.
- Dependencies: `enums.py`.
- Verification: `modules/mta_common/tests/test_outcome_and_attribution_evidence.py`.

### `episode.py`

Source: `modules/mta_common/src/episode.py`

- Responsibility: Define `CampaignEpisode`, composing one campaign's decision-time-available and observed-after-treatment records, with no field that can hold evaluation-only ground truth.
- Inputs: `Campaign`, `BudgetConstraints`, `BudgetObservation`, `DeliveryObservation`, `OutcomeObservation`, `AttributionEvidence`.
- Outputs: `CampaignEpisode`.
- Dependencies: `attribution_evidence.py`, `budget.py`, `campaign.py`, `delivery.py`, `outcome.py`.
- Verification: `modules/mta_common/tests/test_episode_and_evaluation_isolation.py`.

### `evaluation_only.py`

Source: `modules/mta_common/src/evaluation_only.py`

- Responsibility: Define `EvaluationGroundTruth` and `EvaluationEpisode`, the only place in the canonical model allowed to carry simulator-known ground truth, and `assert_no_ground_truth_fields`, the automated isolation check.
- Inputs: A simulator-backed evaluation harness's ground-truth fields; a `CampaignEpisode` to pair with them.
- Outputs: `EvaluationGroundTruth`, `EvaluationEpisode`, the `FORBIDDEN_MODEL_FACING_FIELDS` constant, `assert_no_ground_truth_fields`.
- Dependencies: `episode.py`; Python standard library `dataclasses`.
- Verification: `modules/mta_common/tests/test_episode_and_evaluation_isolation.py`.

### `presentation/similarity.py`

Source: `modules/mta_common/src/presentation/similarity.py`

- Responsibility: Define `SimilarityReference`, a dashboard-facing "similar items" pointer, in a namespace structurally unreachable from every core, model-facing class.
- Inputs: A future, separate similarity process's output.
- Outputs: `SimilarityReference`.
- Dependencies: Python standard library only; deliberately does not import anything else in `modules/mta_common/src/`.
- Verification: `modules/mta_common/tests/test_similarity_isolation.py`.

### `legacy_adapters.py`

Source: `modules/mta_common/src/legacy_adapters.py`

- Responsibility: Bidirectionally bridge today's Amazon-specific shapes and the canonical model; the only module here that imports from `modules.mta_attribution` or `modules.mta_standard`.
- Inputs: Five-segment and four-segment touchpoint keys, `AttributionResult`, `TouchpointSpend`, `StandardAttributionRow`, `strategy_request.json` and `initial_budget_recommendation.json` fragments.
- Outputs: `Touchpoint`, `AttributionEvidence`, `DeliveryObservation`, `OutcomeObservation`, `ReportingScope`, `Campaign`, `AdGroup`, `BudgetConstraints`, `BudgetObservation`; and, in the reverse direction, a five-segment key projected from a `Touchpoint`.
- Dependencies: Every canonical module listed above, plus `modules.mta_attribution.src.attribution_contract`, `modules.mta_attribution.src.touchpoint_key`, `modules.mta_standard.src.output_contract`, `modules.mta_standard.src.touchpoint_adapter`.
- Verification: `modules/mta_common/tests/test_legacy_adapters.py`.

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future response-prediction model would consume `CampaignEpisode` as its training and inference row shape. A future strategy optimizer would read `StrategyObjective`, `BudgetUsagePolicy`, and `BudgetConstraints` to decide an allocation, and `CampaignEpisode` to evaluate one. A future evaluation harness would consume `EvaluationEpisode` to compare a model's decision against simulator ground truth without that ground truth ever reaching the model itself. None of these consumers exist yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Every class described here is implemented and tested: 96 tests across 9 files in `modules/mta_common/tests/` pass under `python -X utf8 -B -m unittest discover -s modules/mta_common/tests -t . -p "test_*.py"`. Nothing in `script/`, `modules/mta_attribution`, `modules/mta_standard`, `modules/mta_strategy_recommendation`, or the dashboard currently imports `modules.mta_common`; this is a foundation laid ahead of that integration, not a change to any running pipeline's behavior today.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No real second-provider adapter exists; `Provider.GENERIC` and `GENERIC_CAPABILITIES` demonstrate the contract's shape, not a working integration.
- No optimizer, incrementality-estimation source, or similarity calculation is implemented; the classes that would carry their output (`OutcomeObservation`'s incremental fields, `SimilarityReference`) exist and stay unpopulated.
- `enums.py` uses `enum.StrEnum` for its seven vocabularies, a deliberate deviation from this repository's otherwise near-total avoidance of the `Enum` family, chosen so `Provider`, `FieldAvailability`, and the rest are not restatable as five different ad-hoc string conventions across the classes that reference them.
- No current pipeline component calls `legacy_adapters.py`; it is exercised only by its own test suite until a future change wires a real caller to it.
