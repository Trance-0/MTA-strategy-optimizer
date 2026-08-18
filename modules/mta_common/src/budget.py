"""Budget constraints (forward-looking) and budget observations (spend).

``modules/mta_strategy_recommendation`` is entirely pre-spend today: every
budget-shaped field it has (`total_daily_budget`, `campaign_budget_seed`,
`initial_daily_budget`, `minimum_required_daily_budget`) is a forward-looking
allocation amount. No `actual_spend` concept exists anywhere in that module;
the closest real spend field in the whole repository is
`AdsDailyPerformance.cost` in the dashboard schema, which is not connected to
the budget recommender at all. ``BudgetConstraints`` models the former;
``BudgetObservation`` models the latter and is new, since nothing observes
authorized budget against actual spend today.

Data flow: a future strategy optimizer would read ``BudgetConstraints`` and
``StrategyObjective``/``BudgetUsagePolicy`` to decide an allocation; a future
reporting integration would populate ``BudgetObservation`` from delivery
data. Neither the optimizer nor that integration is implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import AssignmentType, BudgetUsagePolicy
from .reporting_scope import ReportingScope


@dataclass(frozen=True)
class BudgetConstraints:
    """Forward-looking budget bounds and usage policy for one campaign.

    Attributes:
        campaign_id: The constrained ``Campaign.campaign_id``.
        minimum_daily_budget: Optional feasibility floor, mirroring
            ``budget_recommender.py``'s ``minimum_required_daily_budget``.
        maximum_daily_budget: Optional authorized ceiling.
        budget_usage_policy: Whether the full budget must be used or only up
            to it. Declared here for a future optimizer to read; this class
            does not enforce it against any observed spend.
    """

    campaign_id: str
    budget_usage_policy: BudgetUsagePolicy
    minimum_daily_budget: float | None = None
    maximum_daily_budget: float | None = None

    def __post_init__(self) -> None:
        if not str(self.campaign_id).strip():
            raise ValueError("campaign_id is required")
        if self.minimum_daily_budget is not None and self.minimum_daily_budget < 0:
            raise ValueError("minimum_daily_budget must not be negative")
        if self.maximum_daily_budget is not None and self.maximum_daily_budget < 0:
            raise ValueError("maximum_daily_budget must not be negative")
        if (
            self.minimum_daily_budget is not None
            and self.maximum_daily_budget is not None
            and self.minimum_daily_budget > self.maximum_daily_budget
        ):
            raise ValueError("minimum_daily_budget must not exceed maximum_daily_budget")


@dataclass(frozen=True)
class BudgetObservation:
    """What budget was configured and what was actually spent, for one scope.

    ``configured_budget`` and ``actual_spend`` are independent fields.
    ``actual_spend < configured_budget`` is valid and expected — a campaign
    is not required to exhaust its authorized budget — so this class does
    not assume or enforce equality between the two.

    Attributes:
        campaign_id: The observed ``Campaign.campaign_id``.
        reporting_scope: Account, market, currency, and window this
            observation covers.
        configured_budget: Optional authorized budget for the scope.
        actual_spend: Optional amount actually spent in the scope.
        intervention_id: Reserved for a future randomized or rule-based
            budget intervention study. Not populated by any current data
            source.
        baseline_budget: Reserved counterfactual budget for an intervention.
            Not populated by any current data source.
        budget_delta: Reserved ``configured_budget - baseline_budget`` for an
            intervention. Not populated by any current data source.
        assignment_type: Reserved assignment mechanism for an intervention.
            Not populated by any current data source.
        randomized: Reserved flag for whether assignment was randomized. Not
            populated by any current data source.
    """

    campaign_id: str
    reporting_scope: ReportingScope
    configured_budget: float | None = None
    actual_spend: float | None = None
    intervention_id: str | None = None
    baseline_budget: float | None = None
    budget_delta: float | None = None
    assignment_type: AssignmentType | None = None
    randomized: bool | None = None

    def __post_init__(self) -> None:
        if not str(self.campaign_id).strip():
            raise ValueError("campaign_id is required")
        if self.configured_budget is not None and self.configured_budget < 0:
            raise ValueError("configured_budget must not be negative")
        if self.actual_spend is not None and self.actual_spend < 0:
            raise ValueError("actual_spend must not be negative")
