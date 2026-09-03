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

import re
import threading
import time
from datetime import date, timedelta
from typing import Any, Callable, Mapping

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
    history_window_bounds,
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


#: An accepted window bound: a calendar date, and nothing else.
#:
#: The bounds reach SQL as bound parameters, so this is not what keeps the
#: query safe. It is what keeps a malformed bound from being compared against
#: a `YYYY-MM-DD` column as a string and silently returning nothing.
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_history_window(start: Any, end: Any) -> dict[str, str | None]:
    """Validate an inclusive `report_date` window, ignoring malformed bounds.

    An unparseable or reversed bound is dropped rather than refused: the window
    is a reading convenience, and a request that asks for a nonsense range is
    better answered with the unbounded history than with an error card in place
    of the view.
    """
    first = str(start).strip() if start not in (None, "") else None
    last = str(end).strip() if end not in (None, "") else None
    if first and not _DATE_PATTERN.match(first):
        first = None
    if last and not _DATE_PATTERN.match(last):
        last = None
    if first and last and first > last:
        first, last = last, first
    return {"start": first, "end": last}


#: How much history a browser is given when it asks for none in particular.
#:
#: A full history is 100,000 rows and above 50 MB of JSON, which is a long wait
#: for a first view of a chart. A quarter is a reading unit rather than a round
#: number, and it is enough of the budget/spend relationship to be worth
#: drawing. It is a default, not a limit: the view reports the range it did not
#: load and can ask for all of it.
DEFAULT_HISTORY_DAYS = 90


def resolve_history_window(start: Any, end: Any) -> dict[str, str | None]:
    """Validate a requested window, or default to the most recent quarter.

    Applied where a browser is served, not inside the loaders: an unbounded
    load means the whole history everywhere else, which is what the static
    exporter and the compatibility snapshot depend on. A request that names
    either bound is honoured as given and never widened to the default.
    """
    bounds = parse_history_window(start, end)
    if bounds["start"] or bounds["end"]:
        return bounds
    observed = load_history_bounds()
    latest = observed.get("earliest") and observed.get("latest")
    if not latest:
        return bounds
    last = date.fromisoformat(observed["latest"])
    first = max(
        date.fromisoformat(observed["earliest"]),
        last - timedelta(days=DEFAULT_HISTORY_DAYS - 1),
    )
    # Already the whole range: reported as unbounded so the view does not
    # describe a complete history as a partial one.
    if first <= date.fromisoformat(observed["earliest"]):
        return bounds
    return {"start": first.isoformat(), "end": observed["latest"]}


def load_research_history(
    progress: Callable[[int, str], None] | None = None,
    window: Mapping[str, Any] | None = None,
) -> dict:
    """Return and cache the observation-heavy research arrays separately.

    Keyed by the requested window as well as by name, so widening a window
    reads the source rather than returning the narrower slice already cached
    under a bare key.
    """
    bounds = parse_history_window(
        (window or {}).get("start"), (window or {}).get("end")
    )
    key = f"researchHistory:{bounds['start'] or ''}:{bounds['end'] or ''}"
    return cached(key, lambda: simulation_research_history(progress, bounds))


def load_history_bounds() -> dict:
    """Return and cache the full observed date range, independent of any window."""
    return cached("researchHistoryBounds", history_window_bounds)


def _research_fields(
    *names: str,
    history: bool = False,
    progress: Callable[[int, str], None] | None = None,
    window: Mapping[str, Any] | None = None,
) -> dict:
    """Return one mergeable `simulationResearch` slice by declared fields.

    A history slice also carries `historyWindow`: the bounds that were applied
    and the full range they were taken from. The view needs both to say what it
    is showing, and a reader cannot infer the range that was excluded from the
    rows that survived it.
    """
    if progress:
        progress(18, "Reading Campaign metadata")
    core = cached("simulationResearch", simulation_research_core)
    if progress:
        progress(34, "Campaign metadata ready")
    observations = load_research_history(progress, window) if history else {}
    combined = {**core, **observations}
    if progress:
        progress(92, "Preparing dashboard history")
    slice_ = {name: combined.get(name, []) for name in names}
    if history:
        bounds = parse_history_window(
            (window or {}).get("start"), (window or {}).get("end")
        )
        observed = load_history_bounds()
        slice_["historyWindow"] = {
            "start": bounds["start"],
            "end": bounds["end"],
            "earliest": observed.get("earliest"),
            "latest": observed.get("latest"),
        }
    return {"simulationResearch": slice_}


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


#: The resources whose payload depends on the requested history window, and the
#: `simulationResearch` fields each one carries. Declared once so the windowed
#: and unwindowed paths cannot drift into returning different fields for the
#: same resource name.
WINDOWED_FIELDS: dict[str, tuple[str, ...]] = {
    "research-overview": (
        "providers",
        "products",
        "campaigns",
        "adGroups",
        "touchpoints",
        "history",
        "delivery",
    ),
    "research-campaign-history": (
        "providers",
        "products",
        "campaigns",
        "campaignProductLinks",
        "history",
        "delivery",
    ),
}

#: Every other resource ignores a window, so one on their URL changes nothing.
WINDOWED_RESOURCES = frozenset(WINDOWED_FIELDS)


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
        *WINDOWED_FIELDS["research-overview"], history=True
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
        *WINDOWED_FIELDS["research-campaign-history"], history=True
    ),
}


def load_resource(resource: str, window: Mapping[str, Any] | None = None) -> dict:
    """Load one registered dashboard resource or raise `KeyError`."""
    if window and resource in WINDOWED_RESOURCES:
        return _windowed_resource(resource, window=window)
    return RESOURCE_LOADERS[resource]()


def _windowed_resource(
    resource: str,
    progress: Callable[[int, str], None] | None = None,
    window: Mapping[str, Any] | None = None,
) -> dict:
    """Load one window-aware resource with its declared fields."""
    return _research_fields(
        *WINDOWED_FIELDS[resource],
        history=True,
        progress=progress,
        window=window,
    )


def load_resource_with_progress(
    resource: str,
    progress: Callable[[int, str], None],
    window: Mapping[str, Any] | None = None,
) -> dict:
    """Load a resource while reporting meaningful server-side milestones."""
    progress(8, "Checking the configured data source")
    if resource in WINDOWED_RESOURCES:
        return _windowed_resource(resource, progress=progress, window=window)
    progress(35, f"Reading {resource.replace('-', ' ')}")
    payload = load_resource(resource)
    progress(92, "Preparing dashboard data")
    return payload
