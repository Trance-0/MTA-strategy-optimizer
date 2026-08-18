---
title: Reporting Scope
description: The marketplace, advertiser, currency, date range, and optional campaign group that bounds a report
compact: "ReportingScope holds marketplace, advertiser_id, currency, report_start_date, report_end_date, and optional campaign_group_id. Rejects blank required fields and an end date before the start date. Assembled by legacy_adapters.reporting_scope_from_campaign_group from two separate legacy source dicts, campaign_group and mta_source, never one."
order: 40
lang: en-US
---

# Reporting Scope

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`ReportingScope` states the marketplace, advertiser, currency, and date range that bounds a report, plus an optional campaign group identifier when the report is scoped to one. It exists so that every record derived from a report, budgets, observations, evidence, can be traced back to the specific market, account, and time window it came from, without each of those records repeating the same five fields individually.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/reporting_scope.py`. Has no dependency on any other class in the canonical model; it is built entirely from plain strings.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### marketplace

#### Type

`str`.

#### Requiredness

Required, non-blank.

#### Meaning

The marketplace this report covers, for example an Amazon marketplace identifier.

#### Missingness

Not applicable; a blank `marketplace` is rejected outright rather than represented as missing.

#### Validation

`__post_init__` raises `ValueError` if `marketplace` is blank after stripping whitespace.

### advertiser_id

#### Type

`str`.

#### Requiredness

Required, non-blank.

#### Meaning

The advertiser account this report covers.

#### Missingness

Not applicable; a blank `advertiser_id` is rejected outright.

#### Validation

`__post_init__` raises `ValueError` if `advertiser_id` is blank after stripping whitespace.

### currency

#### Type

`str`.

#### Requiredness

Required, non-blank.

#### Meaning

The currency all monetary figures within this report's scope are denominated in.

#### Missingness

Not applicable; a blank `currency` is rejected outright.

#### Validation

`__post_init__` raises `ValueError` if `currency` is blank after stripping whitespace.

### report_start_date

#### Type

`str`.

#### Requiredness

Required, non-blank.

#### Meaning

The first date, inclusive, this report's scope covers.

#### Missingness

Not applicable; a blank `report_start_date` is rejected outright.

#### Validation

`__post_init__` raises `ValueError` if blank, and raises `ValueError` if `report_end_date < report_start_date` under plain string comparison.

### report_end_date

#### Type

`str`.

#### Requiredness

Required, non-blank.

#### Meaning

The last date, inclusive, this report's scope covers.

#### Missingness

Not applicable; a blank `report_end_date` is rejected outright.

#### Validation

`__post_init__` raises `ValueError` if blank, and raises `ValueError` if `report_end_date < report_start_date`. This comparison is a plain string comparison, not a parsed-date comparison, so both fields must already be in a lexicographically-comparable format such as `YYYY-MM-DD` for the check to be meaningful; `ReportingScope` does not itself enforce a date format.

### campaign_group_id

#### Type

`str | None`.

#### Requiredness

Optional; defaults to `None`.

#### Meaning

The campaign group this report is scoped to, when the report covers a single campaign group rather than an entire advertiser account.

#### Missingness

`None` when the report is not scoped to a specific campaign group. Unlike Touchpoint's optional fields, this has no companion `FieldAvailability`, ReportingScope predates and does not use the [Field Availability](/en/introduction/data-models/vocabularies/field-availability.md) pattern for this field.

#### Validation

None; `campaign_group_id` may be `None` or any string, including blank, with no rejection.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `marketplace`, `advertiser_id`, `currency`, `report_start_date`, and `report_end_date` are always non-blank.
- `report_end_date` is never lexicographically less than `report_start_date`.
- `campaign_group_id` is unconstrained: `None`, a blank string, or any non-blank string are all accepted without error.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to other canonical classes

`ReportingScope` has no field of any other canonical class's type and is not currently embedded as a field within any other class defined under `modules/mta_common/src/`. It stands alone as the scope descriptor that a caller associates with a set of records by convention, not by structural embedding.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

Two separate legacy mapping-like inputs, read together by one adapter function rather than one shared source:

- A `campaign_group` mapping, read for `marketplace`, `advertiser_id`, `currency`, and `campaign_group_id`.
- An `mta_source` mapping, read for `report_start_date` and `report_end_date`.

### Canonical Conversion

`legacy_adapters.reporting_scope_from_campaign_group(campaign_group, *, mta_source)` reads `campaign_group["marketplace"]`, `campaign_group["advertiser_id"]`, `campaign_group["currency"]`, and `campaign_group["campaign_group_id"]`, and separately reads `mta_source["report_start_date"]` and `mta_source["report_end_date"]`, combining both into one `ReportingScope`. The two inputs are kept separate because the legacy campaign group data and the legacy report date range do not live in the same source table.

### Information Loss

None identified: every field `ReportingScope` defines is read directly from one of the two legacy inputs with no collapsing, defaulting, or sentinel substitution.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

```python
from modules.mta_common.src.reporting_scope import ReportingScope

scope = ReportingScope(
    marketplace="ATVPDKIKX0DER",
    advertiser_id="A1B2C3D4E5",
    currency="USD",
    report_start_date="2026-01-01",
    report_end_date="2026-01-31",
    campaign_group_id="CG-100",
)
```

```python
from modules.mta_common.src.legacy_adapters import reporting_scope_from_campaign_group

scope = reporting_scope_from_campaign_group(
    campaign_group={
        "marketplace": "ATVPDKIKX0DER",
        "advertiser_id": "A1B2C3D4E5",
        "currency": "USD",
        "campaign_group_id": "CG-100",
    },
    mta_source={"report_start_date": "2026-01-01", "report_end_date": "2026-01-31"},
)
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future reporting or export layer would attach a `ReportingScope` to a batch of budget, delivery, or evidence records to label which market, advertiser, currency, and date range they were computed from. No such layer exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Implemented and tested in `modules/mta_common/tests/test_budget_and_delivery.py`'s `ReportingScopeTests` (end date before start date rejected, blank required fields rejected) and exercised by `modules/mta_common/tests/test_legacy_adapters.py`'s campaign-group adaptation tests. See [Canonical Data Model](/en/introduction/data-models/index.md) for the full test count and command.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- `report_start_date` and `report_end_date` are validated as plain strings, not parsed dates; a non-`YYYY-MM-DD`-style format would pass validation while comparing incorrectly.
- `campaign_group_id` has no `FieldAvailability` companion, unlike the optional fields on Touchpoint; there is no structural way to distinguish "not scoped to a campaign group" from "campaign group unknown."
- Not embedded as a field on any other canonical class today, so associating a `ReportingScope` with a batch of records is a caller convention rather than an enforced structural link.
