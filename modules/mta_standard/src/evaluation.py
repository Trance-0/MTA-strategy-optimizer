"""Score models against simulator ground truth.

The only module that opens `simulation_ground_truth`. It returns a `GroundTruth`
that no loader, dataset, or model accepts as input, which is what keeps the
answer out of any training feature.

Data flow:
    simulation_ground_truth -> `load_simulation_ground_truth` -> `GroundTruth`
    model + dataset         -> `fit` -> timed `attribute` -> standard rows
    both                    -> `evaluate_standard_output` -> `EvaluationReport`

Metrics per outcome: credit-share MAE and RMSE, total variation distance,
Spearman rho, top-k overlap, and conservation error, plus one runtime per model.

Model and ground-truth touchpoints are aligned on their union with a missing
touchpoint scored as zero, so omitting a touchpoint is penalised rather than
silently excused.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from modules.mta_attribution.src.attribution_contract import read_csv_normalized
from modules.mta_attribution.src.attribution_model_comparison import spearman_rho
from modules.mta_attribution.src.attribution_model_interface import MtaAttributionModel

from .dataloader import MtaSimDataset, ReportScope, parse_iso_date, required_text
from .output_contract import (
    SUPPORTED_OUTCOMES,
    StandardAttributionRow,
    validate_standard_output,
)
from .touchpoint_adapter import canonicalize_four_segment_key


MTA_SIM_GROUND_TRUTH_FIELDS: tuple[str, ...] = (
    "report_start_date",
    "report_end_date",
    "marketplace",
    "path",
    "normalized_touchpoint",
    "causal_increment",
    "credit_share",
    "expected_conversion_probability",
)

DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class GroundTruth:
    """Simulator credit shares, reachable only through this evaluation module.

    MTA-SIM publishes ground truth at the path × touchpoint grain and does not
    state whether ``credit_share`` is normalised per path or per report. This
    loader therefore applies one deterministic rule in both cases: sum
    ``credit_share`` per touchpoint, then divide by the sum over touchpoints.
    When the table already holds one normalised row per touchpoint, that rule
    is the identity.

    Attributes:
        report_start_date: Inclusive ISO start date.
        report_end_date: Inclusive ISO end date.
        marketplace: Advertising marketplace code.
        credit_share: Normalised share per canonical four-segment touchpoint.
        causal_increment: Summed removal increment per touchpoint, kept for
            reporting; it is never normalised.
        row_count: Number of ground-truth rows read.
    """

    report_start_date: str
    report_end_date: str
    marketplace: str
    credit_share: Mapping[str, float]
    causal_increment: Mapping[str, float]
    row_count: int

    @property
    def touchpoints(self) -> tuple[str, ...]:
        """Return the sorted four-segment touchpoints covered by ground truth.

        Returns:
            tuple[str, ...]: Sorted canonical four-segment keys.
        """
        return tuple(sorted(self.credit_share))


@dataclass(frozen=True)
class EvaluationMetrics:
    """Comparison of one model's shares against ground truth for one outcome.

    Attributes:
        outcome: The evaluated outcome.
        touchpoint_count: Size of the aligned touchpoint index.
        credit_share_mae: Mean absolute error of credit shares.
        credit_share_rmse: Root mean squared error of credit shares.
        total_variation_distance: Half the L1 distance between share vectors.
        spearman_rho: Rank correlation, or ``None`` when undefined.
        top_k_overlap: Overlap rate of the top-k touchpoints.
        top_k: The ``k`` actually used, capped by the touchpoint count.
        conservation_error: Absolute deviation of the model's share sum from
            its required total (1.0, or 0.0 for a zero observed outcome).
    """

    outcome: str
    touchpoint_count: int
    credit_share_mae: float
    credit_share_rmse: float
    total_variation_distance: float
    spearman_rho: float | None
    top_k_overlap: float
    top_k: int
    conservation_error: float


@dataclass(frozen=True)
class EvaluationReport:
    """The full evaluation of one model against ground truth.

    Attributes:
        model_id: Evaluated model identifier.
        model_version: Evaluated model version.
        scope: Report scope of the evaluated dataset.
        runtime_seconds: Wall-clock duration of the model's ``attribute`` call.
        metrics: One :class:`EvaluationMetrics` per outcome.
        missing_in_model: Ground-truth touchpoints the model did not report.
        missing_in_ground_truth: Model touchpoints absent from ground truth.
    """

    model_id: str
    model_version: str
    scope: ReportScope
    runtime_seconds: float
    metrics: Mapping[str, EvaluationMetrics]
    missing_in_model: tuple[str, ...]
    missing_in_ground_truth: tuple[str, ...]


def load_simulation_ground_truth(
    ground_truth: str | Path, *, scope: ReportScope | None = None
) -> GroundTruth:
    """Load ``simulation_ground_truth`` for evaluation only.

    This is the single entry point for the ground-truth table. It returns a
    :class:`GroundTruth`, which no loader, dataset, or model accepts, so a
    ground-truth value cannot reach a training feature by way of this API.

    Args:
        ground_truth: Path to the CSV, anywhere on the filesystem.
        scope: When given, the ground truth must cover exactly this report
            window and marketplace.

    Returns:
        GroundTruth: Normalised credit shares per four-segment touchpoint.

    Raises:
        FileNotFoundError: if the CSV does not exist.
        ValueError: if the header does not match the contract, the table is
            empty, a share is not a finite non-negative number, the shares sum
            to zero, the table spans more than one scope, or the scope
            disagrees with the supplied dataset scope.
    """
    source = Path(ground_truth)
    if not source.is_file():
        raise FileNotFoundError(f"simulation_ground_truth not found: {source}")

    fieldnames, rows = read_csv_normalized(source)
    if tuple(fieldnames) != MTA_SIM_GROUND_TRUTH_FIELDS:
        raise ValueError(
            f"{source}: simulation_ground_truth header must exactly match "
            f"{list(MTA_SIM_GROUND_TRUTH_FIELDS)}; got={fieldnames}"
        )
    if not rows:
        raise ValueError(f"{source}: simulation_ground_truth must contain a data row")

    scopes: set[tuple[str, str, str]] = set()
    shares: dict[str, float] = {}
    increments: dict[str, float] = {}
    for row_number, row in enumerate(rows, start=2):
        context = f"{source}: simulation_ground_truth row {row_number}"
        start_text = required_text(row, "report_start_date", context)
        end_text = required_text(row, "report_end_date", context)
        parse_iso_date(start_text, context)
        parse_iso_date(end_text, context)
        marketplace = required_text(row, "marketplace", context)
        scopes.add((start_text, end_text, marketplace))

        touchpoint = canonicalize_four_segment_key(
            required_text(row, "normalized_touchpoint", context)
        )
        share = _finite_number(row.get("credit_share"), f"{context}: credit_share")
        if share < 0:
            raise ValueError(f"{context}: credit_share must be non-negative")
        increment = _finite_number(
            row.get("causal_increment"), f"{context}: causal_increment"
        )
        shares[touchpoint] = shares.get(touchpoint, 0.0) + share
        increments[touchpoint] = increments.get(touchpoint, 0.0) + increment

    if len(scopes) != 1:
        raise ValueError(
            f"{source}: simulation_ground_truth must cover exactly one report window "
            f"and marketplace; found {len(scopes)}"
        )
    total = math.fsum(shares.values())
    if total <= 0:
        raise ValueError(f"{source}: simulation_ground_truth credit shares sum to zero")

    start_text, end_text, marketplace = next(iter(scopes))
    if scope is not None and (
        start_text != scope.report_start_date
        or end_text != scope.report_end_date
        or marketplace != scope.marketplace
    ):
        raise ValueError(
            f"{source}: ground-truth scope ({start_text}..{end_text}, {marketplace}) "
            f"does not match dataset scope ({scope.report_start_date}.."
            f"{scope.report_end_date}, {scope.marketplace})"
        )

    return GroundTruth(
        report_start_date=start_text,
        report_end_date=end_text,
        marketplace=marketplace,
        credit_share=MappingProxyType(
            {key: value / total for key, value in sorted(shares.items())}
        ),
        causal_increment=MappingProxyType(dict(sorted(increments.items()))),
        row_count=len(rows),
    )


def _finite_number(value: object, context: str) -> float:
    """Coerce a ground-truth numeric field.

    Args:
        value: The candidate number.
        context: Prefix used in the error message.

    Returns:
        float: The coerced value.

    Raises:
        ValueError: if the value is missing, non-numeric, or not finite.
    """
    if value in (None, "") or not str(value).strip():
        raise ValueError(f"{context} is required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric; got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{context} must be finite; got {value!r}")
    return number


def _top_k_overlap(
    left: Mapping[str, float], right: Mapping[str, float], k: int
) -> float:
    """Return the overlap rate of the two highest-scoring touchpoint sets.

    Ties are broken by touchpoint name so the result is deterministic.

    Args:
        left: Model shares by touchpoint.
        right: Ground-truth shares by touchpoint.
        k: Number of leading touchpoints to compare.

    Returns:
        float: ``|top_k(left) ∩ top_k(right)| / k``, or 0.0 when ``k`` is zero.
    """
    if k <= 0:
        return 0.0
    top_left = set(sorted(left, key=lambda key: (-left[key], key))[:k])
    top_right = set(sorted(right, key=lambda key: (-right[key], key))[:k])
    return len(top_left & top_right) / k


def evaluate_standard_output(
    rows: Sequence[StandardAttributionRow],
    dataset: MtaSimDataset,
    ground_truth: GroundTruth,
    *,
    runtime_seconds: float = 0.0,
    top_k: int = DEFAULT_TOP_K,
) -> EvaluationReport:
    """Compare validated standard output against ground truth.

    Args:
        rows: Standard rows from exactly one model version.
        dataset: The dataset the rows were produced from.
        ground_truth: Loaded ground truth for the same scope.
        runtime_seconds: Measured attribution runtime to record.
        top_k: Number of leading touchpoints compared; capped by the aligned
            touchpoint count.

    Returns:
        EvaluationReport: Metrics for every outcome.

    Raises:
        ValueError: if the rows fail the standard output contract, come from
            more than one model version, or the scopes disagree.

    Invariants:
        Model and ground-truth touchpoints are aligned on their union, with an
        absent touchpoint scored as zero share, so a model that omits a
        touchpoint is penalised rather than silently excused.
    """
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    validate_standard_output(rows, outcome_totals=dataset.outcome_totals)

    models = {(row.model_id, row.model_version) for row in rows}
    if len(models) != 1:
        raise ValueError(f"evaluation requires exactly one model version; got {sorted(models)}")
    model_id, model_version = next(iter(models))

    if (
        ground_truth.report_start_date != dataset.scope.report_start_date
        or ground_truth.report_end_date != dataset.scope.report_end_date
        or ground_truth.marketplace != dataset.scope.marketplace
    ):
        raise ValueError("ground-truth scope does not match the dataset scope")

    model_keys = {row.touchpoint for row in rows}
    truth_keys = set(ground_truth.credit_share)
    index = sorted(model_keys | truth_keys)
    truth_vector = {key: ground_truth.credit_share.get(key, 0.0) for key in index}

    metrics: dict[str, EvaluationMetrics] = {}
    for outcome in SUPPORTED_OUTCOMES:
        outcome_rows = {
            row.touchpoint: row.attribution_share
            for row in rows
            if row.outcome == outcome
        }
        model_vector = {key: outcome_rows.get(key, 0.0) for key in index}
        deviations = [
            model_vector[key] - truth_vector[key] for key in index
        ]
        count = len(index)
        mae = math.fsum(abs(value) for value in deviations) / count
        rmse = math.sqrt(math.fsum(value * value for value in deviations) / count)
        tvd = 0.5 * math.fsum(abs(value) for value in deviations)
        expected_total = 0.0 if dataset.outcome_totals[outcome] == 0 else 1.0
        effective_k = min(top_k, count)
        metrics[outcome] = EvaluationMetrics(
            outcome=outcome,
            touchpoint_count=count,
            credit_share_mae=mae,
            credit_share_rmse=rmse,
            total_variation_distance=tvd,
            spearman_rho=spearman_rho(model_vector, truth_vector),
            top_k_overlap=_top_k_overlap(model_vector, truth_vector, effective_k),
            top_k=effective_k,
            conservation_error=abs(
                math.fsum(model_vector.values()) - expected_total
            ),
        )

    return EvaluationReport(
        model_id=model_id,
        model_version=model_version,
        scope=dataset.scope,
        runtime_seconds=runtime_seconds,
        metrics=MappingProxyType(metrics),
        missing_in_model=tuple(sorted(truth_keys - model_keys)),
        missing_in_ground_truth=tuple(sorted(model_keys - truth_keys)),
    )


def evaluate_model(
    model: MtaAttributionModel,
    dataset: MtaSimDataset,
    ground_truth: GroundTruth,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> EvaluationReport:
    """Fit, run, time, and evaluate one model through the common interface.

    Args:
        model: Any model implementing :class:`MtaAttributionModel`.
        dataset: The model-facing dataset.
        ground_truth: Loaded ground truth for the same scope.
        top_k: Number of leading touchpoints compared.

    Returns:
        EvaluationReport: Metrics for every outcome, including the measured
        runtime of the ``attribute`` call.

    Invariants:
        Ground truth is passed to the evaluator only, never to ``fit`` or
        ``attribute``, so no model can observe it.
    """
    model.fit(dataset)
    started = time.perf_counter()
    rows = model.attribute(dataset)
    runtime_seconds = time.perf_counter() - started
    return evaluate_standard_output(
        rows,
        dataset,
        ground_truth,
        runtime_seconds=runtime_seconds,
        top_k=top_k,
    )


def compare_models(
    models: Sequence[MtaAttributionModel],
    dataset: MtaSimDataset,
    ground_truth: GroundTruth,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[EvaluationReport]:
    """Evaluate several models on one dataset under identical conditions.

    Args:
        models: Models to compare.
        dataset: The shared model-facing dataset.
        ground_truth: Shared ground truth.
        top_k: Number of leading touchpoints compared.

    Returns:
        list[EvaluationReport]: One report per model, in the given order.
    """
    return [
        evaluate_model(model, dataset, ground_truth, top_k=top_k) for model in models
    ]
