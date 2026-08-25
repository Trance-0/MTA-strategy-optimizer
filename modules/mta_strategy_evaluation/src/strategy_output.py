"""The one decision type every strategy returns and every evaluator accepts.

Two producers answer the same question in two shapes today. The deterministic
initializer writes ``initial_budget_recommendation.json``, whose Campaigns
carry a ``budget_seed_share`` and a list of Ad Group slots; the Campaign
budget optimizer writes ``campaign_strategy.json``, whose Campaigns carry an
``optimized_budget`` and no Ad Group at all. Nothing could compare them,
because no type existed that both are instances of. ``StrategyOutput`` is
that type.

It carries the *decision* and not the reasoning behind it: no fitted curve,
no expected revenue, no attribution share. An evaluator that could see the
reasoning would be scoring the argument rather than the outcome.
``uses_attribution`` records which side of the attribution boundary the
producing strategy stood on; it does not carry the attribution.

``ConservationReport`` is derived by :meth:`StrategyOutput.conservation`
rather than stored as a field. A stored report is free to disagree with the
allocation beside it and nothing would say which was authoritative; a derived
one cannot. A failing report does not raise: ``__post_init__`` rejects what is
structurally impossible (a negative budget, an unknown execution status, a
duplicate Campaign), while conservation is a property of an otherwise
well-formed allocation that this layer's job is to report.

Data flow: ``strategy_projection`` reads the committed artifacts into this
type -> ``evaluation_episode`` pairs one with the observations that followed
it -> ``script/evaluate_strategies.py`` writes the result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from modules.mta_common.src.enums import Provider
from modules.mta_common.src.lineage import DataLineage
from modules.mta_common.src.reporting_scope import ReportingScope

#: An unoptimized seed, as the deterministic initializer produces.
ALLOCATION_TYPE_INITIAL_SEED = "INITIAL_SEED"

#: An optimized allocation, as the Campaign budget optimizer produces. The
#: evaluator reports the two separately rather than averaging them: a seed is
#: not a failed optimization.
ALLOCATION_TYPE_OPTIMIZED = "OPTIMIZED"

ALLOCATION_TYPES: frozenset[str] = frozenset(
    {ALLOCATION_TYPE_INITIAL_SEED, ALLOCATION_TYPE_OPTIMIZED}
)

#: Exactly the values `budget_recommender.py` writes to `execution_status`.
EXECUTION_STATUSES: frozenset[str] = frozenset(
    {"EXECUTABLE", "INSUFFICIENT_BUDGET_FOR_MINIMUMS", "UNEXECUTABLE"}
)

#: Shares are already normalized, so an absolute bound is the whole statement.
#: A relative tolerance beside it would be a second, looser version of the same
#: rule. Matches the attribution layer's share tolerance.
SHARE_ABSOLUTE_TOLERANCE = 1e-12

#: Money accumulates floating-point error proportional to its magnitude, so a
#: residual passes if it is within either bound.
BUDGET_ABSOLUTE_TOLERANCE = 1e-6
BUDGET_RELATIVE_TOLERANCE = 1e-9


def _within_tolerance(residual: float, magnitude: float) -> bool:
    """Return whether a monetary residual is inside either budget tolerance."""

    return abs(residual) <= max(
        BUDGET_ABSOLUTE_TOLERANCE, BUDGET_RELATIVE_TOLERANCE * abs(magnitude)
    )


def _require_finite_non_negative(value: float | None, name: str) -> None:
    """Reject a monetary field that is negative or not a real number."""

    if value is None:
        return
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _require_share(value: float, name: str) -> None:
    """Reject a share outside the closed unit interval."""

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class AdGroupBudgetSlot:
    """One Ad Group slot's share of its Campaign's allocation.

    A slot rather than an Ad Group: the initializer allocates to positions
    that do not exist yet, so this carries the recommender-assigned
    ``ad_group_slot_id`` and no reference to a created Ad Group.

    Attributes:
        ad_group_slot_id: The recommender-assigned slot identifier.
        allocation_basis: How this slot's share was derived, for example
            ``CAMPAIGN_MTA_EQUAL_SPLIT``.
        budget_share: This slot's fraction of the Campaign Group total, on
            the same basis as ``CampaignBudgetDecision.budget_share`` so the
            two are directly summable.
        budget: The absolute daily budget in the output's currency, or
            ``None`` in relative-shares-only mode.
    """

    ad_group_slot_id: str
    budget_share: float
    allocation_basis: str | None = None
    budget: float | None = None

    def __post_init__(self) -> None:
        if not str(self.ad_group_slot_id).strip():
            raise ValueError("ad_group_slot_id is required")
        _require_share(self.budget_share, "budget_share")
        _require_finite_non_negative(self.budget, "budget")

    def to_dict(self) -> dict:
        """Return this slot as JSON-compatible values, preserving ``None``."""

        return {
            "ad_group_slot_id": self.ad_group_slot_id,
            "allocation_basis": self.allocation_basis,
            "budget_share": self.budget_share,
            "budget": self.budget,
        }


@dataclass(frozen=True)
class CampaignBudgetDecision:
    """One Campaign's share of a strategy's allocation.

    ``budget_share`` is required and ``budget`` is not, because the share is
    the one field both producers can always supply: the initializer stores it
    directly, and the optimizer's is derived from its budget over the
    allocated total.

    Attributes:
        campaign_id: The allocated Campaign.
        budget_share: This Campaign's fraction of the group total.
        budget: The absolute daily budget in the output's currency, or
            ``None`` in relative-shares-only mode.
        ad_product: The Campaign's advertising product, when the producing
            artifact recorded it on the allocation.
        provider: The advertising platform, when known.
        ad_groups: Ordered slots, empty for a strategy that does not divide
            below the Campaign. Empty is the honest value for the optimizer,
            which claims ``NOT_AD_GROUP_OPTIMIZED``.
        execution_status: Whether the allocation can actually be executed.
        decision_basis: How the number was arrived at, for example
            ``CAMPAIGN_RESPONSE_MARGINAL_EQUALIZATION``.
    """

    campaign_id: str
    budget_share: float
    budget: float | None = None
    ad_product: str | None = None
    provider: Provider | None = None
    ad_groups: tuple[AdGroupBudgetSlot, ...] = field(default_factory=tuple)
    execution_status: str = "EXECUTABLE"
    decision_basis: str | None = None

    def __post_init__(self) -> None:
        if not str(self.campaign_id).strip():
            raise ValueError("campaign_id is required")
        _require_share(self.budget_share, "budget_share")
        _require_finite_non_negative(self.budget, "budget")
        if self.execution_status not in EXECUTION_STATUSES:
            raise ValueError(
                f"execution_status must be one of {sorted(EXECUTION_STATUSES)}; "
                f"received {self.execution_status!r}"
            )
        slot_ids = [slot.ad_group_slot_id for slot in self.ad_groups]
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError(
                f"campaign {self.campaign_id!r} repeats an ad_group_slot_id; "
                "a duplicate would double-count in the conservation sums"
            )

    def to_dict(self) -> dict:
        """Return this decision as JSON-compatible values, preserving ``None``."""

        return {
            "campaign_id": self.campaign_id,
            "budget_share": self.budget_share,
            "budget": self.budget,
            "ad_product": self.ad_product,
            "provider": None if self.provider is None else self.provider.value,
            "ad_groups": [slot.to_dict() for slot in self.ad_groups],
            "execution_status": self.execution_status,
            "decision_basis": self.decision_basis,
        }


@dataclass(frozen=True)
class ConservationReport:
    """Whether one allocation lost, invented, or overspent money.

    Derived by :meth:`StrategyOutput.conservation`; never stored on the
    output it describes.

    Attributes:
        within_campaign_share_error: Worst absolute residual of constraint
            (1), the within-Campaign share sum against the Campaign's share.
        campaign_share_error: Absolute residual of constraint (2), the
            Campaign shares against one.
        within_campaign_budget_error: Worst absolute residual of constraint
            (3), the within-Campaign budget sum against the Campaign's budget.
        budget_overrun: How much constraint (4) was exceeded by, and ``0.0``
            when it was not. Leaving budget unallocated is permitted, so
            underspend is never reported here.
        share_tolerance: The absolute tolerance shares were judged against.
        budget_absolute_tolerance: The absolute tolerance money was judged
            against.
        budget_relative_tolerance: The relative tolerance money was judged
            against; a residual passes if it is within either.
        violations: Human-readable descriptions, in constraint order.
        is_conserving: True exactly when ``violations`` is empty.
    """

    within_campaign_share_error: float
    campaign_share_error: float
    within_campaign_budget_error: float
    budget_overrun: float
    violations: tuple[str, ...] = field(default_factory=tuple)
    share_tolerance: float = SHARE_ABSOLUTE_TOLERANCE
    budget_absolute_tolerance: float = BUDGET_ABSOLUTE_TOLERANCE
    budget_relative_tolerance: float = BUDGET_RELATIVE_TOLERANCE

    @property
    def is_conserving(self) -> bool:
        """Return whether every constraint held within its tolerance."""

        return not self.violations

    def to_dict(self) -> dict:
        """Return this report as JSON-compatible values."""

        return {
            "within_campaign_share_error": self.within_campaign_share_error,
            "campaign_share_error": self.campaign_share_error,
            "within_campaign_budget_error": self.within_campaign_budget_error,
            "budget_overrun": self.budget_overrun,
            "share_tolerance": self.share_tolerance,
            "budget_absolute_tolerance": self.budget_absolute_tolerance,
            "budget_relative_tolerance": self.budget_relative_tolerance,
            "violations": list(self.violations),
            "is_conserving": self.is_conserving,
        }


@dataclass(frozen=True)
class StrategyOutput:
    """One strategy's budget decision for one Campaign Group and window.

    Attributes:
        strategy_id: Which strategy produced this, lowercase and
            underscore-separated.
        strategy_version: The version of the contract it was executed under,
            so a stored evaluation says which strategy contract it scored.
        allocation_type: ``INITIAL_SEED`` or ``OPTIMIZED``.
        scope: The marketplace, advertiser, currency, and window this
            allocation was computed for. Every monetary field on this output
            is denominated in ``scope.currency``.
        campaigns: One decision per allocated Campaign, in the producing
            artifact's own order.
        total_budget: The authorized total the allocation had to fit inside.
            ``None`` means relative-shares-only mode, which relaxes the
            monetary constraints to the share constraints alone; it is not a
            stand-in for zero.
        uses_attribution: Whether Multi-Touch Attribution evidence informed
            this allocation. Attribution may inform an Initial Strategy and
            must never reach a fitted response model or the optimizer.
        lineage: Where this decision came from. ``None`` when the producer
            recorded no provenance; the projection readers always populate it.
        warnings: Ordered warning codes the producing strategy raised,
            carried through so a plan already known to be weak does not read
            as a clean one after projection.
    """

    strategy_id: str
    strategy_version: str
    allocation_type: str
    scope: ReportingScope
    campaigns: tuple[CampaignBudgetDecision, ...]
    total_budget: float | None = None
    uses_attribution: bool = False
    lineage: DataLineage | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("strategy_id", "strategy_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        if self.allocation_type not in ALLOCATION_TYPES:
            raise ValueError(
                f"allocation_type must be one of {sorted(ALLOCATION_TYPES)}; "
                f"received {self.allocation_type!r}"
            )
        if not self.campaigns:
            raise ValueError(
                "campaigns must not be empty; a strategy that allocated to no "
                "Campaign made no decision to evaluate"
            )
        identifiers = [decision.campaign_id for decision in self.campaigns]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(
                "campaigns repeats a campaign_id; a duplicate would silently "
                "double-count in the conservation sums"
            )
        _require_finite_non_negative(self.total_budget, "total_budget")

    def conservation(self) -> ConservationReport:
        """Check the four conservation constraints over this allocation.

        Pure: two equal outputs return equal reports, and nothing is mutated.
        Constraints (1) and (3) apply only to Campaigns that carry Ad Group
        slots; a Campaign with none conserves trivially. Constraints (3) and
        (4) are skipped when ``total_budget`` is ``None``, which is what
        relative-shares-only mode means.

        Returns:
            ConservationReport: Each constraint's worst residual and every
            violation, in constraint order. Never raises for a violation.
        """

        violations: list[str] = []

        # (1) Within-Campaign share conservation.
        within_share_error = 0.0
        for decision in self.campaigns:
            if not decision.ad_groups:
                continue
            residual = (
                sum(slot.budget_share for slot in decision.ad_groups)
                - decision.budget_share
            )
            within_share_error = max(within_share_error, abs(residual))
            if abs(residual) > SHARE_ABSOLUTE_TOLERANCE:
                violations.append(
                    f"campaign {decision.campaign_id!r}: ad group shares sum to "
                    f"{sum(slot.budget_share for slot in decision.ad_groups)!r}, "
                    f"which differs from its budget_share "
                    f"{decision.budget_share!r} by {residual!r}"
                )

        # (2) Campaign shares sum to one.
        share_total = sum(decision.budget_share for decision in self.campaigns)
        campaign_share_error = abs(share_total - 1.0)
        if campaign_share_error > SHARE_ABSOLUTE_TOLERANCE:
            violations.append(
                f"Campaign shares sum to {share_total!r}, which differs from 1 "
                f"by {share_total - 1.0!r}"
            )

        within_budget_error = 0.0
        overrun = 0.0
        if self.total_budget is not None:
            # (3) Within-Campaign budget conservation.
            for decision in self.campaigns:
                if not decision.ad_groups or decision.budget is None:
                    continue
                if any(slot.budget is None for slot in decision.ad_groups):
                    continue
                allocated = sum(slot.budget or 0.0 for slot in decision.ad_groups)
                residual = allocated - decision.budget
                within_budget_error = max(within_budget_error, abs(residual))
                if not _within_tolerance(residual, decision.budget):
                    violations.append(
                        f"campaign {decision.campaign_id!r}: ad group budgets sum "
                        f"to {allocated!r}, which differs from its budget "
                        f"{decision.budget!r} by {residual!r}"
                    )

            # (4) Group budget not exceeded. An inequality: leaving budget
            # unallocated is permitted, exceeding the total is not.
            allocated_total = sum(
                decision.budget or 0.0 for decision in self.campaigns
            )
            excess = allocated_total - self.total_budget
            if excess > 0 and not _within_tolerance(excess, self.total_budget):
                overrun = excess
                violations.append(
                    f"Campaign budgets sum to {allocated_total!r}, which exceeds "
                    f"the authorized total {self.total_budget!r} by {excess!r}"
                )

        return ConservationReport(
            within_campaign_share_error=within_share_error,
            campaign_share_error=campaign_share_error,
            within_campaign_budget_error=within_budget_error,
            budget_overrun=overrun,
            violations=tuple(violations),
        )

    def to_dict(self) -> dict:
        """Return this output as JSON-compatible values, preserving ``None``.

        Campaigns are serialized in the order supplied, never re-sorted, so a
        reader sees the producing artifact's own order.
        """

        return {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "allocation_type": self.allocation_type,
            "scope": {
                "marketplace": self.scope.marketplace,
                "advertiser_id": self.scope.advertiser_id,
                "currency": self.scope.currency,
                "report_start_date": self.scope.report_start_date,
                "report_end_date": self.scope.report_end_date,
                "campaign_group_id": self.scope.campaign_group_id,
            },
            "campaigns": [decision.to_dict() for decision in self.campaigns],
            "total_budget": self.total_budget,
            "uses_attribution": self.uses_attribution,
            "lineage": None if self.lineage is None else _lineage_to_dict(self.lineage),
            "warnings": list(self.warnings),
        }


def _lineage_to_dict(lineage: DataLineage) -> dict:
    """Return a DataLineage as JSON-compatible values."""

    return {
        "source_system": lineage.source_system,
        "source_reference": lineage.source_reference,
        "schema_version": lineage.schema_version,
        "transformation_version": lineage.transformation_version,
        "classification": lineage.classification.value,
        "is_synthetic": lineage.is_synthetic,
        "provider": None if lineage.provider is None else lineage.provider.value,
        "report_period_start": lineage.report_period_start,
        "report_period_end": lineage.report_period_end,
    }
