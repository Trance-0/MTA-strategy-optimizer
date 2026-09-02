"""Assemble allow-listed dashboard resources from repository loaders.

The browser requests one resource per selected route instead of receiving the
whole dashboard on entry. Resources still share the same loader cache and merge
into the same client object, so partitioning delivery does not create another
source of truth.

Results are cached in memory so switching views does not re-read the source.
The Reload control clears the cache, and a completed pipeline stage clears it
too, because a stage that succeeded rewrote what the dashboard reads.

Data flow:
    backend/repository/&#42; -> here -> /api/dashboard/resources/<resource>
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from backend.config import active_mode, source_label
from backend.repository.evaluation import strategy_evaluation
from backend.repository.attribution import (
    attribution_results,
    comparison_summary,
    comparison_touchpoints,
    recommended_attribution,
)
from backend.repository.history import ads_daily, entity_bridge, path_report
from backend.repository.research import (
    simulation_research_core,
    simulation_research_history,
)
from backend.repository.strategy import (
    budget_recommendation,
    campaign_strategy,
    candidate_pool,
    strategy_request,
)

#: Ten minutes. Long enough that a reader moving between views reads one
#: consistent snapshot, short enough that a pipeline run started outside this
#: process appears without a restart.
CACHE_TTL_SECONDS = 600.0

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def cached(key: str, producer: Callable[[], Any]) -> Any:
    """Run `producer` at most once per time-to-live, keyed by loader name."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit is not None and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    # Produced outside the lock: a loader takes hundreds of milliseconds and
    # holding the lock across it would serialise every concurrent reader behind
    # the slowest one. Two requests racing the same cold key both compute it,
    # which costs one duplicate read and keeps the readers independent.
    value = producer()
    with _lock:
        _cache[key] = (now, value)
    return value


def clear_caches() -> None:
    """Drop every cached result so the next read hits the source again."""
    with _lock:
        _cache.clear()


#: One entry per compatibility-snapshot key, in payload order.
LOADERS: dict[str, Callable[[], Any]] = {
    "adsDaily": ads_daily,
    "attributionResults": attribution_results,
    "comparisonTouchpoints": comparison_touchpoints,
    "comparisonSummary": comparison_summary,
    "recommendedAttribution": recommended_attribution,
    "entityBridge": entity_bridge,
    "pathReport": path_report,
    "budgetRecommendation": budget_recommendation,
    "campaignStrategy": campaign_strategy,
    "strategyRequest": strategy_request,
    "candidatePool": candidate_pool,
    "simulationResearch": simulation_research_core,
    "strategyEvaluation": strategy_evaluation,
}


def load_snapshot() -> dict:
    """Every loader's result in one object.

    The keys and their order are the contract `dashboard/src/api/client.js`
    reads and `script/export_dashboard_snapshot.py` writes to
    the compatibility snapshot used by schema validation and Python parity
    tests. Browser delivery is partitioned by `RESOURCE_LOADERS` below.
    """
    payload: dict[str, Any] = {"mode": active_mode(), "source": source_label()}
    for key, loader in LOADERS.items():
        payload[key] = cached(key, loader)
    return payload


def load_research_history() -> dict:
    """Return and cache the observation-heavy research arrays separately."""
    return cached("researchHistory", simulation_research_history)


def _research_fields(*names: str, history: bool = False) -> dict:
    """Return one mergeable `simulationResearch` slice by declared fields."""
    core = cached("simulationResearch", simulation_research_core)
    observations = load_research_history() if history else {}
    combined = {**core, **observations}
    return {"simulationResearch": {name: combined.get(name, []) for name in names}}


def _shell_resource() -> dict:
    """Return small deployment and report context used by every route."""
    summary = cached("comparisonSummary", comparison_summary)
    request = cached("strategyRequest", strategy_request)
    first = summary[0] if summary else {}
    group = request.get("campaign_group") or {}
    return {
        "mode": active_mode(),
        "source": source_label(),
        "dashboardContext": {
            "reportStartDate": first.get("report_start_date"),
            "reportEndDate": first.get("report_end_date"),
            "platform": group.get("platform"),
            "marketplace": group.get("marketplace"),
        },
    }


def _resource_fields(*names: str) -> dict:
    """Return declared top-level loader fields with their client key names."""
    return {name: cached(name, LOADERS[name]) for name in names}


#: Public resource names accepted by the HTTP route and static exporter.
#: Values are fixed callables: browser input never becomes a path or query.
RESOURCE_LOADERS: dict[str, Callable[[], dict]] = {
    "shell": _shell_resource,
    "performance": lambda: _resource_fields("adsDaily"),
    "attribution": lambda: _resource_fields(
        "attributionResults",
        "comparisonTouchpoints",
        "comparisonSummary",
        "recommendedAttribution",
    ),
    "budget": lambda: _resource_fields("budgetRecommendation", "strategyRequest"),
    "strategy": lambda: _resource_fields("campaignStrategy"),
    "evaluation": lambda: _resource_fields("strategyEvaluation"),
    "entity-bridge": lambda: _resource_fields("entityBridge"),
    "path-report": lambda: _resource_fields("pathReport"),
    "research-overview": lambda: _research_fields(
        "providers",
        "products",
        "campaigns",
        "adGroups",
        "touchpoints",
        "history",
        "delivery",
        history=True,
    ),
    "research-providers": lambda: _research_fields("providers", "masterObjects"),
    "research-products": lambda: _research_fields("products", "masterObjects"),
    "research-campaigns": lambda: _research_fields(
        "campaigns", "campaignProductLinks", "adGroups", "masterObjects"
    ),
    "research-ad-groups": lambda: _research_fields("adGroups", "masterObjects"),
    "research-touchpoints": lambda: _research_fields("touchpoints", "masterObjects"),
    "research-product-economics": lambda: _research_fields(
        "productEconomics", "masterObjects"
    ),
    "research-generation-configs": lambda: _research_fields(
        "generationConfigs", "masterObjects"
    ),
    "research-campaign-history": lambda: _research_fields(
        "providers",
        "products",
        "campaigns",
        "campaignProductLinks",
        "history",
        "delivery",
        history=True,
    ),
}


def load_resource(resource: str) -> dict:
    """Load one registered dashboard resource or raise `KeyError`."""
    return RESOURCE_LOADERS[resource]()
