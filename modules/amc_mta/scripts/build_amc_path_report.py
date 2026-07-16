from __future__ import annotations

import argparse
import sys
from pathlib import Path


AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from amc_path_builder import PATH_REPORT_FIELDS, build_aggregated_path_rows  # noqa: E402
from amc_mta_attribution import (  # noqa: E402
    PATH_FIELD_DESCRIPTIONS,
    read_csv,
    write_csv_atomic,
)
from config import (  # noqa: E402
    AMC_REPORT_FILE,
    AMC_TOUCHPOINT_EVENTS_FILE,
    MAX_TOUCHPOINT_GAP_DAYS,
    REPORT_END_DATE,
    REPORT_START_DATE,
)


def build_amc_path_report(
    events_file: Path,
    output_file: Path,
    report_start_date: str = REPORT_START_DATE,
    report_end_date: str = REPORT_END_DATE,
    max_gap_days: int = MAX_TOUCHPOINT_GAP_DAYS,
) -> Path:
    rows = build_aggregated_path_rows(
        read_csv(events_file),
        report_start_date=report_start_date,
        report_end_date=report_end_date,
        max_gap_days=max_gap_days,
    )
    write_csv_atomic(output_file, [PATH_FIELD_DESCRIPTIONS, *rows], PATH_REPORT_FIELDS)
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a 14-day contiguous AMC path report.")
    parser.add_argument("--events-file", type=Path, default=AMC_TOUCHPOINT_EVENTS_FILE)
    parser.add_argument("--output-file", type=Path, default=AMC_REPORT_FILE)
    parser.add_argument("--report-start-date", default=REPORT_START_DATE)
    parser.add_argument("--report-end-date", default=REPORT_END_DATE)
    parser.add_argument("--max-gap-days", type=int, default=MAX_TOUCHPOINT_GAP_DAYS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = build_amc_path_report(
        args.events_file,
        args.output_file,
        args.report_start_date,
        args.report_end_date,
        args.max_gap_days,
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
