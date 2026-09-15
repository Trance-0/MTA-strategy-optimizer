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
import math
from datetime import date
from dataclasses import asdict, replace
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
    recommendation `modules/mta_strategy_recommendation/src/generate_initial_budget.py` writes.
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
    scoped = "campaignId" in body
    if scoped:
        dataset, history_selection = _campaign_history_dataset(body)
        # The automatic preview stays within observed support by default.
        body = dict(body)
        ceiling = max(row.configured_budget for row in dataset)
        body.setdefault("totalBudget", ceiling)
        body.setdefault("maximumBudget", ceiling)
    else:
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
    if scoped:
        from modules.mta_strategy_recommendation.src.response_dataset import CampaignResponseDataset
        from modules.mta_strategy_recommendation.src.response_model import ResponseSupport
        target_id = body["campaignId"]
        target_rows = dataset.for_campaign(target_id)
        target_model = models.get(target_id)
        # Fit a transparent reference pool when the target has no usable curve.
        # Original donor identities remain in returned observations and diagnostics.
        if target_model is None or target_model.diagnostics.support == ResponseSupport.INSUFFICIENT_SUPPORT:
            pooled = CampaignResponseDataset(tuple(replace(row, campaign_id=target_id) for row in dataset))
            target_model = fit_campaign_response_models(pooled).get(target_id)
            if target_model and target_model.diagnostics.support != ResponseSupport.INSUFFICIENT_SUPPORT:
                target_model = replace(target_model, diagnostics=replace(target_model.diagnostics,
                    support=ResponseSupport.POOLED_TRANSFER,
                    pooled_campaign_ids=tuple(history_selection["reference_campaign_ids"])))
        models = {target_id: target_model}
        initial_rows = target_rows or dataset.observations
        initial = _initial_strategy(CampaignResponseDataset(tuple(replace(row, campaign_id=target_id) for row in initial_rows)))
    else:
        initial = _initial_strategy(dataset)
    total_budget = body.get("totalBudget")
    if total_budget in (None, ""):
        total_budget = sum(item["initial_budget"] for item in initial["allocations"])
    else:
        total_budget = float(total_budget)
        if not math.isfinite(total_budget) or total_budget <= 0:
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

    historical_recommendation = None
    if scoped and models[target_id].diagnostics.support == ResponseSupport.INSUFFICIENT_SUPPORT:
        # A single budget level supports an observed baseline, not a response curve.
        eligible = [row for row in (target_rows or dataset.observations)
                    if minimum_budget <= row.configured_budget <= min(total_budget, maximum_budget if maximum_budget is not None else total_budget)]
        if not eligible:
            raise ModelUnavailableError("No observed budget satisfies the requested budget limits.")
        groups = {}
        for row in eligible:
            groups.setdefault(row.configured_budget, []).append(row)
        budget, records = max(groups.items(), key=lambda item: (
            sum(row.total_revenue for row in item[1]) / len(item[1]), -item[0]))
        historical_recommendation = {
            "campaign_id": target_id, "recommended_budget": budget,
            "mean_observed_spend": sum(row.actual_spend for row in records) / len(records),
            "mean_observed_revenue": sum(row.total_revenue for row in records) / len(records),
            "observation_count": len(records),
            "reason": "Valid history lacks enough budget variation for a fitted optimum. This is an observed baseline reference, not predicted uplift.",
        }
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
        "optimized_strategy": ({"is_optimized": False, "recommendation_type": "HISTORICAL_BASELINE",
            "allocations": [], "authorized_budget": total_budget} if historical_recommendation else plan.to_dict()),
        "response_models": response_models_to_dict(models),
        "observation_count": len(dataset),
        **({"history_selection": history_selection, "historical_recommendation": historical_recommendation,
            "campaign_id": body["campaignId"], "marketplace": body["marketplace"],
            "dataset_id": body.get("datasetId"),
            "response_observations": [
                {**{key: getattr(row, key) for key in (
                    "campaign_id", "marketplace", "currency", "report_start_date",
                    "report_end_date", "intervention_id", "configured_budget",
                    "actual_spend", "total_revenue")}, "report_date": row.report_start_date}
                for row in dataset]} if scoped else {}),
    }


def _campaign_history_dataset(body):
    """Select valid own or compatible full-source ordinary historical records."""
    from backend.config import use_database, research_snapshot_path
    from backend.repository.snapshot import cached
    from modules.mta_common.src.enums import Provider
    from modules.mta_strategy_recommendation.src.response_dataset import CampaignResponseDataset, CampaignResponseObservation
    campaign_id, marketplace = body.get("campaignId"), body.get("marketplace")
    mode = body.get("historyMode", "full")
    if not isinstance(campaign_id, str) or not campaign_id.strip() or not isinstance(marketplace, str) or not marketplace.strip():
        raise ModelRequestError("campaignId and marketplace are required for a Campaign preview.")
    if mode not in {"full", "campaign"}:
        raise ModelRequestError("historyMode must be full or campaign.")
    if "datasetId" not in body and use_database():
        from backend.database import sql
        def read():
            # Null ordinary levels represent baseline evidence, never every arm.
            # Aggregate before joining and include account/currency in the join.
            rows = sql("""
                with ordinary as (
                    select run_id, campaign_id, advertiser_id, marketplace, currency,
                           report_date, budget_level,
                           case when count(*) = count(total_revenue) and min(total_revenue) >= 0
                                then sum(total_revenue) else null end as total_revenue
                    from mta_sim_outcome_observation
                    where evaluation_only = false and marketplace = :marketplace
                    group by run_id, campaign_id, advertiser_id, marketplace, currency, report_date, budget_level
                )
                select b.*, o.total_revenue
                from mta_sim_budget_observation b
                left join lateral (
                    select total_revenue from ordinary o
                    where o.run_id = b.run_id and o.campaign_id = b.campaign_id
                      and o.advertiser_id = b.advertiser_id and o.marketplace = b.marketplace
                      and o.currency = b.currency and o.report_date = b.report_date
                      and (o.budget_level is not distinct from b.budget_level
                           or (o.budget_level is null and b.budget_level = 1))
                    order by o.budget_level nulls last limit 1
                ) o on true
                where b.marketplace = :marketplace
                order by b.run_id, b.campaign_id, b.report_date, b.budget_level
            """, {"marketplace": marketplace})
            return rows, sql("select * from mta_sim_campaign order by run_id, campaign_id")
        rows, metadata = cached(f"campaign-history-v2:{marketplace}", read)
    else:
        import json
        from backend.services.datasets import dataset_inputs, research_observation_key
        if "datasetId" in body:
            try:
                research = dataset_inputs(body["datasetId"]).get("research") or {}
            except Exception as error:
                raise ModelUnavailableError("The selected dataset is unavailable or changed.") from error
        else:
            path = research_snapshot_path()
            if path is None:
                raise ModelUnavailableError("This source has no ordinary Campaign budget history.")
            research = json.loads(path.read_text(encoding="utf-8"))
        metadata = [dict(item, run_id=run.get("run_id")) for run in research.get("simulation_runs", []) for item in run.get("campaigns", [])]
        outcomes = {}
        for item in research.get("outcome_observations", []):
            outcomes.setdefault((item.get("run_id"), research_observation_key(item)), []).append(item.get("total_revenue"))
        rows = []
        for budget in research.get("budget_observations", []):
            scope = budget.get("reporting_scope") or {}
            if scope.get("marketplace") != marketplace:
                continue
            key = research_observation_key(budget)
            values = outcomes.get((budget.get("run_id"), key))
            if values is None and key[1] == 1:
                values = outcomes.get((budget.get("run_id"), (key[0], None, *key[2:])))
            revenue = sum(values) if values and all(_valid_history_number(v) for v in values) else None
            rows.append({**budget, **scope, "total_revenue": revenue})
    target = [row for row in rows if row.get("campaign_id") == campaign_id]
    if not target:
        raise ModelUnavailableError("No budget records exist for this Campaign and marketplace.")
    accounts = {(row.get("advertiser_id"), row.get("currency")) for row in target}
    if len(accounts) != 1:
        raise ModelRequestError("Campaign history mixes advertisers or currencies; select an isolated dataset.")
    target_meta = [item for item in metadata if item.get("campaign_id") == campaign_id]
    if not target_meta or any(str(item.get("status", "ACTIVE")).upper() not in {"ACTIVE", "ENABLED"} for item in target_meta):
        raise ModelUnavailableError("The selected Campaign is unknown or inactive.")
    segments = {(item.get("provider"), item.get("ad_product")) for item in target_meta}
    if len(segments) != 1:
        raise ModelRequestError("Campaign history has conflicting provider or ad product metadata.")
    metadata_by_key = {(item.get("run_id"), item.get("campaign_id")): item for item in metadata}
    observations, seen, excluded = [], set(), 0
    for row in rows:
        if (row.get("advertiser_id"), row.get("currency")) not in accounts:
            continue
        if mode == "campaign" and row.get("campaign_id") != campaign_id:
            continue
        meta = metadata_by_key.get((row.get("run_id"), row.get("campaign_id")))
        if meta is None and row.get("run_id") is None:
            candidates = [item for item in metadata if item.get("campaign_id") == row.get("campaign_id")]
            meta = candidates[0] if len(candidates) == 1 else None
        if meta is None or (meta.get("provider"), meta.get("ad_product")) not in segments:
            continue
        if str(meta.get("status", "ACTIVE")).upper() not in {"ACTIVE", "ENABLED"}:
            continue
        start = str(row.get("report_start_date") or row.get("report_date"))
        end = str(row.get("report_end_date") or start)
        values = [row.get(field) for field in ("configured_budget", "actual_spend", "total_revenue")]
        try:
            valid_dates = date.fromisoformat(start) == date.fromisoformat(end)
        except ValueError:
            valid_dates = False
        if not valid_dates or not all(_valid_history_number(value) for value in values):
            excluded += 1
            continue
        identity = (row.get("run_id"), row["campaign_id"], start, end, row.get("budget_level"))
        if identity in seen:
            raise ModelRequestError("Campaign history contains repeated budget-period observations.")
        seen.add(identity)
        observations.append(CampaignResponseObservation(
            campaign_id=row["campaign_id"], marketplace=marketplace, report_start_date=start,
            report_end_date=end, currency=row["currency"], provider=Provider(meta["provider"]),
            ad_product=meta["ad_product"], campaign_status=meta.get("status", "ACTIVE"),
            configured_budget=float(values[0]), actual_spend=float(values[1]), total_revenue=float(values[2]),
            impressions=0, clicks=0, intervention_id=str(identity),
        ))
    if not observations:
        raise ModelUnavailableError("No valid ordinary history matches this selection. Choose Full dataset or supply matching observed budget and outcome records.")
    own = [row for row in observations if row.campaign_id == campaign_id]
    return CampaignResponseDataset(tuple(observations)), {
        "mode": mode, "target_observation_count": len(own),
        "reference_observation_count": len(observations) - len(own),
        "reference_campaign_ids": sorted({row.campaign_id for row in observations if row.campaign_id != campaign_id}),
        "excluded_observation_count": excluded,
    }


def _valid_history_number(value):
    """Missing/invalid observations are filtered without inventing measured zero."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _initial_strategy(dataset: Any) -> dict:
    """The Initial Strategy an optimization is compared against.

    Uses each Campaign's own configured baseline budget when the history
    records one, which is the honest starting point for a Campaign that has
    been running, and splits equally only where no history exists. Mirrors what
    `modules/mta_strategy_recommendation/src/generate_campaign_strategy.py` builds, so the two agree.
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
                "script": "modules/mta_strategy_evaluation/src/evaluate_strategies.py",
                "unavailableReason": None,
            },
        },
    }
