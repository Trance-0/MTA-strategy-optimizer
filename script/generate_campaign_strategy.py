"""Fit Campaign response models and write the optimized strategy artifact.

Command-line entry point for the Campaign-level response model and constrained
budget optimizer.

Data flow: MTA-SIM ``simulation_research.json`` -> `mta_sim_research_adapter`
-> `episode_bridge` -> `response_dataset` -> `response_model` ->
`budget_optimizer` -> `outputs/campaign_strategy.json`, which the dashboard's
data source reads.

The artifact holds both strategies so a reader can compare them: the Initial
Strategy with the basis it was built from, and the Optimized Strategy with the
response evidence behind it. Attribution may inform the Initial Strategy only;
it is never an input to the fitted response model or to the optimizer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = PROJECT_ROOT / "modules" / "mta_strategy_recommendation"
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_common.src.budget import BudgetConstraints  # noqa: E402
from modules.mta_common.src.enums import (  # noqa: E402
    BudgetUsagePolicy,
    StrategyObjective,
)
from modules.mta_standard.src.mta_sim_research_adapter import (  # noqa: E402
    load_mta_sim_research_snapshot,
)
from modules.mta_strategy_recommendation.src.budget_optimizer import (  # noqa: E402
    CampaignBudgetRequest,
    optimize_campaign_budgets,
)
from modules.mta_strategy_recommendation.src.episode_bridge import (  # noqa: E402
    campaign_episodes_from_research_snapshot,
)
from modules.mta_strategy_recommendation.src.response_dataset import (  # noqa: E402
    build_campaign_response_dataset,
)
from modules.mta_strategy_recommendation.src.response_model import (  # noqa: E402
    fit_campaign_response_models,
    response_models_to_dict,
)


# How an Initial Strategy's allocation was arrived at. Attribution-derived
# bases are legitimate here and only here.
INITIAL_BASIS_EQUAL_NO_HISTORY = "EQUAL_NO_HISTORY"
INITIAL_BASIS_CONFIGURED_BASELINE = "CONFIGURED_BASELINE"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Fit Campaign response models and optimize Campaign budgets.")
    )
    parser.add_argument(
        "--research-snapshot",
        type=Path,
        required=True,
        help="Path to an MTA-SIM simulation_research.json file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MODULE_ROOT / "outputs" / "campaign_strategy.json",
        help="Destination for the campaign strategy artifact.",
    )
    parser.add_argument(
        "--marketplace",
        default=None,
        help=(
            "Exact marketplace to fit from a multi-marketplace snapshot. "
            "Required when the snapshot carries more than one."
        ),
    )
    parser.add_argument(
        "--total-budget",
        type=float,
        default=None,
        help=(
            "Authorized total daily budget. Defaults to the sum of each "
            "Campaign's observed baseline budget."
        ),
    )
    parser.add_argument(
        "--budget-usage-policy",
        choices=[item.value for item in BudgetUsagePolicy],
        default=BudgetUsagePolicy.SPEND_FULL_BUDGET.value,
        help="Whether the authorized budget must be fully allocated.",
    )
    parser.add_argument(
        "--minimum-budget",
        type=float,
        default=0.0,
        help="Per-Campaign minimum daily budget.",
    )
    parser.add_argument(
        "--maximum-budget",
        type=float,
        default=None,
        help="Per-Campaign maximum daily budget. Unbounded when omitted.",
    )
    arguments = parser.parse_args()

    snapshot = load_mta_sim_research_snapshot(arguments.research_snapshot)
    episodes = campaign_episodes_from_research_snapshot(snapshot)
    marketplaces = sorted(
        {episode.campaign.reporting_scope.marketplace for episode in episodes}
    )
    selected_marketplace = (
        str(arguments.marketplace).strip() if arguments.marketplace else ""
    )
    if not selected_marketplace:
        if len(marketplaces) != 1:
            print(
                "The research snapshot contains several marketplaces; pass "
                f"--marketplace with one of {marketplaces}.",
                file=sys.stderr,
            )
            return 1
        selected_marketplace = marketplaces[0]
    if selected_marketplace not in marketplaces:
        print(
            f"Marketplace {selected_marketplace!r} is not present in the "
            f"research snapshot; available={marketplaces}.",
            file=sys.stderr,
        )
        return 1
    dataset = build_campaign_response_dataset(
        episode
        for episode in episodes
        if episode.campaign.reporting_scope.marketplace == selected_marketplace
    )
    if not len(dataset):
        print(
            "No Campaign-period observations were found in the research "
            "snapshot; nothing to fit.",
            file=sys.stderr,
        )
        return 1

    models = fit_campaign_response_models(dataset)
    initial = _initial_strategy(dataset)
    total_budget = (
        sum(item["initial_budget"] for item in initial["allocations"])
        if arguments.total_budget is None
        else arguments.total_budget
    )
    currency = dataset.observations[0].currency

    requests = [
        CampaignBudgetRequest(
            campaign_id=item["campaign_id"],
            constraints=BudgetConstraints(
                campaign_id=item["campaign_id"],
                budget_usage_policy=BudgetUsagePolicy(arguments.budget_usage_policy),
                minimum_daily_budget=arguments.minimum_budget,
                maximum_daily_budget=arguments.maximum_budget,
            ),
            initial_budget=item["initial_budget"],
            currency=currency,
            is_active=item["is_active"],
            current_budget=item["current_budget"],
        )
        for item in initial["allocations"]
    ]
    plan = optimize_campaign_budgets(
        requests=requests,
        response_models=models,
        total_budget=total_budget,
        objective=StrategyObjective.MAXIMIZE_REVENUE,
        budget_usage_policy=BudgetUsagePolicy(arguments.budget_usage_policy),
    )

    artifact = {
        "currency": currency,
        "initial_strategy": initial,
        "optimized_strategy": plan.to_dict(),
        "response_models": response_models_to_dict(models),
        "response_observations": [
            _observation_row(item) for item in dataset.observations
        ],
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Wrote {arguments.output} "
        f"({len(dataset)} observations, {len(models)} Campaign models, "
        f"optimized={plan.is_optimized})."
    )
    return 0


def _initial_strategy(dataset) -> dict:
    """Build the Initial Strategy this run compares its optimization against.

    Uses each Campaign's own configured baseline budget when the history
    records one, which is the honest starting point for a Campaign that has
    already run. A Campaign with no baseline falls back to an equal share.
    Attribution-proportional seeding remains available through the separate
    initializer; whichever basis is used is labelled here so the dashboard can
    show it.
    """

    allocations = []
    for campaign_id, rows in sorted(dataset.by_campaign().items()):
        latest = rows[-1]
        baseline = latest.baseline_budget
        allocations.append(
            {
                "campaign_id": campaign_id,
                "initial_budget": (
                    float(baseline)
                    if baseline is not None
                    else float(latest.configured_budget)
                ),
                "current_budget": float(latest.configured_budget),
                "is_active": latest.campaign_status.upper() == "ACTIVE",
                "basis": (
                    INITIAL_BASIS_CONFIGURED_BASELINE
                    if baseline is not None
                    else INITIAL_BASIS_EQUAL_NO_HISTORY
                ),
                "provider": latest.provider.value,
                "ad_product": latest.ad_product,
                "marketplace": latest.marketplace,
            }
        )
    return {
        "recommendation_type": "INITIAL_SEED",
        "is_optimized": False,
        "basis": INITIAL_BASIS_CONFIGURED_BASELINE,
        "uses_attribution": False,
        "allocations": allocations,
    }


def _observation_row(observation) -> dict:
    """Flatten one response observation for the dashboard's history markers."""

    return {
        "campaign_id": observation.campaign_id,
        "marketplace": observation.marketplace,
        "report_date": observation.report_start_date,
        "currency": observation.currency,
        "provider": observation.provider.value,
        "ad_product": observation.ad_product,
        "configured_budget": observation.configured_budget,
        "actual_spend": observation.actual_spend,
        "impressions": observation.impressions,
        "clicks": observation.clicks,
        "total_revenue": observation.total_revenue,
        "intervention_id": observation.intervention_id,
        "baseline_budget": observation.baseline_budget,
        "budget_delta": observation.budget_delta,
        "assignment_type": (
            None
            if observation.assignment_type is None
            else observation.assignment_type.value
        ),
        "randomized": observation.randomized,
    }


if __name__ == "__main__":
    raise SystemExit(main())
