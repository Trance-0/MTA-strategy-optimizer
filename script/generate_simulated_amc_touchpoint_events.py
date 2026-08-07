"""Generate the legacy simulated touchpoint-event sample.

Projects synthetic user events into the touchpoint-event shape the path builder
consumes, keeping the same journeys behind both files.

This compatibility command reproduces the committed five-segment fixture. New
datasets use ``generate_mta_sim_dataset.py``.

Data flow: synthetic user events -> `amc_touchpoint_events_sample.csv`
-> `build_path_report`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMC_MTA_ROOT = PROJECT_ROOT / "modules" / "mta_attribution"
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from attribution_contract import write_csv_atomic  # noqa: E402
from config import AMC_TOUCHPOINT_EVENTS_FILE, REPORT_END_DATE, REPORT_START_DATE  # noqa: E402
from synthetic_event_pipeline import (  # noqa: E402
    AMC_EVENT_FIELDS,
    derive_amc_touchpoint_events,
    generate_synthetic_user_events,
)


FIELDS = AMC_EVENT_FIELDS


def generate_rows(
    source_rows: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    source = list(source_rows) if source_rows is not None else generate_synthetic_user_events(
        REPORT_START_DATE, REPORT_END_DATE
    )
    return derive_amc_touchpoint_events(source)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate anonymous AMC concept events from synthetic user events."
    )
    parser.add_argument("--output", type=Path, default=AMC_TOUCHPOINT_EVENTS_FILE)
    args = parser.parse_args()
    rows = generate_rows()
    write_csv_atomic(args.output, rows, FIELDS)
    print(f"Wrote {args.output} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
