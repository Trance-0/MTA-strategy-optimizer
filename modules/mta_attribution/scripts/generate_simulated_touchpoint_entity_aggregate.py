"""Generate the touchpoint-to-delivery-entity bridge sample.

Produces the only file that maps a five-segment touchpoint onto Campaigns and
historical Ad Groups. Without it, attribution shares cannot be carried into the
strategy module.

Data flow: synthetic events -> `amc_touchpoint_entity_aggregate_sample.csv`
-> `mta_strategy_recommendation`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping, Sequence

AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from attribution_contract import write_csv_atomic  # noqa: E402
from config import (  # noqa: E402
    AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE,
    REPORT_END_DATE,
    REPORT_START_DATE,
    SIMULATED_PRIVACY_MIN_USERS,
)
from synthetic_event_pipeline import (  # noqa: E402
    ENTITY_AGGREGATE_FIELDS,
    derive_touchpoint_entity_aggregate,
    generate_synthetic_user_events,
)


FIELDS = ENTITY_AGGREGATE_FIELDS


def generate_rows(
    source_rows: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    source = list(source_rows) if source_rows is not None else generate_synthetic_user_events(
        REPORT_START_DATE, REPORT_END_DATE
    )
    return derive_touchpoint_entity_aggregate(
        source,
        REPORT_START_DATE,
        REPORT_END_DATE,
        SIMULATED_PRIVACY_MIN_USERS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate privacy-safe touchpoint/entity aggregates."
    )
    parser.add_argument(
        "--output", type=Path, default=AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE
    )
    args = parser.parse_args()
    rows = generate_rows()
    write_csv_atomic(args.output, rows, FIELDS)
    print(f"Wrote {args.output} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
