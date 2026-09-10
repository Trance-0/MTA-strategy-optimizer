---
title: Response Model and Assumptions
description: The two-stage functional form, its parameters, and every assumption the model imposes rather than discovers
compact: "Specifies the two-stage Campaign response: `S(B)=capacity*(1-exp(-B/scale))` capped at B, `R(S)=baseline+alpha*(1-exp(-S/kappa))`, the composition the optimizer maximizes, and the imposed concavity, no-time-dimension, and no-interaction assumptions."
lang: en-US
order: 10
---

# Response Model and Assumptions

## Model Intuition <span class="status-label status-verified" aria-label="Verified"></span>

A Campaign that cannot spend the budget it is given has a delivery problem. A Campaign that spends its budget but converts it poorly has a response problem. These fail independently, and a single fitted curve from budget straight to revenue would report one as the other: a Campaign whose spend has flattened at its delivery ceiling looks identical, in a one-stage fit, to a Campaign whose audience has saturated.

The model therefore fits two stages and composes them. The first is a delivery model, the second a conversion model, and only their composition is the objective the optimizer maximizes.

## The Model <span class="status-label status-verified" aria-label="Verified"></span>

### Stage One — Configured Budget to Actual Spend

$$
S(B) = \min\left(B,\; \text{capacity} \times \left(1 - e^{-B / \text{scale}}\right)\right), \qquad S(B) \ge 0
$$

$B$ is the configured budget, the amount authorized before the period ran. $S$ is expected actual spend.

#### `capacity`

The most a Campaign is expected to spend however large its budget grows. It is the horizontal asymptote of the saturating term, and it represents a delivery ceiling: available inventory, eligible auctions, or pacing limits.

#### `scale`

How quickly spend approaches that ceiling. At $B = \text{scale}$ the saturating term has reached $1 - e^{-1} \approx 63.2\%$ of `capacity`. A small `scale` means the Campaign hits its ceiling almost immediately; a large one means spend stays close to linear across the observed range.

#### The `min(B, ...)` cap

A Campaign cannot spend more than it was authorized, so expected spend is additionally capped at the budget itself. This is a hard identity, not a fitted behavior, and it is applied after the saturating term regardless of what the fitted parameters would otherwise produce.

### Stage Two — Actual Spend to Expected Revenue

$$
R(S) = r_0 + \alpha\left(1 - e^{-S / \kappa}\right)
$$

#### `baseline` ($r_0$)

Revenue expected at zero spend. It absorbs demand that would have occurred without this Campaign's advertising. It is *not* an incrementality estimate: nothing in the fit separates organic demand from advertising effect, and the intercept simply takes whatever level the regression assigns it.

#### `alpha` ($\alpha$)

The most advertising can add. As spend grows without bound, expected revenue approaches $r_0 + \alpha$.

#### `kappa` ($\kappa$)

How quickly that addition saturates. At $S = \kappa$ the Campaign has captured $1 - e^{-1} \approx 63.2\%$ of $\alpha$.

### The Composed Objective

$$
\hat{R}(B) = R\big(S(B)\big)
$$

This composition, not either stage alone, is what `CampaignResponseModel.expected_revenue()` returns and what the optimizer maximizes. The marginal quantity the solver equalizes is the derivative of this composition, approximated by a forward difference with a step of one currency unit.

### Marginal Revenue of the Second Stage

$$
\frac{dR}{dS} = \frac{\alpha}{\kappa} e^{-S/\kappa}
$$

Strictly positive and strictly decreasing in spend for $\alpha > 0$. This is the diminishing return the optimizer relies on. The optimizer does not call it directly — it differences the composed response instead — but it is the analytic reason the composition is well-behaved.

## Assumptions <span class="status-label status-verified" aria-label="Verified"></span>

Each item below is a property the model *imposes*. None is discovered from the data, and none is tested against the data before being applied.

### Diminishing returns are imposed, not inferred

`RevenueResponse.__post_init__` raises `ValueError` when `alpha` is negative or `kappa` is non-positive, and the fitting routine clamps both `baseline` and `alpha` to be non-negative before constructing the object. A Campaign whose observed data suggested increasing returns, or a negative advertising effect, cannot be represented: the closest representable fit is a flat curve with `alpha` at zero.

This is deliberate. Concavity is what guarantees the marginal return falls as budget rises, and therefore what makes the equal-marginal allocation a true maximum rather than one of several local answers. But it means a poor fit is reported through the residual diagnostics, never through the shape.

### The response is memoryless in time

No adstock, carryover, lag, seasonality, or trend term exists in either stage. Revenue in a period is modelled as a function of that period's spend alone. A Campaign whose spend this week drives conversions next week is fitted as though both periods responded independently to their own budgets.

Observations are grouped by Campaign, marketplace, period, and intervention, but the period is a grouping key only. Nothing in the fit orders periods or treats an earlier one as informing a later one.

### Campaigns do not interact

Each Campaign has its own fitted curve, and the objective is a plain sum across Campaigns. Cannibalization, halo effects, shared audience overlap, and auction competition between two Campaigns of the same advertiser are not represented. Reallocating budget from one Campaign to another is assumed to move each along its own curve without shifting the other's.

Separability is also what makes the shadow-price solver valid; a model with cross-terms would need a different solver.

### The functional form is assumed, not selected

Both stages are exponential-saturation forms chosen in advance. There is no model selection, no comparison against alternative shapes such as a power law, a logistic, or a Hill function, and no test that the exponential form fits better than another. A Campaign whose true response has a different shape is fitted with the best exponential approximation and reports its residuals honestly, but the reported parameters are still parameters of an assumed form.

### Fit quality is measured in-sample only

The reported errors — mean absolute error for spend, mean absolute and root mean square error for revenue — are computed on the same observations the parameters were fitted to. There is no holdout, no cross-validation, and no out-of-time split inside this module. A low in-sample error is consistent with overfitting a small number of observations and is not evidence of predictive accuracy.

Out-of-time validation belongs to [strategy evaluation](/en/strategy-evaluation/).

### The estimate is an association, not a causal effect

Where budget variation was assigned by a deterministic schedule rather than randomized, the fitted relationship remains a response association. Each observation preserves `assignment_type` and `randomized` so a later evaluation can distinguish the two, but the current fit does not condition on either flag: a randomized arm and a rule-based arm enter the least-squares objective identically.

### Revenue, not profit, is the target

The fitted target is `total_revenue`. Margin, cost of goods, and the organic-versus-incremental split are absent from the model, which is why a `MAXIMIZE_PROFIT` request is refused rather than answered from this curve. See [Strategy Objective](/en/introduction/data-models/vocabularies/strategy-objective.md).

### Currency is a grouping key, not a conversion

All monetary quantities within one fit share one currency. The model performs no currency conversion; a Campaign-period mixing currencies is rejected, and a request whose Campaigns mix currencies is refused.

## Why These Forms <span class="status-label status-verified" aria-label="Verified"></span>

Two properties were required of any candidate form, and the exponential-saturation family satisfies both at the lowest cost.

### It must stay increasing and concave under fitting

The solver's correctness rests on it. Constraining a general functional family to remain concave requires a constrained optimizer; constraining this one requires only two sign checks on `alpha` and `kappa`, enforced in the dataclass constructor so an invalid curve cannot be constructed at all.

### It must be readable by an analyst

Both stages are fitted by deterministic grid-refined least squares over the Python standard library alone. There is no neural network, ensemble, or automated model selection, because an analyst must be able to read the fitted parameters and state what the model believes: this Campaign will not spend past `capacity`, and advertising can add at most `alpha` to its revenue.

Fitting is deterministic: the same dataset produces byte-identical parameters on every run, which is what allows the artifact to be committed and compared.

## Worked Example <span class="status-label status-verified" aria-label="Verified"></span>

From the committed `outputs/campaign_strategy.json`, Campaign `CAMPAIGN-DISPLAY` fitted:

```
spend_response:   capacity = 10.35,   scale = 0.9
revenue_response: baseline = 0.0,     alpha = 2800.1454337340037,  kappa = 72.0
observed_budget_range: [3.0, 9.0]
```

At the optimized budget of `10.321458`:

$$
S = \min\left(10.321458,\; 10.35 \times \left(1 - e^{-10.321458/0.9}\right)\right) = 10.321458
$$

The saturating term evaluates to approximately `10.34989`, so the budget cap binds and expected spend equals the budget. Then:

$$
R = 0 + 2800.145 \times \left(1 - e^{-10.321458/72}\right) \approx 373.97
$$

which is the artifact's `expected_revenue_at_optimized` of `373.965998`.

Note what the numbers say about the fit: `kappa` of 72 is eight times the highest observed spend of 9, so across the entire observed range the revenue stage is operating on the near-linear part of its own curve. The concavity the optimizer relies on is real but shallow here, and `alpha` of 2800 against observed revenues in the low hundreds is an extrapolated asymptote the data does not reach. The optimized budget of 10.32 also sits above the observed range, so `is_extrapolated` is true. This is exactly the case the extrapolation flag exists to disclose.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The functional forms specified on this page are implemented in `response_model.py`, whose full code-level contract is on the [fitting implementation](./fitting-implementation.md) page. That page owns the `## Source Files` entry for the file.

## Verification

- **Scope:** The fitted functional forms, their parameter constraints, and the composition.
- **Cases:** Spend never exceeds configured budget; both stages monotone and concave; `alpha` and `kappa` sign rejection; composition equals stage-two applied to stage-one.
- **Command:** `uv run python -X utf8 -B -m unittest modules.mta_strategy_recommendation.tests.test_response_model`.
- **Limitations:** Verifies the imposed shape, not that the shape is correct for real advertising response. No out-of-sample or alternative-form comparison is performed here.
