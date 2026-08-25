---
title: Initializer Current Implementation
compact: "Algorithm and validation details for the implemented MTA-to-budget initializer: strict inputs, evidence selection, Campaign bridging and scoring, capacity ceilings, equal Ad Group split, invariants, errors, output fields, and worked formulas."
lang: en-US
---

# Initializer Current Implementation

## Current Implementation <span class="status-label status-verified" aria-label="Verified"></span>

The implementation is a deterministic initializer, not a learned optimizer. Its main function, `generate_budget_recommendation()` in `modules/mta_strategy_recommendation/src/budget_recommender.py`, follows this execution order:

### 1. Load aligned evidence

- **Code:** `load_aligned_strategy_inputs()`
- **Algorithm responsibility:** Read request, candidate counts, MTA recommendations, and entity bridge; verify files, hashes, counts, and scope
- **Why it is separate:** A valid allocation must be reproducible from the exact referenced AMC evidence

### 2. Validate the strategy contract

- **Code:** `_campaign_inputs()`
- **Algorithm responsibility:** Require exact schemas, four enabled product Campaigns, normalized Outcome weights, and capacity rules
- **Why it is separate:** Unexpected fields or missing products must not silently alter the allocation universe

### 3. Convert governed MTA values to points

- **Code:** `_recommended_point()`
- **Algorithm responsibility:** Use a reliable point directly or the midpoint of an unreliable interval
- **Why it is separate:** The initializer requires a scalar, while retaining an explicit warning that a range was collapsed

### 4. Bridge touchpoints to Campaigns

- **Code:** `_bridge_campaign_scores()`
- **Algorithm responsibility:** Map the five-segment touchpoint's ad product to its Campaign and verify supporting historical entities
- **Why it is separate:** MTA is at touchpoint grain, but the budget decision begins at Campaign grain

### 5. Combine Outcomes

- **Code:** `_bridge_campaign_scores()`
- **Algorithm responsibility:** Weight converted-user, purchase-count, and revenue contributions into a Campaign MTA score
- **Why it is separate:** The three business Outcomes remain separate until an explicit weighted combination

### 6. Calculate group count

- **Code:** `recommend_ad_group_count()`
- **Algorithm responsibility:** Convert eligible-candidate counts and product capacities into the minimum feasible number of new groups
- **Why it is separate:** Count is an execution-capacity calculation, not a performance prediction

### 7. Allocate the seed

- **Code:** `generate_budget_recommendation()`
- **Algorithm responsibility:** Normalize Campaign scores and split each Campaign share equally among its anonymous new groups
- **Why it is separate:** No evidence exists to distinguish future groups within the same Campaign

### 8. Regenerate and validate

- **Code:** `validate_simulated_hierarchy()`
- **Algorithm responsibility:** Reject forbidden fields, compare against a fresh deterministic result, and test conservation
- **Why it is separate:** The checked file must be exactly reproducible and budget-only

### 1. Verify Evidence Lineage before Calculation

The command-line generator first calls `load_aligned_strategy_inputs()` in `src/hierarchy_validator.py`. Its critical evidence block is:

```python
attribution = _resolve_evidence_path(                               # 1
    attribution_path, source["attribution_file"], "AMC attribution file")
entity = _resolve_evidence_path(                                    # 2
    entity_path, source["entity_file"], "AMC entity file")
if _sha256(attribution) != source["attribution_sha256"]:            # 3
    raise HierarchyValidationError(...)                             # 4
if _sha256(entity) != source["entity_sha256"]:                      # 5
    raise HierarchyValidationError(...)                             # 6
attribution_rows = _read_csv(attribution)                           # 7
entity_rows = _read_csv(entity)                                     # 8
```

#### Line 1-2

- **Detailed step:** Resolve explicit evidence paths when supplied, otherwise use the paths declared by the request
- **Mapping to the algorithm:** Selects the MTA and bridge snapshots that feed the score
- **Why it is implemented this way:** The data can live outside the module without depending on repository-relative imports

#### Line 3-6

- **Detailed step:** Compare each file's Secure Hash Algorithm 256-bit (SHA-256) digest with the request
- **Mapping to the algorithm:** Locks the calculation to exact evidence bytes
- **Why it is implemented this way:** A file with the same name but changed rows must not reproduce under the old lineage identifier

#### Line 7-8

- **Detailed step:** Parse evidence only after integrity passes
- **Mapping to the algorithm:** Establishes the in-memory rows used by the pure recommender
- **Why it is implemented this way:** No score is calculated from unverified evidence

The loader then verifies declared touchpoint and entity row counts, reporting window, marketplace, advertiser, Campaign Group, and the Campaign/ad-product relationship of every entity row. `_campaign_inputs()` adds exact-key validation, requires one enabled Campaign for each supported product, requires Outcome weights to sum to one, and requires the candidate pool to use the same lineage and `USE_ALL_ELIGIBLE` policy.

### 2. Turn a Governed MTA Recommendation into One Scalar

The attribution handoff contains either a reliable point or an unreliable interval. `_recommended_point()` handles both representations explicitly:

```python
status = _required_text(row.get("reliability_status"), ...)          # 1
value = row.get("recommended_value")                                 # 2
if status == "RELIABLE":                                            # 3
    point = _number(value, ...)                                      # 4
    if point > 1.0:                                                  # 5
        raise BudgetRecommendationError(...)
    return point, status                                             # 6
if status != "UNRELIABLE":                                          # 7
    raise BudgetRecommendationError(...)
parts = value[1:-1].split(",")                                      # 8
if len(parts) != 2:                                                 # 9
    raise BudgetRecommendationError(...)
low = _number(parts[0], ...)                                        # 10
high = _number(parts[1], ...)                                       # 11
if low > high or high > 1.0:                                       # 12
    raise BudgetRecommendationError(...)
return (low + high) / 2.0, status                                  # 13
```

#### Line 1-2

- **Detailed step:** Read reliability and recommendation as a coupled contract
- **Algorithm mapping and reason:** A numeric string cannot be interpreted without knowing whether it is a point or range

#### Line 3-6

- **Detailed step:** Validate a reliable recommendation as a non-negative share no greater than one, then use it unchanged
- **Algorithm mapping and reason:** Reliable AMC rows designate Markov as the official point estimate

#### Line 7

- **Detailed step:** Reject any unrecognized governance state
- **Algorithm mapping and reason:** The initializer does not invent behavior for an undefined status

#### Line 8-9

- **Detailed step:** Split the bracket contents and require exactly two fields
- **Algorithm mapping and reason:** Preserves the exact two-endpoint interval shape emitted by AMC MTA

#### Line 10-12

- **Detailed step:** Parse non-negative numeric endpoints, require ascending order, and cap the high endpoint at one
- **Algorithm mapping and reason:** Ensures the interval is a valid range of attribution shares

#### Line 13

- **Detailed step:** Use the arithmetic midpoint as the disclosed representative point
- **Algorithm mapping and reason:** A deterministic scalar is needed for the initial seed; the result records `UNRELIABLE_MTA_RANGE_MIDPOINT_USED`

The midpoint is a current implementation policy, not evidence that the center is more likely than the endpoints. A future optimizer may propagate uncertainty instead, but that is outside this initializer.

### 3. Bridge Touchpoints to Historical Entities and Campaigns

Each Multi-Touch Attribution (MTA) row is keyed by `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`. `_touchpoint_product()` delegates five-segment validation and parsing to the canonical `mta_common` touchpoint adapter, then reads `ad_product` to find the one Campaign for that ad product. `_bridge_campaign_scores()` then finds historical entity rows matching both touchpoint and Campaign.

For each touchpoint and Outcome, the bridge chooses an entity weighting field with `_entity_weight_method()`:

```python
assisted_metric = ASSISTED_METRIC_BY_OUTCOME[outcome]                # 1
for metric in (assisted_metric, *BRIDGE_FALLBACK_METRICS):          # 2
    values = [_number(row.get(metric), ...) for row in rows]        # 3
    if sum(values) > 0:                                             # 4
        return metric.upper(), values                               # 5
return "EQUAL", [1.0] * len(rows)                                  # 6
```

#### Line 1

- **Detailed step:** Select the Outcome-matched assisted metric
- **Mapping and reason:** Converted users, purchases, and revenue should use their corresponding entity evidence first

#### Line 2

- **Detailed step:** Try that metric, then clicks, impressions, and unique users
- **Mapping and reason:** Defines a deterministic evidence-quality fallback order

#### Line 3-4

- **Detailed step:** Validate non-negative values and require positive total mass
- **Mapping and reason:** A zero-total metric cannot define proportions

#### Line 5

- **Detailed step:** Return the first usable method and weights
- **Mapping and reason:** The selected method is recorded for auditability

#### Line 6

- **Detailed step:** Use equal weights only when no evidence field has positive mass
- **Mapping and reason:** Every matched historical entity remains representable without division by zero

The allocation block is:

```python
denominator = sum(entity_weights)                                   # 1
for entity, value in zip(matching_entities, entity_weights):        # 2
    historical_allocations[entity["ad_group_id"]] += (              # 3
        recommended_value * value / denominator                     # 4
    )
allocated = sum(historical_allocations.values())                    # 5
if not math.isclose(allocated, recommended_value, abs_tol=1e-12):   # 6
    raise BudgetRecommendationError(...)                            # 7
outcome_contributions[campaign_id][outcome] += allocated            # 8
```

#### Line 1

- **Detailed step:** Sum the selected bridge weights
- **Algorithm mapping:** Creates the within-touchpoint normalization denominator
- **Why it is implemented this way:** The touchpoint's MTA value must be conserved

#### Line 2-4

- **Detailed step:** Allocate the recommendation across matching historical Ad Groups in proportion to the selected metric
- **Algorithm mapping:** Verifies a concrete touchpoint-to-entity bridge
- **Why it is implemented this way:** Historical entity evidence establishes Campaign membership but does not become a direct score for future groups

#### Line 5-7

- **Detailed step:** Re-sum and compare to the original recommendation at `1e-12` tolerance
- **Algorithm mapping:** Tests local conservation
- **Why it is implemented this way:** A missing or duplicated bridge allocation must stop the run

#### Line 8

- **Detailed step:** Roll the conserved touchpoint value up to its Campaign and Outcome
- **Algorithm mapping:** Produces the grain needed for Campaign scoring
- **Why it is implemented this way:** The historical split is auditable, but the current output creates anonymous new groups rather than reusing historical group IDs

After all rows, the function also requires every touchpoint to contain all three Outcomes, every entity touchpoint to exist in attribution, and each Outcome's `recommended_value` total to equal one. These checks ensure the Campaign contributions form a complete allocation universe.

### 4. Combine the Three Outcomes into a Campaign Score

For Campaign $c$, the code calculates:

$$
\text{Campaign MTA score}(c)
= \sum_{o \in \{\text{converted users},\text{purchase count},\text{revenue}\}}
\text{Outcome weight}(o)\times\text{Campaign contribution}(c,o)
$$

The corresponding code is intentionally short:

```python
contributions = outcome_contributions[campaign_id]                  # 1
score = sum(                                                        # 2
    weights[outcome] * contributions[outcome]                       # 3
    for outcome in OUTCOMES                                         # 4
)
```

#### Line 1

- **Detailed step:** Retrieve the Campaign's three separately conserved contribution shares
- **Why:** Keeps source Outcomes inspectable in the output

#### Line 2-4

- **Detailed step:** Multiply each share by its explicit request weight and add the products
- **Why:** This is the only point where heterogeneous business Outcomes are combined; the weights make that choice visible and reproducible

The recommender rejects a non-positive total Campaign score because it could not normalize such scores into a budget-share distribution.

### 5. Derive the Minimum Feasible Number of New Ad Groups

`recommend_ad_group_count()` uses ceiling division:

```python
def _ceil_ratio(count, capacity):                                   # 1
    return 0 if count == 0 else (count + capacity - 1) // capacity  # 2
```

Line 1 defines how many containers are needed for a candidate type. Line 2 returns zero for no candidates and otherwise performs integer ceiling division, because a partially filled final group still requires a complete group slot.

For SP and SB, the key capacity block is:

```python
capacity_counts = {                                                 # 1
    "keyword_capacity_count": _ceil_ratio(                          # 2
        counts["eligible_keyword_unit_count"], keyword_capacity
    ),
    "sku_capacity_count": _ceil_ratio(                              # 3
        counts["eligible_sku_count"], sku_capacity
    ),
    "legal_pair_capacity_count": _ceil_ratio(                       # 4
        counts["eligible_legal_pair_count"], pair_capacity
    ),
    "target_capacity_count": 0,                                    # 5
    "audience_capacity_count": 0,                                  # 6
}
capacity_required = max(min_groups, *capacity_counts.values())      # 7
```

For SD and DSP, lines 2 and 4 are replaced by target and audience ceiling ratios, while keyword and legal-pair counts must be zero. The maximum in line 7 is used because every capacity constraint must be satisfied simultaneously: the tightest dimension determines the number of groups, subject to `min_ad_groups`. A result above `max_ad_groups` is infeasible and raises an error instead of being silently capped.

The minimum executable Campaign budget is then:

$$
\text{Minimum required daily budget}(c)
= \text{Recommended group count}(c)
\times \text{Minimum daily budget per group}(c)
$$

This minimum is a feasibility check. It does not change the score-based seed allocation.

### 6. Normalize Campaign Scores and Split within Each Campaign

The main allocation block in `generate_budget_recommendation()` is:

```python
score_total = sum(                                                   # 1
    bridge[campaign["campaign_id"]]["campaign_mta_score"]
    for campaign in campaigns
)
campaign_score = bridge[campaign_id]["campaign_mta_score"]          # 2
campaign_share = campaign_score / score_total                       # 3
campaign_budget = campaign_share * (total_budget or 0.0)            # 4
group_share = campaign_share / count                                # 5
for position in range(1, count + 1):                                # 6
    slot_id = f"{campaign_id}_NEW_AG_{position:02d}"                 # 7
    ad_group = {"budget_seed_share": group_share}                   # 8
    ad_group["initial_daily_budget"] = (                            # 9
        group_share * (total_budget or 0.0)
    )
```

#### Line 1

- **Detailed step:** Sum the four Campaign MTA scores
- **Algorithm mapping:** Defines the Campaign normalization universe
- **Why it is implemented this way:** The current Campaign Group is the full budget universe

#### Line 2-3

- **Detailed step:** Read one Campaign score and divide it by the total
- **Algorithm mapping:** Converts heterogeneous weighted scores into shares summing to one
- **Why it is implemented this way:** Only relative score matters for allocation

#### Line 4

- **Detailed step:** Apply the optional Group daily budget
- **Algorithm mapping:** Converts the share to currency
- **Why it is implemented this way:** When no total budget is supplied, the module returns relative shares only

#### Line 5

- **Detailed step:** Divide the Campaign share by its capacity-derived count
- **Algorithm mapping:** Implements equal allocation within the Campaign
- **Why it is implemented this way:** The current data contains no evidence about the anonymous future groups' relative performance

#### Line 6-7

- **Detailed step:** Create a deterministic new-slot identifier and reject collisions with historical IDs
- **Algorithm mapping:** Represents proposed groups without pretending they already exist
- **Why it is implemented this way:** Historical bridge entities and new execution slots must remain distinct

#### Line 8-9

- **Detailed step:** Store both proportional and, when possible, monetary seed values
- **Algorithm mapping:** Supports downstream use with or without a budget baseline
- **Why it is implemented this way:** The same conservation relationship is visible in both units

If a Campaign's score-based budget is below its calculated minimum, the code retains the seed but marks `INSUFFICIENT_BUDGET_FOR_MINIMUMS`; it does not steal budget from another Campaign or claim the plan is executable. If no Group budget is provided, it emits `BUDGET_BASELINE_NOT_PROVIDED` and omits monetary fields.

### 7. Regenerate the Result and Verify Conservation

`validate_simulated_hierarchy()` does not validate only the JSON shape. It regenerates the expected result from the verified inputs, recursively finds the first type, field, length, or value difference, and rejects any output that is not exactly deterministic. It also recursively rejects forbidden strategy fields so a budget-only result cannot acquire targeting or activation content.

The final invariant block verifies the following relationships:

$$
\begin{aligned}
\sum_{g\in c}s_{c,g}&=s_c, &&\text{(1)}\\
\sum_{g\in c}B_{c,g}&=B_c, &&\text{(2)}\\
\sum_c s_c&=1, &&\text{(3)}\\
\sum_c B_c&=B_{\mathrm{seed}}. &&\text{(4)}
\end{aligned}
$$

Lines 1 and 2 conserve each Campaign allocation across its new groups. Lines 3 and 4 conserve the complete Campaign Group in proportional and monetary units. The implementation uses `math.fsum()` and explicit absolute tolerances to account for floating-point representation while still rejecting material drift.

### Current Deliverables

- `strategy_request.json`: Group scope, four Campaigns, AMC lineage, Outcome weights, capacity, and minimum budget.
- `candidate_pool.json`: eligible-candidate counts for each Campaign; it does not store specific candidate IDs.
- `budget_recommender.py`: the pure calculation for count, AMC bridge, Campaign scores, and equal splitting among anonymous groups.
- `outputs/initial_budget_recommendation.json`: the deterministically generated canonical budget result and the only test baseline.
- `hierarchy_validator.py`: the evidence-alignment, exact-regeneration, forbidden-field, and conservation validator.
- AMC files remain read-only; `assisted_*` fields are used only as within-touchpoint bridge weights.
