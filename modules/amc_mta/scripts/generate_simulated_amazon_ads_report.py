from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping, Sequence

AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from amc_mta_attribution import ADS_FIELD_DESCRIPTIONS, write_csv_atomic  # noqa: E402
from config import AMAZON_ADS_REPORT_FILE, REPORT_END_DATE, REPORT_START_DATE  # noqa: E402
from synthetic_event_pipeline import (  # noqa: E402
    ADS_FIELDS,
    derive_amazon_ads_rows,
    generate_synthetic_user_events,
)


FIELDS = ADS_FIELDS
FIELD_DESCRIPTIONS = ADS_FIELD_DESCRIPTIONS


def generate_rows(
    start: date,
    end: date,
    source_rows: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    if start > end:
        raise ValueError("start date must be on or before end date")
    if source_rows is None:
        # The user-event generator needs enough history to form paths. Extending
        # short standalone Ads requests keeps this public helper useful.
        if (end - start).days < 14 and start < date.min + timedelta(days=14):
            raise ValueError("short report window cannot represent 14 days of history")
        source_start = start if (end - start).days >= 14 else start - timedelta(days=14)
        source_rows = generate_synthetic_user_events(source_start, end)
    return derive_amazon_ads_rows(source_rows, start, end)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic Amazon Ads data from synthetic user events."
    )
    parser.add_argument("--output", type=Path, default=AMAZON_ADS_REPORT_FILE)
    parser.add_argument("--start-date", default=REPORT_START_DATE)
    parser.add_argument("--end-date", default=REPORT_END_DATE)
    return parser.parse_args()


def generate_file(output: Path, start: date, end: date) -> None:
    rows = generate_rows(start, end)
    write_csv_atomic(output, [FIELD_DESCRIPTIONS, *rows], FIELDS)


def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    rows = generate_rows(start, end)
    write_csv_atomic(args.output, [FIELD_DESCRIPTIONS, *rows], FIELDS)
    print(f"Wrote {args.output} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
