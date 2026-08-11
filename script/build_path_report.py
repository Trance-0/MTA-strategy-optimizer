"""Build the aggregated path report from raw touchpoint events.

Turns per-journey events into the anonymous aggregated path contract the
attribution models consume: one row per (marketplace, advertiser, path) with its
user, converted-user, purchase, and revenue totals.

Data flow: touchpoint events CSV -> `path_report_builder.build_aggregated_path_rows`
-> `amc_mta_path_report_raw_sample.csv` -> the Markov and Shapley models.

The Amazon Ads report is read only to infer the report window; none of its
delivery metrics enter the path report.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_attribution.config import (  # noqa: E402
    AMAZON_ADS_REPORT_FILE,
    AMC_REPORT_FILE,
    AMC_TOUCHPOINT_EVENTS_FILE,
    MAX_TOUCHPOINT_GAP_DAYS,
)
from modules.mta_attribution.src.attribution_contract import (  # noqa: E402
    PATH_FIELD_DESCRIPTIONS,
    read_csv,
    write_csv_atomic,
)
from modules.mta_attribution.src.path_report_builder import (  # noqa: E402
    PATH_REPORT_FIELDS,
    build_aggregated_path_rows,
)
from script.validate_data_alignment import (  # noqa: E402
    infer_ads_report_window,
    validate_data_alignment_rows,
)


def build_path_report(
    events_file: Path,
    output_file: Path,
    *,
    amazon_ads_report: Path = AMAZON_ADS_REPORT_FILE,
    max_gap_days: int = MAX_TOUCHPOINT_GAP_DAYS,
) -> Path:
    input_paths = {Path(events_file).resolve(), Path(amazon_ads_report).resolve()}
    if Path(output_file).resolve() in input_paths:
        raise ValueError("path report output must not overwrite an input file")
    event_rows = read_csv(events_file)
    ads_rows = read_csv(amazon_ads_report)
    report_start_date, report_end_date = infer_ads_report_window(ads_rows)
    rows = build_aggregated_path_rows(
        event_rows,
        report_start_date=report_start_date,
        report_end_date=report_end_date,
        max_gap_days=max_gap_days,
    )
    if not rows:
        raise ValueError("AMC event report produced zero valid attribution paths")
    validate_data_alignment_rows(rows, ads_rows)
    write_csv_atomic(output_file, [PATH_FIELD_DESCRIPTIONS, *rows], PATH_REPORT_FIELDS)
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a 14-day contiguous AMC path report.")
    parser.add_argument("--events-file", type=Path, default=AMC_TOUCHPOINT_EVENTS_FILE)
    parser.add_argument(
        "--amazon-ads-report", type=Path, default=AMAZON_ADS_REPORT_FILE
    )
    parser.add_argument("--output-file", type=Path, default=AMC_REPORT_FILE)
    parser.add_argument("--max-gap-days", type=int, default=MAX_TOUCHPOINT_GAP_DAYS)
    parser.add_argument("--report-start-date", help=argparse.SUPPRESS)
    parser.add_argument("--report-end-date", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.report_start_date is not None or args.report_end_date is not None:
        parser.error(
            "explicit report dates are no longer supported; "
            "the window is inferred from --amazon-ads-report"
        )
    return args


def main() -> None:
    args = parse_args()
    output = build_path_report(
        args.events_file,
        args.output_file,
        amazon_ads_report=args.amazon_ads_report,
        max_gap_days=args.max_gap_days,
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
