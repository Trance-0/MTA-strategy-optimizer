"""Campaign-level constrained budget optimizer over fitted response curves.

Chooses Campaign budgets ``b_1 ... b_n`` maximizing total expected revenue

    maximize   sum_c R_hat_c(b_c)
    subject to sum_c b_c  = B_total   (SPEND_FULL_BUDGET)
            or sum_c b_c <= B_total   (SPEND_UP_TO_BUDGET)
    and        minimum_c <= b_c <= maximum_c

Because each fitted ``R_hat_c`` is separable, increasing, and concave, the
problem is solved by a shadow price rather than a general solver: there is one
price of budget at which every interior Campaign's marginal expected revenue is
equal, and Campaigns whose bounds bind sit at a bound. The solver is a bisection
on that price, which is deterministic, auditable, and needs no dependency.

The optimization variable is the **Campaign** budget. This module does not
learn or claim Ad Group optimization: the candidate pool carries aggregate
counts rather than distinguishable Ad Group features, so any split below a
Campaign is a projection, labelled ``EQUAL_SPLIT_WITHIN_CAMPAIGN`` and
``NOT_AD_GROUP_OPTIMIZED``.

Attribution is not an input here. A Campaign's optimized budget comes from its
fitted budget/spend/revenue response, never from an attribution share.

Data flow: ``response_model.fit_campaign_response_models`` -> this module ->
dashboard optimized-strategy view.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from modules.mta_common.src.budget import BudgetConstraints
from modules.mta_common.src.enums import BudgetUsagePolicy, StrategyObjective

from .response_model import (
    MODEL_VERSION,
    CampaignResponseModel,
    ResponseSupport,
)


ALLOCATION_BASIS = "CAMPAIGN_RESPONSE_MARGINAL_EQUALIZATION"
AD_GROUP_PROJECTION_BASIS = "EQUAL_SPLIT_WITHIN_CAMPAIGN"
AD_GROUP_OPTIMIZATION_CLAIM = "NOT_AD_GROUP_OPTIMIZED"

# Bisection tolerances. The price search is on marginal revenue per unit of
# budget; the allocation tolerance is in currency units.
_PRICE_ITERATIONS = 200
_ALLOCATION_TOLERANCE = 1e-6


class BudgetOptimizerError(ValueError):
    """Raised when an optimization request is structurally invalid."""


@dataclass(frozen=True)
class CampaignAllocation:
    """One Campaign's initial and optimized budget with its evidence.

    Attributes:
        campaign_id: The allocated Campaign.
        current_budget: The Campaign's budget today, when known.
        initial_budget: The starting allocation compared against.
        optimized_budget: The allocation the solver chose.
        expected_spend_at_initial: Predicted actual spend at the initial
            budget, which may be below it.
        expected_spend_at_optimized: Predicted actual spend at the optimized
            budget.
        expected_revenue_at_initial: Model-estimated revenue at the initial
            budget.
        expected_revenue_at_optimized: Model-estimated revenue at the
            optimized budget.
        expected_revenue_delta: The estimated change between the two.
        marginal_expected_revenue: Added expected revenue per added unit of
            budget at the optimized point.
        response_support: Whether the estimate rests on the Campaign's own
            history or a pooled transfer.
        observed_budget_range: Configured-budget range the fit observed.
        observed_spend_range: Actual-spend range the fit observed.
        is_extrapolated: Whether the optimized budget sits outside the
            observed budget range.
        model_version: Response-model contract version used.
    """

    campaign_id: str
    initial_budget: float
    optimized_budget: float
    expected_spend_at_initial: float
    expected_spend_at_optimized: float
    expected_revenue_at_initial: float
    expected_revenue_at_optimized: float
    expected_revenue_delta: float
    marginal_expected_revenue: float
    response_support: ResponseSupport
    observed_budget_range: tuple[float, float]
    observed_spend_range: tuple[float, float]
    is_extrapolated: bool
    model_version: str = MODEL_VERSION
    current_budget: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JavaScript Object Notation-compatible allocation."""

        return {
            "campaign_id": self.campaign_id,
            "current_budget": self.current_budget,
            "initial_budget": self.initial_budget,
            "optimized_budget": self.optimized_budget,
            "expected_spend_at_initial": self.expected_spend_at_initial,
            "expected_spend_at_optimized": self.expected_spend_at_optimized,
            "expected_revenue_at_initial": self.expected_revenue_at_initial,
            "expected_revenue_at_optimized": self.expected_revenue_at_optimized,
            "expected_revenue_delta": self.expected_revenue_delta,
            "marginal_expected_revenue": self.marginal_expected_revenue,
            "response_support": self.response_support.value,
            "observed_budget_range": list(self.observed_budget_range),
            "observed_spend_range": list(self.observed_spend_range),
            "is_extrapolated": self.is_extrapolated,
            "model_version": self.model_version,
        }


@dataclass(frozen=True)
class OptimizedBudgetPlan:
    """The optimizer's complete result, feasible or not.

    Attributes:
        is_optimized: True only when every response model was usable, the
            constraints were feasible, the solver converged, and the returned
            allocation passed independent post-validation.
        recommendation_type: ``OPTIMIZED_CAMPAIGN_BUDGET`` on success, or a
            failure label. Never ``INITIAL_SEED``: that belongs to the
            separate initializer.
        objective: The requested strategy objective.
        budget_usage_policy: The requested budget usage policy.
        authorized_budget: Total budget the request authorized.
        allocated_budget: Total budget the plan allocates.
        expected_initial_revenue: Model-estimated revenue of the initial plan.
        expected_optimized_revenue: Model-estimated revenue of this plan.
        expected_revenue_increase: The estimated difference. This is an
            expectation from a fitted model, not a guaranteed realized uplift.
        allocations: One entry per optimized Campaign.
        ad_group_projection_basis: How any split below Campaign was produced.
        ad_group_optimization_claim: Explicitly records that Ad Group budgets
            are not optimized.
        infeasibility_reasons: Why the plan is not optimized, when it is not.
        excluded_campaign_ids: Campaigns left out, for example inactive ones
            or ones without response support.
    """

    is_optimized: bool
    recommendation_type: str
    objective: StrategyObjective
    budget_usage_policy: BudgetUsagePolicy
    authorized_budget: float
    allocated_budget: float = 0.0
    expected_initial_revenue: float = 0.0
    expected_optimized_revenue: float = 0.0
    expected_revenue_increase: float = 0.0
    allocations: tuple[CampaignAllocation, ...] = field(default_factory=tuple)
    allocation_basis: str = ALLOCATION_BASIS
    ad_group_projection_basis: str = AD_GROUP_PROJECTION_BASIS
    ad_group_optimization_claim: str = AD_GROUP_OPTIMIZATION_CLAIM
    infeasibility_reasons: tuple[str, ...] = field(default_factory=tuple)
    excluded_campaign_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Return a JavaScript Object Notation-compatible plan."""

        return {
            "is_optimized": self.is_optimized,
            "recommendation_type": self.recommendation_type,
            "objective": self.objective.value,
            "budget_usage_policy": self.budget_usage_policy.value,
            "authorized_budget": self.authorized_budget,
            "allocated_budget": self.allocated_budget,
            "expected_initial_revenue": self.expected_initial_revenue,
            "expected_optimized_revenue": self.expected_optimized_revenue,
            "expected_revenue_increase": self.expected_revenue_increase,
            "allocation_basis": self.allocation_basis,
            "ad_group_projection_basis": self.ad_group_projection_basis,
            "ad_group_optimization_claim": self.ad_group_optimization_claim,
            "allocations": [item.to_dict() for item in self.allocations],
            "infeasibility_reasons": list(self.infeasibility_reasons),
            "excluded_campaign_ids": list(self.excluded_campaign_ids),
        }


@dataclass(frozen=True)
class CampaignBudgetRequest:
    """One Campaign's optimization inputs.

    Attributes:
        campaign_id: The Campaign to allocate to.
        constraints: Canonical minimum, maximum, and usage policy.
        initial_budget: The starting allocation to compare against.
        currency: Currency the budget is denominated in.
        is_active: Whether the Campaign may receive budget at all.
        current_budget: The Campaign's present budget, when known.
    """

    campaign_id: str
    constraints: BudgetConstraints
    initial_budget: float
    currency: str
    is_active: bool = True
    current_budget: float | None = None

    def __post_init__(self) -> None:
        if self.campaign_id != self.constraints.campaign_id:
            raise ValueError(
                "constraints.campaign_id must match campaign_id"
            )
        if self.initial_budget < 0:
            raise ValueError("initial_budget must not be negative")


def optimize_campaign_budgets(
    requests: Sequence[CampaignBudgetRequest],
    response_models: Mapping[str, CampaignResponseModel],
    total_budget: float,
    objective: StrategyObjective = StrategyObjective.MAXIMIZE_REVENUE,
    budget_usage_policy: BudgetUsagePolicy = (
        BudgetUsagePolicy.SPEND_UP_TO_BUDGET
    ),
) -> OptimizedBudgetPlan:
    """Allocate Campaign budgets against fitted response curves.

    Args:
        requests: One entry per Campaign considered for budget.
        response_models: Fitted models keyed by Campaign identifier.
        total_budget: Authorized total budget for the group.
        objective: What to maximize. Only ``MAXIMIZE_REVENUE`` is modeled.
        budget_usage_policy: Whether the total must be exhausted.

    Returns:
        OptimizedBudgetPlan: An optimized plan, or a structured explanation of
        why no responsible optimization exists. Never a fabricated optimum.
    """

    if objective == StrategyObjective.MAXIMIZE_PROFIT:
        # Profit needs a margin-aware response the revenue model does not
        # carry. Silently optimizing revenue instead would answer a different
        # question than the one asked.
        return _failed(
            "PROFIT_OBJECTIVE_NOT_MODELED",
            objective,
            budget_usage_policy,
            total_budget,
            (
                "MAXIMIZE_PROFIT requires a profit-response model; the fitted "
                "response predicts revenue only",
            ),
        )

    problems = _validate_request(requests, total_budget)
    if problems:
        return _failed(
            "INFEASIBLE_REQUEST",
            objective,
            budget_usage_policy,
            total_budget,
            problems,
        )

    active = [item for item in requests if item.is_active]
    excluded = [item.campaign_id for item in requests if not item.is_active]
    supported: list[tuple[CampaignBudgetRequest, CampaignResponseModel]] = []
    for request in active:
        model = response_models.get(request.campaign_id)
        if model is None or not model.is_usable:
            excluded.append(request.campaign_id)
            continue
        supported.append((request, model))

    if not supported:
        return _failed(
            "NO_SUPPORTED_CAMPAIGN_RESPONSE",
            objective,
            budget_usage_policy,
            total_budget,
            (
                "no Campaign has a usable response model, so no optimized "
                "allocation can be justified",
            ),
            excluded_campaign_ids=tuple(sorted(set(excluded))),
        )

    feasibility = _check_feasibility(supported, total_budget, budget_usage_policy)
    if feasibility:
        return _failed(
            "INFEASIBLE_CONSTRAINTS",
            objective,
            budget_usage_policy,
            total_budget,
            feasibility,
            excluded_campaign_ids=tuple(sorted(set(excluded))),
        )

    budgets = _solve(supported, total_budget, budget_usage_policy)
    validation = _validate_allocation(
        supported, budgets, total_budget, budget_usage_policy
    )
    if validation:
        return _failed(
            "SOLVER_VALIDATION_FAILED",
            objective,
            budget_usage_policy,
            total_budget,
            validation,
            excluded_campaign_ids=tuple(sorted(set(excluded))),
        )

    allocations = tuple(
        _allocation(request, model, budgets[request.campaign_id])
        for request, model in supported
    )
    expected_initial = sum(
        item.expected_revenue_at_initial for item in allocations
    )
    expected_optimized = sum(
        item.expected_revenue_at_optimized for item in allocations
    )
    return OptimizedBudgetPlan(
        is_optimized=True,
        recommendation_type="OPTIMIZED_CAMPAIGN_BUDGET",
        objective=objective,
        budget_usage_policy=budget_usage_policy,
        authorized_budget=total_budget,
        allocated_budget=round(sum(budgets.values()), 6),
        expected_initial_revenue=round(expected_initial, 6),
        expected_optimized_revenue=round(expected_optimized, 6),
        expected_revenue_increase=round(expected_optimized - expected_initial, 6),
        allocations=allocations,
        excluded_campaign_ids=tuple(sorted(set(excluded))),
    )


def _validate_request(
    requests: Sequence[CampaignBudgetRequest], total_budget: float
) -> tuple[str, ...]:
    """Validate the request itself, before any response model is consulted."""

    problems: list[str] = []
    if not requests:
        problems.append("no Campaign was supplied")
    if not math.isfinite(total_budget) or total_budget < 0:
        problems.append("total_budget must be finite and non-negative")
    identifiers = [item.campaign_id for item in requests]
    duplicates = sorted({key for key in identifiers if identifiers.count(key) > 1})
    if duplicates:
        problems.append(f"duplicate Campaign identifiers {duplicates}")
    currencies = {item.currency for item in requests}
    if len(currencies) > 1:
        problems.append(
            f"Campaigns mix currencies {sorted(currencies)}; budgets are not "
            "comparable across currencies"
        )
    for item in requests:
        minimum = item.constraints.minimum_daily_budget
        maximum = item.constraints.maximum_daily_budget
        if minimum is not None and maximum is not None and minimum > maximum:
            problems.append(
                f"campaign {item.campaign_id!r} has minimum above maximum"
            )
    return tuple(problems)


def _check_feasibility(
    supported: Sequence[tuple[CampaignBudgetRequest, CampaignResponseModel]],
    total_budget: float,
    budget_usage_policy: BudgetUsagePolicy,
) -> tuple[str, ...]:
    """Verify the bounds can accommodate the authorized budget."""

    problems: list[str] = []
    minimum_total = sum(_minimum(request) for request, _ in supported)
    maximum_total = sum(_maximum(request) for request, _ in supported)
    if minimum_total > total_budget + _ALLOCATION_TOLERANCE:
        problems.append(
            f"minimum budgets total {minimum_total:g}, above the authorized "
            f"{total_budget:g}"
        )
    if (
        budget_usage_policy == BudgetUsagePolicy.SPEND_FULL_BUDGET
        and maximum_total < total_budget - _ALLOCATION_TOLERANCE
    ):
        problems.append(
            f"maximum budgets total {maximum_total:g}, below the authorized "
            f"{total_budget:g}, so the full budget cannot be spent"
        )
    return tuple(problems)


def _minimum(request: CampaignBudgetRequest) -> float:
    """Return a Campaign's budget floor, defaulting to zero."""

    return float(request.constraints.minimum_daily_budget or 0.0)


def _maximum(request: CampaignBudgetRequest) -> float:
    """Return a Campaign's budget ceiling, defaulting to unbounded."""

    maximum = request.constraints.maximum_daily_budget
    return math.inf if maximum is None else float(maximum)


def _solve(
    supported: Sequence[tuple[CampaignBudgetRequest, CampaignResponseModel]],
    total_budget: float,
    budget_usage_policy: BudgetUsagePolicy,
) -> dict[str, float]:
    """Find budgets equalizing marginal expected revenue at one shadow price.

    Each Campaign's demand for budget falls as the price of budget rises, so
    total demand is monotone in the price and a bisection converges. Campaigns
    whose bounds bind clamp to those bounds, which is exactly the behavior the
    equal-marginal condition requires at a constrained optimum.
    """

    def demand(price: float) -> dict[str, float]:
        return {
            request.campaign_id: _campaign_demand(request, model, price)
            for request, model in supported
        }

    def total(price: float) -> float:
        return sum(demand(price).values())

    # At price zero every Campaign wants its maximum. If that still fits, the
    # budget does not bind and each Campaign simply takes what it can use.
    if (
        budget_usage_policy == BudgetUsagePolicy.SPEND_UP_TO_BUDGET
        and total(0.0) <= total_budget + _ALLOCATION_TOLERANCE
    ):
        return demand(0.0)

    low_price = 0.0
    high_price = max(
        _highest_marginal(request, model) for request, model in supported
    ) + 1.0
    for _ in range(_PRICE_ITERATIONS):
        mid_price = (low_price + high_price) / 2.0
        if total(mid_price) > total_budget:
            low_price = mid_price
        else:
            high_price = mid_price
        if high_price - low_price < 1e-12:
            break
    budgets = demand(high_price)

    allocated = sum(budgets.values())
    remainder = total_budget - allocated
    if (
        budget_usage_policy == BudgetUsagePolicy.SPEND_FULL_BUDGET
        and remainder > _ALLOCATION_TOLERANCE
    ):
        budgets = _distribute_remainder(supported, budgets, remainder)
    return budgets


def _campaign_demand(
    request: CampaignBudgetRequest,
    model: CampaignResponseModel,
    price: float,
) -> float:
    """Return the budget a Campaign wants at one price, within its bounds.

    Found by bisection on the Campaign's own marginal expected revenue, which
    is decreasing in budget because both fitted stages saturate.
    """

    minimum = _minimum(request)
    maximum = _maximum(request)
    if maximum <= minimum:
        return minimum
    ceiling = maximum if math.isfinite(maximum) else _search_ceiling(model)
    if model.marginal_expected_revenue(minimum) <= price:
        return minimum
    if model.marginal_expected_revenue(ceiling) >= price:
        return ceiling

    low, high = minimum, ceiling
    for _ in range(_PRICE_ITERATIONS):
        mid = (low + high) / 2.0
        if model.marginal_expected_revenue(mid) > price:
            low = mid
        else:
            high = mid
        if high - low < _ALLOCATION_TOLERANCE:
            break
    return (low + high) / 2.0


def _search_ceiling(model: CampaignResponseModel) -> float:
    """Return a finite search ceiling for an unbounded Campaign.

    Beyond a few multiples of the observed budget range the fitted curve is
    flat, so this bounds the search without changing the optimum.
    """

    observed_high = model.diagnostics.observed_budget_range[1]
    spend_scale = (
        model.spend_response.scale if model.spend_response is not None else 1.0
    )
    return max(observed_high, spend_scale, 1.0) * 8.0


def _highest_marginal(
    request: CampaignBudgetRequest, model: CampaignResponseModel
) -> float:
    """Return a Campaign's marginal expected revenue at its budget floor."""

    return model.marginal_expected_revenue(_minimum(request))


def _distribute_remainder(
    supported: Sequence[tuple[CampaignBudgetRequest, CampaignResponseModel]],
    budgets: Mapping[str, float],
    remainder: float,
) -> dict[str, float]:
    """Place a full-budget remainder on Campaigns with room to take it.

    Reached when every Campaign's marginal revenue has fallen to zero before
    the authorized budget is exhausted, yet the policy requires spending it
    all. The remainder goes to the Campaigns that can still accept budget.
    """

    result = dict(budgets)
    receivers = [
        request
        for request, _ in supported
        if _maximum(request) - result[request.campaign_id] > _ALLOCATION_TOLERANCE
    ]
    while remainder > _ALLOCATION_TOLERANCE and receivers:
        share = remainder / len(receivers)
        moved = 0.0
        still_open: list[CampaignBudgetRequest] = []
        for request in receivers:
            room = _maximum(request) - result[request.campaign_id]
            take = min(share, room)
            result[request.campaign_id] += take
            moved += take
            if room - take > _ALLOCATION_TOLERANCE:
                still_open.append(request)
        remainder -= moved
        receivers = still_open
        if moved <= _ALLOCATION_TOLERANCE:
            break
    return result


def _validate_allocation(
    supported: Sequence[tuple[CampaignBudgetRequest, CampaignResponseModel]],
    budgets: Mapping[str, float],
    total_budget: float,
    budget_usage_policy: BudgetUsagePolicy,
) -> tuple[str, ...]:
    """Independently re-check the solver's own answer before returning it."""

    problems: list[str] = []
    allocated = sum(budgets.values())
    if allocated > total_budget + 1e-4:
        problems.append(
            f"allocated {allocated:g} exceeds authorized {total_budget:g}"
        )
    if (
        budget_usage_policy == BudgetUsagePolicy.SPEND_FULL_BUDGET
        and abs(allocated - total_budget) > 1e-4
    ):
        problems.append(
            f"SPEND_FULL_BUDGET requires allocating {total_budget:g}, "
            f"allocated {allocated:g}"
        )
    for request, model in supported:
        budget = budgets[request.campaign_id]
        if budget < _minimum(request) - 1e-6:
            problems.append(
                f"campaign {request.campaign_id!r} is below its minimum"
            )
        if budget > _maximum(request) + 1e-6:
            problems.append(
                f"campaign {request.campaign_id!r} is above its maximum"
            )
        revenue = model.expected_revenue(budget)
        if not math.isfinite(revenue) or revenue < 0:
            problems.append(
                f"campaign {request.campaign_id!r} predicts a non-finite or "
                "negative expected revenue"
            )
    return tuple(problems)


def _allocation(
    request: CampaignBudgetRequest,
    model: CampaignResponseModel,
    optimized_budget: float,
) -> CampaignAllocation:
    """Build one Campaign's reported allocation and its evidence."""

    initial_revenue = model.expected_revenue(request.initial_budget)
    optimized_revenue = model.expected_revenue(optimized_budget)
    return CampaignAllocation(
        campaign_id=request.campaign_id,
        current_budget=request.current_budget,
        initial_budget=round(request.initial_budget, 6),
        optimized_budget=round(optimized_budget, 6),
        expected_spend_at_initial=round(
            model.expected_spend(request.initial_budget), 6
        ),
        expected_spend_at_optimized=round(
            model.expected_spend(optimized_budget), 6
        ),
        expected_revenue_at_initial=round(initial_revenue, 6),
        expected_revenue_at_optimized=round(optimized_revenue, 6),
        expected_revenue_delta=round(optimized_revenue - initial_revenue, 6),
        marginal_expected_revenue=round(
            model.marginal_expected_revenue(optimized_budget), 9
        ),
        response_support=model.diagnostics.support,
        observed_budget_range=model.diagnostics.observed_budget_range,
        observed_spend_range=model.diagnostics.observed_spend_range,
        is_extrapolated=model.is_extrapolating(optimized_budget),
        model_version=model.diagnostics.model_version,
    )


def _failed(
    recommendation_type: str,
    objective: StrategyObjective,
    budget_usage_policy: BudgetUsagePolicy,
    total_budget: float,
    reasons: Sequence[str],
    excluded_campaign_ids: tuple[str, ...] = (),
) -> OptimizedBudgetPlan:
    """Return a structured non-optimized result rather than a fake optimum."""

    return OptimizedBudgetPlan(
        is_optimized=False,
        recommendation_type=recommendation_type,
        objective=objective,
        budget_usage_policy=budget_usage_policy,
        authorized_budget=total_budget,
        infeasibility_reasons=tuple(reasons),
        excluded_campaign_ids=excluded_campaign_ids,
    )
