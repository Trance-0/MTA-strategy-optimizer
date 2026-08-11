"""The standard attribution row and its four invariants.

Defines the one row shape every model emits, so results from different models are
directly comparable, and validates that a model's output is internally coherent
before anything downstream trusts it.

Invariants enforced: non-negativity, row uniqueness per model/scope/touchpoint/
outcome, share conservation, and outcome conservation.

Data flow: a model's `attribute` -> `list[StandardAttributionRow]`
-> `validate_standard_output` -> the evaluator or a CSV writer.

An outcome whose observed total is zero must have shares summing to zero, not
one, and must carry the `ZERO_OUTCOME_TOTAL` warning. Redistributing credit for
an outcome that never occurred would manufacture attribution from nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from modules.mta_attribution.src.attribution_model_comparison import OUTCOME_FIELDS

from .touchpoint_adapter import canonicalize_four_segment_key


# The standardized contract reports the same three outcomes the existing
# comparison layer already governs, so the outcome vocabulary is imported
# instead of being restated.
SUPPORTED_OUTCOMES: tuple[str, ...] = tuple(OUTCOME_FIELDS)

STANDARD_OUTPUT_FIELDS: tuple[str, ...] = (
    "model_id",
    "model_version",
    "report_start_date",
    "report_end_date",
    "marketplace",
    "touchpoint",
    "outcome",
    "attribution_share",
    "attributed_value",
    "valid",
    "warnings",
)

ZERO_OUTCOME_WARNING = "ZERO_OUTCOME_TOTAL"

_SHARE_TOLERANCE = 1e-6
_RELATIVE_VALUE_TOLERANCE = 1e-9

# Identity of a standard row: one model version may report one value per
# touchpoint and outcome inside one report scope.
_ROW_KEY_FIELDS: tuple[str, ...] = (
    "model_id",
    "model_version",
    "report_start_date",
    "report_end_date",
    "marketplace",
    "touchpoint",
    "outcome",
)
_GROUP_KEY_FIELDS: tuple[str, ...] = (
    "model_id",
    "model_version",
    "report_start_date",
    "report_end_date",
    "marketplace",
    "outcome",
)


@dataclass(frozen=True)
class StandardAttributionRow:
    """One standardized attribution result.

    Attributes:
        model_id: Stable identifier of the producing model.
        model_version: Version of that model's contract and behaviour.
        report_start_date: Inclusive ISO start date of the report scope.
        report_end_date: Inclusive ISO end date of the report scope.
        marketplace: Advertising marketplace code.
        touchpoint: Canonical four-segment MTA-SIM touchpoint key.
        outcome: One of :data:`SUPPORTED_OUTCOMES`.
        attribution_share: Share of the outcome credited to the touchpoint.
        attributed_value: Absolute outcome credited to the touchpoint.
        valid: Whether the producing model considers the row usable.
        warnings: Ordered, de-duplicated warning codes for the row.
    """

    model_id: str
    model_version: str
    report_start_date: str
    report_end_date: str
    marketplace: str
    touchpoint: str
    outcome: str
    attribution_share: float
    attributed_value: float
    valid: bool = True
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        """Render the row in the flat, CSV-ready standard field order.

        Returns:
            dict: One entry per :data:`STANDARD_OUTPUT_FIELDS` name, with
            ``warnings`` joined by ``'|'`` and ``valid`` lowercased, matching
            how the existing comparison outputs encode boolean columns.
        """
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "report_start_date": self.report_start_date,
            "report_end_date": self.report_end_date,
            "marketplace": self.marketplace,
            "touchpoint": self.touchpoint,
            "outcome": self.outcome,
            "attribution_share": self.attribution_share,
            "attributed_value": self.attributed_value,
            "valid": str(self.valid).lower(),
            "warnings": "|".join(self.warnings),
        }


def standard_rows_to_dicts(
    rows: Sequence[StandardAttributionRow],
) -> list[dict]:
    """Render a sequence of standard rows for CSV writing.

    Args:
        rows: The standard rows to render.

    Returns:
        list[dict]: One flat dictionary per row.
    """
    return [row.as_dict() for row in rows]


def _finite_non_negative(value: object, context: str) -> float:
    """Coerce a numeric field and enforce finiteness and non-negativity.

    Args:
        value: The candidate number.
        context: Prefix used in the error message.

    Returns:
        float: The coerced value.

    Raises:
        ValueError: if the value is not numeric, not finite, or negative.
    """
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric; got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{context} must be finite; got {value!r}")
    if number < 0:
        raise ValueError(f"{context} must be non-negative; got {value!r}")
    return number


def validate_standard_output(
    rows: Sequence[StandardAttributionRow],
    *,
    outcome_totals: Mapping[str, float],
    expected_touchpoints: Sequence[str] | None = None,
) -> dict:
    """Validate the standardized output contract.

    Four invariants are enforced, as required of every standardized model:
    non-negativity, row uniqueness, share conservation, and outcome
    conservation.

    Args:
        rows: The standard rows produced by one or more models.
        outcome_totals: Observed totals per outcome for the report scope, as
            carried by :class:`dataloader.MtaSimDataset`.
        expected_touchpoints: When given, every model/outcome group must report
            exactly this set of four-segment touchpoints.

    Returns:
        dict: ``{"row_count", "group_count", "models"}`` describing what passed.

    Raises:
        ValueError: if the rows are empty, a field is malformed, a row identity
            repeats, shares do not sum to one (or to zero for an outcome whose
            observed total is zero), or attributed values do not sum to the
            observed outcome total.

    Invariants:
        Share conservation is checked to an absolute tolerance of 1e-6. Outcome
        conservation additionally allows a relative tolerance of 1e-9 so that
        float summation over many touchpoints cannot fail a correct model.
    """
    if not rows:
        raise ValueError("standard output must contain at least one row")

    missing_totals = sorted(set(SUPPORTED_OUTCOMES) - set(outcome_totals))
    if missing_totals:
        raise ValueError(f"outcome_totals is missing outcome(s): {missing_totals}")

    expected_keys = (
        None
        if expected_touchpoints is None
        else {canonicalize_four_segment_key(key) for key in expected_touchpoints}
    )

    seen: set[tuple] = set()
    groups: dict[tuple, list[StandardAttributionRow]] = {}
    for index, row in enumerate(rows):
        context = f"standard row {index}"
        if not isinstance(row, StandardAttributionRow):
            raise ValueError(f"{context} must be a StandardAttributionRow")
        for name in ("model_id", "model_version", "marketplace"):
            if not str(getattr(row, name)).strip():
                raise ValueError(f"{context}: {name} is required")
        if row.outcome not in SUPPORTED_OUTCOMES:
            raise ValueError(
                f"{context}: outcome must be one of {list(SUPPORTED_OUTCOMES)}; "
                f"got {row.outcome!r}"
            )
        canonical = canonicalize_four_segment_key(row.touchpoint)
        if canonical != row.touchpoint:
            raise ValueError(
                f"{context}: touchpoint must be a canonical four-segment key; "
                f"got {row.touchpoint!r}"
            )
        if not isinstance(row.valid, bool):
            raise ValueError(f"{context}: valid must be a boolean")
        if len(set(row.warnings)) != len(row.warnings):
            raise ValueError(f"{context}: warnings must not repeat")
        _finite_non_negative(row.attribution_share, f"{context}: attribution_share")
        _finite_non_negative(row.attributed_value, f"{context}: attributed_value")

        identity = tuple(getattr(row, name) for name in _ROW_KEY_FIELDS)
        if identity in seen:
            raise ValueError(f"{context}: duplicate standard row identity {identity}")
        seen.add(identity)
        groups.setdefault(
            tuple(getattr(row, name) for name in _GROUP_KEY_FIELDS), []
        ).append(row)

    for group_key, group_rows in sorted(groups.items()):
        outcome = group_key[-1]
        label = f"{group_key[0]}/{group_key[1]} {outcome}"
        total = float(outcome_totals[outcome])
        share_total = math.fsum(row.attribution_share for row in group_rows)
        value_total = math.fsum(row.attributed_value for row in group_rows)

        if expected_keys is not None:
            actual_keys = {row.touchpoint for row in group_rows}
            if actual_keys != expected_keys:
                missing = sorted(expected_keys - actual_keys)
                extra = sorted(actual_keys - expected_keys)
                raise ValueError(
                    f"{label}: touchpoint set differs; missing={missing}, extra={extra}"
                )

        # A zero observed outcome must not be redistributed: an all-zero share
        # vector is the only conserving answer, so 1.0 is rejected here.
        expected_share_total = 0.0 if total == 0 else 1.0
        if not math.isclose(
            share_total, expected_share_total, rel_tol=0, abs_tol=_SHARE_TOLERANCE
        ):
            raise ValueError(
                f"{label}: shares must sum to {expected_share_total}; got {share_total}"
            )

        value_tolerance = max(
            _SHARE_TOLERANCE, abs(total) * _RELATIVE_VALUE_TOLERANCE
        )
        if not math.isclose(value_total, total, rel_tol=0, abs_tol=value_tolerance):
            raise ValueError(
                f"{label}: attributed values must sum to the observed total {total}; "
                f"got {value_total}"
            )
        if total == 0 and any(
            ZERO_OUTCOME_WARNING not in row.warnings for row in group_rows
        ):
            raise ValueError(
                f"{label}: a zero observed outcome requires the "
                f"{ZERO_OUTCOME_WARNING} warning on every row"
            )

    return {
        "row_count": len(rows),
        "group_count": len(groups),
        "models": sorted({(row.model_id, row.model_version) for row in rows}),
    }
