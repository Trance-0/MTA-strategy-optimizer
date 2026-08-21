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
`--report-start-date` and `--report-end-date` narrow which Ads rows are read;
the window is still inferred from whatever survives that filter, so the two can
never disagree. A narrowed run also reconciles the two inputs against each
other, because a touchpoint can take delivery inside a window while the
journeys that touch it convert outside it; what that excludes is printed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from datetime import date
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

from modules.mta_attribution.src.attribution_contract import (  # noqa: E402
    read_csv,
    read_csv_normalized,
    write_csv_atomic,
)
from modules.mta_attribution.src.path_report_builder import (  # noqa: E402
    build_aggregated_path_rows,
)
from modules.mta_attribution.src.touchpoint_key import (  # noqa: E402
    touchpoint_key_from_ads_row,
)
from script.validate_data_alignment import (  # noqa: E402
    infer_ads_report_window,
    touchpoints_from_amc_path,
)
from script.build_path_report import build_path_report  # noqa: E402
from script.run_attribution_models import run_attribution_models  # noqa: E402


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


def _windowed_copy(
    source: Path,
    destination: Path,
    date_field: str,
    report_start_date: date | None,
    report_end_date: date | None,
    subject: str,
) -> Path:
    """Copy a CSV, keeping only rows whose `date_field` is inside the window.

    Returns the original path when no window was requested, so an unnarrowed
    run reads the same files it always did rather than rewritten copies.

    `read_csv_normalized` rather than `read_csv`: the Ads report carries a
    Chinese field-description row directly under the header, and `read_csv`
    drops it. The copy must keep it, or readers downstream see a differently
    shaped file than the one this filtered. A row whose date does not parse --
    that description row, in practice -- is kept for the same reason and left
    for the downstream validator to judge, so a malformed report surfaces as
    itself rather than as an empty window.
    """
    if report_start_date is None and report_end_date is None:
        return source

    fieldnames, rows = read_csv_normalized(source)
    kept = []
    selected = 0
    for row in rows:
        raw = str(row.get(date_field, "")).strip()
        # An event time is a timestamp; its date is the part the window applies
        # to, so the value is truncated at `T` before parsing.
        try:
            parsed = date.fromisoformat(raw.split("T")[0])
        except ValueError:
            kept.append(row)
            continue
        if report_start_date is not None and parsed < report_start_date:
            continue
        if report_end_date is not None and parsed > report_end_date:
            continue
        kept.append(row)
        selected += 1

    if selected == 0:
        raise ValueError(
            f"the requested report window selected no {subject} rows; "
            f"start={report_start_date} end={report_end_date}"
        )

    write_csv_atomic(destination, kept, fieldnames)
    return destination


def _attributable_touchpoints(events_file: Path, ads_rows: list[dict]) -> set[str]:
    """The touchpoints the path report actually carries for these inputs.

    Built with `build_aggregated_path_rows` rather than read off the event rows,
    because those are not the same set: an event can sit inside the window and
    still contribute no path, and the alignment validator compares the Ads
    report against the assembled paths. Reconciling against anything else leaves
    the same mismatch it was meant to resolve.
    """
    report_start_date, report_end_date = infer_ads_report_window(ads_rows)
    rows = build_aggregated_path_rows(
        read_csv(events_file),
        report_start_date=report_start_date,
        report_end_date=report_end_date,
        max_gap_days=MAX_TOUCHPOINT_GAP_DAYS,
    )
    keys: set[str] = set()
    for row in rows:
        keys.update(touchpoints_from_amc_path(row["path"]))
    return keys


def _reconcile_windowed_ads_report(
    amazon_ads_report: Path, events_file: Path, destination: Path
) -> tuple[Path, list[str]]:
    """Drop Ads rows for touchpoints the windowed paths do not carry.

    The alignment validator requires the Ads report and the assembled paths to
    describe exactly the same touchpoint set. Over the full window they do.
    Inside a narrower one they need not: a touchpoint can take delivery every
    day while the journeys that touch it convert outside the window, and the
    sparser the touchpoint the more likely that is -- in the committed reports
    every window under about three weeks has at least one.

    Unmatched delivery is a property of the window the reader chose, not a fault
    in the data, so it is reconciled and named rather than raised. Dropping the
    Ads rows rather than inventing events is the conservative direction: it
    narrows what the run claims to cover instead of attributing outcomes to a
    touchpoint that recorded none. The excluded keys are returned so the caller
    can report them, because a silently narrowed run reads as a complete one.
    """
    fieldnames, rows = read_csv_normalized(amazon_ads_report)
    observed = _attributable_touchpoints(events_file, read_csv(amazon_ads_report))

    kept = []
    excluded: set[str] = set()
    retained: set[str] = set()
    for row in rows:
        try:
            key = touchpoint_key_from_ads_row(row, verify_stored=False)
        except ValueError:
            # The Chinese field-description row, in practice. Kept as-is so the
            # copy stays the same shape as the file it filtered.
            kept.append(row)
            continue
        if key in observed:
            kept.append(row)
            retained.add(key)
        else:
            excluded.add(key)

    if not excluded:
        return amazon_ads_report, []
    if not retained:
        raise ValueError(
            "the requested report window carries no touchpoint with both "
            "delivery and journey events; widen the window"
        )

    write_csv_atomic(destination, kept, fieldnames)
    return destination, sorted(excluded)


def run_pipeline(
    events_file: Path = AMC_TOUCHPOINT_EVENTS_FILE,
    amazon_ads_report: Path = AMAZON_ADS_REPORT_FILE,
    path_report: Path = AMC_REPORT_FILE,
    output_dir: Path = ATTRIBUTION_OUTPUT_DIR,
    *,
    report_start_date: date | None = None,
    report_end_date: date | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[Path]:
    """Build and publish every attribution artifact.

    `progress` receives a line as each stage begins. It defaults to None so a
    caller that imports this function sees no output it did not ask for; the
    command-line entry point passes a printer, which is what lets a caller
    watching stdout -- the dashboard, or a reader in a terminal -- see which
    stage a long run is in rather than only that it is still going.
    """
    report = progress or (lambda _message: None)
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

        # Both inputs are narrowed to the same window, and the copies live in
        # this temporary workspace so a narrowed run never rewrites the
        # committed reports it read from. Filtering the Ads report alone is not
        # enough: `build_path_report` requires every CONVERSION to fall inside
        # the window the Ads report implies, so leaving the events unfiltered
        # fails validation on the events that now sit outside it.
        amazon_ads_report = _windowed_copy(
            amazon_ads_report,
            temporary_root / amazon_ads_report.name,
            "reportDate",
            report_start_date,
            report_end_date,
            "Amazon Ads",
        )
        events_file = _windowed_copy(
            events_file,
            temporary_root / events_file.name,
            "event_time",
            report_start_date,
            report_end_date,
            "touchpoint event",
        )

        # Only under a narrowed window: over the full window the two sets match,
        # and reconciling an unnarrowed run would let a genuine extract mismatch
        # pass as a reconciliation instead of failing validation as it should.
        if report_start_date is not None or report_end_date is not None:
            amazon_ads_report, excluded = _reconcile_windowed_ads_report(
                amazon_ads_report,
                events_file,
                temporary_root / f"reconciled_{amazon_ads_report.name}",
            )
            for touchpoint in excluded:
                report(
                    f"Excluded {touchpoint}: delivery in this window, "
                    "but no journey events inside it."
                )

        report("Building the aggregated path report from touchpoint events.")
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
            progress=report,
        )
        report("Publishing the attribution outputs.")

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
    parser.add_argument(
        "--report-start-date",
        type=date.fromisoformat,
        default=None,
        help=(
            "Keep only Amazon Ads rows on or after this ISO date. The report "
            "window is still inferred from whatever survives the filter."
        ),
    )
    parser.add_argument(
        "--report-end-date",
        type=date.fromisoformat,
        default=None,
        help="Keep only Amazon Ads rows on or before this ISO date.",
    )
    args = parser.parse_args()
    if (
        args.report_start_date is not None
        and args.report_end_date is not None
        and args.report_start_date > args.report_end_date
    ):
        parser.error("--report-start-date must not be after --report-end-date")
    return args


def main() -> None:
    args = parse_args()
    outputs = run_pipeline(
        events_file=args.events_file,
        amazon_ads_report=args.amazon_ads_report,
        path_report=args.path_report,
        output_dir=args.output_dir,
        report_start_date=args.report_start_date,
        report_end_date=args.report_end_date,
        # `flush` because a caller reading this pipe -- the dashboard's stage
        # runner, or a terminal -- should see a stage begin when it begins, not
        # when a block buffer happens to fill.
        progress=lambda message: print(message, flush=True),
    )
    # Read the window back from the published path report, not from the input
    # Ads report: under a narrowed run those are different windows, and the one
    # worth printing is the one that was actually published.
    published = read_csv(args.path_report)
    report_start = min(row["report_start_date"] for row in published)
    report_end = max(row["report_end_date"] for row in published)

    print("AMC MTA pipeline complete.")
    print(f"Report window: {report_start} to {report_end}")
    print("Outputs:")
    for path in outputs:
        print(f"- {path}")


if __name__ == "__main__":
    main()
