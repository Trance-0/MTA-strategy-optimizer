"""Load MTA-SIM tables into a model-facing dataset.

Entry point of the standardized layer. Reads MTA-SIM's tables from any
filesystem path, adapts their four-segment keys onto the repository's
five-segment contract, and returns a dataset the models can consume.

Data flow:
    amc_path_report (four-segment paths)
      -> header and scope validation
      -> `SimulatorConfig.adapt_path`      : five-segment paths
      -> `validate_amc_aggregated_row`     : existing path invariants
      -> `MtaSimDataset.path_rows`         : model-facing rows
    amazon_ads_daily_touchpoint_performance
      -> validated and annotated -> `MtaSimDataset.ads_rows` (diagnostic only)

Ground-truth isolation is structural: `MtaSimDataset` has no field that can hold
`simulation_ground_truth`, this module exposes no loader for it, and both
model-facing loaders reject a header carrying a ground-truth column.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from .touchpoint_adapter import (
    SimulatorConfig,
    canonicalize_four_segment_key,
    four_segment_key_from_ads_row,
    to_four_segment,
)

from modules.mta_attribution.src.attribution_contract import (
    NULL,
    PATH_FIELD_DESCRIPTIONS,
    read_csv_normalized,
    safe_float,
    safe_int,
    validate_amc_aggregated_row,
)
from modules.mta_attribution.src.attribution_model_comparison import read_amc_csv_strict


# MTA-SIM's amc_path_report columns are identical to this repository's path
# contract, so the existing strict reader is reused rather than duplicated.
MTA_SIM_PATH_REPORT_FIELDS: tuple[str, ...] = tuple(PATH_FIELD_DESCRIPTIONS)

MTA_SIM_ADS_FIELDS: tuple[str, ...] = (
    "reportDate",
    "marketplace",
    "accountId",
    "adProduct",
    "adType",
    "creativeType",
    "inventoryType",
    "placement",
    "normalizedTouchpoint",
    "currencyCode",
    "impressions",
    "clicks",
    "cost",
    "purchases",
    "sales",
    "unitsSold",
)

# Columns that exist only in simulation_ground_truth. They must never reach a
# model-facing structure, so the loader treats their presence as a contract
# breach rather than as extra data to ignore.
GROUND_TRUTH_ONLY_FIELDS = frozenset(
    {
        "normalized_touchpoint",
        "causal_increment",
        "credit_share",
        "expected_conversion_probability",
    }
)

OUTCOME_TOTAL_FIELDS: tuple[str, ...] = (
    "converted_users",
    "purchase_count",
    "revenue",
)


@dataclass(frozen=True)
class ReportScope:
    """The single reporting scope a standardized dataset may cover.

    Attributes:
        report_start_date: Inclusive ISO start date.
        report_end_date: Inclusive ISO end date.
        marketplace: Advertising marketplace code.
        advertiser_id: AMC advertiser identifier.
    """

    report_start_date: str
    report_end_date: str
    marketplace: str
    advertiser_id: str


@dataclass(frozen=True)
class MtaSimDataset:
    """A model-facing MTA-SIM dataset with no access to ground truth.

    Ground-truth isolation is structural rather than procedural: this container
    has no field that can hold ``simulation_ground_truth``, and the loader that
    builds it accepts no ground-truth path. Reaching ground truth therefore
    requires the separate evaluation API in ``evaluation``.

    Attributes:
        scope: The single report scope covered by every row.
        path_rows: Path-report rows whose ``path`` uses five-segment keys, ready
            for the existing Markov and Shapley implementations.
        ads_rows: Daily performance rows kept for diagnostics and reporting.
            Empty when no performance table was supplied.
        touchpoints: Sorted four-segment keys observed in the path report.
        outcome_totals: Observed totals per outcome, used for conservation
            checks in the standard output contract.
        config: The simulator configuration used to adapt keys.
    """

    scope: ReportScope
    path_rows: tuple[Mapping[str, object], ...]
    ads_rows: tuple[Mapping[str, object], ...]
    touchpoints: tuple[str, ...]
    outcome_totals: Mapping[str, float]
    config: SimulatorConfig

    def five_segment_touchpoints(self) -> tuple[str, ...]:
        """Return the sorted five-segment keys used by the wrapped models.

        Returns:
            tuple[str, ...]: One five-segment key per four-segment touchpoint.
        """
        return tuple(sorted(self.config.to_five_segment(key) for key in self.touchpoints))


def _reject_ground_truth_fields(fieldnames: Sequence[str], source: Path) -> None:
    """Fail when a model-facing table carries ground-truth-only columns.

    Args:
        fieldnames: The header of the table being loaded.
        source: Path used in the error message.

    Raises:
        ValueError: if any ground-truth-only column is present.
    """
    leaked = sorted(GROUND_TRUTH_ONLY_FIELDS.intersection(fieldnames))
    if leaked:
        raise ValueError(
            f"{source}: model-facing table must not contain simulation_ground_truth "
            f"column(s): {leaked}"
        )


def required_text(row: Mapping[str, object], field: str, context: str) -> str:
    """Return a stripped required field value.

    Args:
        row: The row being read.
        field: Field name to read.
        context: Prefix used in the error message.

    Returns:
        str: The stripped value.

    Raises:
        ValueError: if the value is missing or blank.
    """
    raw = row.get(field)
    value = "" if raw is None else str(raw).strip()
    if not value:
        raise ValueError(f"{context}: {field} is required")
    return value


def parse_iso_date(value: str, context: str) -> date:
    """Parse an ISO date with a contract-specific error message.

    Args:
        value: Candidate ISO date text.
        context: Prefix used in the error message.

    Returns:
        date: The parsed date.

    Raises:
        ValueError: if the text is not an ISO date.
    """
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{context}: {value!r} must be an ISO date") from exc


def load_amc_path_report(
    path_report: str | Path, *, config: SimulatorConfig
) -> tuple[ReportScope, tuple[Mapping[str, object], ...], tuple[str, ...]]:
    """Load ``amc_path_report`` from any location and adapt it to five segments.

    Args:
        path_report: Path to the CSV. May sit anywhere on the filesystem; no
            repository-relative default is applied.
        config: Simulator configuration supplying each touchpoint's cost type.

    Returns:
        tuple: ``(scope, path_rows, four_segment_touchpoints)`` where
        ``path_rows`` carry five-segment paths and the touchpoints are sorted
        canonical four-segment keys.

    Raises:
        FileNotFoundError: if the CSV does not exist.
        ValueError: if the header does not match the contract, a ground-truth
            column is present, the rows span more than one report scope, a path
            violates the aggregated-path contract, or a touchpoint has no
            configured cost-type mapping.

    Invariants:
        Every returned path is expressed in five-segment keys and passes the
        existing aggregated-row validation unchanged.
    """
    source = Path(path_report)
    if not source.is_file():
        raise FileNotFoundError(f"amc_path_report not found: {source}")

    fieldnames, _ = read_csv_normalized(source)
    _reject_ground_truth_fields(fieldnames, source)
    raw_rows = read_amc_csv_strict(source)
    if not raw_rows:
        raise ValueError(f"{source}: amc_path_report must contain at least one data row")

    scopes: set[tuple[str, str, str, str]] = set()
    adapted_rows: list[dict] = []
    four_segment_keys: set[str] = set()
    for row_number, row in enumerate(raw_rows, start=2):
        context = f"{source}: amc_path_report row {row_number}"
        start_text = required_text(row, "report_start_date", context)
        end_text = required_text(row, "report_end_date", context)
        start_date = parse_iso_date(start_text, context)
        end_date = parse_iso_date(end_text, context)
        if start_date > end_date:
            raise ValueError(f"{context}: report window is inverted")
        marketplace = required_text(row, "marketplace", context)
        advertiser_id = required_text(row, "advertiser_id", context)
        scopes.add((start_text, end_text, marketplace, advertiser_id))

        raw_path = required_text(row, "path", context)
        for part in raw_path.split(">"):
            token = part.strip()
            if token and token != NULL:
                four_segment_keys.add(canonicalize_four_segment_key(token))
        try:
            adapted_path = config.adapt_path(raw_path)
        except ValueError as exc:
            raise ValueError(f"{context}: {exc}") from exc

        adapted = {**dict(row), "path": adapted_path}
        validate_amc_aggregated_row(adapted, row_number)
        adapted_rows.append(adapted)

    if len(scopes) != 1:
        raise ValueError(
            f"{source}: amc_path_report must contain exactly one report window, "
            f"marketplace, and advertiser_id; found {len(scopes)}"
        )
    config.assert_reversible(four_segment_keys)
    start_text, end_text, marketplace, advertiser_id = next(iter(scopes))
    scope = ReportScope(
        report_start_date=start_text,
        report_end_date=end_text,
        marketplace=marketplace,
        advertiser_id=advertiser_id,
    )
    return scope, tuple(adapted_rows), tuple(sorted(four_segment_keys))


def load_amazon_ads_daily_touchpoint_performance(
    ads_performance: str | Path,
    *,
    config: SimulatorConfig,
    scope: ReportScope | None = None,
) -> tuple[Mapping[str, object], ...]:
    """Load ``amazon_ads_daily_touchpoint_performance`` from any location.

    The table is a diagnostic and reporting input. It is validated and annotated
    here but never enters the model-facing path rows, because the standard
    output contract carries no spend or efficiency column.

    Args:
        ads_performance: Path to the CSV, anywhere on the filesystem.
        config: Simulator configuration supplying each touchpoint's cost type.
        scope: When given, the marketplace and account are checked against the
            path report's scope.

    Returns:
        tuple: Rows annotated with ``touchpoint`` (four-segment),
        ``five_segment_touchpoint``, ``cost_type``, and ``interaction_type``.
        ``unitsSold`` is preserved verbatim as an optional diagnostic.

    Raises:
        FileNotFoundError: if the CSV does not exist.
        ValueError: if the header does not match the contract, a ground-truth
            column is present, a stored ``normalizedTouchpoint`` disagrees with
            the key derived from its component columns, a touchpoint has no
            configured mapping, or the scope disagrees with the path report.
    """
    source = Path(ads_performance)
    if not source.is_file():
        raise FileNotFoundError(
            f"amazon_ads_daily_touchpoint_performance not found: {source}"
        )

    fieldnames, rows = read_csv_normalized(source)
    _reject_ground_truth_fields(fieldnames, source)
    if tuple(fieldnames) != MTA_SIM_ADS_FIELDS:
        raise ValueError(
            f"{source}: amazon_ads_daily_touchpoint_performance header must exactly "
            f"match {list(MTA_SIM_ADS_FIELDS)}; got={fieldnames}"
        )
    if not rows:
        raise ValueError(
            f"{source}: amazon_ads_daily_touchpoint_performance must contain at "
            "least one data row"
        )

    annotated: list[dict] = []
    for row_number, row in enumerate(rows, start=2):
        context = (
            f"{source}: amazon_ads_daily_touchpoint_performance row {row_number}"
        )
        derived = four_segment_key_from_ads_row(row, row_number=row_number)
        stored = canonicalize_four_segment_key(
            required_text(row, "normalizedTouchpoint", context)
        )
        if stored != derived:
            raise ValueError(
                f"{context}: normalizedTouchpoint mismatch; expected {derived}, "
                f"actual {stored}"
            )
        parse_iso_date(required_text(row, "reportDate", context), context)
        cost_type = config.cost_type_for(derived)
        annotated.append(
            {
                **dict(row),
                "touchpoint": derived,
                "five_segment_touchpoint": config.to_five_segment(derived),
                "cost_type": cost_type,
                "interaction_type": config.interaction_type_for(derived),
            }
        )

    if scope is not None:
        marketplaces = {str(row["marketplace"]).strip() for row in annotated}
        accounts = {str(row["accountId"]).strip() for row in annotated}
        if marketplaces != {scope.marketplace} or accounts != {scope.advertiser_id}:
            raise ValueError(
                f"{source}: scope mismatch; amc_path_report="
                f"({scope.marketplace}, {scope.advertiser_id}), performance="
                f"({sorted(marketplaces)}, {sorted(accounts)})"
            )
    return tuple(annotated)


def load_mta_sim_dataset(
    path_report: str | Path,
    ads_performance: str | Path | None = None,
    *,
    config: SimulatorConfig,
) -> MtaSimDataset:
    """Load a complete model-facing MTA-SIM dataset from external paths.

    Args:
        path_report: Path to ``amc_path_report``; required.
        ads_performance: Optional path to
            ``amazon_ads_daily_touchpoint_performance``.
        config: Simulator configuration supplying each touchpoint's cost type.

    Returns:
        MtaSimDataset: The loaded dataset. It has no ground-truth field, and
        this function accepts no ground-truth path, so ground truth cannot
        enter a training feature or the model-facing dataset through it.

    Raises:
        FileNotFoundError: if a named CSV does not exist.
        ValueError: if any table violates its contract or the two tables
            disagree on scope.

    Invariants:
        Both paths may point anywhere on the filesystem; nothing in this
        function depends on the repository's own directory layout.
    """
    scope, path_rows, touchpoints = load_amc_path_report(path_report, config=config)
    ads_rows: tuple[Mapping[str, object], ...] = ()
    if ads_performance is not None:
        ads_rows = load_amazon_ads_daily_touchpoint_performance(
            ads_performance, config=config, scope=scope
        )

    # Revenue is monetary and the two count outcomes are integral, so each is
    # summed with the reader that already governs its type in the path contract.
    totals = {
        outcome: float(
            sum(
                safe_float(row.get(outcome))
                if outcome == "revenue"
                else safe_int(row.get(outcome))
                for row in path_rows
            )
        )
        for outcome in OUTCOME_TOTAL_FIELDS
    }
    return MtaSimDataset(
        scope=scope,
        path_rows=path_rows,
        ads_rows=ads_rows,
        touchpoints=touchpoints,
        outcome_totals=MappingProxyType(totals),
        config=config,
    )


def four_segment_touchpoints_from_path_rows(
    path_rows: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    """Collect sorted four-segment keys from five-segment path rows.

    Args:
        path_rows: Rows whose ``path`` uses five-segment keys.

    Returns:
        tuple[str, ...]: Sorted canonical four-segment keys, excluding ``Null``.

    Raises:
        ValueError: if a path contains a non-canonical five-segment key.
    """
    keys: set[str] = set()
    for row in path_rows:
        for part in str(row.get("path", "")).split(">"):
            token = part.strip()
            if token and token != NULL:
                keys.add(to_four_segment(token))
    return tuple(sorted(keys))
