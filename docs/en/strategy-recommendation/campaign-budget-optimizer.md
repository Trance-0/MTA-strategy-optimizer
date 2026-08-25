---
title: Campaign Budget Response Model and Optimizer
description: Fitted two-stage Campaign response curves and the constrained allocation solved from them
compact: "Implemented optimizer: `response_dataset` aggregation rules and forbidden features, two-stage `response_model` saturating fits with TARGET_HISTORY/POOLED_TRANSFER support, shadow-price `budget_optimizer` under SPEND_FULL_BUDGET/SPEND_UP_TO_BUDGET, `campaign_strategy.json` fields, structured refusals."
lang: en-US
source_files: modules/mta_strategy_recommendation/src/response_dataset.py, modules/mta_strategy_recommendation/src/response_model.py, modules/mta_strategy_recommendation/src/budget_optimizer.py, modules/mta_strategy_recommendation/src/episode_bridge.py, script/generate_campaign_strategy.py
---

# Campaign Budget Response Model and Optimizer <span class="status-label status-verified" aria-label="Verified"></span>

## 1. What This Answers, and What the Initializer Answers

The [budget initializer](module-overview/) answers a structural question: how many new Ad Groups does each Campaign need, and what starting budget does each new group receive when nothing is yet known about it. Its answer is a seed, labelled `INITIAL_SEED` with `is_optimized=false`, and it is derived from historical Multi-Touch Attribution (MTA) credit.

This page specifies a different question:

> Given Campaigns whose budgets have already been varied and observed, what budget should each Campaign receive so that total expected revenue is greatest, subject to the budget the business authorized and the floor and ceiling on each Campaign?

The two are not competing versions of one calculation. The initializer allocates where there is no response evidence; the optimizer allocates where there is. The generated artifact carries both so a reader can compare them side by side.

### Attribution is not an input to the optimizer

This is the boundary the [optimization plan](optimization-plan.md) identified as section 5.3, and the implementation enforces it rather than merely recommending it.

Attribution divides credit for outcomes that already happened. A touchpoint may hold a large attributed share because its historical budget was large, because it sat close to conversion, or because it genuinely performed better; the share alone cannot separate these. Budget response is the different question of what changes when the budget changes, and only a record of budgets actually varying can answer it.

`response_dataset.py` therefore enforces the boundary in code. `FORBIDDEN_RESPONSE_FEATURES` names every attribution result, presentation-only similarity value, and simulator ground-truth field, and `assert_no_forbidden_response_features()` rejects any of them offered as a model feature. Passing an `EvaluationEpisode` — the record that carries the simulator's organic and incremental split — raises `ResponseDatasetError` outright.

## 2. Data Flow

The chain runs from the Multi-Touch Attribution Simulator (MTA-SIM) research snapshot to the dashboard:

`simulation_research.json` → `mta_sim_research_adapter` → `episode_bridge` → `response_dataset` → `response_model` → `budget_optimizer` → `outputs/campaign_strategy.json` → the dashboard's Optimization Log.

Each stage narrows what the next may see. The adapter reads the simulator's file contract into canonical `mta_common` objects. The bridge joins those flat lists into `CampaignEpisode` records on Campaign, marketplace, and period, reading the *observed* records only. The dataset builder aggregates episodes into one row per Campaign-period. Only then does fitting begin.

## 3. The Response Dataset

One row represents one Campaign, one marketplace, and one period, carrying what was decided and what was then observed.

A row may hold decision-time context (Provider, ad product, marketplace, currency, Campaign status), the assigned intervention (configured budget, baseline budget, budget delta, assignment type, whether assignment was randomized), and the observation (actual spend, impressions, clicks, total revenue).

### Aggregation rules

Several episodes covering the same Campaign, marketplace, and period are summed into one observation, which is how a Campaign advertising several Products still yields one Campaign-period revenue figure.

Impressions, clicks, and revenue are **summed** across the episodes of that period. Configured budget and actual spend are **taken once**, not summed: they describe the Campaign-period itself, and episodes repeat the same budget decision rather than each contributing a share of it. Summing them would multiply one budget by the number of Products the Campaign advertised.

A Campaign-period that mixes currencies is rejected. A Campaign-period carrying several distinct intervention identifiers is also rejected, because exactly one budget decision is observable per Campaign and period.

## 4. The Two-Stage Response Model

A Campaign that cannot spend the budget it is given has a delivery problem. A Campaign that spends its budget but converts it poorly has a response problem. These fail independently, and a single fitted curve from budget straight to revenue would report one as the other. The model therefore fits two stages:

$$
S(B) = \text{capacity} \times \left(1 - e^{-B / \text{scale}}\right), \qquad S(B) \le B
$$

$$
R(S) = r_0 + \alpha\left(1 - e^{-S / \kappa}\right)
$$

The first maps configured budget $B$ to expected actual spend $S$, bounded by the budget itself because a Campaign cannot spend more than it was authorized. The second maps actual spend to expected revenue, where $r_0$ is revenue expected at zero spend, $\alpha$ is the most advertising can add, and $\kappa$ governs how quickly that addition saturates.

Expected revenue for a budget is the composition of the two, $R(S(B))$, which is the quantity the optimizer maximizes.

### Why these forms

For $\alpha \ge 0$ and $\kappa > 0$ the revenue stage is increasing and concave in spend. Concavity is not decoration: it is what guarantees the marginal return falls as budget rises, and therefore what makes the equal-marginal allocation in section 5 a true maximum rather than one of several local answers.

Both stages are fitted by deterministic grid-refined least squares over the Python standard library alone. There is no neural network, ensemble, or automated model selection, because an analyst must be able to read the fitted parameters and state what the model believes. For each candidate $\kappa$ the linear parameters $r_0$ and $\alpha$ follow in closed form from ordinary least squares, then are clamped non-negative so the fitted curve keeps the shape the optimizer depends on.

Fitting is deterministic: the same dataset produces byte-identical parameters on every run.

### Evidence support

Every fit is labelled with the evidence standing behind it, so a borrowed curve is never mistaken for observed behavior.

#### `TARGET_HISTORY`

Fitted from that Campaign's own budget variation. A Campaign qualifies with at least `MINIMUM_TARGET_OBSERVATIONS` (4) observations across at least `MINIMUM_DISTINCT_BUDGETS` (3) distinct configured budgets. Below that it has a history, not a response.

#### `POOLED_TRANSFER`

Fitted from comparable Campaigns because the target Campaign lacks sufficient variation of its own. Pooling is within a segment of Provider, ad product, marketplace, and currency, and requires at least two contributing Campaigns. The borrowed model records `pooled_campaign_ids`. These estimates are legitimate but are not that Campaign's observed behavior, and both the artifact and the dashboard say so.

Pooling uses ordinary decision-time Campaign attributes. It is unrelated to the dashboard's [presentation-only similarity](/en/introduction/data-models/presentation-only-similarity/) feature, which must never influence a fitted model.

#### `INSUFFICIENT_SUPPORT`

Neither route is possible. The Campaign is returned with no curve at all rather than a falsely precise one, `is_usable` is false, and the optimizer excludes it. Calling `expected_revenue()` on such a model raises `ResponseModelError` rather than returning a number that would look like an estimate.

### Reported diagnostics

Each fit reports observation count, intervention count, distinct budget count, observed budget and spend ranges, a fit status per stage, and residual error: mean absolute error for spend, and both mean absolute error and root mean square error for revenue. The observed ranges are what later decide whether an optimized budget is an extrapolation.

## 5. The Constrained Optimizer

The optimizer chooses Campaign budgets $b_1 \ldots b_n$ solving:

$$
\max_{b} \sum_c \hat{R}_c(b_c)
$$

subject to $\sum_c b_c = B_{\text{total}}$ under `SPEND_FULL_BUDGET`, or $\sum_c b_c \le B_{\text{total}}$ under `SPEND_UP_TO_BUDGET`, and $\text{minimum}_c \le b_c \le \text{maximum}_c$ for every Campaign.

### Why a shadow price rather than a general solver

Because each fitted $\hat{R}_c$ is separable, increasing, and concave, the optimum has a structure worth exploiting. There is exactly one price of budget $\lambda$ at which every interior Campaign's marginal expected revenue is equal:

$$
\frac{\partial \hat{R}_c}{\partial b_c} = \lambda \quad \text{for every Campaign not sitting at a bound}
$$

Campaigns whose floor or ceiling binds sit at that bound, which is precisely what the equal-marginal condition requires at a constrained optimum. Each Campaign's demand for budget falls as $\lambda$ rises, so total demand is monotone in $\lambda$ and a bisection converges on the price that exhausts the authorized budget. The solver is therefore deterministic, auditable, and needs no external dependency.

The marginal return is taken as a forward difference over the *composed* response, so the spend stage's own saturation is included. A derivative of the revenue stage alone would miss a Campaign that has stopped being able to spend what it is given.

### The optimization variable is the Campaign

The optimizer does not learn or claim Ad Group optimization. The candidate pool carries aggregate counts rather than features that distinguish one new Ad Group from another, so any split below a Campaign is a projection, not an optimization. Every plan states this in two fields it always carries: `ad_group_projection_basis` is `EQUAL_SPLIT_WITHIN_CAMPAIGN`, and `ad_group_optimization_claim` is `NOT_AD_GROUP_OPTIMIZED`. This is the same limit the [optimization plan](optimization-plan.md) records as section 5.4, stated in output rather than left to the reader.

### Structured refusal instead of a fabricated optimum

When no responsible optimization exists the optimizer returns a plan with `is_optimized=false`, a `recommendation_type` naming the failure, and `infeasibility_reasons` explaining it. It never returns an allocation it cannot justify, and it never labels its result `INITIAL_SEED`, which belongs to the separate initializer.

#### `PROFIT_OBJECTIVE_NOT_MODELED`

`MAXIMIZE_PROFIT` was requested. The fitted response predicts revenue, not margin, so optimizing revenue and calling it profit would answer a different question than the one asked.

#### `INFEASIBLE_REQUEST`

The request is structurally invalid: no Campaign supplied, a non-finite or negative total budget, duplicate Campaign identifiers, a Campaign whose minimum exceeds its maximum, or Campaigns mixing currencies, whose budgets are not comparable.

#### `NO_SUPPORTED_CAMPAIGN_RESPONSE`

No Campaign has a usable response model, so no optimized allocation can be justified.

#### `INFEASIBLE_CONSTRAINTS`

The bounds cannot accommodate the authorized budget: the minimums total more than is authorized, or under `SPEND_FULL_BUDGET` the maximums total less than the amount that must be spent.

#### `SOLVER_VALIDATION_FAILED`

The solver returned an answer that independent post-validation rejected. Before any plan is reported, the allocation is re-checked against the constraints it was meant to satisfy: it must not exceed the authorized total, must hit it exactly under `SPEND_FULL_BUDGET`, must respect every Campaign's floor and ceiling, and must predict a finite non-negative revenue for each. A solver is a piece of numerical code, and this is what stops a convergence failure from being reported as an optimum.

### Excluded Campaigns

An inactive Campaign, or one whose response model is unusable, is excluded from the allocation and named in `excluded_campaign_ids`. Exclusion is reported rather than silent, because a Campaign that received no budget and a Campaign that was never considered are different outcomes.

## 6. Extrapolation

A budget outside the range the fit observed is still the solver's answer, but it rests on the curve's shape beyond the evidence. Each allocation therefore carries `is_extrapolated` alongside the `observed_budget_range` that determines it, and the dashboard names every extrapolated Campaign rather than letting the number stand unqualified.

This matters most for a Campaign whose budget genuinely bound: its observed range may be narrow precisely because it never had room to grow, which is the case where the optimizer most wants to increase it and has least evidence for how far.

## 7. Output Artifact

`script/generate_campaign_strategy.py` writes `modules/mta_strategy_recommendation/outputs/campaign_strategy.json` with JavaScript Object Notation (JSON) keys sorted, so two runs over one snapshot produce identical files.

### `currency`

The currency every monetary figure in the artifact is denominated in.

### `initial_strategy`

The starting point the optimization is compared against, with `recommendation_type` of `INITIAL_SEED` and `is_optimized=false`. Each allocation records its `basis`: `CONFIGURED_BASELINE` when the Campaign's history records a baseline budget, or `EQUAL_NO_HISTORY` when it does not. The strategy states `uses_attribution` so a reader knows whether attribution informed the seed. Attribution may inform the Initial Strategy; it is never an input to the fitted response model or to the optimizer.

### `optimized_strategy`

The plan described in section 5: `is_optimized`, `recommendation_type`, `objective`, `budget_usage_policy`, `authorized_budget`, `allocated_budget`, the expected initial and optimized revenue with their difference, `allocation_basis` of `CAMPAIGN_RESPONSE_MARGINAL_EQUALIZATION`, the two Ad Group disclosure fields, `allocations`, `infeasibility_reasons`, and `excluded_campaign_ids`.

Each entry in `allocations` carries the Campaign's current, initial, and optimized budget; expected spend and expected revenue at both the initial and optimized budget; the revenue delta; the marginal expected revenue at the optimized point; the `response_support` label; the observed budget and spend ranges; `is_extrapolated`; and the `model_version`.

Expected revenue figures are estimates from a fitted model. They are not a guaranteed realized uplift, and the dashboard labels them accordingly.

### `response_models`

Every fitted model keyed by Campaign, each with its `model_id`, `model_version` of `CAMPAIGN_RESPONSE_V1`, currency, both stages' parameters, and diagnostics. Models round-trip through `to_dict`/`from_dict` and `to_str`/`from_str`, so a stored artifact rebuilds the exact curve that produced a past recommendation.

### `response_observations`

The flattened Campaign-period rows the fit consumed, so the evidence behind a curve is reproducible from the artifact alone.

## 8. Run

```bash
uv run python -X utf8 -B script/generate_campaign_strategy.py \
  --research-snapshot path/to/simulation_research.json
```

`--output` redirects the artifact, `--total-budget` sets the authorized total (defaulting to the sum of each Campaign's observed baseline), `--budget-usage-policy` selects `SPEND_FULL_BUDGET` or `SPEND_UP_TO_BUDGET`, and `--minimum-budget` and `--maximum-budget` set the per-Campaign bounds.

The command exits non-zero when the snapshot yields no Campaign-period observations, rather than writing an artifact with nothing fitted.

The dashboard reads the artifact from its documented path when present. It is a generated file and is never committed; a checkout that has not run the command shows stage 5 as `NOT RUN` and continues to display the initializer's seed.

## 9. Verification

```bash
python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -t . -p "test_*.py"
```

115 tests cover this module. `test_response_dataset.py` covers aggregation and the forbidden-feature boundary, `test_response_model.py` the fitted shapes and support labels, and `test_budget_optimizer.py` both usage policies, every constraint, the equal-marginal condition, and each structured refusal.

`test_response_pipeline.py` is the end-to-end check that matters most: it runs the pinned MTA-SIM generator over a budget-intervention configuration, then adapts, aggregates, fits, and optimizes its real output. It asserts that spend never exceeds the configured budget, that the fitted curves stay monotone and concave, that evaluation-only truth never reaches the model-facing rows, and that the chain ends in a validated plan. Hand-built fixtures cannot prove the file contract between the two repositories holds; this does.

## 10. What This Stage Does Not Establish

The optimizer maximizes expected revenue under a fitted model. That is not a claim of causal incrementality, and the [optimization plan](optimization-plan.md) separates the two deliberately.

The fitted response is estimated from observed budget variation. Where that variation was assigned by a deterministic schedule rather than randomized, the estimate remains a response association rather than a causal effect, which is why each observation preserves its `assignment_type` and `randomized` flags. The `randomized` flag is recorded so a later evaluation can distinguish the two; the current model does not condition on it.

Comparison against the equal-split, MTA-seed, and historical-budget baselines, out-of-time validation, and the synthetic ground-truth evaluation belong to [strategy evaluation](/en/strategy-evaluation/) and are not performed here. Demonstrating a production gain requires a compliant experiment or holdout; neither an attribution share nor a fitted curve proves one.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

This section is the code-level contract for the four Python files implementing the response model and optimizer, plus the command that runs them.

### `response_dataset.py`

Source: `modules/mta_strategy_recommendation/src/response_dataset.py`

**Responsibility.** Aggregate `CampaignEpisode` records into one Campaign-period row per assigned budget intervention, and enforce what a response feature may never be. The trainer, the optimizer, and the dashboard all read this builder rather than each re-deriving Campaign totals, so one definition of "what a Campaign spent and earned in a period" exists.

**Public entry points.** `build_campaign_response_dataset(episodes) -> CampaignResponseDataset` and `assert_no_forbidden_response_features(feature_names) -> None`. `CampaignResponseDataset` exposes `campaign_ids`, `for_campaign()`, and `by_campaign()`; `CampaignResponseObservation` exposes `is_intervention` and `period_key`.

**Ordering and determinism.** Rows are ordered by Campaign, marketplace, and period start date. Revenue is rounded to six decimal places. The same episodes always produce the same dataset.

**Errors.** `ResponseDatasetError` for an `EvaluationEpisode`, a non-`CampaignEpisode`, a missing budget observation, mixed currencies within one Campaign-period, several distinct interventions within one Campaign-period, or a forbidden feature name. Negative budget, spend, revenue, impressions, or clicks raise `ValueError`.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_dataset.py`.

### `response_model.py`

Source: `modules/mta_strategy_recommendation/src/response_model.py`

**Responsibility.** Fit the two-stage budget-to-spend-to-revenue response per Campaign, label the evidence behind each fit, and report fit quality. Contains no allocation logic.

**Public entry points.** `fit_campaign_response_models(dataset) -> Mapping[str, CampaignResponseModel]`, plus `response_models_to_dict()` and `response_models_from_dict()` for the serialized artifact. `CampaignResponseModel` exposes `is_usable`, `expected_spend()`, `expected_revenue_from_spend()`, `expected_revenue()`, `marginal_expected_revenue(budget, step=1.0)`, and `is_extrapolating()`.

**Contract.** `MODEL_VERSION` is `CAMPAIGN_RESPONSE_V1`. `SpendResponse` requires non-negative capacity and positive scale; `RevenueResponse` requires non-negative baseline and alpha and positive kappa; both reject violations with `ValueError`, which is what keeps every fitted curve increasing and concave. Fitting is deterministic. A Campaign needs at least 4 observations across at least 3 distinct budgets for `TARGET_HISTORY`; pooling requires at least 2 contributing Campaigns in a Provider, ad product, marketplace, and currency segment.

**Errors.** `ResponseModelError` when an unusable model is asked for an estimate, or when `marginal_expected_revenue` receives a non-positive step.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_model.py`.

### `budget_optimizer.py`

Source: `modules/mta_strategy_recommendation/src/budget_optimizer.py`

**Responsibility.** Allocate Campaign budgets against fitted response curves by equalizing marginal expected revenue at a single shadow price, subject to the authorized total and each Campaign's bounds. Attribution is not an input.

**Public entry points.** `optimize_campaign_budgets(requests, response_models, total_budget, objective=MAXIMIZE_REVENUE, budget_usage_policy=SPEND_UP_TO_BUDGET) -> OptimizedBudgetPlan`, with `CampaignBudgetRequest`, `CampaignAllocation`, and `OptimizedBudgetPlan` as the surrounding types. `ALLOCATION_BASIS`, `AD_GROUP_PROJECTION_BASIS`, and `AD_GROUP_OPTIMIZATION_CLAIM` are the exported constant labels.

**Guarantees.** A returned plan with `is_optimized=true` has passed independent post-validation: the allocation is within the authorized total, exact under `SPEND_FULL_BUDGET` to within `1e-4`, within every Campaign's floor and ceiling to within `1e-6`, and predicts a finite non-negative revenue for each Campaign. Otherwise `is_optimized` is false and `infeasibility_reasons` is non-empty. `recommendation_type` is `OPTIMIZED_CAMPAIGN_BUDGET` on success and never `INITIAL_SEED`. Budgets and revenues are rounded to six decimal places; marginal revenue to nine.

**Errors.** `CampaignBudgetRequest` raises `ValueError` when its constraints name a different Campaign or its initial budget is negative. Structural and infeasibility problems are returned as a non-optimized plan rather than raised, so a caller always receives an explanation.

**Verification.** `modules/mta_strategy_recommendation/tests/test_budget_optimizer.py`.

### `episode_bridge.py`

Source: `modules/mta_strategy_recommendation/src/episode_bridge.py`

**Responsibility.** Join the research adapter's flat canonical lists into `CampaignEpisode` values on Campaign, marketplace, and period, which is the only type the response dataset accepts.

**Public entry point.** `campaign_episodes_from_research_snapshot(snapshot) -> tuple[CampaignEpisode, ...]`, one episode per Campaign, marketplace, and period holding a budget observation.

**Contract.** Reads the snapshot's *observed* records only. `evaluation_outcome_observations` carry organic and incremental splits the simulator knows because it generated them, and are never composed into an episode; attribution evidence is likewise not attached. A budget observation naming an unknown Campaign is skipped. Each Campaign is restated in its observed period's reporting scope, because `CampaignEpisode` requires one currency across every scope it composes.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_pipeline.py`.

### `generate_campaign_strategy.py`

Source: `script/generate_campaign_strategy.py`

**Responsibility.** Command-line entry point running the full chain and writing the artifact holding both strategies.

**Contract.** Requires `--research-snapshot`. Writes sorted-key JSON with a trailing newline and `\n` line endings to `outputs/campaign_strategy.json` by default. Returns exit code 1 with a message on standard error when the snapshot yields no Campaign-period observations. The Initial Strategy's basis is `CONFIGURED_BASELINE` when a baseline budget exists and `EQUAL_NO_HISTORY` otherwise; a Campaign is active when its status is `ACTIVE`, case-insensitively.

**Verification.** `modules/mta_strategy_recommendation/tests/test_response_pipeline.py` covers the chain this command wraps.
