---
title: Data Lineage
description: Provenance for one canonical record, referencing a logical source rather than a local file path
compact: "DataLineage: canonical provenance value object generalizing today's content-hash-only source tracking into source system, logical source reference, schema version, transformation version, RecordClassification, and synthetic-versus-observed status. Optional; no current adapter populates it."
order: 20
lang: en-US
---

# Data Lineage

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`DataLineage` is a reusable value object describing where a canonical record came from: which system produced it, what logical source it was read from, under which schema and transformation version, and whether it is synthetic or observed. It exists to generalize today's only lineage-like mechanism — the `source_*_sha256` content-hash fields on `BudgetRecommendationRun` in the dashboard schema, described in [Dashboard Data Model](/en/market-simulation/dashboard-data-model.md#budgetrecommendationrun) — into a structured, provider-agnostic shape.

Today's provenance is narrow by necessity: it is a byte-level [Secure Hash Algorithm 256-bit (SHA-256)](/en/reference/definitions#sha-256-secure-hash-algorithm-256-bit) digest of an attribution file and an entity file, verified by `_sha256()` in `modules/mta_strategy_recommendation`'s hierarchy validator, so a recommendation can be traced back to the exact evidence bytes that justified it. That mechanism answers "did this exact file change" but not "what system produced it," "under what schema version," or "is this real or simulated data." `DataLineage` references a logical source — a table name, a report name, a provider — rather than a local filesystem path, since the same logical source may be read from a CSV extract in one environment and a database table in another; a path would break across that boundary while a logical reference would not.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/lineage.py`. Sits in the "historical evidence and lineage" layer of the [Canonical Data Model](/en/introduction/data-models/index.md), alongside [Attribution Evidence](/en/introduction/data-models/historical-evidence-and-lineage/attribution-evidence.md). Unlike `AttributionEvidence`, no other canonical class currently embeds a `DataLineage` field — this module defines the type but requires no class above to carry one, so adoption can be gradual.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### source_system

#### Type

`str`

#### Requiredness

Required.

#### Meaning

The system of record this data came from, for example `AMAZON_ADS_AMC` or `MTA_SIM_GENERATOR`. A free-form identifier, not one of this module's enums, since the set of possible source systems is open-ended and not owned by the canonical model.

#### Missingness

Not applicable; rejected outright when blank.

#### Validation

`__post_init__` strips and rejects a blank value with `ValueError`.

### provider

#### Type

[`Provider`](/en/introduction/data-models/vocabularies/provider.md) `| None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

The provider this lineage is scoped to, when the source is provider-specific. `None` when the source is not tied to one advertising platform, for example a cross-provider synthetic generator.

#### Missingness

Represented as `None`; `DataLineage` does not use `FieldAvailability` for this field, since a `None` provider here means "genuinely not provider-scoped," not one of the five distinguishable reasons a value could be missing that [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md) tracks.

#### Validation

None; any `Provider` member or `None` is accepted.

### source_reference

#### Type

`str`

#### Requiredness

Required.

#### Meaning

A logical reference to the source — a table name or report name, not a local file path — so lineage survives moving the same logical source between a CSV extract and a database import.

#### Missingness

Not applicable; rejected outright when blank.

#### Validation

`__post_init__` strips and rejects a blank value with `ValueError`.

### schema_version

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Version of the source schema this record was read under, so a downstream consumer can tell whether two records were produced under compatible schema expectations.

#### Missingness

Not applicable; rejected outright when blank.

#### Validation

`__post_init__` strips and rejects a blank value with `ValueError`.

### transformation_version

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Version of the adapter or compatibility layer that produced this record from the source, for example a `legacy_adapters.py` version, so a later change to adaptation logic is distinguishable from a change in the source data itself.

#### Missingness

Not applicable; rejected outright when blank.

#### Validation

`__post_init__` strips and rejects a blank value with `ValueError`.

### classification

#### Type

[`RecordClassification`](/en/introduction/data-models/vocabularies/record-classification.md)

#### Requiredness

Required.

#### Meaning

Whether this record's fields were available at decision time, observed only after treatment, or are evaluation-only ground truth.

#### Missingness

Not applicable; every `DataLineage` instance states one of the three `RecordClassification` values.

#### Validation

None beyond `RecordClassification`'s own closed vocabulary; any invalid value is a `TypeError`/`ValueError` at the enum-construction level before `DataLineage.__post_init__` ever runs.

### is_synthetic

#### Type

`bool`

#### Requiredness

Required.

#### Meaning

Whether the source is simulated data (for example, the MTA-SIM generator) rather than a real observed platform report.

#### Missingness

Not applicable; always `True` or `False`.

#### Validation

None; any boolean is accepted.

### report_period_start

#### Type

`str | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Inclusive ISO start date of the source's own reporting period, which may differ from the [Reporting Scope](/en/introduction/data-models/touchpoint-and-provider-contract/reporting-scope.md) window of the record this lineage describes — for example, a source report covering a full quarter feeding a canonical record scoped to one month within it.

#### Missingness

Represented as `None` when the source's own period is not tracked separately from the record's `ReportingScope` window.

#### Validation

None.

### report_period_end

#### Type

`str | None`

#### Requiredness

Optional, defaults to `None`.

#### Meaning

Inclusive ISO end date of the source's own reporting period, paired with `report_period_start`.

#### Missingness

Represented as `None` when the source's own period is not tracked separately.

#### Validation

None.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `source_system`, `source_reference`, `schema_version`, and `transformation_version` are never blank.
- `source_reference` is a logical name, never a local filesystem path, by convention documented in the module docstring — this is not mechanically enforced by `__post_init__`, since the class cannot distinguish a path-shaped string from a table-name-shaped string.
- `report_period_start`/`report_period_end`, when both given, are not cross-validated against each other or against a record's `ReportingScope` window; unlike `ReportingScope.__post_init__`, `DataLineage` does not require `report_period_end >= report_period_start`.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Provider

`DataLineage.provider`, when set, uses the same [Provider](/en/introduction/data-models/vocabularies/provider.md) vocabulary as [Touchpoint](/en/introduction/data-models/touchpoint-and-provider-contract/touchpoint.md) and [Campaign](/en/introduction/data-models/campaign-identity/campaign.md), rather than a separate lineage-specific provider concept.

### Relationship to Record Classification

`DataLineage.classification` reuses [Record Classification](/en/introduction/data-models/vocabularies/record-classification.md) rather than defining its own decision-time/observed/evaluation-only vocabulary, keeping this concept singular across the module.

### Relationship to Attribution Evidence and Other Canonical Records

No canonical class currently embeds a `DataLineage` field. The module docstring states the intended relationship: "any canonical record's producer may attach a `DataLineage` describing how that record was derived," but this module defines the type without requiring [Attribution Evidence](/en/introduction/data-models/historical-evidence-and-lineage/attribution-evidence.md), [Budget Observation](/en/introduction/data-models/budget-delivery-and-outcome-observations/budget-observation.md), or any other class to carry one, so adoption can be gradual rather than a breaking change to every existing class.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

`BudgetRecommendationRun` (table `budget_recommendation_run`) in the dashboard schema, described in [Dashboard Data Model](/en/market-simulation/dashboard-data-model.md#budgetrecommendationrun), carries `source_*` columns: the window, marketplace, advertiser, and SHA-256 digests of the attribution and entity input files consumed by one budget-initializer run. Separately, `modules/mta_strategy_recommendation`'s hierarchy validator computes and compares these digests via its internal `_sha256()` helper (documented in [Strategy Recommendation Source Files](/en/strategy-recommendation/module-overview/source-files.md)) against the digests declared in `strategy_request.json`'s `source` object.

### Canonical Conversion

None. `modules/mta_common/src/legacy_adapters.py` defines no function that constructs a `DataLineage` from either of these sources — verified directly by inspecting `legacy_adapters.py`, which contains no reference to `DataLineage` or `Lineage` anywhere in the file. `DataLineage` is available for a future adapter to populate, but no such adapter exists today.

### Information Loss

Not applicable, since no conversion exists yet to lose information. If a future adapter is written, the content-hash-only source today — `strategy_request.json`'s `source` object, carrying `attribution_sha256`, `entity_sha256`, `attribution_file`, and `entity_file`, verified in `modules/mta_strategy_recommendation`'s hierarchy validator, and the corresponding `source_*` columns on `BudgetRecommendationRun` — would map onto `DataLineage.source_reference` at best partially: a SHA-256 digest identifies exact bytes but not a stable logical name the way `DataLineage.source_reference` is intended to (for example, `"amc_attribution_output"` versus a digest that changes on every run). A faithful adapter would need to supply `source_reference` as a stable logical name separate from the digest, which today's schema does not carry.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.enums import Provider, RecordClassification
from modules.mta_common.src.lineage import DataLineage

lineage = DataLineage(
    source_system="MTA_SIM_GENERATOR",
    source_reference="amazon_ads_daily_touchpoint_performance",
    schema_version="4.0",
    transformation_version="1.0",
    classification=RecordClassification.DECISION_TIME,
    is_synthetic=True,
    provider=Provider.AMAZON_ADS,
)
```

A blank required field is rejected:

```python
DataLineage(
    source_system="",
    source_reference="daily_performance",
    schema_version="4.0",
    transformation_version="1.0",
    classification=RecordClassification.OBSERVED_AFTER_TREATMENT,
    is_synthetic=True,
)  # raises ValueError
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future adapter could construct a `DataLineage` alongside any canonical record it produces, so a downstream consumer can trace a [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md)'s fields back to the exact source system, schema version, and synthetic-versus-observed status that produced them. A future evaluation harness could use `is_synthetic` and `classification` together to confirm that no evaluation-only ground truth leaked into a record it treats as decision-time or observed-after-treatment input. Neither consumer is implemented yet.

## Current Availability <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The class itself is implemented and its own field validation is tested by `DataLineageTests` in `modules/mta_common/tests/test_outcome_and_attribution_evidence.py`. No current adapter, pipeline component, or other canonical class populates or embeds a `DataLineage` — it exists only as a defined type, exercised by its own direct-construction tests.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No adapter exists from either of today's provenance mechanisms (`BudgetRecommendationRun.source_*` columns, or `strategy_request.json`'s `source` object) into `DataLineage`. Building one is future work, not something this session implements.
- No canonical class embeds a `DataLineage` field yet, so constructing one today has no effect on any other record's validation or behavior.
- `report_period_start`/`report_period_end` are not cross-validated against each other or against the record's own `ReportingScope` window, unlike `ReportingScope.__post_init__`'s `report_end_date >= report_start_date` check.
