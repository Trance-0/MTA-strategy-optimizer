from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from config import (
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
    REFERENCE_WINDOW_DAYS,
    SHAPLEY_OUTPUT_FILE,
)
from scripts.build_amc_path_report import build_amc_path_report
from scripts.run_amc_attribution import run_amc_attribution


def publish_with_rollback(
    replacements: list[tuple[Path, Path]], backup_dir: Path
) -> None:
    """Publish a file set and restore the prior set if any replacement fails."""
    destinations = [destination.resolve() for _, destination in replacements]
    if len(destinations) != len(set(destinations)):
        raise ValueError("artifact publication contains duplicate destinations")
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
        for source, destination in replacements:
            destination.parent.mkdir(parents=True, exist_ok=True)
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


def main() -> None:
    final_path_report = Path(AMC_REPORT_FILE)
    final_output_dir = Path(ATTRIBUTION_OUTPUT_DIR)
    final_output_dir.mkdir(parents=True, exist_ok=True)

    # Build every artifact in one temporary workspace. A validation or model
    # failure therefore leaves the previously published artifacts untouched.
    with tempfile.TemporaryDirectory(prefix=".amc_mta_pipeline_", dir=AMC_MTA_ROOT) as tmp:
        temporary_root = Path(tmp)
        temporary_path_report = temporary_root / final_path_report.name
        temporary_output_dir = temporary_root / "outputs"

        build_amc_path_report(
            events_file=Path(AMC_TOUCHPOINT_EVENTS_FILE),
            output_file=temporary_path_report,
        )
        temporary_outputs = run_amc_attribution(
            amc_report=temporary_path_report,
            output_dir=temporary_output_dir,
            amazon_ads_report=Path(AMAZON_ADS_REPORT_FILE),
            max_touchpoint_gap_days=MAX_TOUCHPOINT_GAP_DAYS,
            reference_window_days=REFERENCE_WINDOW_DAYS,
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

    print("AMC MTA pipeline complete.")
    print("Outputs:")
    for path in [final_path_report, *final_outputs]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
