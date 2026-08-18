"""Historical attribution evidence, kept free of any optimization claim.

Adapts today's two attribution-result shapes — ``AttributionResult`` /
``result_rows()``'s 18-column dict in ``mta_attribution``, and the separate
``StandardAttributionRow`` in ``mta_standard`` — into one canonical evidence
type. Deliberately excludes marginal-return, causal-incrementality,
optimal-budget, and product-contribution-profit fields: this class is pure
historical evidence about how much of a past outcome one touchpoint's
attribution share explains, not a claim about what a future budget change
would cause or what it should be. A future optimizer may read
``AttributionEvidence`` as one input among several; it must not read an
optimization target out of this class, because this class does not define
one (there is no `MTA_share * profit` field here or anywhere in this
module).

Data flow: ``legacy_adapters.attribution_evidence_from_standard_row`` and
``legacy_adapters.attribution_evidence_from_attribution_result`` build this
type from the two existing shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .reporting_scope import ReportingScope
from .touchpoint import Touchpoint


@dataclass(frozen=True)
class AttributionEvidence:
    """One touchpoint's attributed share of one outcome, for one model run.

    Attributes:
        model_id: Stable identifier of the producing model.
        model_version: Version of that model's contract and behavior.
        reporting_scope: Account, market, currency, and window the
            attribution ran over.
        touchpoint: The touchpoint this evidence describes.
        outcome: The outcome name, for example ``converted_users``,
            ``purchase_count``, or ``revenue``.
        attribution_share: Share of the outcome credited to the touchpoint,
            in ``[0, 1]``.
        attributed_value: Absolute outcome amount credited to the
            touchpoint.
        valid: Whether the producing model considers the row usable.
        warnings: Ordered, de-duplicated warning codes for the row, for
            example ``ZERO_OUTCOME_TOTAL``.
    """

    model_id: str
    model_version: str
    reporting_scope: ReportingScope
    touchpoint: Touchpoint
    outcome: str
    attribution_share: float
    attributed_value: float
    valid: bool = True
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name in ("model_id", "model_version", "outcome"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if not (0.0 <= self.attribution_share <= 1.0 + 1e-9):
            raise ValueError("attribution_share must be between 0 and 1")
        if self.attributed_value < 0:
            raise ValueError("attributed_value must not be negative")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("warnings must not repeat")
