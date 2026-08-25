---
title: Initializer Source Files
compact: "Code-level specification for hierarchy_validator.py, budget_recommender.py, generate_initial_budget.py, and validate_simulated_hierarchy.py: entry points, schemas, ordering, hashing, arithmetic, refusals, output publication, and verification commands."
lang: en-US
source_files: modules/mta_strategy_recommendation/src/hierarchy_validator.py, modules/mta_strategy_recommendation/src/budget_recommender.py, script/generate_initial_budget.py, script/validate_simulated_hierarchy.py
---

# Initializer Source Files

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

##### `BudgetRecommendationError`

Raised for malformed strategy objects, unsupported products, incomplete attribution, impossible capacities, bridge failures, and non-conserving score inputs.

##### `_exact_keys()`

Requires an object to contain exactly the declared keys; both missing and unexpected keys fail.

##### `_required_text()`

Accepts only a non-empty trimmed string and returns its trimmed value.

##### `_number()`

Accepts a finite Python numeric value at or above the supplied minimum. Booleans are rejected.

##### `_json_number()`

Applies `_number()` and additionally requires a real JSON numeric type rather than a numeric string.

##### `_integer()`

Accepts a non-Boolean integer at or above the supplied minimum.

##### `_objects()`

Requires a JSON list whose every member is an object and returns those objects.

##### `_index_unique()`

Indexes rows by a required text field and rejects duplicate identifiers.

##### `_ceil_ratio()`

Returns zero for zero demand; otherwise calculates integer ceiling division for one capacity dimension.

##### `_touchpoint_product()`

Uses `mta_common.legacy_adapters.touchpoint_from_five_segment_key()` as the single five-part parser, reads the canonical touchpoint's `ad_product`, and requires one of the four supported Ad Products. Adapter validation failures become `BudgetRecommendationError` with the source-row context preserved.

##### `_recommended_point()`

Uses a `RELIABLE` numeric recommendation directly; for `UNRELIABLE` `[low,high]`, returns the midpoint and the midpoint warning.

##### `_campaign_inputs()`

Validates sample version, Campaign Group, Campaigns, Outcome weights, budget, pool lineage, candidate counts, product-specific fields, capacities, and minimum budgets; returns normalized calculation inputs.

##### `recommend_ad_group_count()`

Applies the SP/SB or SD/DSP ceiling-capacity formula, respects `min_ad_groups`, and fails rather than silently capping a result above `max_ad_groups`.

##### `_entity_weight_method()`

Selects the first bridge metric with positive mass: Outcome-specific `assisted_*`, then clicks, impressions, unique users, then equal weights.

##### `_bridge_campaign_scores()`

Maps touchpoint/Outcome values through matching historical entity rows, verifies touchpoint conservation, aggregates Campaign Outcome contributions, and applies Outcome weights to obtain `campaign_mta_score`.

##### `generate_budget_recommendation()`

Normalizes Campaign scores, calculates optional Campaign budgets, checks minimum-budget feasibility, equally divides each Campaign seed among anonymous new slots, and emits derivation and warning metadata.

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

##### `HierarchyValidationError`

Public validation failure for unreadable inputs, evidence mismatch, schema/scope violations, output drift, forbidden fields, or failed invariants.

##### `_read_json()`

Reads one UTF-8 JSON object and rejects unreadable, malformed, or non-object roots.

##### `_read_csv()`

Reads one UTF-8 CSV through `DictReader` and requires a header.

##### `_sha256()`

Streams exact file bytes into SHA-256; evidence identity is byte-level rather than filename-level.

##### `_required_text()`

Requires a non-empty trimmed text value for lineage and scope comparisons.

##### `_integer()`

Requires a non-Boolean integer at or above the supplied minimum.

##### `_resolve_evidence_path()`

Uses an explicit CLI path when supplied; otherwise resolves the path declared by the request and requires an existing file.

##### `_forbidden_paths()`

Recursively locates candidate IDs, targeting assignments, actions, roles, pairings, entity evidence, and historical/source Ad Group fields forbidden in the budget-only output.

##### `_first_difference()`

Recursively reports the first object-field, list-length, primitive-type, or exact primitive-value difference between fresh and committed results.

##### `_validate_budget_invariants()`

Uses `math.fsum()` and explicit tolerances to check Campaign and Ad Group share conservation and, when a budget exists, monetary conservation.

##### `load_aligned_strategy_inputs()`

Reads request and pool JSON plus attribution and entity CSVs; verifies hashes, row counts, sample version, report/advertiser/marketplace/Group scope, Campaign/product coverage, MTA Outcome completeness, and bridge compatibility. Entity validation reuses `_touchpoint_product()` rather than maintaining a second touchpoint parser.

##### `validate_simulated_hierarchy()`

Reloads evidence, regenerates the recommendation, runs exact comparison, forbidden-field checks, and invariants, then returns a compact validation summary.

**Inputs and outputs.** `load_aligned_strategy_inputs(data_dir,
attribution_path, entity_path)` returns the validated request, pool, attribution
rows, and entity rows. `validate_simulated_hierarchy()` additionally reads the
recommendation path and returns a summary containing Campaign and recommended
Ad Group counts, evidence counts, normalization universe, budget-baseline state,
recommendation type, and warnings.

**Dependencies.** `budget_recommender.py`, the canonical `mta_common` legacy adapter, and the Python standard library.

**Verification.** `modules/mta_strategy_recommendation/tests/test_hierarchy_validator.py`.

### `generate_initial_budget.py`

Source: `script/generate_initial_budget.py`

**Responsibility.** Project-level CLI for loading aligned evidence and invoking
`generate_budget_recommendation()`.

#### `--data-dir`

Selects the directory containing `strategy_request.json` and `candidate_pool.json`.

#### `--attribution`

Overrides the governed MTA attribution CSV path.

#### `--entity`

Overrides the historical entity-bridge CSV path.

#### `--output` / `--fixture`

Selects the canonical result checked by check mode.

#### `--check-output` / `--check-fixture`

Generates in memory and requires exact `json.dumps(..., indent=2)` output after CRLF-to-LF normalization.

#### normal mode

Prints generated JSON to standard output and does not overwrite the canonical artifact.

#### exit `0`

Generation succeeded or check mode matched exactly.

#### exit `1`

Input/evidence loading, generation, file reading, or exact comparison failed; the reason is written to standard error.

`main()` resolves the repository root, parses the arguments, loads inputs through
`load_aligned_strategy_inputs()`, generates the seed, and chooses print or exact
check behavior.

### `validate_simulated_hierarchy.py`

Source: `script/validate_simulated_hierarchy.py`

**Responsibility.** Read-only end-to-end preflight for the simulated strategy
hierarchy and committed canonical output.

#### `--data-dir`

Selects the strategy request and candidate pool directory.

#### `--recommendation`

Selects the recommendation artifact to reproduce and validate.

#### `--attribution`

Overrides the MTA attribution CSV.

#### `--entity`

Overrides the entity-bridge CSV.

#### success

Prints the compact validation summary as JSON and exits `0`.

#### failure

Prints `INVALID: <reason>` to standard error and exits `1`.

`main()` resolves current repository paths, delegates the complete contract to
`validate_simulated_hierarchy()`, and writes no artifacts.
