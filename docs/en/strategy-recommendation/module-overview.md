---
title: MTA-Driven Ad Group Budget Initializer
description: Deterministic Campaign and Ad Group budget seed derived from governed MTA evidence and capacity constraints
compact: "Implemented strategy contract: evidence pinning, MTA-to-Campaign bridge, weighted Campaign scores, capacity-derived Ad Group counts, equal budget split, validation invariants, and source-file API reference."
lang: en-US
source_files: modules/mta_strategy_recommendation/src/hierarchy_validator.py, modules/mta_strategy_recommendation/src/budget_recommender.py, script/generate_initial_budget.py, script/validate_simulated_hierarchy.py
provenance:
  original_author: Jiahao Yao
  original_handle: yao-LLL
  source_branch: codex/yao-friday-reference
  source_commit: 3c4aa9e64d270b5be670c5b23fa4a8cc50bb5434
---

# MTA-Driven Ad Group Budget Initializer

This module generates only the **count and initial budget** of new Ad Groups. It does not generate Keyword/SKU assignments, Targeting, actions, or strategy roles, and it does not optimize, assess causal incrementality, or activate automatically.

Candidate counts and product capacities determine each Campaign's new Ad Group count. MTA Outcomes and the AMC entity bridge determine Campaign budget shares. Each Campaign share is then divided by its anonymous new-group count to obtain the initial budget for every new Ad Group.

The current Campaign Group always contains four Campaigns, using Sponsored Products (SP), Sponsored Brands (SB), Sponsored Display (SD), and Amazon Demand-Side Platform (DSP) respectively. The actual capacity result for the v4 sample is `1/1/1/1`; it is calculated from the inputs rather than hard-coded.

## Current Implementation <span class="status-label status-verified" aria-label="Verified"></span>

The implementation is a deterministic initializer, not a learned optimizer. Its main function, `generate_budget_recommendation()` in `modules/mta_strategy_recommendation/src/budget_recommender.py`, follows this execution order:

| Stage | Code | Algorithm responsibility | Why it is separate |
| --- | --- | --- | --- |
| 1. Load aligned evidence | `load_aligned_strategy_inputs()` | Read request, candidate counts, MTA recommendations, and entity bridge; verify files, hashes, counts, and scope | A valid allocation must be reproducible from the exact referenced AMC evidence |
| 2. Validate the strategy contract | `_campaign_inputs()` | Require exact schemas, four enabled product Campaigns, normalized Outcome weights, and capacity rules | Unexpected fields or missing products must not silently alter the allocation universe |
| 3. Convert governed MTA values to points | `_recommended_point()` | Use a reliable point directly or the midpoint of an unreliable interval | The initializer requires a scalar, while retaining an explicit warning that a range was collapsed |
| 4. Bridge touchpoints to Campaigns | `_bridge_campaign_scores()` | Map the five-segment touchpoint's ad product to its Campaign and verify supporting historical entities | MTA is at touchpoint grain, but the budget decision begins at Campaign grain |
| 5. Combine Outcomes | `_bridge_campaign_scores()` | Weight converted-user, purchase-count, and revenue contributions into a Campaign MTA score | The three business Outcomes remain separate until an explicit weighted combination |
| 6. Calculate group count | `recommend_ad_group_count()` | Convert eligible-candidate counts and product capacities into the minimum feasible number of new groups | Count is an execution-capacity calculation, not a performance prediction |
| 7. Allocate the seed | `generate_budget_recommendation()` | Normalize Campaign scores and split each Campaign share equally among its anonymous new groups | No evidence exists to distinguish future groups within the same Campaign |
| 8. Regenerate and validate | `validate_simulated_hierarchy()` | Reject forbidden fields, compare against a fresh deterministic result, and test conservation | The checked file must be exactly reproducible and budget-only |

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

| Line | Detailed step | Mapping to the algorithm | Why it is implemented this way |
| --- | --- | --- | --- |
| 1-2 | Resolve explicit evidence paths when supplied, otherwise use the paths declared by the request | Selects the MTA and bridge snapshots that feed the score | The data can live outside the module without depending on repository-relative imports |
| 3-6 | Compare each file's Secure Hash Algorithm 256-bit (SHA-256) digest with the request | Locks the calculation to exact evidence bytes | A file with the same name but changed rows must not reproduce under the old lineage identifier |
| 7-8 | Parse evidence only after integrity passes | Establishes the in-memory rows used by the pure recommender | No score is calculated from unverified evidence |

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

| Line | Detailed step | Algorithm mapping and reason |
| --- | --- | --- |
| 1-2 | Read reliability and recommendation as a coupled contract | A numeric string cannot be interpreted without knowing whether it is a point or range |
| 3-6 | Validate a reliable recommendation as a non-negative share no greater than one, then use it unchanged | Reliable AMC rows designate Markov as the official point estimate |
| 7 | Reject any unrecognized governance state | The initializer does not invent behavior for an undefined status |
| 8-9 | Split the bracket contents and require exactly two fields | Preserves the exact two-endpoint interval shape emitted by AMC MTA |
| 10-12 | Parse non-negative numeric endpoints, require ascending order, and cap the high endpoint at one | Ensures the interval is a valid range of attribution shares |
| 13 | Use the arithmetic midpoint as the disclosed representative point | A deterministic scalar is needed for the initial seed; the result records `UNRELIABLE_MTA_RANGE_MIDPOINT_USED` |

The midpoint is a current implementation policy, not evidence that the center is more likely than the endpoints. A future optimizer may propagate uncertainty instead, but that is outside this initializer.

### 3. Bridge Touchpoints to Historical Entities and Campaigns

Each MTA row is keyed by `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`. `_touchpoint_product()` validates all five segments and reads the first segment to find the one Campaign for that ad product. `_bridge_campaign_scores()` then finds historical entity rows matching both touchpoint and Campaign.

For each touchpoint and Outcome, the bridge chooses an entity weighting field with `_entity_weight_method()`:

```python
assisted_metric = ASSISTED_METRIC_BY_OUTCOME[outcome]                # 1
for metric in (assisted_metric, *BRIDGE_FALLBACK_METRICS):          # 2
    values = [_number(row.get(metric), ...) for row in rows]        # 3
    if sum(values) > 0:                                             # 4
        return metric.upper(), values                               # 5
return "EQUAL", [1.0] * len(rows)                                  # 6
```

| Line | Detailed step | Mapping and reason |
| --- | --- | --- |
| 1 | Select the Outcome-matched assisted metric | Converted users, purchases, and revenue should use their corresponding entity evidence first |
| 2 | Try that metric, then clicks, impressions, and unique users | Defines a deterministic evidence-quality fallback order |
| 3-4 | Validate non-negative values and require positive total mass | A zero-total metric cannot define proportions |
| 5 | Return the first usable method and weights | The selected method is recorded for auditability |
| 6 | Use equal weights only when no evidence field has positive mass | Every matched historical entity remains representable without division by zero |

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

| Line | Detailed step | Algorithm mapping | Why it is implemented this way |
| --- | --- | --- | --- |
| 1 | Sum the selected bridge weights | Creates the within-touchpoint normalization denominator | The touchpoint's MTA value must be conserved |
| 2-4 | Allocate the recommendation across matching historical Ad Groups in proportion to the selected metric | Verifies a concrete touchpoint-to-entity bridge | Historical entity evidence establishes Campaign membership but does not become a direct score for future groups |
| 5-7 | Re-sum and compare to the original recommendation at `1e-12` tolerance | Tests local conservation | A missing or duplicated bridge allocation must stop the run |
| 8 | Roll the conserved touchpoint value up to its Campaign and Outcome | Produces the grain needed for Campaign scoring | The historical split is auditable, but the current output creates anonymous new groups rather than reusing historical group IDs |

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

| Line | Detailed step | Why |
| --- | --- | --- |
| 1 | Retrieve the Campaign's three separately conserved contribution shares | Keeps source Outcomes inspectable in the output |
| 2-4 | Multiply each share by its explicit request weight and add the products | This is the only point where heterogeneous business Outcomes are combined; the weights make that choice visible and reproducible |

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

| Line | Detailed step | Algorithm mapping | Why it is implemented this way |
| --- | --- | --- | --- |
| 1 | Sum the four Campaign MTA scores | Defines the Campaign normalization universe | The current Campaign Group is the full budget universe |
| 2-3 | Read one Campaign score and divide it by the total | Converts heterogeneous weighted scores into shares summing to one | Only relative score matters for allocation |
| 4 | Apply the optional Group daily budget | Converts the share to currency | When no total budget is supplied, the module returns relative shares only |
| 5 | Divide the Campaign share by its capacity-derived count | Implements equal allocation within the Campaign | The current data contains no evidence about the anonymous future groups' relative performance |
| 6-7 | Create a deterministic new-slot identifier and reject collisions with historical IDs | Represents proposed groups without pretending they already exist | Historical bridge entities and new execution slots must remain distinct |
| 8-9 | Store both proportional and, when possible, monetary seed values | Supports downstream use with or without a budget baseline | The same conservation relationship is visible in both units |

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

## Run

```bash
uv run python -X utf8 -B script/generate_initial_budget.py --check-output
uv run python -X utf8 -B script/validate_simulated_hierarchy.py
python3 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -p 'test_*.py'
```

Without `--check-output`, the generator writes its result to standard output so downstream consumers can save it separately. The old `--check-fixture` option remains as a compatibility alias; current documentation and new calls consistently use `--check-output`.

## Documentation

- [Overall model plan](model-plan.md)
- [Detailed current Ad Group initial-budget calculation](current-budget-calculation.md)
- [Problem definition and research plan from MTA to Ad Group budget](optimization-plan.md)
- [Output data contract](output-data-contract.md)
- [Budget strategy output contract](strategy-output-contract.md)
- [Simulated input description](../market-simulation/strategy-simulated-data.md)
- Canonical initial-budget result: `modules/mta_strategy_recommendation/outputs/initial_budget_recommendation.json`

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

This section is the code-level contract for the four Python files that implement
and expose the initializer. It follows the current documentation architecture:
source contracts remain in the owning module page rather than in a parallel
`implementation/` tree.

### `budget_recommender.py`

Source: `modules/mta_strategy_recommendation/src/budget_recommender.py`

**Responsibility.** Validate the already aligned strategy objects, calculate
Campaign scores and capacity-derived Ad Group counts, and return the deterministic
`INITIAL_SEED` recommendation. The module consumes attribution artifacts; it does
not call attribution-model Python code and does not activate advertising entities.

**Primary input.** `generate_budget_recommendation(request, pool,
attribution_rows, entity_rows)` receives the complete validated request and pool
objects plus governed MTA and historical entity rows. The pool contains anonymous
candidate counts rather than candidate identities.

**Output.** One Campaign Group recommendation containing Campaign Outcome
contributions, MTA score, proportional and optional monetary seed, anonymous new
Ad Group slots, feasibility status, evidence derivation, and warnings. It always
reports `recommendation_type = INITIAL_SEED` and `is_optimized = false`.

#### API and helper contract

| Symbol | Contract |
| --- | --- |
| `BudgetRecommendationError` | Raised for malformed strategy objects, unsupported products, incomplete attribution, impossible capacities, bridge failures, and non-conserving score inputs. |
| `_exact_keys()` | Requires an object to contain exactly the declared keys; both missing and unexpected keys fail. |
| `_required_text()` | Accepts only a non-empty trimmed string and returns its trimmed value. |
| `_number()` | Accepts a finite Python numeric value at or above the supplied minimum. Booleans are rejected. |
| `_json_number()` | Applies `_number()` and additionally requires a real JSON numeric type rather than a numeric string. |
| `_integer()` | Accepts a non-Boolean integer at or above the supplied minimum. |
| `_objects()` | Requires a JSON list whose every member is an object and returns those objects. |
| `_index_unique()` | Indexes rows by a required text field and rejects duplicate identifiers. |
| `_ceil_ratio()` | Returns zero for zero demand; otherwise calculates integer ceiling division for one capacity dimension. |
| `_touchpoint_product()` | Parses the first segment of the five-part touchpoint and requires one of the four supported Ad Products. |
| `_recommended_point()` | Uses a `RELIABLE` numeric recommendation directly; for `UNRELIABLE` `[low,high]`, returns the midpoint and the midpoint warning. |
| `_campaign_inputs()` | Validates sample version, Campaign Group, Campaigns, Outcome weights, budget, pool lineage, candidate counts, product-specific fields, capacities, and minimum budgets; returns normalized calculation inputs. |
| `recommend_ad_group_count()` | Applies the SP/SB or SD/DSP ceiling-capacity formula, respects `min_ad_groups`, and fails rather than silently capping a result above `max_ad_groups`. |
| `_entity_weight_method()` | Selects the first bridge metric with positive mass: Outcome-specific `assisted_*`, then clicks, impressions, unique users, then equal weights. |
| `_bridge_campaign_scores()` | Maps touchpoint/Outcome values through matching historical entity rows, verifies touchpoint conservation, aggregates Campaign Outcome contributions, and applies Outcome weights to obtain `campaign_mta_score`. |
| `generate_budget_recommendation()` | Normalizes Campaign scores, calculates optional Campaign budgets, checks minimum-budget feasibility, equally divides each Campaign seed among anonymous new slots, and emits derivation and warning metadata. |

#### Calculation boundary

For Campaign $c$ and Outcome $o$, bridged contribution is:

$$
C_{c,o}=\sum_t V_{t,o}\,E_{t,o,c}
$$

where $V_{t,o}$ is the governed MTA point and $E_{t,o,c}$ is the conserved
entity-bridge share assigned to Campaign $c$. The weighted Campaign score is:

$$
S_c=\sum_o w_o C_{c,o}
$$

and the Campaign budget share is:

$$
P_c=\frac{S_c}{\sum_j S_j}
$$

For $N_c$ anonymous new slots in Campaign $c$ and Group budget $B$:

$$
B_{c,g}=B\times P_c\times\frac{1}{N_c}
$$

This is historical-credit initialization, not a response curve, causal lift
estimate, marginal ROAS model, or constrained optimum.

**Dependencies.** Python standard library and the four aligned data objects.

**Verification.** `modules/mta_strategy_recommendation/tests/test_hierarchy_validator.py`
exercises the public generator and all failure, bridge, capacity, warning, and
conservation boundaries.

### `hierarchy_validator.py`

Source: `modules/mta_strategy_recommendation/src/hierarchy_validator.py`

**Responsibility.** Load and align the exact evidence snapshot, verify that a
committed recommendation is a deterministic result of it, reject activation or
candidate-assignment content, and enforce proportional and monetary conservation.

#### API and helper contract

| Symbol | Contract |
| --- | --- |
| `HierarchyValidationError` | Public validation failure for unreadable inputs, evidence mismatch, schema/scope violations, output drift, forbidden fields, or failed invariants. |
| `_read_json()` | Reads one UTF-8 JSON object and rejects unreadable, malformed, or non-object roots. |
| `_read_csv()` | Reads one UTF-8 CSV through `DictReader` and requires a header. |
| `_sha256()` | Streams exact file bytes into SHA-256; evidence identity is byte-level rather than filename-level. |
| `_required_text()` | Requires a non-empty trimmed text value for lineage and scope comparisons. |
| `_integer()` | Requires a non-Boolean integer at or above the supplied minimum. |
| `_resolve_evidence_path()` | Uses an explicit CLI path when supplied; otherwise resolves the path declared by the request and requires an existing file. |
| `_forbidden_paths()` | Recursively locates candidate IDs, targeting assignments, actions, roles, pairings, entity evidence, and historical/source Ad Group fields forbidden in the budget-only output. |
| `_first_difference()` | Recursively reports the first object-field, list-length, primitive-type, or exact primitive-value difference between fresh and committed results. |
| `_validate_budget_invariants()` | Uses `math.fsum()` and explicit tolerances to check Campaign and Ad Group share conservation and, when a budget exists, monetary conservation. |
| `load_aligned_strategy_inputs()` | Reads request and pool JSON plus attribution and entity CSVs; verifies hashes, row counts, sample version, report/advertiser/marketplace/Group scope, Campaign/product coverage, MTA Outcome completeness, and bridge compatibility. |
| `validate_simulated_hierarchy()` | Reloads evidence, regenerates the recommendation, runs exact comparison, forbidden-field checks, and invariants, then returns a compact validation summary. |

**Inputs and outputs.** `load_aligned_strategy_inputs(data_dir,
attribution_path, entity_path)` returns the validated request, pool, attribution
rows, and entity rows. `validate_simulated_hierarchy()` additionally reads the
recommendation path and returns a summary containing Campaign and recommended
Ad Group counts, evidence counts, normalization universe, budget-baseline state,
recommendation type, and warnings.

**Dependencies.** `budget_recommender.py` and Python standard library.

**Verification.** `modules/mta_strategy_recommendation/tests/test_hierarchy_validator.py`.

### `generate_initial_budget.py`

Source: `script/generate_initial_budget.py`

**Responsibility.** Project-level CLI for loading aligned evidence and invoking
`generate_budget_recommendation()`.

| Interface | Behavior |
| --- | --- |
| `--data-dir` | Selects the directory containing `strategy_request.json` and `candidate_pool.json`. |
| `--attribution` | Overrides the governed MTA attribution CSV path. |
| `--entity` | Overrides the historical entity-bridge CSV path. |
| `--output` / `--fixture` | Selects the canonical result checked by check mode. |
| `--check-output` / `--check-fixture` | Generates in memory and requires exact `json.dumps(..., indent=2)` output after CRLF-to-LF normalization. |
| normal mode | Prints generated JSON to standard output and does not overwrite the canonical artifact. |
| exit `0` | Generation succeeded or check mode matched exactly. |
| exit `1` | Input/evidence loading, generation, file reading, or exact comparison failed; the reason is written to standard error. |

`main()` resolves the repository root, parses the arguments, loads inputs through
`load_aligned_strategy_inputs()`, generates the seed, and chooses print or exact
check behavior.

### `validate_simulated_hierarchy.py`

Source: `script/validate_simulated_hierarchy.py`

**Responsibility.** Read-only end-to-end preflight for the simulated strategy
hierarchy and committed canonical output.

| Interface | Behavior |
| --- | --- |
| `--data-dir` | Selects the strategy request and candidate pool directory. |
| `--recommendation` | Selects the recommendation artifact to reproduce and validate. |
| `--attribution` | Overrides the MTA attribution CSV. |
| `--entity` | Overrides the entity-bridge CSV. |
| success | Prints the compact validation summary as JSON and exits `0`. |
| failure | Prints `INVALID: <reason>` to standard error and exits `1`. |

`main()` resolves current repository paths, delegates the complete contract to
`validate_simulated_hierarchy()`, and writes no artifacts.

