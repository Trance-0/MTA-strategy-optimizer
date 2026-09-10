---
title: Output Artifact and Verification
description: Where every product is written, the field-by-field contract of the strategy artifact, and the tests that verify it
compact: "Where the pipeline's products are written, the field-by-field `campaign_strategy.json` contract with values from the committed artifact, the command and every option that produces it, the two callers of the same chain, and the 116 tests that verify it."
lang: en-US
order: 50
source_files: modules/mta_strategy_recommendation/src/generate_campaign_strategy.py
test_files: modules/mta_strategy_recommendation/tests/test_response_pipeline.py
---

# Output Artifact and Verification

## Where Each Product Is Saved <span class="status-label status-verified" aria-label="Verified"></span>

The pipeline holds four products, and only the last is durable.

### The training rows

In memory only. `CampaignResponseDataset` is built, fitted against, and discarded within a single process. No cache file, comma-separated values (CSV) export, or database table holds it. Its contents survive only through the artifact's `response_observations` list, which is why that list exists.

### The fitted curves

In memory during the run, then serialized into the artifact's `response_models` object. They round-trip exactly through `response_models_to_dict` and `response_models_from_dict`, so a stored artifact rebuilds the curve that produced a past recommendation rather than approximating it.

### The optimized plan

In memory during the run, then serialized into `optimized_strategy`.

### The artifact

`modules/mta_strategy_recommendation/outputs/campaign_strategy.json`, or wherever `--output` directs it. This is the only file the pipeline writes.

The artifact is written as `json.dumps(artifact, indent=2, sort_keys=True)` with a trailing newline and explicit `\n` line endings, so a rerun over unchanged input produces a byte-identical file and a diff shows only real changes.

The file is deliberately committed. `.gitignore` ignores `modules/*/outputs/` in general but negates this path explicitly, alongside `initial_budget_recommendation.json`, because the strategy evaluation tests read it as a fixture. A checkout therefore always has a plan to display, and a rerun's diff is reviewable.

## No Database Representation <span class="status-label status-verified" aria-label="Verified"></span>

`campaign_strategy.json` is produced by a research command rather than by the import pipeline, so there is no table to reassemble it from. `backend/repository/strategy.py`'s `campaign_strategy()` reads the artifact in its own shape in both file mode and database mode, and returns the same empty object for an absent file that a database-mode run with no artifact returns. The dashboard's Optimization Log reads an empty object as "the optimizer has not run", which is the honest reading in either mode.

This is the deliberate exception among the strategy snapshot keys: the other three have relational representations, and this one does not.

## The Artifact Contract <span class="status-label status-verified" aria-label="Verified"></span>

Five top-level keys. Values below are from the committed artifact, which fits two Campaigns from 40 observations in the `TOY` marketplace.

### `currency`

The single currency every figure in the file is denominated in, taken from the first observation. `"USD"` in the committed artifact. It is a grouping key, not a conversion: the dataset builder rejects a Campaign-period mixing currencies rather than converting.

### `initial_strategy`

The starting point the optimization is compared against.

#### `recommendation_type`

Always `INITIAL_SEED`. Never `OPTIMIZED_CAMPAIGN_BUDGET`.

#### `is_optimized`

Always `false`. A seed is not an optimization, and the two are labelled apart so a dashboard cannot present one as the other.

#### `basis`

The strategy-level label, `CONFIGURED_BASELINE`.

#### `uses_attribution`

`false` for this command's seed. The field exists because attribution *may* legitimately inform an Initial Strategy — the separate [budget initializer](../module-overview/) does exactly that — so a reader needs to know which kind of seed this is. Attribution is never an input to the fitted response model or to the optimizer.

#### `allocations`

One entry per Campaign, sorted by Campaign identifier. Each carries `campaign_id`, `initial_budget`, `current_budget`, `is_active`, its own `basis`, and the `provider`, `ad_product`, and `marketplace` that identify the Campaign's placement.

The per-allocation `basis` is `CONFIGURED_BASELINE` when the Campaign's latest row records a baseline budget, and `EQUAL_NO_HISTORY` when it does not. `initial_budget` is that baseline where one exists and the latest configured budget otherwise; `current_budget` is always the latest configured budget. `is_active` is true when the Campaign's status is `ACTIVE`, compared case-insensitively.

In the committed artifact `CAMPAIGN-DISPLAY` has `initial_budget` 6.0 against `current_budget` 3.0 — the last observed arm cut the budget below its baseline — and `CAMPAIGN-SEARCH` has 60.0 against 90.0, the reverse.

### `optimized_strategy`

The plan, in the shape [the optimizer](./optimizer-implementation.md) produces.

#### Scalars

`is_optimized` true; `recommendation_type` `OPTIMIZED_CAMPAIGN_BUDGET`; `objective` `MAXIMIZE_REVENUE`; `budget_usage_policy` `SPEND_FULL_BUDGET`; `authorized_budget` and `allocated_budget` both 66.0, which is the sum of the two initial budgets because no `--total-budget` was passed; `expected_initial_revenue` 283.661433; `expected_optimized_revenue` 429.599449; `expected_revenue_increase` 145.938016.

#### Disclosure fields

`allocation_basis` is `CAMPAIGN_RESPONSE_MARGINAL_EQUALIZATION`. `ad_group_projection_basis` is `EQUAL_SPLIT_WITHIN_CAMPAIGN` and `ad_group_optimization_claim` is `NOT_AD_GROUP_OPTIMIZED`. The last two are always present, on every plan, so no consumer can read a Campaign-level result as an Ad Group-level one.

#### Diagnostic lists

`infeasibility_reasons` is empty on a feasible plan and names every problem otherwise. `excluded_campaign_ids` names every Campaign dropped for being inactive or unusable, so "received no budget" stays distinguishable from "was never considered". Both are empty in the committed artifact.

#### `allocations`

Per Campaign: `campaign_id`; the three budgets `current_budget`, `initial_budget`, and `optimized_budget`; `expected_spend_at_initial` and `expected_spend_at_optimized`; `expected_revenue_at_initial` and `expected_revenue_at_optimized`; `expected_revenue_delta`; `marginal_expected_revenue`; `response_support`; `observed_budget_range` and `observed_spend_range`; `is_extrapolated`; and `model_version`.

The committed allocation for `CAMPAIGN-DISPLAY` reads `optimized_budget` 10.321458 against `initial_budget` 6.0, `expected_revenue_at_optimized` 373.965998 against 223.887267, and `is_extrapolated` true against `observed_budget_range` of `[3.0, 9.0]`. `CAMPAIGN-SEARCH` moves the other way: 55.678542 against 60.0, with `expected_revenue_delta` of −4.140715 and `is_extrapolated` false.

That negative delta is the equal-marginal condition doing its job. The two `marginal_expected_revenue` values are 0.960382903 and 0.960386621 — equal to seven significant figures, which is the solver's convergence signature. The optimizer took budget from the Campaign earning less at the margin and gave it to the one earning more, and the plan-level increase of 145.938016 is the net of the two.

Every expected revenue figure is an estimate from a fitted model, not a guaranteed realized uplift, and the dashboard labels them accordingly.

### `response_models`

`model_version` at the top, then `campaign_models` keyed by Campaign identifier in sorted order. Each model carries `model_id` (`CAMPAIGN_RESPONSE_V1:CAMPAIGN-DISPLAY`), `model_version`, `currency`, `spend_response` (`capacity`, `scale`), `revenue_response` (`baseline`, `alpha`, `kappa`), and `diagnostics`.

The committed `CAMPAIGN-DISPLAY` model is `capacity` 10.35 with `scale` 0.9, and `baseline` 0.0 with `alpha` 2800.1454337340037 and `kappa` 72.0. Its diagnostics record 20 observations across 5 distinct budgets, both fit statuses `FITTED`, support `TARGET_HISTORY`, an empty `pooled_campaign_ids`, `spend_mean_absolute_error` of 0.0, and `revenue_mean_absolute_error` of 47.75648543197463.

A spend error of exactly zero is the fitted curve reproducing the observations exactly, which is what happens when every observed arm spent its full configured budget: the cap in $\min(B, \cdot)$ binds everywhere, and no capacity or scale in the grid changes the prediction. It is not evidence that spend saturation was measured. The [model page](./model-and-assumptions.md) explains why a $\kappa$ of 72 against a highest observed spend of 9 means the fitted curve is nearly linear over the evidence, and why the plan's extrapolation to 10.32 rests on shape rather than on data.

### `response_observations`

Every training row the fit consumed, flattened, so the evidence behind a curve is reproducible from the artifact alone. Field names match the dataset's with one deliberate rename: `report_start_date` is emitted as `report_date`, because each row covers a single day in current use and the dashboard's history markers plot it as a point.

A committed row:

```json
{
  "actual_spend": 4.5,
  "ad_product": "AMAZON_DSP",
  "assignment_type": "RULE_BASED",
  "baseline_budget": 6.0,
  "budget_delta": -1.5,
  "campaign_id": "CAMPAIGN-DISPLAY",
  "clicks": 260,
  "configured_budget": 4.5,
  "currency": "USD",
  "impressions": 449,
  "intervention_id": "CAMPAIGN-DISPLAY:TOY:2026-01-01:0.75",
  "marketplace": "TOY",
  "provider": "AMAZON_ADS",
  "randomized": false,
  "report_date": "2026-01-01",
  "total_revenue": 142.55
}
```

`assignment_type` of `RULE_BASED` with `randomized` false is the honest disclosure that this arm was assigned by a deterministic schedule. The fit uses the row either way; the flag is preserved so a later evaluation can tell a response association from a causal effect.

## The Command <span class="status-label status-verified" aria-label="Verified"></span>

```bash
uv run python -X utf8 -B -m modules.mta_strategy_recommendation.src.generate_campaign_strategy \
  --research-snapshot path/to/simulation_research.json
```

### `--research-snapshot`

Required. Path to an MTA-SIM `simulation_research.json`. A dashboard run may materialize that file from its selected database research scope first, then invoke this same command unchanged, so there is one code path rather than a file path and a database path.

### `--marketplace`

Selects one reporting scope. Optional when the snapshot carries exactly one marketplace; mandatory when it carries several. A name absent from the snapshot exits 1 and lists what is available, rather than fitting nothing.

### `--output`

Redirects the artifact. Defaults to `modules/mta_strategy_recommendation/outputs/campaign_strategy.json`. Parent directories are created.

### `--total-budget`

The authorized total. Defaults to the sum of each Campaign's initial budget, which makes the default run a pure reallocation of what is already being spent — the comparison that isolates the optimizer's contribution from a budget increase.

### `--budget-usage-policy`

`SPEND_FULL_BUDGET` or `SPEND_UP_TO_BUDGET`. Defaults to `SPEND_FULL_BUDGET` here, which is the opposite of `optimize_campaign_budgets`'s own default, because a command producing a plan for review should show what spending the whole authorization looks like.

### `--minimum-budget` and `--maximum-budget`

Per-Campaign floor and ceiling, applied uniformly to every Campaign. The floor defaults to 0.0 and the ceiling to unbounded.

### Exit codes

0 on success, after printing the observation count, the model count, and whether the plan is optimized. 1 with a message on standard error when the marketplace is ambiguous or absent, or when the selected input yields no Campaign-period observations — never an artifact with nothing fitted in it.

## The Same Chain Has Two Callers <span class="status-label status-verified" aria-label="Verified"></span>

`generate_campaign_strategy.py` is the command-line caller. `backend/services/models.py`'s `optimize()` is the second, serving `POST /api/models/optimize`: it runs the identical adapter, bridge, dataset, fit, and solve, and returns the same four keys plus an `observation_count` instead of writing a file. The dashboard's job runner takes the third route, invoking the command itself with `--output` pointed at a per-run runtime directory.

### Known drift between the two callers

The two callers build the Initial Strategy differently, and the backend's docstring claims they agree when they do not.

`generate_campaign_strategy.py` takes each Campaign's latest row and uses its recorded `baseline_budget`, emitting the per-allocation key `basis` along with `provider`, `ad_product`, and `marketplace`.

`backend/services/models.py` averages every configured budget the Campaign was observed at, emits the key `allocation_basis`, and omits the three placement fields. Its `EQUAL_NO_HISTORY` branch also triggers on a zero average rather than on an absent baseline.

Because the Initial Strategy's total is the default authorized budget, the two callers can authorize different totals from the same snapshot and therefore produce different optimized plans. For the committed data the command's total is 66.0 (6.0 + 60.0, the recorded baselines) while the mean of observed budgets would give a different figure. This specification records the divergence rather than picking a winner; resolving it is a code change, not a documentation one.

## The Tests <span class="status-label status-verified" aria-label="Verified"></span>

```bash
uv run python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -t . -p "test_*.py"
```

116 tests cover this module.

### `test_response_dataset.py`

18 tests: aggregation, the summed-versus-consistent asymmetry, the rejection of a conflicting decision field, and the forbidden-feature boundary.

### `test_response_model.py`

28 tests: fitted shapes stay increasing and concave, both grids, the support labels and their thresholds, pooled transfer, the refusal to estimate from an unusable model, and serialization round-trips.

### `test_budget_optimizer.py`

26 tests: both budget usage policies, floors and ceilings binding and not, the equal-marginal condition across unconstrained Campaigns, and each of the five structured refusals.

### `test_response_pipeline.py`

10 tests, and the ones that matter most. This file runs the pinned MTA-SIM generator over a budget-intervention configuration, then adapts, aggregates, fits, and optimizes its real output. It asserts that spend never exceeds the configured budget, that the fitted curves stay monotone and concave, that evaluation-only truth never reaches the model-facing rows, and that the chain ends in a validated plan. Hand-built fixtures cannot prove the file contract between the two repositories holds; running the real generator does.

### `test_hierarchy_validator.py`

34 tests, covering the module's structural validation rather than the optimizer.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `generate_campaign_strategy.py`

Source: `modules/mta_strategy_recommendation/src/generate_campaign_strategy.py`

**Responsibility.** Command-line entry point running the full chain and writing the artifact holding both strategies.

**Public entry point.** `main() -> int`, invoked through `python -m`. `_initial_strategy(dataset)` and `_observation_row(observation)` are internal. `INITIAL_BASIS_CONFIGURED_BASELINE` and `INITIAL_BASIS_EQUAL_NO_HISTORY` are the exported basis labels.

**Inputs.** `--research-snapshot` (required), `--marketplace`, `--output`, `--total-budget`, `--budget-usage-policy`, `--minimum-budget`, `--maximum-budget`.

**Outputs.** One JavaScript Object Notation (JSON) artifact with the five keys above, written sorted-key with a trailing newline and `\n` line endings. A summary line on standard output.

**Dependencies.** `argparse`, `json`, `sys`, and `pathlib` from the standard library; `modules.mta_common.src.budget` and `.enums`; `modules.mta_standard.src.mta_sim_research_adapter`; and the four `mta_strategy_recommendation` modules that form the chain.

**Contract.** `--marketplace` is mandatory when the input contains several. The Initial Strategy's basis is `CONFIGURED_BASELINE` when a baseline budget exists and `EQUAL_NO_HISTORY` otherwise; a Campaign is active when its status is `ACTIVE`, case-insensitively. Returns exit code 1 with a message on standard error when the marketplace is ambiguous or unknown, or when the selected input yields no Campaign-period observations.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_pipeline.py` covers the chain this command wraps.

## Verification

- **Scope:** The generated artifact, its field contract, and the command that produces it.
- **Cases:** End-to-end generation from a real MTA-SIM research snapshot, serialization round-trips, the marketplace selection branches, and the empty-dataset exit.
- **Command:** `uv run python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -t . -p "test_*.py"`.
- **Limitations:** Runs against local fixtures or a locally executed generator, not a live production database. External generator execution requires the pinned checkout.
