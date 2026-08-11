"""End-to-end attribution pipeline entry point.

Runs the whole chain in one temporary workspace and publishes only if every
stage succeeds, so a validation failure leaves the previously published
artifacts untouched.

Data flow:
    touchpoint events + Amazon Ads report
      -> `build_path_report`      : aggregated five-segment path report
      -> `run_attribution_models` : Markov + Shapley results, comparison,
                                    recommended attribution
      -> `publish_with_rollback`  : six artifacts moved into place atomically

The report window is inferred from the Ads report rather than configured, so the
published window can never disagree with the delivery data it was derived from.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMC_MTA_ROOT = PROJECT_ROOT / "modules" / "mta_attribution"
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_attribution.config import (  # noqa: E402
    AMAZON_ADS_REPORT_FILE,
    AMC_REPORT_FILE,
    AMC_MTA_ROOT,
    AMC_TOUCHPOINT_EVENTS_FILE,
    ATTRIBUTION_OUTPUT_DIR,
    MARKOV_OUTPUT_FILE,
    MAX_TOUCHPOINT_GAP_DAYS,
    MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE,
    RECOMMENDED_ATTRIBUTION_FILE,
    SHAPLEY_OUTPUT_FILE,
)

from modules.mta_attribution.src.attribution_contract import read_csv  # noqa: E402
from script.build_path_report import build_path_report  # noqa: E402
from script.run_attribution_models import run_attribution_models  # noqa: E402
from script.validate_data_alignment import infer_ads_report_window  # noqa: E402


def publish_with_rollback(
    replacements: list[tuple[Path, Path]], backup_dir: Path
) -> None:
    """Publish a file set and restore the prior set if any replacement fails."""
    destinations = [destination.resolve() for _, destination in replacements]
    if len(destinations) != len(set(destinations)):
        raise ValueError("artifact publication contains duplicate destinations")
    staged_replacements: list[tuple[Path, Path]] = []
    try:
        for source, destination in replacements:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.publish_", dir=destination.parent
            )
            os.close(descriptor)
            staged = Path(temporary_name)
            try:
                shutil.copy2(source, staged)
            except Exception:
                staged.unlink(missing_ok=True)
                raise
            staged_replacements.append((staged, destination))
    except Exception:
        for staged, _ in staged_replacements:
            staged.unlink(missing_ok=True)
        raise

    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: dict[Path, Path | None] = {}
    for index, (_, destination) in enumerate(replacements):
        if destination.exists():
            backup = backup_dir / f"{index:02d}_{destination.name}"
            shutil.copy2(destination, backup)
            backups[destination] = backup
        else:
            backups[destination] = None

    published: list[Path] = []
    try:
        for source, destination in staged_replacements:
            os.replace(source, destination)
            published.append(destination)
    except Exception:
        rollback_errors = []
        for destination in reversed(published):
            backup = backups[destination]
            try:
                if backup is None:
                    destination.unlink(missing_ok=True)
                else:
                    os.replace(backup, destination)
            except Exception as rollback_error:  # pragma: no cover - catastrophic I/O
                rollback_errors.append(f"{destination}: {rollback_error}")
        if rollback_errors:
            raise RuntimeError(
                "artifact publication and rollback both failed: "
                + "; ".join(rollback_errors)
            )
        raise
    finally:
        for staged, _ in staged_replacements:
            staged.unlink(missing_ok=True)


def match_outputs_by_name(
    generated: list[Path], expected: list[Path]
) -> list[tuple[Path, Path]]:
    """Pair generated artifacts with destinations without relying on list order."""
    generated_by_name = {path.name: path for path in generated}
    expected_names = {path.name for path in expected}
    if (
        len(generated_by_name) != len(generated)
        or len(expected_names) != len(expected)
        or set(generated_by_name) != expected_names
    ):
        raise ValueError(
            "generated attribution outputs do not match the expected artifact set"
        )
    return [(generated_by_name[destination.name], destination) for destination in expected]


def _derived_outputs(path_report: Path, output_dir: Path) -> list[Path]:
    return [
        path_report,
        output_dir / MARKOV_OUTPUT_FILE,
        output_dir / SHAPLEY_OUTPUT_FILE,
        output_dir / MODEL_COMPARISON_TOUCHPOINTS_FILE,
        output_dir / MODEL_COMPARISON_SUMMARY_FILE,
        output_dir / RECOMMENDED_ATTRIBUTION_FILE,
    ]


def _validate_artifact_paths(
    events_file: Path,
    amazon_ads_report: Path,
    destinations: list[Path],
) -> None:
    input_paths = {events_file.resolve(), amazon_ads_report.resolve()}
    resolved_destinations = [path.resolve() for path in destinations]
    conflicts = input_paths.intersection(resolved_destinations)
    for destination in resolved_destinations:
        if destination.exists() and any(
            source.exists() and os.path.samefile(source, destination)
            for source in input_paths
        ):
            conflicts.add(destination)
    if conflicts:
        raise ValueError(
            "derived artifact path must not overwrite an input file: "
            f"{sorted(str(path) for path in conflicts)}"
        )
    if len(resolved_destinations) != len(set(resolved_destinations)):
        raise ValueError("derived artifact paths must be unique")
    for index, path in enumerate(resolved_destinations):
        for other in resolved_destinations[index + 1 :]:
            if path in other.parents or other in path.parents:
                raise ValueError("derived artifact paths must not contain one another")


def run_pipeline(
    events_file: Path = AMC_TOUCHPOINT_EVENTS_FILE,
    amazon_ads_report: Path = AMAZON_ADS_REPORT_FILE,
    path_report: Path = AMC_REPORT_FILE,
    output_dir: Path = ATTRIBUTION_OUTPUT_DIR,
) -> list[Path]:
    events_file = Path(events_file)
    amazon_ads_report = Path(amazon_ads_report)
    final_path_report = Path(path_report)
    final_output_dir = Path(output_dir)
    destinations = _derived_outputs(final_path_report, final_output_dir)
    _validate_artifact_paths(events_file, amazon_ads_report, destinations)

    # Build every artifact in one temporary workspace. A validation or model
    # failure therefore leaves the previously published artifacts untouched.
    with tempfile.TemporaryDirectory(prefix=".amc_mta_pipeline_", dir=AMC_MTA_ROOT) as tmp:
        temporary_root = Path(tmp)
        temporary_path_report = temporary_root / final_path_report.name
        temporary_output_dir = temporary_root / "outputs"

        build_path_report(
            events_file=events_file,
            output_file=temporary_path_report,
            amazon_ads_report=amazon_ads_report,
            max_gap_days=MAX_TOUCHPOINT_GAP_DAYS,
        )
        temporary_outputs = run_attribution_models(
            amc_report=temporary_path_report,
            output_dir=temporary_output_dir,
            amazon_ads_report=amazon_ads_report,
            max_touchpoint_gap_days=MAX_TOUCHPOINT_GAP_DAYS,
        )

        final_outputs = [
            final_output_dir / MARKOV_OUTPUT_FILE,
            final_output_dir / SHAPLEY_OUTPUT_FILE,
            final_output_dir / MODEL_COMPARISON_TOUCHPOINTS_FILE,
            final_output_dir / MODEL_COMPARISON_SUMMARY_FILE,
            final_output_dir / RECOMMENDED_ATTRIBUTION_FILE,
        ]
        publish_with_rollback(
            [
                (temporary_path_report, final_path_report),
                *match_outputs_by_name(temporary_outputs, final_outputs),
            ],
            temporary_root / "backups",
        )
    return destinations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build AMC paths and attribution outputs using the Ads date window."
    )
    parser.add_argument("--events-file", type=Path, default=AMC_TOUCHPOINT_EVENTS_FILE)
    parser.add_argument(
        "--amazon-ads-report", type=Path, default=AMAZON_ADS_REPORT_FILE
    )
    parser.add_argument("--path-report", type=Path, default=AMC_REPORT_FILE)
    parser.add_argument("--output-dir", type=Path, default=ATTRIBUTION_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_start, report_end = infer_ads_report_window(read_csv(args.amazon_ads_report))
    outputs = run_pipeline(
        events_file=args.events_file,
        amazon_ads_report=args.amazon_ads_report,
        path_report=args.path_report,
        output_dir=args.output_dir,
    )

    print("AMC MTA pipeline complete.")
    print(
        "Report window: "
        f"{report_start.isoformat()} to {report_end.isoformat()}"
    )
    print("Outputs:")
    for path in outputs:
        print(f"- {path}")


if __name__ == "__main__":
    main()
