---
title: Recommended Strategy Structure
description: The shared interface every strategy must satisfy — identity, capabilities, inputs, outputs, and conservation contract
compact: "PROPOSED, unimplemented `Strategy` abstract base with `allocate`/`save`/`load`, plus `StrategyCapabilities`, `StrategyScope`, `StrategyEvidence`, `StrategyConstraints`, `StrategyAllocation` dataclass fields and conservation tolerances. Read when defining the interface; not a description of shipped code."
lang: en-US
---

# Recommended Strategy Structure

## Design Principle <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The attribution layer settled on one interface — `fit`/`attribute`/`save`/`load` with a `ModelCapabilities` declaration — and every model since has conformed to it. The strategy layer should follow the same pattern: one abstract contract that admits both the current seed initializer and future optimizers without changing the evaluation framework.

A strategy, in this project's sense, is any callable procedure that consumes a Campaign Group scope, attribution evidence, candidate counts, and a total budget, and produces an Ad Group budget allocation that satisfies explicit constraints.

## The `Strategy` Interface <span class="status-label status-recommendation" aria-label="Recommendation"></span>

```python
from abc import ABC, abstractmethod
from typing import ClassVar

class StrategyCapabilities:
    """Declare what a strategy can and cannot do."""

    requires_attribution_evidence: bool
    requires_candidate_pool: bool
    requires_fit: bool
    supports_persistence: bool
    deterministic: bool
    objective: str               # e.g., "revenue", "profit", "balanced"
    constraint_types: list[str]  # e.g., ["total_budget", "min_budget", "max_budget"]


class Strategy(ABC):
    strategy_id: ClassVar[str]
    strategy_version: ClassVar[str]
    capabilities: ClassVar[StrategyCapabilities]

    @abstractmethod
    def allocate(
        self,
        scope: StrategyScope,
        evidence: StrategyEvidence,
        constraints: StrategyConstraints,
    ) -> StrategyAllocation: ...

    @abstractmethod
    def save(self, path: str) -> str: ...

    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "Strategy": ...
```

### Identity Fields


#### `strategy_id`

**Type:** `str`

**Meaning:** Unique identifier within the strategy registry; lowercase, underscore-separated

#### `strategy_version`

**Type:** `str`

**Meaning:** [Semantic version](/en/reference/definitions) of this strategy's contract; a breaking output change must advance the major version

#### `capabilities`

**Type:** `StrategyCapabilities`

**Meaning:** Declared capabilities a caller can inspect without instantiating the strategy


### Capabilities Declaration

`StrategyCapabilities` lets a caller filter the registry before loading — the same pattern used by [`ModelCapabilities`](/en/attribution/standardized-interface/#the-model-interface) in the attribution layer.


#### `requires_attribution_evidence`

**Type:** `bool`

**Meaning:** Whether `allocate()` needs Multi-Touch Attribution (MTA) rows; `false` would mean equal-split or historical-only strategies

#### `requires_candidate_pool`

**Type:** `bool`

**Meaning:** Whether `allocate()` needs candidate Keyword and Stock Keeping Unit (SKU) counts

#### `requires_fit`

**Type:** `bool`

**Meaning:** Whether the strategy must be fitted on historical data before `allocate()`

#### `supports_persistence`

**Type:** `bool`

**Meaning:** Whether `save()`/`load()` round-trip is supported

#### `deterministic`

**Type:** `bool`

**Meaning:** Whether the same inputs always produce byte-identical outputs

#### `objective`

**Type:** `str`

**Meaning:** The business objective this strategy targets

#### `constraint_types`

**Type:** `list[str]`

**Meaning:** The constraint types this strategy can satisfy


### Input: `StrategyScope`

```python
@dataclass(frozen=True)
class StrategyScope:
    campaign_group_id: str
    marketplace: str
    advertiser_id: str
    report_start_date: str    # ISO date YYYY-MM-DD
    report_end_date: str      # ISO date YYYY-MM-DD
    campaigns: list[CampaignSpec]
```


#### `campaign_group_id`

**Meaning:** The Campaign Group this allocation is for

#### `marketplace`

**Meaning:** Advertising marketplace (e.g., `US`, `UK`)

#### `advertiser_id`

**Meaning:** Advertiser account identifier

#### `report_start_date`, `report_end_date`

**Meaning:** Observation window for the attribution evidence; must be valid [ISO dates](/en/reference/definitions#iso-date-format) and `start <= end`

#### `campaigns`

**Meaning:** Ordered list of Campaign specifications within the group


`CampaignSpec` carries the fixed properties of one Campaign:


#### `campaign_id`

**Meaning:** Unique identifier within the group

#### `ad_product`

**Meaning:** One of Sponsored Products (SP), Sponsored Brands (SB), Sponsored Display (SD), or Demand-Side Platform (DSP) (see [advertising platform terms](/en/reference/definitions#advertising-platform-terms))

#### `enabled`

**Meaning:** Whether the Campaign participates in this allocation

#### `min_ad_groups`

**Meaning:** Minimum new Ad Groups this Campaign must receive

#### `max_ad_groups`

**Meaning:** Maximum new Ad Groups this Campaign can receive

#### `min_daily_budget_per_group`

**Meaning:** Floor for each new group's daily budget


### Input: `StrategyEvidence`

```python
@dataclass(frozen=True)
class StrategyEvidence:
    attribution: list[AttributionRow]
    candidates: CandidatePool
    entity_bridge: list[EntityBridgeRow]
    lineage: EvidenceLineage
```


#### `attribution`

**Meaning:** Rows from [the governed MTA recommendation](/en/market-simulation/amc-data-contract#models-and-outputs); each row contains a touchpoint, three Outcome shares, reliability status, and recommended value

#### `candidates`

**Meaning:** Eligible candidate counts per Campaign, as in the current [`candidate_pool.json`](/en/strategy-recommendation/output-data-contract)

#### `entity_bridge`

**Meaning:** Historical touchpoint-to-entity relationships for bridging attribution grain to Campaign grain

#### `lineage`

**Meaning:** Content hashes and scope of the evidence files, matching the pattern in the [current initializer](/en/strategy-recommendation/module-overview/current-implementation#1-verify-evidence-lineage-before-calculation)


### Input: `StrategyConstraints`

```python
@dataclass(frozen=True)
class StrategyConstraints:
    total_daily_budget: float | None
    outcome_weights: dict[str, float]   # e.g., {"converted_users": 0.4, "purchase_count": 0.3, "revenue": 0.3}
    ad_group_min_budget: float
    ad_group_max_budget: float | None
    additional: dict[str, Any]          # Extension point for future constraint types
```


#### `total_daily_budget`

**Meaning:** Group-level daily budget ceiling; `None` means relative-shares-only mode

#### `outcome_weights`

**Meaning:** Weights for combining the three [MTA Outcomes](/en/attribution/#three-outcome-types) into a single score; must sum to 1

#### `ad_group_min_budget`

**Meaning:** Floor for any single Ad Group budget

#### `ad_group_max_budget`

**Meaning:** Ceiling for any single Ad Group budget; `None` means unbounded

#### `additional`

**Meaning:** Extension point for constraints not yet in the contract (inventory, pacing, margin)


### Output: `StrategyAllocation`

```python
@dataclass(frozen=True)
class StrategyAllocation:
    strategy_id: str
    strategy_version: str
    scope: StrategyScope
    lineage: EvidenceLineage
    allocation_type: str         # "INITIAL_SEED" | "OPTIMIZED"
    campaigns: list[CampaignAllocation]
    conservation: ConservationReport
    warnings: list[str]
```


#### `strategy_id`, `strategy_version`

**Meaning:** Which strategy and contract produced this allocation

#### `scope`

**Meaning:** The Campaign Group scope this allocation was computed for

#### `lineage`

**Meaning:** Evidence lineage, carried forward from input for auditability

#### `allocation_type`

**Meaning:** Whether this is an unoptimized seed or an optimized result

#### `campaigns`

**Meaning:** One allocation record per Campaign

#### `conservation`

**Meaning:** Report proving budget and share conservation

#### `warnings`

**Meaning:** Ordered, non-repeating warning codes (e.g., `NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY`)


`CampaignAllocation` mirrors the current [Ad Group output contract](/en/strategy-recommendation/strategy-output-contract#4-ad-group-output):


#### `campaign_id`

**Meaning:** Campaign within the group

#### `ad_product`

**Meaning:** Advertising product of the Campaign

#### `recommended_ad_group_count`

**Meaning:** Number of new Ad Groups

#### `count_rationale`

**Meaning:** Candidate counts, capacities, and how the count was derived

#### `campaign_mta_score`

**Meaning:** Weighted Outcome contribution for this Campaign

#### `budget_seed_share`

**Meaning:** Campaign's share of the total budget

#### `campaign_budget_seed`

**Meaning:** Absolute Campaign budget, when a total is supplied

#### `ad_groups`

**Meaning:** Ordered list of anonymous Ad Group budget slots

#### `execution_status`

**Meaning:** `EXECUTABLE`, `INSUFFICIENT_BUDGET_FOR_MINIMUMS`, or `UNEXECUTABLE`


## Conservation Contract <span class="status-label status-recommendation" aria-label="Recommendation"></span>

Every strategy must satisfy the same conservation invariants as the current initializer. The evaluation framework enforces them, so a strategy that fails conservation is rejected before scoring.

$$
\begin{aligned}
\sum_{g\in c} s_{c,g} &= s_c &&\text{(1) Within-Campaign share conservation},\\[4pt]
\sum_c s_c &= 1 &&\text{(2) Campaign shares sum to one},\\[4pt]
\sum_{g\in c} B_{c,g} &= B_c &&\text{(3) Within-Campaign budget conservation},\\[4pt]
\sum_c B_c &\le B_{\mathrm{total}} &&\text{(4) Group budget not exceeded}.
\end{aligned}
$$

Constraint (4) is an inequality: a strategy may leave budget unallocated, but it must not exceed the total. When no total budget is supplied, monetary constraints are relaxed and only share constraints (1) and (2) apply.

**Tolerances** follow the attribution-layer precedent:


#### Share conservation

**Absolute tolerance:** `1e-12`

**Relative tolerance:** —

#### Budget conservation

**Absolute tolerance:** `1e-6`

**Relative tolerance:** `1e-9`


## Status Labels

This document uses the same status labels as the rest of the documentation:

- <span class="status-label status-recommendation" aria-label="Recommendation"></span> **Recommendation**: proposed design awaiting review and implementation.
- <span class="status-label status-verified" aria-label="Verified"></span> **Verified**: confirmed by code or data (no section is verified yet — the implementation does not exist).

## References

- [Strategy evaluation framework](./index.md)
- [Strategy loader](./strategy-loader.md)
- [Standardized MTA interface](/en/attribution/standardized-interface/)
- [Strategy output contract](/en/strategy-recommendation/strategy-output-contract)
- [Ad Group initial-budget output data contract](/en/strategy-recommendation/output-data-contract)
