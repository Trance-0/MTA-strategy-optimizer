"""Serve the three Python models over HTTP: attribution, recommendation, evaluation.

Each of the three runs the project's own module code in this process and
returns its result as JSON. They are synchronous and bounded: a caller gets an
answer in one request rather than starting a job and polling for it. The
long-running whole-pipeline commands remain in `backend/services/jobs.py`,
because those rewrite files under `modules/` and take minutes; these compute an
answer and write nothing.

The division between the two is what a reader should hold onto. A job runs the
documented command-line script and publishes artifacts. A model endpoint fits
and answers, leaving the published artifacts exactly as they were, so a caller
can ask "what would this model say" without changing what the dashboard reads.

Three models, three sources:

* Attribution runs any model in `modules.mta_standard.src.model_registry`
  through the standardized `fit`/`attribute` interface.
* Recommendation runs the deterministic budget initializer in
  `modules.mta_strategy_recommendation.src.budget_recommender`, and the fitted
  response-model optimizer in `budget_optimizer` when a research snapshot is
  configured.
* Evaluation scores a model's standard output against simulator ground truth
  using `modules.mta_standard.src.evaluation`.

The evaluation endpoint deserves its caveat stated plainly rather than
discovered: `modules/mta_strategy_evaluation/` is specified in
`docs/en/strategy-evaluation/` but not implemented, so *strategy* evaluation
has nothing to serve. What this endpoint serves is *attribution model*
evaluation against ground truth, which does exist, and it says so when it
cannot do the other thing.

Data flow:
    POST /api/models/&#42; -> here -> modules/&#42;/src -> JSON
"""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from backend.config import (
    ATTRIBUTION_MODULE,
    SIMULATED_DIR,
    simulator_data_directory,
)


class ModelRequestError(ValueError):
    """A request the model layer refuses, with the reason and the remedy."""


class ModelUnavailableError(RuntimeError):
    """A model that is specified but not built, or an input that is absent."""


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def _default_path_report() -> Path:
    """The path report a request that names none is fitted against."""
    directory = simulator_data_directory()
    if directory is not None and (directory / "amc_path_report.csv").is_file():
        return directory / "amc_path_report.csv"
    return SIMULATED_DIR / "amc_mta_path_report_raw_sample.csv"


def _default_ads_report() -> Path | None:
    """The MTA-SIM daily performance report, when one is configured.

    The committed ``amazon_ads_report_sample.csv`` is the dashboard's Amazon
    Ads extract. Its columns deliberately differ from MTA-SIM's stricter
    diagnostic table, and attribution does not consume either table, so it is
    not supplied as a misleading default.
    """
    directory = simulator_data_directory()
    if directory is not None:
        candidate = directory / "amazon_ads_daily_touchpoint_performance.csv"
        if candidate.is_file():
            return candidate
    return None


def _resolve_input(value: Any, default: Path | None) -> Path | None:
    """Resolve a caller-supplied input path, or fall back to the default.

    A caller-supplied path must exist and must be a file. It is deliberately
    not restricted to a directory: the loaders accept a table from anywhere on
    the filesystem, and this service runs behind an authenticated proxy on a
    machine whose operator already chose what to expose. What is refused is a
    path that is not there, so a typo fails immediately and by name.
    """
    if value in (None, ""):
        return default
    path = Path(str(value)).expanduser()
    if not path.is_file():
        raise ModelRequestError(f"No such file: {path}")
    return path


def load_dataset(body: dict | None = None) -> Any:
    """Load the model-facing dataset a request asks for.

    The dataset has no field that can hold ground truth and the loader accepts
    no ground-truth path, so ground truth cannot reach a model through this
    function. Evaluation opens it separately.
    """
    from modules.mta_standard.src.dataloader import load_mta_sim_dataset

    body = body or {}
    path_report = _resolve_input(body.get("pathReport"), _default_path_report())
    ads_report = _resolve_input(body.get("adsReport"), _default_ads_report())
    if path_report is None or not path_report.is_file():
        raise ModelUnavailableError(
            "No path report is available to fit against. Run the attribution "
            "stage, or configure MTA_SIM_DATA_DIR with a generated run."
        )
    return load_mta_sim_dataset(path_report, ads_report)


# ---------------------------------------------------------------------------
# 1. Attribution
# ---------------------------------------------------------------------------


def registered_models() -> list[dict]:
    """Every registered attribution model and what it declares it can do.

    Read from `MODEL_REGISTRY` rather than listed here, so a model added to the
    registry is served without an edit to this file, and a model removed from
    it stops being offered rather than failing when called.
    """
    from modules.mta_standard.src.model_registry import MODEL_REGISTRY

    described = []
    for model_id, model_class in sorted(MODEL_REGISTRY.items()):
        capabilities = model_class.capabilities
        described.append(
            {
                "model_id": model_id,
                "model_version": model_class.model_version,
                "requires_fit": capabilities.requires_fit,
                "supports_persistence": capabilities.supports_persistence,
                "deterministic": capabilities.deterministic,
                "supported_outcomes": list(capabilities.supported_outcomes),
                "grain": capabilities.grain,
            }
        )
    return described


def attribute(model_id: str, body: dict | None = None) -> dict:
    """Fit one registered model and return its standard rows.

    The rows are validated against the standard output contract before they
    are returned, so a caller never receives output the project's own pipeline
    would have rejected.

    Raises:
        ModelRequestError: if `model_id` is not registered, naming the ones
            that are.
    """
    from modules.mta_standard.src.model_registry import build_model
    from modules.mta_standard.src.output_contract import (
        standard_rows_to_dicts,
        validate_standard_output,
    )

    body = body or {}
    try:
        model = build_model(model_id)
    except KeyError as error:
        raise ModelRequestError(str(error)) from None

    dataset = load_dataset(body)
    started = time.perf_counter()
    rows = tuple(model.fit(dataset).attribute(dataset))
    runtime_seconds = time.perf_counter() - started
    validate_standard_output(rows, outcome_totals=dataset.outcome_totals)

    return {
        "model_id": model.model_id,
        "model_version": model.model_version,
        "scope": asdict(dataset.scope),
        "runtime_seconds": runtime_seconds,
        "touchpoint_count": len(dataset.touchpoints),
        "row_count": len(rows),
        "rows": standard_rows_to_dicts(rows),
    }


def compare(model_ids: list[str], body: dict | None = None) -> dict:
    """Run several registered models over one dataset under identical conditions.

    One dataset load rather than one per model, so a difference between two
    results is a difference between the models rather than between two reads.
    """
    from modules.mta_standard.src.model_pipeline import run_registered_models
    from modules.mta_standard.src.output_contract import standard_rows_to_dicts

    if not model_ids:
        raise ModelRequestError("At least one model_id is required.")
    if len(set(model_ids)) != len(model_ids):
        raise ModelRequestError("model_ids must be distinct.")

    dataset = load_dataset(body)
    try:
        runs = run_registered_models(dataset, model_ids)
    except KeyError as error:
        raise ModelRequestError(str(error)) from None

    return {
        "scope": asdict(dataset.scope),
        "runs": {
            model_id: {
                "model_id": run.model_id,
                "row_count": len(run.rows),
                "rows": standard_rows_to_dicts(run.rows),
            }
            for model_id, run in runs.items()
        },
    }


# ---------------------------------------------------------------------------
# 2. Recommendation
# ---------------------------------------------------------------------------


def recommend(body: dict | None = None) -> dict:
    """Produce the deterministic Ad Group count and budget seed.

    This is the initializer, not an optimizer: the allocation is derived from
    historical attribution evidence by a fixed formula, and `is_optimized` is
    false for every run it produces. The optimizer is `optimize()` below and
    needs evidence the initializer does not.

    Inputs default to what the repository already carries -- the strategy
    request, the candidate pool, the published attribution results, and the
    entity bridge -- so a caller can post an empty body and get the same
    recommendation `script/generate_initial_budget.py` writes.
    """
    from modules.mta_strategy_recommendation.src.budget_recommender import (
        BudgetRecommendationError,
        generate_budget_recommendation,
    )

    from backend.repository.attribution import recommended_attribution
    from backend.repository.history import entity_bridge
    from backend.repository.strategy import candidate_pool, strategy_request

    body = body or {}
    request = body.get("request") or strategy_request()
    pool = body.get("candidatePool") or candidate_pool()
    if not request or not pool:
        raise ModelUnavailableError(
            "The budget initializer needs a strategy request and a candidate "
            "pool. Neither was supplied and the configured source carries "
            "neither; run the strategy stage or supply them in the request body."
        )

    attribution_rows = body.get("attributionRows") or recommended_attribution()
    entity_rows = body.get("entityRows") or entity_bridge()

    try:
        return generate_budget_recommendation(
            request, pool, attribution_rows, entity_rows
        )
    except BudgetRecommendationError as error:
        raise ModelRequestError(str(error)) from None


def optimize(body: dict | None = None) -> dict:
    """Fit Campaign response models and solve the constrained allocation.

    Unlike `recommend()`, this needs the same Campaign observed at several
    budget levels: a budget-to-revenue curve cannot be fitted from a single
    reporting window. That evidence comes from an MTA-SIM research snapshot,
    so the endpoint refuses with the remedy rather than fitting a curve through
    one point.

    Attribution is never an input here. It may inform the Initial Strategy this
    result is compared against; it is not an input to the fitted response model
    or to the optimizer.
    """
    from modules.mta_common.src.budget import BudgetConstraints
    from modules.mta_common.src.enums import BudgetUsagePolicy, StrategyObjective
    from modules.mta_standard.src.mta_sim_research_adapter import (
        load_mta_sim_research_snapshot,
    )
    from modules.mta_strategy_recommendation.src.budget_optimizer import (
        BudgetOptimizerError,
        CampaignBudgetRequest,
        optimize_campaign_budgets,
    )
    from modules.mta_strategy_recommendation.src.episode_bridge import (
        campaign_episodes_from_research_snapshot,
    )
    from modules.mta_strategy_recommendation.src.response_dataset import (
        build_campaign_response_dataset,
    )
    from modules.mta_strategy_recommendation.src.response_model import (
        fit_campaign_response_models,
        response_models_to_dict,
    )

    from backend.config import research_snapshot_path

    body = body or {}
    snapshot_path = _resolve_input(
        body.get("researchSnapshot"), research_snapshot_path()
    )
    if snapshot_path is None:
        raise ModelUnavailableError(
            "Fitting a budget response curve needs the same Campaign observed "
            "at several budget levels, which a single reporting window does "
            "not carry. Configure MTA_SIM_DATA_DIR with a research snapshot, "
            "or supply researchSnapshot in the request body."
        )

    snapshot = load_mta_sim_research_snapshot(snapshot_path)
    dataset = build_campaign_response_dataset(
        campaign_episodes_from_research_snapshot(snapshot)
    )
    if not len(dataset):
        raise ModelUnavailableError(
            "No Campaign-period observations were found in the research "
            "snapshot; there is nothing to fit."
        )

    models = fit_campaign_response_models(dataset)
    initial = _initial_strategy(dataset)
    total_budget = body.get("totalBudget")
    if total_budget in (None, ""):
        total_budget = sum(item["initial_budget"] for item in initial["allocations"])
    else:
        total_budget = float(total_budget)
        if total_budget <= 0:
            raise ModelRequestError("totalBudget must be a positive number.")

    policy_name = body.get("budgetUsagePolicy") or BudgetUsagePolicy.SPEND_FULL_BUDGET.value
    try:
        policy = BudgetUsagePolicy(policy_name)
    except ValueError:
        raise ModelRequestError(
            f"budgetUsagePolicy is not a recognized policy: {policy_name}."
        ) from None

    minimum_budget = float(body.get("minimumBudget") or 0.0)
    maximum_budget = body.get("maximumBudget")
    maximum_budget = float(maximum_budget) if maximum_budget not in (None, "") else None
    currency = dataset.observations[0].currency

    requests = [
        CampaignBudgetRequest(
            campaign_id=item["campaign_id"],
            constraints=BudgetConstraints(
                campaign_id=item["campaign_id"],
                budget_usage_policy=policy,
                minimum_daily_budget=minimum_budget,
                maximum_daily_budget=maximum_budget,
            ),
            initial_budget=item["initial_budget"],
            currency=currency,
            is_active=item["is_active"],
            current_budget=item["current_budget"],
        )
        for item in initial["allocations"]
    ]

    try:
        plan = optimize_campaign_budgets(
            requests=requests,
            response_models=models,
            total_budget=total_budget,
            objective=StrategyObjective.MAXIMIZE_REVENUE,
            budget_usage_policy=policy,
        )
    except BudgetOptimizerError as error:
        raise ModelRequestError(str(error)) from None

    return {
        "currency": currency,
        "initial_strategy": initial,
        "optimized_strategy": plan.to_dict(),
        "response_models": response_models_to_dict(models),
        "observation_count": len(dataset),
    }


def _initial_strategy(dataset: Any) -> dict:
    """The Initial Strategy an optimization is compared against.

    Uses each Campaign's own configured baseline budget when the history
    records one, which is the honest starting point for a Campaign that has
    been running, and splits equally only where no history exists. Mirrors what
    `script/generate_campaign_strategy.py` builds, so the two agree.
    """
    by_campaign: dict[str, dict] = {}
    for observation in dataset.observations:
        record = by_campaign.setdefault(
            observation.campaign_id,
            {"campaign_id": observation.campaign_id, "budgets": [], "is_active": True},
        )
        record["budgets"].append(float(observation.configured_budget))

    allocations = []
    for record in by_campaign.values():
        budgets = record["budgets"]
        baseline = sum(budgets) / len(budgets) if budgets else 0.0
        allocations.append(
            {
                "campaign_id": record["campaign_id"],
                "initial_budget": baseline,
                "current_budget": baseline,
                "is_active": record["is_active"],
                "allocation_basis": (
                    "CONFIGURED_BASELINE" if baseline > 0 else "EQUAL_NO_HISTORY"
                ),
            }
        )
    return {"allocations": allocations}


# ---------------------------------------------------------------------------
# 3. Evaluation
# ---------------------------------------------------------------------------


def _default_ground_truth() -> Path | None:
    """The simulator ground-truth table, when a research run supplies one."""
    directory = simulator_data_directory()
    if directory is None:
        return None
    candidate = directory / "simulation_ground_truth.csv"
    return candidate if candidate.is_file() else None


def evaluate(body: dict | None = None) -> dict:
    """Score one or more models' output against simulator ground truth.

    Ground truth is opened here and passed to the evaluator only, never to
    `fit` or `attribute`, so no model can observe the answer it is being
    scored against. That isolation is structural in the module this calls: the
    dataset type has no field that can hold ground truth.

    Raises:
        ModelUnavailableError: when no ground-truth table is configured, which
            is every deployment reading the committed reports. The committed
            samples record what the platform reported, not what actually caused
            each conversion, and ground truth is the second of those. Only a
            generated MTA-SIM run carries it.
    """
    from modules.mta_standard.src.evaluation import (
        compare_models,
        load_simulation_ground_truth,
    )
    from modules.mta_standard.src.model_registry import build_model

    body = body or {}
    top_k_value = body.get("topK")
    if top_k_value in (None, ""):
        top_k_value = 5
    try:
        top_k = int(top_k_value)
    except (TypeError, ValueError):
        raise ModelRequestError("topK must be a positive integer.") from None
    if top_k <= 0:
        raise ModelRequestError("topK must be a positive integer.")

    ground_truth_path = _resolve_input(
        body.get("groundTruth"), _default_ground_truth()
    )
    if ground_truth_path is None:
        raise ModelUnavailableError(
            "Evaluation scores a model against simulator ground truth, which "
            "the committed platform reports do not carry: they record what the "
            "platform reported, not what caused each conversion. Configure "
            "MTA_SIM_DATA_DIR with a generated run that includes "
            "simulation_ground_truth.csv, or supply groundTruth in the request "
            "body."
        )

    model_ids = body.get("modelIds") or ([body["modelId"]] if body.get("modelId") else [])
    if not model_ids:
        raise ModelRequestError(
            "At least one modelId is required. GET /api/models lists the "
            "registered identifiers."
        )

    dataset = load_dataset(body)
    ground_truth = load_simulation_ground_truth(ground_truth_path, scope=dataset.scope)
    try:
        models = [build_model(model_id) for model_id in model_ids]
    except KeyError as error:
        raise ModelRequestError(str(error)) from None

    reports = compare_models(models, dataset, ground_truth, top_k=top_k)
    return {
        "scope": asdict(dataset.scope),
        "reports": [_report_to_dict(report) for report in reports],
    }


def _report_to_dict(report: Any) -> dict:
    """Render one evaluation report as JSON.

    Rendered field by field rather than by a generic conversion, so a field
    added to the report reaches this API only when someone decides it should.
    """
    return {
        "model_id": report.model_id,
        "model_version": report.model_version,
        "scope": asdict(report.scope),
        "runtime_seconds": report.runtime_seconds,
        "metrics": {
            outcome: {
                "outcome": metrics.outcome,
                "touchpoint_count": metrics.touchpoint_count,
                "credit_share_mae": metrics.credit_share_mae,
                "credit_share_rmse": metrics.credit_share_rmse,
                "total_variation_distance": metrics.total_variation_distance,
                "spearman_rho": metrics.spearman_rho,
                "top_k_overlap": metrics.top_k_overlap,
                "top_k": metrics.top_k,
                "conservation_error": metrics.conservation_error,
            }
            for outcome, metrics in report.metrics.items()
        },
        "missing_in_model": list(report.missing_in_model),
        "missing_in_ground_truth": list(report.missing_in_ground_truth),
    }


def catalogue() -> dict:
    """What the three model endpoints can do in this deployment.

    Answers before a caller commits to a request: which attribution models are
    registered, whether the optimizer has evidence to fit against, and whether
    ground truth is present. A capability that depends on configuration is
    reported as configured or not, with the remedy, rather than discovered as a
    failure.
    """
    from backend.config import research_snapshot_path

    ground_truth = _default_ground_truth()
    snapshot = research_snapshot_path()
    return {
        "attribution": {
            "available": True,
            "models": registered_models(),
            "dataset": str(_default_path_report()),
        },
        "recommendation": {
            "available": True,
            "optimizerAvailable": snapshot is not None,
            "researchSnapshot": str(snapshot) if snapshot else None,
            "unavailableReason": (
                None
                if snapshot
                else (
                    "The response-model optimizer needs a research snapshot; "
                    "configure MTA_SIM_DATA_DIR. The deterministic initializer "
                    "at POST /api/models/recommend needs none."
                )
            ),
        },
        "evaluation": {
            "available": ground_truth is not None,
            "groundTruth": str(ground_truth) if ground_truth else None,
            "unavailableReason": (
                None
                if ground_truth
                else (
                    "No simulation_ground_truth.csv is configured. Configure "
                    "MTA_SIM_DATA_DIR with a generated MTA-SIM run."
                )
            ),
            "strategyEvaluation": {
                "available": True,
                "script": "script/evaluate_strategies.py",
                "unavailableReason": None,
            },
        },
    }
