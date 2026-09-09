"""Project one explicit registered dataset without consulting legacy sources.

Public observations and catalogues are derived solely from validated inputs.
Research joins ordinary outcomes; latent and evaluation-only records never
enter the charts. Completed model results retain their dataset/run provenance.
"""

from __future__ import annotations

import copy

from backend.repository.coercion import project, rename, split_touchpoint
from backend.repository.history import ADS_COLUMN_RENAMES, ADS_FIELDS, PATH_FIELDS
from backend.repository.master_data import derive_master_data
from backend.repository.research import EMPTY_RESEARCH, _flatten_observation
from backend.repository.snapshot import RESOURCE_LOADERS, parse_history_window
from backend.services.datasets import TRUTH_FIELDS, dataset_inputs, get_dataset, research_observation_key


def _observed(value):
    """Remove evaluation-only fields recursively before public serialization."""
    if isinstance(value, dict):
        return {key: _observed(child) for key, child in value.items() if key not in TRUTH_FIELDS}
    if isinstance(value, list):
        return [_observed(child) for child in value]
    return value


def _within(row, bounds, field="report_date"):
    value = row.get(field)
    return bool(value and (not bounds["start"] or value >= bounds["start"]) and (not bounds["end"] or value <= bounds["end"]))


def _observation_key(row):
    return research_observation_key(row)


def _research(inputs, ads, bounds, descriptor):
    result = copy.deepcopy(EMPTY_RESEARCH)
    result.update(derive_master_data(ads, []))
    research = inputs.get("research") or {}
    runs = research.get("simulation_runs") or []
    if runs:
        result["runs"] = [{key: run[key] for key in ("run_id", "seed", "configuration_sha256") if key in run} for run in runs]
        for source, target in (("providers", "providers"), ("products", "products"), ("campaigns", "campaigns"), ("ad_groups", "adGroups"), ("product_economics", "productEconomics"), ("campaign_product_links", "campaignProductLinks")):
            result[target] = [_observed(item) for run in runs for item in run.get(source, [])]
        result["generationConfigs"] = [{key: run.get(key) for key in ("run_id", "seed", "configuration_sha256")} for run in runs]
    # Aggregate ordinary touchpoint/product outcomes once per budget-period.
    # Copying one budget for every outcome would multiply its spend in totals.
    outcomes = {}
    for item in research.get("outcome_observations", []):
        outcomes.setdefault(_observation_key(item), []).append(item)
    history = []
    for item in research.get("budget_observations", []):
        row = _observed(_flatten_observation(item))
        if not _within(row, bounds):
            continue
        attached = outcomes.get(_observation_key(item), [])
        for field in ("total_revenue", "total_units", "contribution_profit"):
            values = [entry.get(field) for entry in attached]
            row[field] = sum(float(value) for value in values) if values and all(value is not None for value in values) else None
        history.append(row)
    result["history"] = history
    result["delivery"] = [_observed(_flatten_observation(item)) for item in research.get("delivery_observations", []) if _within(_flatten_observation(item), bounds)]
    result["touchpointObservations"] = [{"observed": _observed(item["observed"])} for item in research.get("touchpoint_observations", []) if isinstance(item.get("observed"), dict)]
    result["historyWindow"] = {**bounds, "earliest": descriptor["scope"]["start"], "latest": descriptor["scope"]["end"]}
    return result


def _result(dataset_id, stage):
    # Imported lazily to keep the dataset repository independent of queue setup.
    from backend.services.workbench import latest_run
    record = latest_run(dataset_id, stage)
    # Read once so a concurrent completion cannot pair new values with an old ID.
    return (record.get("result", {}), {key: value for key, value in record.items() if key != "result"}) if record else ({}, None)


def load_dataset_resource(dataset_id, resource, start=None, end=None):
    """Return an existing snapshot-shaped resource from explicit private inputs."""
    if resource not in RESOURCE_LOADERS:
        raise KeyError("Unknown resource.")
    descriptor = get_dataset(dataset_id)
    inputs = dataset_inputs(dataset_id)
    bounds = parse_history_window(start, end)
    scope = descriptor["scope"]
    context = {"reportStartDate": scope["start"], "reportEndDate": scope["end"],
               "marketplace": scope["marketplace"], "currency": scope["currency"],
               "advertiserId": scope["advertiserId"], "platform": "AMAZON_ADS"}
    payload = {"dataset": descriptor, "dashboardContext": context}
    if resource == "shell":
        return {**payload, "mode": "registered", "source": descriptor["name"]}
    ads = project(split_touchpoint(rename(inputs["performance"], ADS_COLUMN_RENAMES)), ADS_FIELDS)
    if resource == "performance":
        payload["adsDaily"] = [row for row in ads if _within(row, bounds)]
    elif resource == "path-report":
        payload["pathReport"] = project([
            {**row, "path_length": sum(part.strip() != "Null" for part in row["path"].split(">"))}
            for row in inputs["paths"]
            if (not bounds["start"] or row["report_start_date"] >= bounds["start"])
            and (not bounds["end"] or row["report_end_date"] <= bounds["end"])
        ], PATH_FIELDS)
    elif resource == "entity-bridge":
        payload["entityBridge"] = []
    elif resource.startswith("research-"):
        research = _research(inputs, ads, bounds, descriptor)
        fields = {
            "research-overview": ("providers", "products", "campaigns", "adGroups", "touchpoints", "history", "delivery", "historyWindow"),
            "research-providers": ("providers", "masterObjects"),
            "research-products": ("products", "masterObjects"),
            "research-campaigns": ("campaigns", "campaignProductLinks", "adGroups", "masterObjects"),
            "research-ad-groups": ("adGroups", "masterObjects"),
            "research-touchpoints": ("touchpoints", "touchpointObservations", "masterObjects"),
            "research-product-economics": ("productEconomics", "masterObjects"),
            "research-generation-configs": ("generationConfigs", "masterObjects"),
            "research-campaign-history": ("providers", "products", "campaigns", "campaignProductLinks", "history", "delivery", "historyWindow"),
        }[resource]
        payload["simulationResearch"] = {key: research[key] for key in fields}
    elif resource == "budget":
        payload.update(budgetRecommendation={}, strategyRequest={}, candidatePool=[])
    else:
        stage = {"attribution": "attribution", "strategy": "optimization", "evaluation": "evaluation"}[resource]
        result, record = _result(dataset_id, stage)
        if resource == "attribution":
            payload.update({key: result.get(key, []) for key in ("attributionResults", "comparisonTouchpoints", "comparisonSummary", "recommendedAttribution")})
        else:
            payload["campaignStrategy" if resource == "strategy" else "strategyEvaluation"] = result
        payload["runProvenance"] = {stage: record}
    return payload
