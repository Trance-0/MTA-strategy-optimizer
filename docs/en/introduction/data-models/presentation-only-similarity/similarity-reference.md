---
title: Similarity Reference
description: A dashboard-facing "similar items" pointer, structurally isolated from every model-facing canonical class
compact: "SimilarityReference is a presentation-only dataclass in a separate namespace, proven unreachable from every model-facing class by four independent isolation tests. No legacy source or adapter populates it; only a future, unimplemented similarity process would."
order: 10
lang: en-US
---

# SimilarityReference

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`SimilarityReference` is a dashboard-facing pointer from one subject entity to a similar comparable entity — for example, "this Product is similar to that Product" — carrying a similarity score and a human-readable rationale for display. It exists so a future similarity process, not implemented anywhere in this repository, has a defined place to put its output for the dashboard to render, without that output ever being mistaken for canonical model input.

The class sits at the end of a one-way, non-feeding-back data flow: canonical product and campaign information (read elsewhere in the model) may in the future feed a separate similarity process; that process's output is a `SimilarityReference`, consumed only by the dashboard. It never flows back into attribution, response modeling, or budget optimization — no `AttributionEvidence`, `CampaignEpisode`, or future optimizer input is derived from it. See [Canonical Data Model](/en/introduction/data-models/index.md) for where this path branches off the main model-facing flow.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/presentation/similarity.py`, inside the `presentation` subpackage — a namespace deliberately separate from the flat `modules/mta_common/src/` layer that holds every core, model-facing class (`Campaign`, `Product`, `CampaignEpisode`, and the rest). This placement is the mechanism, not just a label: the presentation layer is the one layer in the canonical model permitted to depend on nothing but the standard library and to be depended on by nothing else in `modules/mta_common/src/`.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### subject_type

#### Type
`str`

#### Requiredness
Required.

#### Meaning
What kind of entity `subject_id` identifies, for example `PRODUCT` or `CAMPAIGN`. Not a controlled `StrEnum` vocabulary — a free string, since the set of subject types a future similarity process might compare is not yet known.

#### Missingness
Not applicable; this field has no missingness state. It is required and validated non-blank.

#### Validation
Rejected (raises `ValueError`) when blank or all-whitespace, by `__post_init__`.

### subject_id

#### Type
`str`

#### Requiredness
Required.

#### Meaning
Id of the entity the similarity was computed for. A plain string id, not a `Campaign`/`Product` object reference — this is why `presentation/similarity.py` does not need to import the core package at all, and therefore cannot participate in an import cycle with it.

#### Missingness
Not applicable; required and validated non-blank.

#### Validation
Rejected when blank or all-whitespace. Rejected when equal to `comparable_id` (see [Invariants](#invariants)).

### comparable_id

#### Type
`str`

#### Requiredness
Required.

#### Meaning
Id of the similar entity being referenced, of the same `subject_type` as `subject_id`.

#### Missingness
Not applicable; required and validated non-blank.

#### Validation
Rejected when blank or all-whitespace. Rejected when equal to `subject_id`.

### similarity_score

#### Type
`float`

#### Requiredness
Required.

#### Meaning
A presentation-only similarity value in the closed interval `[0, 1]`. Explicitly not a model input — nothing in the canonical model reads it, per the isolation guarantees in [Relationships](#relationships).

#### Missingness
Not applicable; required.

#### Validation
Rejected (raises `ValueError`) when outside `[0.0, 1.0]`.

### rationale

#### Type
`str | None`

#### Requiredness
Optional; defaults to `None`.

#### Meaning
Free-text, human-readable explanation for display alongside the reference, for example why the dashboard considers the two entities similar.

#### Missingness
`None` when no explanation is supplied. This field does not use the five-state `FieldAvailability` vocabulary that core observation classes use — see [Known Limitations](#known-limitations).

#### Validation
None; any string or `None` is accepted.

### generated_by

#### Type
`str | None`

#### Requiredness
Optional; defaults to `None`.

#### Meaning
Identifier of the process or model version that produced this reference, for traceability back to whichever future similarity process generated it.

#### Missingness
`None` when not supplied.

#### Validation
None; any string or `None` is accepted.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `subject_type`, `subject_id`, and `comparable_id` must each be non-blank.
- `comparable_id` must differ from `subject_id`: a subject cannot be recorded as its own comparable.
- `similarity_score` must fall within `[0.0, 1.0]`.
- All validation runs in `__post_init__` on a `@dataclass(frozen=True)`, so an invalid `SimilarityReference` cannot be constructed at all — there is no partially-valid instance to catch downstream.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to the core canonical model

`SimilarityReference` is structurally isolated from every core, model-facing dataclass (`Campaign`, `Product`, `Touchpoint`, `CampaignEpisode`, and the rest under the flat `modules/mta_common/src/` layer). `modules/mta_common/tests/test_similarity_isolation.py` proves this isolation four independent ways, all currently passing:

- `NoCoreModuleImportsPresentationTests.test_no_core_source_file_references_presentation_by_name`: a word-boundary regular expression (`\bpresentation\b`) scans every core source file's raw text and asserts none references the `presentation` package by name. The word-boundary match is deliberate — it distinguishes the package name `presentation` from the unrelated English word "representation," which appears legitimately in other docstrings (for example, describing `Campaign` as "independent of platform or product count").
- `NoCoreModuleImportsPresentationTests.test_no_core_source_file_parses_to_an_import_of_presentation`: every core source file is parsed into an Abstract Syntax Tree with the standard library `ast` module, and every `ast.ImportFrom`/`ast.Import` node is inspected to assert none names `presentation`. This catches an import the text-search test could theoretically miss (for example, an aliased or dynamically constructed import string), by checking the actual parsed import structure rather than raw text.
- `NoCoreModuleImportsPresentationTests.test_importing_every_core_module_does_not_load_presentation`: every core module is imported in a fresh `subprocess`, and the resulting `sys.modules` is checked for any `modules.mta_common...presentation...` entry. Run in a subprocess specifically because unittest's own test discovery has, by the time any test body executes, already imported every `test_*.py` file in the directory — including `test_similarity_isolation.py` itself, which imports `SimilarityReference` at module scope — so checking `sys.modules` in-process would report a false leak caused by the test file, not by the core modules under test. The subprocess gives a clean `sys.modules` that reflects only importing the core modules themselves.
- `NoCoreDataclassAcceptsSimilarityReferenceTests.test_no_core_dataclass_field_is_typed_as_similarity_reference`: every dataclass in every core module is inspected with `typing.get_type_hints`, and every one of its fields is asserted to not be type-hinted as `SimilarityReference`. This is the one check that would catch the actual failure mode the first three cannot: a core dataclass accepting a `SimilarityReference` value via a field typed as a generic `object`, or otherwise without a literal import-time reference to the `presentation` package that the earlier tests scan for.

Together these prove both that the presentation layer cannot reach into the core model (no core file imports it) and that the core model cannot reach into the presentation layer (no core field accepts its type) — full isolation in both directions, not just one.

### Relationship to Product and Campaign

`subject_id`/`comparable_id` may in the future identify a [Product](/en/introduction/data-models/product-identity-and-economics/product.md) or [Campaign](/en/introduction/data-models/campaign-identity/campaign.md), but only by plain string id, never by object reference. The future similarity process that would populate this class is expected to read canonical `Product`/`Campaign` data as its input, but that dependency runs one way: canonical data flows into the similarity process, never the reverse.

### Relationship to the dashboard

The sole documented consumer of `SimilarityReference` is the dashboard, for display purposes. No response model, attribution model, or optimizer is a documented or possible consumer, by construction (see the isolation tests above).

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

None. No existing data source, report, or schema in this repository carries a similarity relationship between two entities.

### Canonical Conversion

Not applicable. `modules/mta_common/src/legacy_adapters.py` — the only module permitted to adapt legacy shapes into the canonical model — contains no function that constructs a `SimilarityReference`, and none is planned as part of this foundation; a `SimilarityReference` is populated only by a future, separate similarity-calculation process that this module deliberately does not implement.

### Information Loss

Not applicable; there is no legacy source to lose information from.

## Examples <span class="status-label status-recommendation" aria-label="Recommendation"></span>

```python
from modules.mta_common.src.presentation.similarity import SimilarityReference

reference = SimilarityReference(
    subject_type="PRODUCT",
    subject_id="PRODUCT-A",
    comparable_id="PRODUCT-B",
    similarity_score=0.87,
    rationale="Same category and brand, comparable price band.",
    generated_by="similarity-model-v0",
)
```

`subject_id`/`comparable_id` may in practice hold a [SKU](/en/reference/definitions#sku-stock-keeping-unit) or other product identifier once a similarity process exists; the class itself imposes no such constraint. Constructing a reference with a repeated id, or a score outside `[0, 1]`, raises `ValueError` immediately rather than producing an invalid instance:

```python
SimilarityReference(
    subject_type="PRODUCT",
    subject_id="PRODUCT-A",
    comparable_id="PRODUCT-A",  # raises ValueError: same as subject_id
    similarity_score=1.0,
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future similarity process would read canonical `Product`/`Campaign` data, compute a similarity score by a method this repository does not implement or specify, and emit one `SimilarityReference` per subject/comparable pair. A future dashboard view would read those references to render "similar items" panels. Neither consumer exists yet; only the type they would produce and consume, respectively, is implemented here.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested: `SimilarityReference`'s own validation (unit-interval score, non-blank ids, subject-cannot-equal-comparable) and all four isolation guarantees above are covered by `modules/mta_common/tests/test_similarity_isolation.py`, part of the 96 tests across 9 files in `modules/mta_common/tests/` that currently pass. No current pipeline component or dashboard code constructs a `SimilarityReference`; it is exercised only by its own test suite.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- No similarity calculation is implemented anywhere in this repository; this page documents only the presentation-only type that would carry such a calculation's output.
- `rationale` and `generated_by` use plain `str | None`, not the five-state `FieldAvailability` vocabulary the core model uses elsewhere (see [Field Availability](/en/introduction/data-models/vocabularies/field-availability.md)) — a deliberate simplification, since this is a presentation-only type with no requirement to distinguish *why* an optional display field is absent.
- `subject_type` is a free string rather than a controlled vocabulary, since the set of entity types a future similarity process might compare across is not yet known; this may need to become a shared enum once a real similarity process exists.
