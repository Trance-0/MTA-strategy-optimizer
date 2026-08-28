"""Run the pinned ZheyuanWu generator and load its output for MTA models.

This adapter is the boundary between the external ``MTA-SIM-dataset``
submodule and the local standardized model layer. It invokes the public
ZheyuanWu pipeline, derives the explicit CPC/CPM mapping from the resolved
simulation configuration, and loads only the path and performance tables into
``MtaSimDataset``. Simulation ground truth remains a separate evaluation-only
artifact and is never attached to the model-facing dataset.

Data flow:
    pinned submodule + caller configuration
      -> ZheyuanWu validated generator
      -> native five-segment CSV tables, or historical four-segment tables
      -> optional ``SimulatorConfig`` legacy adapter
      -> ``MtaSimDataset`` for registered local models
"""

from __future__ import annotations

import importlib
import importlib.util
import csv
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

from .dataloader import MtaSimDataset, load_mta_sim_dataset
from .touchpoint_adapter import SimulatorConfig


SUPPORTED_VARIANTS = ("baseline", "regional")
PATH_REPORT_NAME = "amc_path_report.csv"
PERFORMANCE_REPORT_NAME = "amazon_ads_daily_touchpoint_performance.csv"
GROUND_TRUTH_NAME = "simulation_ground_truth.csv"
MODEL_PATH_REPORT_NAME = "model_input_amc_path_report.csv"
EVALUATION_GROUND_TRUTH_NAME = "model_evaluation_ground_truth.csv"


@dataclass(frozen=True)
class GeneratedMtaSimRun:
    """Describe one generated and adapted MTA-SIM dataset run.

    Attributes:
        manifest: Deterministic manifest returned by the external generator.
        output_directory: Caller-owned directory containing generated files.
        source_path_report: Unmodified generated daily path report.
        path_report: Aggregated single-scope path report used by local models.
        performance_report: Generated Amazon Ads daily performance report.
        source_ground_truth: Unmodified generated ground-truth table.
        ground_truth: Single-scope ground-truth view for evaluation only.
        simulator_config: Explicit billing map retained for legacy input and
            interaction-specific performance annotation.
        dataset: Model-facing dataset that structurally excludes ground truth.
    """

    manifest: dict[str, Any]
    output_directory: Path
    source_path_report: Path
    path_report: Path
    performance_report: Path
    source_ground_truth: Path
    ground_truth: Path
    simulator_config: SimulatorConfig
    dataset: MtaSimDataset


def _zheyuanwu_root(submodule_root: str | Path) -> Path:
    """Return and validate the ZheyuanWu Python project inside the submodule.

    Args:
        submodule_root: Checkout root of the pinned MTA-SIM-dataset submodule.

    Returns:
        Path: Absolute path containing the ``simulations`` package.

    Raises:
        FileNotFoundError: If the submodule was not initialized completely.
    """

    root = Path(submodule_root).resolve()
    project = root / "ZheyuanWu"
    if not (project / "simulations").is_dir():
        raise FileNotFoundError(
            "MTA-SIM submodule is not initialized: expected "
            f"{project / 'simulations'}. Run git submodule update --init --recursive."
        )
    return project


def _import_generator_modules(
    zheyuanwu_root: Path, variant: str
) -> tuple[ModuleType, ModuleType]:
    """Import the selected public generator and its configuration loader.

    Args:
        zheyuanwu_root: Directory containing the external ``simulations`` package.
        variant: ``baseline`` or ``regional``.

    Returns:
        tuple[ModuleType, ModuleType]: Public pipeline and configuration modules.

    Raises:
        ValueError: If the variant is unsupported.
        RuntimeError: If another ``simulations`` package is already imported.
    """

    if variant not in SUPPORTED_VARIANTS:
        raise ValueError(
            f"generator variant must be one of {SUPPORTED_VARIANTS}; got {variant!r}"
        )
    package_root = zheyuanwu_root / "simulations"
    loaded = sys.modules.get("simulations")
    if loaded is not None:
        loaded_file = getattr(loaded, "__file__", None)
        if (
            loaded_file is not None
            and zheyuanwu_root not in Path(loaded_file).resolve().parents
        ):
            raise RuntimeError(
                "a different simulations package is already imported; start a clean "
                "Python process before invoking the pinned MTA-SIM generator"
            )
    if loaded is None:
        specification = importlib.util.spec_from_file_location(
            "simulations",
            package_root / "__init__.py",
            submodule_search_locations=[str(package_root)],
        )
        if specification is None or specification.loader is None:
            raise ImportError(
                f"cannot load external simulations package: {package_root}"
            )
        loaded = importlib.util.module_from_spec(specification)
        sys.modules["simulations"] = loaded
        try:
            specification.loader.exec_module(loaded)
        except Exception:
            sys.modules.pop("simulations", None)
            raise
    package = importlib.import_module(f"simulations.{variant}.mta_dataset")
    configuration = importlib.import_module(
        f"simulations.{variant}.mta_dataset.configuration"
    )
    return package, configuration


def _simulator_config(configuration: object) -> SimulatorConfig:
    """Build the explicit local billing adapter from resolved generator config.

    Args:
        configuration: Baseline or regional configuration returned by ZheyuanWu.

    Returns:
        SimulatorConfig: Advertising-object keys mapped to CPC or CPM.

    Raises:
        ValueError: If a touchpoint does not have exactly one billing basis.
    """

    baseline = getattr(configuration, "baseline_configuration", configuration)
    capabilities_by_provider = {
        capabilities.provider: capabilities
        for capabilities in getattr(baseline, "provider_capabilities", ())
    }
    mapping: dict[str, str] = {}
    for touchpoint in baseline.touchpoints:
        has_cpc = touchpoint.cost_per_click is not None
        has_cpm = touchpoint.cost_per_thousand_impressions is not None
        if has_cpc == has_cpm:
            raise ValueError(
                "each generated touchpoint must define exactly one billing basis: "
                f"{touchpoint.identifier}"
            )
        try:
            key = touchpoint.normalized_key()
        except TypeError:
            interaction = "CLICK" if has_cpc else "IMPRESSION"
            capabilities = capabilities_by_provider.get(touchpoint.provider)
            if capabilities is None:
                key = touchpoint.normalized_key(interaction).rsplit(":", 1)[0]
            else:
                key = touchpoint.normalized_key(interaction, capabilities).rsplit(
                    ":", 1
                )[0]
        mapping[key] = "CPC" if has_cpc else "CPM"
    return SimulatorConfig.from_mapping(mapping)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read one generated UTF-8 CSV while preserving its physical header."""

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"generated CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def _write_csv(
    path: Path, fieldnames: list[str], rows: list[dict[str, object]]
) -> Path:
    """Write one deterministic adapter-owned UTF-8 CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def prepare_single_scope_path_report(
    source_path_report: Path,
    performance_report: Path,
    destination: Path,
) -> Path:
    """Aggregate uploaded daily path windows into one model report scope.

    The source report is read only. Every row contributes to the per-path sum,
    while the accompanying performance report supplies the complete inclusive
    window and confirms the single marketplace and advertiser scope.
    """

    path_fields, path_rows = _read_csv(source_path_report)
    _, performance_rows = _read_csv(performance_report)
    if not path_rows or not performance_rows:
        raise ValueError("generated path and performance tables must not be empty")

    marketplaces = {row["marketplace"].strip() for row in performance_rows}
    advertisers = {row["accountId"].strip() for row in performance_rows}
    report_dates = {row["reportDate"].strip() for row in performance_rows}
    if len(marketplaces) != 1 or len(advertisers) != 1:
        raise ValueError(
            "the local standardized model requires one marketplace and advertiser; "
            f"generated marketplaces={sorted(marketplaces)}, "
            f"advertisers={sorted(advertisers)}"
        )
    report_start = min(report_dates)
    report_end = max(report_dates)
    marketplace = next(iter(marketplaces))
    advertiser = next(iter(advertisers))

    aggregates: dict[str, dict[str, object]] = {}
    for row in path_rows:
        if (
            row["marketplace"].strip() != marketplace
            or row["advertiser_id"].strip() != advertiser
        ):
            raise ValueError(
                "generated path and performance tables do not share one scope"
            )
        path = row["path"].strip()
        aggregate = aggregates.setdefault(
            path,
            {
                "report_start_date": report_start,
                "report_end_date": report_end,
                "marketplace": marketplace,
                "advertiser_id": advertiser,
                "path": path,
                "users": 0,
                "converted_users": 0,
                "purchase_count": 0,
                "revenue": Decimal("0"),
            },
        )
        for field in ("users", "converted_users", "purchase_count"):
            aggregate[field] = int(aggregate[field]) + int(row[field])
        aggregate["revenue"] = Decimal(str(aggregate["revenue"])) + Decimal(
            row["revenue"]
        )

    rows = []
    for path in sorted(aggregates):
        row = dict(aggregates[path])
        row["revenue"] = format(Decimal(str(row["revenue"])), "f")
        rows.append(row)
    return _write_csv(destination, path_fields, rows)


def prepare_single_scope_reports(
    source_path_report: str | Path,
    source_performance_report: str | Path,
    destination_path_report: str | Path,
    destination_performance_report: str | Path,
    *,
    marketplace: str | None = None,
) -> tuple[Path, Path]:
    """Partition uploaded reports and aggregate paths into one model scope.

    A multi-marketplace upload requires an exact marketplace selection. Both
    prepared files use that selection, so attribution can never join one
    market's paths to another market's spend. Source files remain unchanged.
    """
    source_path = Path(source_path_report)
    source_performance = Path(source_performance_report)
    destination_path = Path(destination_path_report)
    destination_performance = Path(destination_performance_report)
    path_fields, path_rows = _read_csv(source_path)
    performance_fields, performance_rows = _read_csv(source_performance)
    if not path_rows or not performance_rows:
        raise ValueError("uploaded path and performance tables must not be empty")

    path_marketplaces = {row["marketplace"].strip() for row in path_rows}
    performance_marketplaces = {row["marketplace"].strip() for row in performance_rows}
    available = path_marketplaces & performance_marketplaces
    selected = "" if marketplace is None else marketplace.strip()
    if not selected:
        if len(available) != 1:
            raise ValueError(
                "uploaded reports contain multiple marketplaces; select one "
                f"from {sorted(available)}"
            )
        selected = next(iter(available))
    if selected not in available:
        raise ValueError(
            f"selected marketplace {selected!r} is absent from both uploaded "
            f"reports; available={sorted(available)}"
        )

    filtered_paths = [
        row for row in path_rows if row["marketplace"].strip() == selected
    ]
    filtered_performance = [
        row for row in performance_rows if row["marketplace"].strip() == selected
    ]
    _write_csv(destination_path, path_fields, filtered_paths)
    _write_csv(
        destination_performance,
        performance_fields,
        filtered_performance,
    )
    prepare_single_scope_path_report(
        destination_path,
        destination_performance,
        destination_path,
    )
    return destination_path, destination_performance


def _prepare_evaluation_ground_truth(
    source_ground_truth: Path,
    destination: Path,
    *,
    report_start_date: str,
    report_end_date: str,
) -> Path:
    """Rewrite only ground-truth scope fields for aggregate model evaluation."""

    fields, source_rows = _read_csv(source_ground_truth)
    rows: list[dict[str, object]] = []
    for source_row in source_rows:
        rows.append(
            {
                **source_row,
                "report_start_date": report_start_date,
                "report_end_date": report_end_date,
            }
        )
    return _write_csv(destination, fields, rows)


def generate_and_load_mta_sim_dataset(
    *,
    submodule_root: str | Path,
    configuration_path: str | Path,
    output_directory: str | Path,
    variant: str = "baseline",
) -> GeneratedMtaSimRun:
    """Generate a validated dataset and adapt it to the local model contract.

    Args:
        submodule_root: Checkout root of the pinned MTA-SIM-dataset submodule.
        configuration_path: Caller-selected ZheyuanWu configuration file.
        output_directory: Caller-owned destination for generated artifacts.
        variant: Generator family, either ``baseline`` or ``regional``.

    Returns:
        GeneratedMtaSimRun: Generated paths, manifest, adapter, and dataset.

    Raises:
        FileNotFoundError: If the submodule or configuration is missing.
        ValueError: If generation or local adaptation violates a data contract.

    Invariants:
        The external generator performs simulation, validation, and storage.
        The local loader receives only path and performance data; ground truth
        remains available solely through the separate evaluation API.
    """

    project_root = _zheyuanwu_root(submodule_root)
    configuration_source = Path(configuration_path).resolve()
    if not configuration_source.is_file():
        raise FileNotFoundError(
            f"MTA-SIM configuration does not exist: {configuration_source}"
        )
    destination = Path(output_directory).resolve()
    generator, configuration_module = _import_generator_modules(project_root, variant)
    resolved_configuration = configuration_module.load_configuration(
        configuration_source
    )
    adapter_config = _simulator_config(resolved_configuration)
    manifest = generator.run_pipeline(
        configuration_path=configuration_source,
        output_directory=destination,
        storage_mode="csv",
    )

    source_path_report = destination / PATH_REPORT_NAME
    performance_report = destination / PERFORMANCE_REPORT_NAME
    source_ground_truth = destination / GROUND_TRUTH_NAME
    path_report = prepare_single_scope_path_report(
        source_path_report,
        performance_report,
        destination / MODEL_PATH_REPORT_NAME,
    )
    dataset = load_mta_sim_dataset(
        path_report,
        performance_report,
        config=adapter_config,
    )
    ground_truth = _prepare_evaluation_ground_truth(
        source_ground_truth,
        destination / EVALUATION_GROUND_TRUTH_NAME,
        report_start_date=dataset.scope.report_start_date,
        report_end_date=dataset.scope.report_end_date,
    )
    return GeneratedMtaSimRun(
        manifest=manifest,
        output_directory=destination,
        source_path_report=source_path_report,
        path_report=path_report,
        performance_report=performance_report,
        source_ground_truth=source_ground_truth,
        ground_truth=ground_truth,
        simulator_config=adapter_config,
        dataset=dataset,
    )
