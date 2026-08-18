"""Observed outcomes, kept distinct from organic baseline and incrementality.

Today's outcome fields (`converted_users`, `purchase_count`, `revenue` in the
path report; `purchases`/`sales` in the Ads report) are all total-observed
values. Nothing in the current pipeline separates organic (would have
happened without advertising) from incremental (caused by advertising), and
``docs/en/market-simulation/index.md`` explicitly isolates
`simulation_ground_truth`, the only place such a split is known, as
evaluation-only. ``OutcomeObservation`` therefore keeps `total_units`/
`total_revenue` as the only fields any current adapter can populate, and adds
`expected_organic_*`/`incremental_*` fields that stay ``None`` until a real
incrementality-estimation source exists — this class must never be used to
fabricate an incremental figure from total-observed data.

Data flow: ``legacy_adapters.py`` populates only the `total_*` fields from
today's path-report and Ads-report rows. A future incrementality model would
populate the `expected_organic_*`/`incremental_*` fields and record how in
`incrementality_evidence_source`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .reporting_scope import ReportingScope
from .touchpoint import Touchpoint


@dataclass(frozen=True)
class OutcomeObservation:
    """Total, organic, and incremental outcomes for one Touchpoint.

    Attributes:
        touchpoint: The observed ``Touchpoint``.
        reporting_scope: Account, market, currency, and window this
            observation covers.
        total_units: Total observed unit count, encompassing both organic
            and ad-driven demand. Not itself a claim of ad-causation.
        total_revenue: Total observed revenue, on the same basis.
        expected_organic_units: Estimated units that would have occurred
            without advertising. ``None`` until a real estimation source is
            wired in; never derived here from ``total_units``.
        expected_organic_revenue: Estimated revenue that would have occurred
            without advertising. Same rule as ``expected_organic_units``.
        incremental_units: ``total_units`` attributable to advertising.
            ``None`` until a real estimation source is wired in; never
            assumed equal to ``total_units``.
        incremental_revenue: ``total_revenue`` attributable to advertising.
            Same rule as ``incremental_units``.
        incrementality_evidence_source: Free-text description of what
            produced the incremental figures, required whenever either
            incremental field is populated so a reader can judge the
            evidence behind it.
    """

    touchpoint: Touchpoint
    reporting_scope: ReportingScope
    total_units: int | None = None
    total_revenue: float | None = None
    expected_organic_units: float | None = None
    expected_organic_revenue: float | None = None
    incremental_units: float | None = None
    incremental_revenue: float | None = None
    incrementality_evidence_source: str | None = None

    def __post_init__(self) -> None:
        if self.total_units is not None and self.total_units < 0:
            raise ValueError("total_units must not be negative")
        if self.total_revenue is not None and self.total_revenue < 0:
            raise ValueError("total_revenue must not be negative")
        incremental_given = (
            self.incremental_units is not None or self.incremental_revenue is not None
        )
        if incremental_given and not self.incrementality_evidence_source:
            raise ValueError(
                "incrementality_evidence_source is required when an incremental "
                "field is populated"
            )
