"""Compose MTA-SIM research records into model-facing Campaign episodes.

``mta_sim_research_adapter`` reads the simulator's file contract into canonical
``mta_common`` objects but leaves them as flat lists. This module joins those
lists on Campaign, marketplace, and period to produce ``CampaignEpisode``
values, which is the only type the response dataset accepts.

The join deliberately reads the simulator's *observed* records only. The
snapshot's ``evaluation_outcome_observations`` carry organic and incremental
splits the simulator knows because it generated them; they are evaluation-only
truth and are never composed into a ``CampaignEpisode``. Attribution evidence
is likewise not attached: the response model must work without it.

Data flow: ``simulation_research.json`` -> ``mta_sim_research_adapter`` ->
this module -> ``response_dataset.build_campaign_response_dataset``.
"""

from __future__ import annotations

from collections import defaultdict

from modules.mta_common.src.budget import BudgetConstraints, BudgetObservation
from modules.mta_common.src.campaign import Campaign
from modules.mta_common.src.delivery import DeliveryObservation
from modules.mta_common.src.enums import BudgetUsagePolicy
from modules.mta_common.src.episode import CampaignEpisode
from modules.mta_common.src.outcome import OutcomeObservation
from modules.mta_standard.src.mta_sim_research_adapter import (
    MtaSimResearchSnapshot,
)


def campaign_episodes_from_research_snapshot(
    snapshot: MtaSimResearchSnapshot,
) -> tuple[CampaignEpisode, ...]:
    """Join one research snapshot's observed records into Campaign episodes.

    Args:
        snapshot: Canonical records loaded from ``simulation_research.json``.

    Returns:
        One ``CampaignEpisode`` per Campaign, marketplace, and period that has
        a budget observation. Delivery and outcome records are attached to the
        episode whose Campaign and period they belong to.
    """

    campaigns = {item.campaign_id: item for item in snapshot.campaigns}
    delivery_by_key = _group_by_campaign_period(
        snapshot.delivery_observations, snapshot.delivery_contexts
    )
    outcome_by_key = _group_by_campaign_period(
        snapshot.outcome_observations,
        snapshot.outcome_contexts[: len(snapshot.outcome_observations)],
    )

    episodes: list[CampaignEpisode] = []
    for budget in snapshot.budget_observations:
        campaign = campaigns.get(budget.campaign_id)
        if campaign is None:
            continue
        scope = budget.reporting_scope
        key = (
            budget.campaign_id,
            scope.marketplace,
            scope.report_start_date,
        )
        episodes.append(
            CampaignEpisode(
                campaign=_campaign_in_scope(campaign, budget),
                budget_constraints=BudgetConstraints(
                    campaign_id=budget.campaign_id,
                    budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
                ),
                budget_observation=budget,
                delivery_observations=tuple(delivery_by_key.get(key, ())),
                outcome_observations=tuple(outcome_by_key.get(key, ())),
            )
        )
    return tuple(episodes)


def _campaign_in_scope(
    campaign: Campaign, budget: BudgetObservation
) -> Campaign:
    """Return the Campaign restated in its observed period's scope.

    ``CampaignEpisode`` requires one currency across every scope it composes.
    The Campaign's own scope describes where its identity was read, which may
    be a different marketplace from the period being observed.
    """

    from dataclasses import replace

    return replace(campaign, reporting_scope=budget.reporting_scope)


def _group_by_campaign_period(
    observations: tuple[DeliveryObservation | OutcomeObservation, ...],
    contexts: tuple,
) -> dict[tuple[str, str, str], list]:
    """Group observations by the Campaign and period they were observed in.

    The Campaign identifier travels in the adapter's parallel context mapping
    because the canonical delivery and outcome classes are Touchpoint-scoped
    rather than Campaign-scoped.
    """

    grouped: dict[tuple[str, str, str], list] = defaultdict(list)
    for observation, context in zip(observations, contexts):
        campaign_id = context.get("campaign_id")
        if campaign_id is None:
            continue
        scope = observation.reporting_scope
        grouped[
            (str(campaign_id), scope.marketplace, scope.report_start_date)
        ].append(observation)
    return grouped
