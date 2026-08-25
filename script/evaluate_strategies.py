"""Evaluate project strategy artifacts and write one dashboard-ready report.

Command-line entry point for the fourth pipeline stage. It projects the
initializer and optimizer artifacts into ``StrategyOutput``, checks allocation
conservation, compares conserving strategies with observed Campaign response
when the observations cover every allocation, and optionally fits the
contributed budget-to-revenue model.

Data flow: strategy recommendation outputs plus an optional MTA-SIM research
snapshot -> strategy projection and evaluation layers ->
``modules/mta_strategy_evaluation/outputs/strategy_evaluation.json``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = PROJECT_ROOT / "modules" / "mta_strategy_evaluation"
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_common.src.budget import (  # noqa: E402
    BudgetConstraints,
    BudgetObservation,
)
from modules.mta_common.src.campaign import Campaign  # noqa: E402
from modules.mta_common.src.delivery import DeliveryObservation  # noqa: E402
from modules.mta_common.src.enums import (  # noqa: E402
    AssignmentType,
    BudgetUsagePolicy,
    FieldAvailability,
    Provider,
)
from modules.mta_common.src.episode import CampaignEpisode  # noqa: E402
from modules.mta_common.src.outcome import OutcomeObservation  # noqa: E402
from modules.mta_common.src.reporting_scope import ReportingScope  # noqa: E402
from modules.mta_common.src.touchpoint import (  # noqa: E402
    Touchpoint,
    TouchpointFieldAvailability,
)
from modules.mta_standard.src.mta_sim_research_adapter import (  # noqa: E402
    load_mta_sim_research_snapshot,
)
from modules.mta_strategy_evaluation.adapters.asin_gmv_nn_adapter import (  # noqa: E402
    ContributedModelError,
    DEFAULT_NETWORK,
    MINIMUM_PANEL_ROWS,
    contributed_model_report,
)
from modules.mta_strategy_evaluation.src.evaluation_episode import (  # noqa: E402
    GroundTruthScore,
    StrategyEvaluationEpisode,
    check_contract,
    run_evaluation_layers,
)
from modules.mta_strategy_evaluation.src.strategy_output import (  # noqa: E402
    StrategyOutput,
)
from modules.mta_strategy_evaluation.src.strategy_projection import (  # noqa: E402
    CAMPAIGN_STRATEGY_ARTIFACT,
    UNRECORDED_ADVERTISER,
    load_strategy_outputs,
)
from modules.mta_strategy_recommendation.src.episode_bridge import (  # noqa: E402
    campaign_episodes_from_research_snapshot,
)
from modules.mta_strategy_recommendation.src.response_dataset import (  # noqa: E402
    build_campaign_response_dataset,
)


DEFAULT_STRATEGY_DIRECTORY = (
    PROJECT_ROOT / "modules" / "mta_strategy_recommendation" / "outputs"
)
DEFAULT_OUTPUT = MODULE_ROOT / "outputs" / "strategy_evaluation.json"
STRATEGY_REQUEST_PATH = (
    PROJECT_ROOT
    / "modules"
    / "mta_strategy_recommendation"
    / "data"
    / "simulated"
    / "strategy_request.json"
)
NUMPY_REMEDY = "uv sync --extra strategy-evaluation"


def main() -> int:
    """Run the evaluation command, returning one only for no projections."""

    arguments = _parser().parse_args()
    currency = _strategy_currency(STRATEGY_REQUEST_PATH)

    print("Projecting strategies")
    attempts = load_strategy_outputs(
        arguments.strategy_directory,
        currency=currency,
        is_synthetic=True,
    )

    episodes = _load_observed_episodes(
        arguments.strategy_directory, arguments.research_snapshot
    )
    episodes_by_campaign = _episodes_by_campaign(episodes)

    print("Checking conservation")
    projected = [attempt.output for attempt in attempts if attempt.succeeded]
    contract_results = {
        output.strategy_id: check_contract(output) for output in projected
    }

    print("Comparing against baselines")
    strategies = [
        _evaluate_output(
            output,
            contract_result=contract_results[output.strategy_id],
            episodes_by_campaign=episodes_by_campaign,
        )
        for output in projected
    ]

    print("Fitting the contributed model")
    contributed_models: list[dict] = []
    if arguments.fit_contributed_model:
        contributed_models.append(_fit_contributed_model(episodes))

    skipped = [
        {
            "artifact": attempt.artifact,
            "strategy_id": attempt.strategy_id,
            "reasons": [attempt.error or "projection failed without a reason"],
        }
        for attempt in attempts
        if not attempt.succeeded
    ]
    conserved = sum(
        1 for result in contract_results.values() if result.is_conserving
    )
    artifact = {
        "strategies": strategies,
        "contributed_models": contributed_models,
        "summary": {
            "projected": len(projected),
            "conserved": conserved,
            "skipped": skipped,
        },
    }

    print("Writing the artifact")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Wrote {arguments.output} "
        f"({len(projected)} projected, {conserved} conserved, "
        f"{len(skipped)} skipped)."
    )
    return 0 if projected else 1


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Evaluate the project strategy recommendation artifacts."
    )
    parser.add_argument(
        "--strategy-directory",
        type=Path,
        default=DEFAULT_STRATEGY_DIRECTORY,
        help="Directory holding the initializer and optimizer artifacts.",
    )
    parser.add_argument(
        "--research-snapshot",
        type=Path,
        default=None,
        help="Optional MTA-SIM simulation_research.json observation source.",
    )
    parser.add_argument(
        "--fit-contributed-model",
        action="store_true",
        help="Fit and report the contributed budget-to-revenue model.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination for the strategy evaluation artifact.",
    )
    return parser


def _strategy_currency(path: Path) -> str | None:
    """Read the initializer's currency from the project strategy request."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = (document.get("campaign_group") or {}).get("currency")
    currency = str(value).strip() if value is not None else ""
    return currency or None


def _load_observed_episodes(
    strategy_directory: Path, research_snapshot: Path | None
) -> tuple[CampaignEpisode, ...]:
    """Load canonical observations from the selected source."""

    if research_snapshot is not None:
        return campaign_episodes_from_research_snapshot(
            load_mta_sim_research_snapshot(research_snapshot)
        )

    path = strategy_directory / CAMPAIGN_STRATEGY_ARTIFACT
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = document.get("response_observations") or []
    if not isinstance(rows, list):
        return ()
    return tuple(_episode_from_response_row(row) for row in rows)


def _episode_from_response_row(row: Mapping[str, Any]) -> CampaignEpisode:
    """Adapt one optimizer response row to a canonical Campaign episode."""

    campaign_id = str(row["campaign_id"])
    provider = Provider(str(row["provider"]))
    ad_product = str(row["ad_product"])
    report_date = str(row["report_date"])
    scope = ReportingScope(
        marketplace=str(row["marketplace"]),
        advertiser_id=UNRECORDED_ADVERTISER,
        currency=str(row["currency"]),
        report_start_date=report_date,
        report_end_date=report_date,
    )
    availability = TouchpointFieldAvailability(
        placement=FieldAvailability.AVAILABLE,
        creative=FieldAvailability.AVAILABLE,
        interaction_type=FieldAvailability.AVAILABLE,
    )
    touchpoint = Touchpoint(
        provider=provider,
        ad_product=ad_product,
        format="CAMPAIGN_RESPONSE_OBSERVATION",
        placement="UNSPECIFIED",
        creative="UNSPECIFIED",
        interaction_type="CLICK",
        field_availability=availability,
    )
    revenue = float(row.get("total_revenue") or 0.0)
    spend = float(row.get("actual_spend") or 0.0)
    return CampaignEpisode(
        campaign=Campaign(
            campaign_id=campaign_id,
            campaign_name=campaign_id,
            provider=provider,
            ad_product=ad_product,
            status="ACTIVE",
            reporting_scope=scope,
        ),
        budget_constraints=BudgetConstraints(
            campaign_id=campaign_id,
            budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
        ),
        budget_observation=BudgetObservation(
            campaign_id=campaign_id,
            reporting_scope=scope,
            configured_budget=float(row.get("configured_budget") or 0.0),
            actual_spend=spend,
            intervention_id=_optional_text(row.get("intervention_id")),
            baseline_budget=_optional_float(row.get("baseline_budget")),
            budget_delta=_optional_float(row.get("budget_delta")),
            assignment_type=_assignment_type(row.get("assignment_type")),
            randomized=row.get("randomized"),
        ),
        delivery_observations=(
            DeliveryObservation(
                touchpoint=touchpoint,
                reporting_scope=scope,
                cost=spend,
                reported_purchases=0,
                reported_sales=revenue,
                impressions=int(row.get("impressions") or 0),
                clicks=int(row.get("clicks") or 0),
            ),
        ),
        outcome_observations=(
            OutcomeObservation(
                touchpoint=touchpoint,
                reporting_scope=scope,
                total_revenue=revenue,
            ),
        ),
    )


def _optional_text(value: Any) -> str | None:
    """Return a non-empty string, preserving absence."""

    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _optional_float(value: Any) -> float | None:
    """Return an optional numeric artifact field as a float."""

    return None if value is None else float(value)


def _assignment_type(value: Any) -> AssignmentType | None:
    """Return the recorded assignment type, preserving absence."""

    return None if value is None else AssignmentType(str(value))


def _episodes_by_campaign(
    episodes: Iterable[CampaignEpisode],
) -> dict[str, tuple[CampaignEpisode, ...]]:
    """Group episodes by Campaign identifier while preserving input order."""

    grouped: dict[str, list[CampaignEpisode]] = {}
    for episode in episodes:
        grouped.setdefault(episode.campaign.campaign_id, []).append(episode)
    return {key: tuple(value) for key, value in grouped.items()}


def _evaluate_output(
    output: StrategyOutput,
    *,
    contract_result,
    episodes_by_campaign: Mapping[str, tuple[CampaignEpisode, ...]],
) -> dict:
    """Run every available layer for one projected strategy."""

    missing = [
        decision.campaign_id
        for decision in output.campaigns
        if decision.campaign_id not in episodes_by_campaign
    ]
    base = {
        "strategy_id": output.strategy_id,
        "allocation_type": output.allocation_type,
        "decision": output.to_dict(),
        "contract": contract_result.to_dict(),
        "ground_truth": GroundTruthScore().to_dict(),
    }
    if not contract_result.is_conserving:
        base["baseline_comparison"] = {
            "was_run": False,
            "reason": (
                "The strategy did not conserve, so comparing it with a "
                "baseline would not be meaningful."
            ),
        }
        return base
    if missing:
        base["baseline_comparison"] = {
            "was_run": False,
            "reason": (
                "No observation episode exists for every allocated Campaign; "
                f"unobserved Campaigns: {missing}."
            ),
        }
        return base

    selected = tuple(
        episode
        for decision in output.campaigns
        for episode in episodes_by_campaign[decision.campaign_id]
    )
    result = run_evaluation_layers(
        StrategyEvaluationEpisode(strategy_output=output, episodes=selected)
    ).to_dict()
    base["baseline_comparison"] = {
        "was_run": True,
        **(result["baseline_comparison"] or {}),
    }
    base["ground_truth"] = result["ground_truth"]
    return base


def _fit_contributed_model(episodes: tuple[CampaignEpisode, ...]) -> dict:
    """Fit the contributed model or return an actionable unavailable report."""

    if importlib.util.find_spec("numpy") is None:
        return {
            "model_id": "asin_free_gmv_network",
            "contrib_folder": "mlp",
            "available": False,
            "reason": "NumPy is not installed, so the model cannot be fitted.",
            "remedy": NUMPY_REMEDY,
        }
    try:
        return contributed_model_report(
            build_campaign_response_dataset(episodes),
            network=DEFAULT_NETWORK,
            minimum_rows=MINIMUM_PANEL_ROWS,
        )
    except (ContributedModelError, ModuleNotFoundError, ImportError) as error:
        return {
            "model_id": "asin_free_gmv_network",
            "contrib_folder": "mlp",
            "available": False,
            "reason": str(error),
            "remedy": NUMPY_REMEDY,
        }


if __name__ == "__main__":
    raise SystemExit(main())
