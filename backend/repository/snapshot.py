"""Assemble every loader's result into the one payload the client reads.

`GET /api/dashboard` returns this object whole rather than paginating it. The
whole snapshot is roughly 400 KB of JSON, smaller than the artifacts it was
read from, and sending it once is what lets the six views share one source of
truth instead of each issuing its own request and each seeing a slightly
different moment.

Results are cached in memory so switching views does not re-read the source.
The Reload control clears the cache, and a completed pipeline stage clears it
too, because a stage that succeeded rewrote what the dashboard reads.

Data flow:
    backend/repository/&#42; -> here -> GET /api/dashboard
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
from backend.repository.research import simulation_research
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


#: One entry per snapshot key, in the order the payload presents them.
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
    "simulationResearch": simulation_research,
    "strategyEvaluation": strategy_evaluation,
}


def load_snapshot() -> dict:
    """Every loader's result in one object.

    The keys and their order are the contract `dashboard/src/api/client.js`
    reads and `script/export_dashboard_snapshot.py` writes to
    `data/snapshot.json` for the static build. A key removed here disappears
    from a view without the view knowing why, so the set is asserted by
    `backend/tests/test_snapshot.py`.
    """
    payload: dict[str, Any] = {"mode": active_mode(), "source": source_label()}
    for key, loader in LOADERS.items():
        payload[key] = cached(key, loader)
    return payload
