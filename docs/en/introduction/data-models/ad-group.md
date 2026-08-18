---
title: Ad Group
description: The canonical, addressable representation of one ad group belonging to a Campaign
compact: "Frozen dataclass `AdGroup` in modules/mta_common/src/campaign.py: ad_group_id, campaign_id, optional allocation_basis, budget_seed_share (0-1), initial_daily_budget (>=0). Makes Ad Group an addressable object instead of a bridge key. Adapted from initial_budget_recommendation.json by legacy_adapters.ad_group_from_recommended_slot."
lang: en-US
---

# Ad Group

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

`AdGroup` is the canonical representation of one ad group belonging to exactly one [`Campaign`](./campaign.md). It exists because today's only representation of an ad group is a bridge key — `entity.get("ad_group_id")` inside `strategy_request.json`'s entity evidence — never an addressable object with its own fields. `AdGroup` gives an ad group its own identity, its owning campaign, and the fields today's `budget_recommender.py` already computes for it (`allocation_basis`, `budget_seed_share`, `initial_daily_budget`), so a recommended ad group can be represented before it exists as a real, platform-created object.

## Ownership and Layer <span class="status-label status-verified" aria-label="Verified"></span>

Defined in `modules/mta_common/src/campaign.py`, alongside [`Campaign`](./campaign.md). Part of the Campaign Identity layer of the [Canonical Data Model](./index.md): it depends only on [`Campaign`](./campaign.md) (by `campaign_id` reference, not by embedding), and has no further downstream dependents among the classes documented here.

## Fields <span class="status-label status-verified" aria-label="Verified"></span>

### ad_group_id

#### Type

`str`

#### Requiredness

Required.

#### Meaning

Stable ad group identifier, or a recommender-assigned slot identifier before the ad group is actually created on the advertising platform. The two are not distinguished by a separate field — see Known Limitations.

#### Missingness

Not applicable; every `AdGroup` must carry an identifier, whether platform-assigned or recommender-assigned.

#### Validation

`__post_init__` rejects a blank or whitespace-only string.

### campaign_id

#### Type

`str`

#### Requiredness

Required.

#### Meaning

The owning [`Campaign.campaign_id`](./campaign.md#campaign_id). A plain string reference, not an embedded `Campaign` object.

#### Missingness

Not applicable; an `AdGroup` with no owning campaign cannot be represented.

#### Validation

`__post_init__` rejects a blank or whitespace-only string.

### allocation_basis

#### Type

`str | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Description of how this ad group's budget share was derived, mirroring `budget_recommender.py`'s own `allocation_basis` output field (for example `EQUAL_SPLIT`).

#### Missingness

`None` when no allocation basis has been computed or supplied for this ad group. `AdGroup` does not distinguish among the five [Field Availability](./field-availability.md) states for this field — it is a plain optional, not a `FieldAvailability`-tracked one, since no current or planned source needs to distinguish, for example, "not applicable" from "not yet computed" here.

#### Validation

None beyond the type itself.

### budget_seed_share

#### Type

`float | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Fraction of the owning campaign's budget seed assigned to this ad group.

#### Missingness

`None` when no share has been computed.

#### Validation

`__post_init__` rejects a value outside the closed interval `[0.0, 1.0]` when one is given; `None` always passes.

### initial_daily_budget

#### Type

`float | None`

#### Requiredness

Optional; defaults to `None`.

#### Meaning

Recommended starting daily budget for this ad group.

#### Missingness

`None` when the recommendation carried no budget baseline. This is the normal case for the current adapter path — see Legacy Mapping.

#### Validation

`__post_init__` rejects a negative value when one is given; `None` always passes.

## Invariants <span class="status-label status-verified" aria-label="Verified"></span>

- `ad_group_id` and `campaign_id` must both be non-blank strings.
- `budget_seed_share`, when present, must satisfy `0.0 <= budget_seed_share <= 1.0`.
- `initial_daily_budget`, when present, must satisfy `initial_daily_budget >= 0`.
- `AdGroup` is immutable (`@dataclass(frozen=True)`).
- Nothing in `AdGroup` validates that `campaign_id` names a `Campaign` that actually exists; that cross-reference is a caller's responsibility, matching today's logical (not database-enforced) foreign key.

## Relationships <span class="status-label status-verified" aria-label="Verified"></span>

### Relationship to Campaign

Every `AdGroup` names exactly one owning [`Campaign`](./campaign.md) through `campaign_id`. `Campaign` does not hold a back-reference collection of its ad groups.

### Relationship to Campaign Episode

[`CampaignEpisode`](./campaign-episode.md) composes at the `Campaign` level, not the `AdGroup` level; `AdGroup` is not currently one of its fields.

## Legacy Mapping <span class="status-label status-verified" aria-label="Verified"></span>

### Current Source Fields

`initial_budget_recommendation.json`'s per-campaign `recommended_ad_groups[]` entries, each carrying `ad_group_slot_id`, `allocation_basis`, `budget_seed_share`, and optionally `initial_daily_budget`.

### Canonical Conversion

`legacy_adapters.ad_group_from_recommended_slot(slot, *, campaign_id)` maps `slot["ad_group_slot_id"]` to `ad_group_id`, copies `allocation_basis` and `budget_seed_share` through `None`-safe float coercion, and takes `campaign_id` as a separate keyword argument since the slot itself does not carry it.

### Information Loss

`initial_daily_budget` stays `None` whenever the slot dictionary has no `initial_daily_budget` key, matching `budget_recommender.py`'s own conditional inclusion of that field — `StrategyRequestAdapterTests.test_campaign_and_scope_and_ad_group_adapt` in `modules/mta_common/tests/test_legacy_adapters.py` exercises exactly this case and asserts the result is `None`. No field is silently defaulted to `0.0` in its place. Separately, `ad_group_slot_id` becoming `ad_group_id` means a recommended-but-not-yet-created ad group and a real, platform-assigned ad group are represented with the same field and cannot be told apart from `AdGroup` alone.

## Examples <span class="status-label status-verified" aria-label="Verified"></span>

Constructing directly:

```python
from modules.mta_common.src.campaign import AdGroup

ad_group = AdGroup(
    ad_group_id="AG-1",
    campaign_id="CAMP-1",
    allocation_basis="EQUAL_SPLIT",
    budget_seed_share=0.25,
    initial_daily_budget=50.0,
)
```

A minimal ad group, with every optional field left `None`:

```python
ad_group = AdGroup(ad_group_id="AG-1", campaign_id="CAMP-1")
```

Adapting from today's recommendation output:

```python
from modules.mta_common.src.legacy_adapters import ad_group_from_recommended_slot

ad_group = ad_group_from_recommended_slot(
    {
        "ad_group_slot_id": "SLOT-1",
        "allocation_basis": "EQUAL_SPLIT",
        "budget_seed_share": 0.5,
    },
    campaign_id="CAMP-1",
)
# ad_group.initial_daily_budget is None: the slot carried no budget baseline.
```

## Downstream Usage <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A future constrained optimizer, described in [Strategy Optimization Model](/en/strategy-recommendation/index.md), would read `budget_seed_share`/`initial_daily_budget` as a starting point for per-ad-group budget decisions. No such consumer exists yet.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

Fully implemented and validated by 7 dedicated tests in `modules/mta_common/tests/test_campaign.py` (`AdGroupTests`), with the `initial_budget_recommendation.json` adapter path covered by `StrategyRequestAdapterTests` in `modules/mta_common/tests/test_legacy_adapters.py`. Part of the 96-test `modules/mta_common` suite, all passing. Nothing outside `modules/mta_common/tests/` constructs an `AdGroup` yet.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- `ad_group_id` does not distinguish a recommender-assigned slot identifier from a real, platform-created ad group identifier; both occupy the same field.
- `AdGroup` does not validate that its `campaign_id` refers to an existing `Campaign`; that referential check is a caller responsibility.
- No `DataLineage` is attached to an `AdGroup` to record whether it came from a real platform read or from a not-yet-created recommendation — that distinction currently exists only informally, in which adapter function produced it.
