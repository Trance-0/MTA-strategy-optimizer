---
title: Record Classification
description: When in the decision cycle a record's fields became available, a required Data Lineage field connecting to the evaluation-only isolation pattern
compact: "RecordClassification StrEnum (DECISION_TIME, OBSERVED_AFTER_TREATMENT, EVALUATION_ONLY_GROUND_TRUTH) in modules/mta_common/src/enums.py — required field on DataLineage.classification. EVALUATION_ONLY_GROUND_TRUTH connects to evaluation_only.py's isolation pattern. No legacy_adapters.py function populates it."
order: 60
lang: en-US
---

# Record Classification

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`RecordClassification` states when in a campaign's decision cycle a record's fields became knowable: before treatment was chosen, only after treatment ran, or only to a simulator or controlled experiment. It is a required field on [Data Lineage](/en/introduction/data-models/historical-evidence-and-lineage/data-lineage.md), so every record's provenance carries an explicit statement of timing rather than leaving a reader to infer it from which fields happen to be populated.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/enums.py`, the vocabulary layer every other canonical class in `modules/mta_common/src/` depends on. `RecordClassification` has no dependency of its own beyond the Python standard library.

## Members <span class="status-label status-verified" aria-label="Verified"></span>

### DECISION_TIME

#### Meaning

Known before treatment (budget, targeting) is chosen — the fields a decision-maker or model had available at the moment of the decision.

### OBSERVED_AFTER_TREATMENT

#### Meaning

Known only after treatment ran, from normal reporting — the fields describing what actually happened once a campaign was live.

### EVALUATION_ONLY_GROUND_TRUTH

#### Meaning

Known only to a simulator or a controlled experiment; must never reach a model-facing record. See [Relationship to Evaluation-Only Isolation](#relationship-to-evaluation-only-isolation) below.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- Exactly three members exist: `DECISION_TIME`, `OBSERVED_AFTER_TREATMENT`, `EVALUATION_ONLY_GROUND_TRUTH`.
- As a `StrEnum`, each member's value is an exact string match of its name (`RecordClassification.DECISION_TIME == "DECISION_TIME"`).
- `DataLineage.classification` is required, with no default; a `DataLineage` cannot be constructed without choosing one of the three members.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Data Lineage

[Data Lineage](/en/introduction/data-models/historical-evidence-and-lineage/data-lineage.md)'s `classification: RecordClassification` field is required, alongside `source_system`, `source_reference`, `schema_version`, and `transformation_version`. Its docstring: "Whether this record's fields were available at decision time, observed only after treatment, or are evaluation-only ground truth."

### Relationship to Evaluation-Only Isolation

`EVALUATION_ONLY_GROUND_TRUTH` names the same category `modules/mta_common/src/evaluation_only.py` isolates by construction, not by this enum member alone. `CampaignEpisode` (see [Campaign Episode](/en/introduction/data-models/composed-episodes-and-evaluation-isolation/campaign-episode.md)) has no field for simulator-known ground truth; `EvaluationEpisode` holds a `CampaignEpisode` and an `EvaluationGroundTruth` as two separate composed fields — composition, not inheritance — so a function typed to accept `CampaignEpisode` has no attribute path into ground truth even if an `EvaluationEpisode` is passed by mistake. The module's `FORBIDDEN_MODEL_FACING_FIELDS` frozenset (`true_incremental_units`, `true_incremental_revenue`, `true_causal_effect`, `simulator_ground_truth_id`) and its `assert_no_ground_truth_fields()` function give this guarantee an automated, reusable check, independent of whether a `DataLineage.classification` value is set correctly.

### Relationship to legacy_adapters.py

No function in `modules/mta_common/src/legacy_adapters.py` reads, produces, or accepts a `RecordClassification` value; the module does not import it, and none of the functions that could construct a `DataLineage` do so today.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. Today's only lineage-like fields are the `source_*_sha256` provenance hashes on `BudgetRecommendationRun` in the dashboard schema — content hashes, not a structured statement of when a record's fields became available.

### Canonical Conversion

None. `legacy_adapters.py` does not import `RecordClassification` or `DataLineage`; no adapter function in this repository constructs a `DataLineage` from a legacy source today. `lineage.py`'s own module docstring states this module "defines the type but does not require any class above to carry one, so adoption can be gradual."

### Information Loss

Not applicable. There is no legacy source and no adapter, so there is no conversion in which information could be lost.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.lineage import DataLineage
from modules.mta_common.src.enums import RecordClassification

# From modules/mta_common/tests/test_outcome_and_attribution_evidence.py::DataLineageTests
lineage = DataLineage(
    source_system="MTA_SIM_GENERATOR",
    source_reference="amazon_ads_daily_touchpoint_performance",
    schema_version="4.0",
    transformation_version="1.0",
    classification=RecordClassification.DECISION_TIME,
    is_synthetic=True,
)
lineage.classification  # RecordClassification.DECISION_TIME
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future record producer adopting `DataLineage` would set `classification=RecordClassification.EVALUATION_ONLY_GROUND_TRUTH` on any record it attaches to an `EvaluationGroundTruth`, giving that record's provenance an explicit, checkable label consistent with `assert_no_ground_truth_fields()`'s structural guarantee — the two mechanisms would corroborate each other rather than either alone being authoritative. No such producer exists yet, since `DataLineage` adoption is gradual and optional today.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented in `modules/mta_common/src/enums.py`, required by `DataLineage` in `modules/mta_common/src/lineage.py`, and exercised by `modules/mta_common/tests/test_outcome_and_attribution_evidence.py::DataLineageTests`. The related isolation guarantee is exercised separately by `modules/mta_common/tests/test_episode_and_evaluation_isolation.py`.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No current adapter or pipeline component constructs a `DataLineage`, so no record in this repository carries a `RecordClassification` value today outside of tests.
- `EVALUATION_ONLY_GROUND_TRUTH`'s safety depends on `evaluation_only.py`'s structural isolation (composition, `FORBIDDEN_MODEL_FACING_FIELDS`, `assert_no_ground_truth_fields()`), not on this enum member being set correctly — a `DataLineage.classification` mislabeled as `DECISION_TIME` on an actually-evaluation-only record would not by itself leak ground truth into a model-facing class, but it would make the record's own provenance statement wrong.
- `RecordClassification` is an `enum.StrEnum`, one of seven vocabularies in `enums.py` that make up this repository's only use of the `Enum` family outside `modules/mta_common/`. Every other canonical class here is a plain `@dataclass(frozen=True)`; `StrEnum` was chosen for these seven vocabularies specifically so `RecordClassification` and the rest are not restated as ad-hoc string literals across the classes that reference them, at the cost of introducing a dependency the rest of this repository deliberately avoids.
