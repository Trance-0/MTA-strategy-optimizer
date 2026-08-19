"""Two-stage Campaign response model: budget to spend, then spend to revenue.

The two stages are fitted separately because they answer different questions
and can fail independently. A Campaign may be unable to spend the budget it is
given (a delivery problem) while still converting the spend it does make
efficiently (a response problem), and an optimizer that conflated the two would
misread one as the other.

    expected_spend(B)            configured budget -> expected actual spend
    expected_revenue_from_spend(S)   actual spend -> expected revenue
    expected_revenue(B)          the composition of the two

Both stages use transparent, monotone, saturating forms fitted by deterministic
grid-refined least squares over the standard library alone. There is no neural
network, ensemble, or opaque automated model selection here: an analyst must be
able to read the fitted parameters and say what the model believes.

    spend:    S(B)  = capacity * (1 - exp(-B / scale)),  bounded by S(B) <= B
    revenue:  R(S)  = r0 + alpha * (1 - exp(-S / kappa))

The revenue stage is concave and increasing in spend for ``alpha >= 0`` and
``kappa > 0``, which is what lets the optimizer equalize marginal returns.

Attribution output is not an input to either stage. Neither is simulator ground
truth or dashboard similarity. See ``response_dataset`` for the enforced list.

Data flow: ``response_dataset.build_campaign_response_dataset`` -> this module
-> ``budget_optimizer``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping, Sequence

from .response_dataset import (
    CampaignResponseDataset,
    CampaignResponseObservation,
)


MODEL_VERSION = "CAMPAIGN_RESPONSE_V1"

# A Campaign needs enough distinct budget levels to say anything about how it
# responds to a budget change. Below this it has a history, not a response.
MINIMUM_TARGET_OBSERVATIONS = 4
MINIMUM_DISTINCT_BUDGETS = 3


class ResponseSupport(StrEnum):
    """What evidence stands behind one Campaign's response estimate.

    Attributes:
        TARGET_HISTORY: Fitted from that Campaign's own budget variation.
        POOLED_TRANSFER: Fitted from comparable Campaigns' history because the
            target Campaign has insufficient history of its own. Estimates are
            legitimate but are not that Campaign's observed behavior.
        INSUFFICIENT_SUPPORT: No responsible estimate is available.
    """

    TARGET_HISTORY = "TARGET_HISTORY"
    POOLED_TRANSFER = "POOLED_TRANSFER"
    INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"


class FitStatus(StrEnum):
    """Whether a fit produced usable parameters."""

    FITTED = "FITTED"
    DEGENERATE = "DEGENERATE"
    UNFITTED = "UNFITTED"


class ResponseModelError(ValueError):
    """Raised when a response model is used outside its contract."""


@dataclass(frozen=True)
class SpendResponse:
    """Saturating map from configured budget to expected actual spend.

    ``capacity`` is the most a Campaign is expected to spend however large its
    budget grows; ``scale`` controls how quickly it approaches that ceiling.
    Expected spend is additionally capped at the budget itself, since a
    Campaign cannot spend more than it was authorized.
    """

    capacity: float
    scale: float

    def __post_init__(self) -> None:
        if self.capacity < 0:
            raise ValueError("capacity must not be negative")
        if self.scale <= 0:
            raise ValueError("scale must be positive")

    def expected_spend(self, configured_budget: float) -> float:
        """Return expected actual spend for one configured budget."""

        if configured_budget <= 0:
            return 0.0
        saturating = self.capacity * (
            1.0 - math.exp(-configured_budget / self.scale)
        )
        return max(0.0, min(configured_budget, saturating))

    def to_dict(self) -> dict[str, float]:
        """Return JavaScript Object Notation-compatible parameters."""

        return {"capacity": self.capacity, "scale": self.scale}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SpendResponse":
        """Rebuild a spend response from serialized parameters."""

        return cls(
            capacity=float(payload["capacity"]), scale=float(payload["scale"])
        )


@dataclass(frozen=True)
class RevenueResponse:
    """Concave, increasing map from actual spend to expected revenue.

    ``baseline`` is revenue expected at zero spend, ``alpha`` the most
    advertising can add, and ``kappa`` how quickly that addition saturates.
    """

    baseline: float
    alpha: float
    kappa: float

    def __post_init__(self) -> None:
        if self.baseline < 0:
            raise ValueError("baseline must not be negative")
        if self.alpha < 0:
            raise ValueError("alpha must not be negative")
        if self.kappa <= 0:
            raise ValueError("kappa must be positive")

    def expected_revenue(self, actual_spend: float) -> float:
        """Return expected revenue for one actual spend."""

        if actual_spend <= 0:
            return self.baseline
        return self.baseline + self.alpha * (
            1.0 - math.exp(-actual_spend / self.kappa)
        )

    def marginal_revenue(self, actual_spend: float) -> float:
        """Return the derivative of expected revenue with respect to spend.

        Strictly decreasing in spend, which is the diminishing return the
        optimizer equalizes across Campaigns.
        """

        if actual_spend < 0:
            return 0.0
        return (self.alpha / self.kappa) * math.exp(-actual_spend / self.kappa)

    def to_dict(self) -> dict[str, float]:
        """Return JavaScript Object Notation-compatible parameters."""

        return {
            "baseline": self.baseline,
            "alpha": self.alpha,
            "kappa": self.kappa,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RevenueResponse":
        """Rebuild a revenue response from serialized parameters."""

        return cls(
            baseline=float(payload["baseline"]),
            alpha=float(payload["alpha"]),
            kappa=float(payload["kappa"]),
        )


@dataclass(frozen=True)
class ResponseDiagnostics:
    """What evidence produced a fit and how well it described that evidence.

    Attributes:
        support: Whether the fit came from target history, a pooled transfer,
            or nothing usable.
        observation_count: Campaign-periods the fit consumed.
        intervention_count: How many of those carried a recorded intervention.
        distinct_budget_count: Distinct configured budgets observed.
        observed_budget_range: Lowest and highest configured budget observed.
        observed_spend_range: Lowest and highest actual spend observed.
        spend_fit_status: Whether the spend stage produced usable parameters.
        revenue_fit_status: Whether the revenue stage did.
        spend_mean_absolute_error: Mean absolute spend residual.
        revenue_mean_absolute_error: Mean absolute revenue residual.
        revenue_root_mean_square_error: Root mean square revenue residual.
        model_version: Version of the fitting contract used.
        pooled_campaign_ids: Campaigns a pooled fit borrowed from.
    """

    support: ResponseSupport
    observation_count: int = 0
    intervention_count: int = 0
    distinct_budget_count: int = 0
    observed_budget_range: tuple[float, float] = (0.0, 0.0)
    observed_spend_range: tuple[float, float] = (0.0, 0.0)
    spend_fit_status: FitStatus = FitStatus.UNFITTED
    revenue_fit_status: FitStatus = FitStatus.UNFITTED
    spend_mean_absolute_error: float | None = None
    revenue_mean_absolute_error: float | None = None
    revenue_root_mean_square_error: float | None = None
    model_version: str = MODEL_VERSION
    pooled_campaign_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Return JavaScript Object Notation-compatible diagnostics."""

        return {
            "support": self.support.value,
            "observation_count": self.observation_count,
            "intervention_count": self.intervention_count,
            "distinct_budget_count": self.distinct_budget_count,
            "observed_budget_range": list(self.observed_budget_range),
            "observed_spend_range": list(self.observed_spend_range),
            "spend_fit_status": self.spend_fit_status.value,
            "revenue_fit_status": self.revenue_fit_status.value,
            "spend_mean_absolute_error": self.spend_mean_absolute_error,
            "revenue_mean_absolute_error": self.revenue_mean_absolute_error,
            "revenue_root_mean_square_error": (
                self.revenue_root_mean_square_error
            ),
            "model_version": self.model_version,
            "pooled_campaign_ids": list(self.pooled_campaign_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResponseDiagnostics":
        """Rebuild diagnostics from a serialized artifact."""

        budget_range = tuple(payload["observed_budget_range"])
        spend_range = tuple(payload["observed_spend_range"])
        return cls(
            support=ResponseSupport(str(payload["support"])),
            observation_count=int(payload["observation_count"]),
            intervention_count=int(payload["intervention_count"]),
            distinct_budget_count=int(payload["distinct_budget_count"]),
            observed_budget_range=(float(budget_range[0]), float(budget_range[1])),
            observed_spend_range=(float(spend_range[0]), float(spend_range[1])),
            spend_fit_status=FitStatus(str(payload["spend_fit_status"])),
            revenue_fit_status=FitStatus(str(payload["revenue_fit_status"])),
            spend_mean_absolute_error=_optional_float(
                payload.get("spend_mean_absolute_error")
            ),
            revenue_mean_absolute_error=_optional_float(
                payload.get("revenue_mean_absolute_error")
            ),
            revenue_root_mean_square_error=_optional_float(
                payload.get("revenue_root_mean_square_error")
            ),
            model_version=str(payload.get("model_version", MODEL_VERSION)),
            pooled_campaign_ids=tuple(
                str(item) for item in payload.get("pooled_campaign_ids", ())
            ),
        )


@dataclass(frozen=True)
class CampaignResponseModel:
    """One Campaign's fitted budget-to-spend-to-revenue response.

    Attributes:
        campaign_id: The Campaign this model estimates, or a pooled model
            identifier when ``diagnostics.support`` is ``POOLED_TRANSFER``.
        currency: Currency every monetary figure is denominated in.
        spend_response: Fitted budget-to-spend stage.
        revenue_response: Fitted spend-to-revenue stage.
        diagnostics: The evidence and fit quality behind both stages.
    """

    campaign_id: str
    currency: str
    spend_response: SpendResponse | None
    revenue_response: RevenueResponse | None
    diagnostics: ResponseDiagnostics

    @property
    def is_usable(self) -> bool:
        """Return whether this model may drive an optimized recommendation."""

        return (
            self.spend_response is not None
            and self.revenue_response is not None
            and self.diagnostics.support != ResponseSupport.INSUFFICIENT_SUPPORT
        )

    def expected_spend(self, configured_budget: float) -> float:
        """Return expected actual spend for one configured budget."""

        self._require_usable()
        return self.spend_response.expected_spend(configured_budget)

    def expected_revenue_from_spend(self, actual_spend: float) -> float:
        """Return expected revenue for one actual spend."""

        self._require_usable()
        return self.revenue_response.expected_revenue(actual_spend)

    def expected_revenue(self, configured_budget: float) -> float:
        """Return expected revenue for one configured budget.

        Composes the two stages: budget determines spend, spend determines
        revenue. This is the objective the optimizer maximizes.
        """

        return self.expected_revenue_from_spend(
            self.expected_spend(configured_budget)
        )

    def marginal_expected_revenue(
        self, configured_budget: float, step: float = 1.0
    ) -> float:
        """Return added expected revenue per added unit of configured budget.

        Uses a forward difference over the composed response so the spend
        stage's own saturation is included, which a derivative of the revenue
        stage alone would miss.
        """

        self._require_usable()
        if step <= 0:
            raise ResponseModelError("step must be positive")
        lower = self.expected_revenue(max(0.0, configured_budget))
        upper = self.expected_revenue(max(0.0, configured_budget) + step)
        return (upper - lower) / step

    def is_extrapolating(self, configured_budget: float) -> bool:
        """Return whether a budget lies outside the observed budget range."""

        low, high = self.diagnostics.observed_budget_range
        return configured_budget < low or configured_budget > high

    def _require_usable(self) -> None:
        if not self.is_usable:
            raise ResponseModelError(
                f"campaign {self.campaign_id!r} has "
                f"{self.diagnostics.support.value} and cannot produce a "
                "response estimate"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a reproducible JavaScript Object Notation artifact."""

        return {
            "model_id": f"{MODEL_VERSION}:{self.campaign_id}",
            "model_version": MODEL_VERSION,
            "campaign_id": self.campaign_id,
            "currency": self.currency,
            "spend_response": (
                None if self.spend_response is None else self.spend_response.to_dict()
            ),
            "revenue_response": (
                None
                if self.revenue_response is None
                else self.revenue_response.to_dict()
            ),
            "diagnostics": self.diagnostics.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CampaignResponseModel":
        """Rebuild a response model from its serialized artifact."""

        spend = payload.get("spend_response")
        revenue = payload.get("revenue_response")
        return cls(
            campaign_id=str(payload["campaign_id"]),
            currency=str(payload["currency"]),
            spend_response=None if spend is None else SpendResponse.from_dict(spend),
            revenue_response=(
                None if revenue is None else RevenueResponse.from_dict(revenue)
            ),
            diagnostics=ResponseDiagnostics.from_dict(payload["diagnostics"]),
        )

    def to_str(self) -> str:
        """Return the artifact as deterministic serialized text."""

        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_str(cls, value: str) -> "CampaignResponseModel":
        """Rebuild a response model from serialized text."""

        return cls.from_dict(json.loads(value))


def fit_campaign_response_models(
    dataset: CampaignResponseDataset,
) -> Mapping[str, CampaignResponseModel]:
    """Fit one response model per Campaign, falling back to a pooled model.

    A Campaign with enough of its own budget variation is fitted from its own
    history (``TARGET_HISTORY``). A Campaign without it borrows a pooled fit
    over comparable Campaigns (``POOLED_TRANSFER``), which is labelled so no
    reader mistakes it for that Campaign's observed behavior. When neither is
    possible the Campaign is returned with ``INSUFFICIENT_SUPPORT`` rather
    than a falsely precise curve.

    Args:
        dataset: Campaign-period response observations.

    Returns:
        Mapping of Campaign identifier to its fitted response model.
    """

    grouped = dataset.by_campaign()
    pooled_by_segment = _fit_pooled_models(grouped)
    models: dict[str, CampaignResponseModel] = {}
    for campaign_id, observations in grouped.items():
        target = _fit_single(campaign_id, observations, ResponseSupport.TARGET_HISTORY)
        if target is not None:
            models[campaign_id] = target
            continue
        pooled = pooled_by_segment.get(_segment_key(observations[0]))
        if pooled is not None:
            models[campaign_id] = replace(pooled, campaign_id=campaign_id)
            continue
        models[campaign_id] = _insufficient(campaign_id, observations)
    return models


def _fit_pooled_models(
    grouped: Mapping[str, Sequence[CampaignResponseObservation]],
) -> Mapping[tuple[str, str, str, str], CampaignResponseModel]:
    """Fit one pooled model per comparable Provider, product, and market.

    Pooling uses ordinary decision-time Campaign attributes. It is unrelated
    to the dashboard's presentation-only similarity feature, which must never
    influence a fitted model.
    """

    segments: dict[
        tuple[str, str, str, str], list[CampaignResponseObservation]
    ] = {}
    contributors: dict[tuple[str, str, str, str], set[str]] = {}
    for campaign_id, observations in grouped.items():
        for item in observations:
            key = _segment_key(item)
            segments.setdefault(key, []).append(item)
            contributors.setdefault(key, set()).add(campaign_id)

    pooled: dict[tuple[str, str, str, str], CampaignResponseModel] = {}
    for key, observations in segments.items():
        if len(contributors[key]) < 2:
            continue
        model = _fit_single(
            f"POOLED:{':'.join(key)}",
            observations,
            ResponseSupport.POOLED_TRANSFER,
        )
        if model is not None:
            pooled[key] = replace(
                model,
                diagnostics=replace(
                    model.diagnostics,
                    pooled_campaign_ids=tuple(sorted(contributors[key])),
                ),
            )
    return pooled


def _segment_key(
    observation: CampaignResponseObservation,
) -> tuple[str, str, str, str]:
    """Return the decision-time segment a pooled model is fitted within."""

    return (
        str(observation.provider.value),
        observation.ad_product,
        observation.marketplace,
        observation.currency,
    )


def _fit_single(
    campaign_id: str,
    observations: Sequence[CampaignResponseObservation],
    support: ResponseSupport,
) -> CampaignResponseModel | None:
    """Fit both stages, or return ``None`` when evidence is insufficient."""

    budgets = [item.configured_budget for item in observations]
    spends = [item.actual_spend for item in observations]
    revenues = [item.total_revenue for item in observations]
    distinct_budgets = len({round(value, 6) for value in budgets})
    if (
        len(observations) < MINIMUM_TARGET_OBSERVATIONS
        or distinct_budgets < MINIMUM_DISTINCT_BUDGETS
    ):
        return None

    spend_response = _fit_spend_response(budgets, spends)
    revenue_response = _fit_revenue_response(spends, revenues)
    if spend_response is None or revenue_response is None:
        return None

    spend_errors = [
        abs(spend_response.expected_spend(budget) - spend)
        for budget, spend in zip(budgets, spends)
    ]
    revenue_errors = [
        revenue_response.expected_revenue(spend) - revenue
        for spend, revenue in zip(spends, revenues)
    ]
    diagnostics = ResponseDiagnostics(
        support=support,
        observation_count=len(observations),
        intervention_count=sum(1 for item in observations if item.is_intervention),
        distinct_budget_count=distinct_budgets,
        observed_budget_range=(min(budgets), max(budgets)),
        observed_spend_range=(min(spends), max(spends)),
        spend_fit_status=FitStatus.FITTED,
        revenue_fit_status=FitStatus.FITTED,
        spend_mean_absolute_error=_mean(spend_errors),
        revenue_mean_absolute_error=_mean([abs(item) for item in revenue_errors]),
        revenue_root_mean_square_error=math.sqrt(
            _mean([item * item for item in revenue_errors])
        ),
    )
    return CampaignResponseModel(
        campaign_id=campaign_id,
        currency=observations[0].currency,
        spend_response=spend_response,
        revenue_response=revenue_response,
        diagnostics=diagnostics,
    )


def _insufficient(
    campaign_id: str, observations: Sequence[CampaignResponseObservation]
) -> CampaignResponseModel:
    """Return a model that reports why it cannot estimate a response."""

    budgets = [item.configured_budget for item in observations]
    spends = [item.actual_spend for item in observations]
    return CampaignResponseModel(
        campaign_id=campaign_id,
        currency=observations[0].currency if observations else "",
        spend_response=None,
        revenue_response=None,
        diagnostics=ResponseDiagnostics(
            support=ResponseSupport.INSUFFICIENT_SUPPORT,
            observation_count=len(observations),
            intervention_count=sum(
                1 for item in observations if item.is_intervention
            ),
            distinct_budget_count=len({round(value, 6) for value in budgets}),
            observed_budget_range=(
                (min(budgets), max(budgets)) if budgets else (0.0, 0.0)
            ),
            observed_spend_range=(
                (min(spends), max(spends)) if spends else (0.0, 0.0)
            ),
            spend_fit_status=FitStatus.UNFITTED,
            revenue_fit_status=FitStatus.UNFITTED,
        ),
    )


def _fit_spend_response(
    budgets: Sequence[float], spends: Sequence[float]
) -> SpendResponse | None:
    """Fit the saturating budget-to-spend stage by deterministic search."""

    highest_spend = max(spends)
    if highest_spend <= 0:
        return None
    capacity_grid = [highest_spend * factor for factor in (1.0, 1.15, 1.35, 1.6, 2.0)]
    highest_budget = max(budgets) or highest_spend
    scale_grid = [
        highest_budget * factor
        for factor in (0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.5, 4.0, 8.0)
    ]
    best: SpendResponse | None = None
    best_error = math.inf
    for capacity in capacity_grid:
        for scale in scale_grid:
            if scale <= 0:
                continue
            candidate = SpendResponse(capacity=capacity, scale=scale)
            error = sum(
                (candidate.expected_spend(budget) - spend) ** 2
                for budget, spend in zip(budgets, spends)
            )
            if error < best_error - 1e-12:
                best_error = error
                best = candidate
    return best


def _fit_revenue_response(
    spends: Sequence[float], revenues: Sequence[float]
) -> RevenueResponse | None:
    """Fit the concave spend-to-revenue stage by deterministic search.

    ``kappa`` is searched on a fixed grid; for each candidate the linear
    parameters ``baseline`` and ``alpha`` follow in closed form from ordinary
    least squares, then are clamped non-negative so the fitted curve stays
    increasing and concave.
    """

    highest_spend = max(spends)
    if highest_spend <= 0 or len(spends) < 2:
        return None
    best: RevenueResponse | None = None
    best_error = math.inf
    for factor in (
        0.05, 0.1, 0.15, 0.25, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0
    ):
        kappa = highest_spend * factor
        if kappa <= 0:
            continue
        basis = [1.0 - math.exp(-spend / kappa) for spend in spends]
        solved = _least_squares_intercept_slope(basis, revenues)
        if solved is None:
            continue
        baseline, alpha = solved
        candidate = RevenueResponse(
            baseline=max(0.0, baseline), alpha=max(0.0, alpha), kappa=kappa
        )
        error = sum(
            (candidate.expected_revenue(spend) - revenue) ** 2
            for spend, revenue in zip(spends, revenues)
        )
        if error < best_error - 1e-12:
            best_error = error
            best = candidate
    return best


def _least_squares_intercept_slope(
    basis: Sequence[float], targets: Sequence[float]
) -> tuple[float, float] | None:
    """Solve ``targets ~ intercept + slope * basis`` in closed form."""

    count = len(basis)
    if count < 2:
        return None
    mean_basis = _mean(basis)
    mean_target = _mean(targets)
    variance = sum((value - mean_basis) ** 2 for value in basis)
    if variance <= 1e-12:
        return None
    covariance = sum(
        (value - mean_basis) * (target - mean_target)
        for value, target in zip(basis, targets)
    )
    slope = covariance / variance
    return mean_target - slope * mean_basis, slope


def _mean(values: Sequence[float]) -> float:
    """Return the arithmetic mean, or zero for an empty sequence."""

    return sum(values) / len(values) if values else 0.0


def _optional_float(value: Any) -> float | None:
    """Return a float, preserving an absent value as ``None``."""

    return None if value is None else float(value)


def response_models_to_dict(
    models: Mapping[str, CampaignResponseModel],
) -> dict[str, Any]:
    """Return a serializable artifact holding every fitted Campaign model."""

    return {
        "model_version": MODEL_VERSION,
        "campaign_models": {
            campaign_id: model.to_dict()
            for campaign_id, model in sorted(models.items())
        },
    }


def response_models_from_dict(
    payload: Mapping[str, Any],
) -> Mapping[str, CampaignResponseModel]:
    """Rebuild every Campaign response model from a serialized artifact."""

    return {
        campaign_id: CampaignResponseModel.from_dict(item)
        for campaign_id, item in payload["campaign_models"].items()
    }
