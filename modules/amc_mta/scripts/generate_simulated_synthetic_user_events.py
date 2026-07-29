from __future__ import annotations

import argparse
import sys
from pathlib import Path

AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from amc_mta_attribution import write_csv_atomic  # noqa: E402
from config import REPORT_END_DATE, REPORT_START_DATE, SYNTHETIC_USER_EVENTS_FILE  # noqa: E402
from synthetic_event_pipeline import (  # noqa: E402
    SYNTHETIC_EVENT_FIELDS,
    generate_synthetic_user_events,
)


FIELDS = SYNTHETIC_EVENT_FIELDS


def generate_rows() -> list[dict[str, object]]:
    return generate_synthetic_user_events(REPORT_START_DATE, REPORT_END_DATE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate simulation-only user events.")
    parser.add_argument("--output", type=Path, default=SYNTHETIC_USER_EVENTS_FILE)
    args = parser.parse_args()
    rows = generate_rows()
    write_csv_atomic(args.output, rows, FIELDS)
    print(f"Wrote {args.output} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
