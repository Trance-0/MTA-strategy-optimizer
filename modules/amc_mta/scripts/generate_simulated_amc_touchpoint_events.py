from __future__ import annotations

import argparse
import sys
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path

AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from amc_mta_attribution import write_csv_atomic  # noqa: E402
from config import AMC_TOUCHPOINT_EVENTS_FILE, REPORT_END_DATE, REPORT_START_DATE  # noqa: E402
from simulated_touchpoints import (  # noqa: E402
    ADVERTISER_ID, MARKETPLACE, TOUCHPOINT_CATALOG, validate_touchpoint_catalog,
)

TOUCHPOINT_KEYS = tuple(spec.key for spec in TOUCHPOINT_CATALOG)

FIELDS = ["journey_id","event_type","event_time","ad_product","format","placement","creative","interaction_type","marketplace","advertiser_id","users","converted_users","purchase_count","revenue","new_to_brand_purchases"]

def _touch(journey: str, when: datetime, key: str) -> dict:
    ad_product, fmt, placement, creative, interaction = key.split(":")
    return {"journey_id": journey, "event_type": "TOUCHPOINT", "event_time": when.isoformat().replace("+00:00", "Z"), "ad_product": ad_product, "format": fmt, "placement": "" if placement == "UNSPECIFIED" else placement, "creative": "" if creative == "UNSPECIFIED" else creative, "interaction_type": interaction}

def _conversion(journey: str, when: datetime, seed: int) -> dict:
    converted = 18 + seed % 11
    purchases = converted + 3 + seed % 7
    return {"journey_id": journey, "event_type": "CONVERSION", "event_time": when.isoformat().replace("+00:00", "Z"), "marketplace": MARKETPLACE, "advertiser_id": ADVERTISER_ID, "users": converted + 20 + seed % 13, "converted_users": converted, "purchase_count": purchases, "revenue": f"{purchases * (72 + seed % 19):.2f}", "new_to_brand_purchases": seed % 4}

def generate_rows() -> list[dict]:
    validate_touchpoint_catalog(TOUCHPOINT_CATALOG)
    start = datetime.fromisoformat(REPORT_START_DATE).date()
    end = datetime.fromisoformat(REPORT_END_DATE).date()
    if (start.month, start.day) != (1, 1) or (end.month, end.day) != (12, 31) or start.year != end.year:
        raise ValueError("event sample requires one complete natural year")
    year = start.year
    rows: list[dict] = []
    for month in range(1, 13):
        for template in range(12):
            journey = f"annual_{month:02d}_{template:02d}"
            conversion = datetime(year, month, 20 + template % 5, 12, tzinfo=timezone.utc)
            touch_count = 3 if template < 6 else 2
            code = (month - 1) * 12 + template
            first = code % len(TOUCHPOINT_KEYS)
            second = (first + 1 + code // len(TOUCHPOINT_KEYS)) % len(TOUCHPOINT_KEYS)
            indices = [first, second]
            if touch_count == 3:
                third = (first + second + 1) % len(TOUCHPOINT_KEYS)
                while third in indices:
                    third = (third + 1) % len(TOUCHPOINT_KEYS)
                indices.append(third)
            for position in range(touch_count):
                day_offset = (9, 5, 2)[position] if touch_count == 3 else (5, 2)[position]
                key = TOUCHPOINT_KEYS[indices[position]]
                rows.append(_touch(journey, conversion.replace(day=conversion.day - day_offset), key))
            rows.append(_conversion(journey, conversion, month * 20 + template))
            if template == 0:
                rows.append(_conversion(journey, conversion.replace(hour=13), month * 20 + 19))
    rows.extend([
        _touch("reject_start", datetime(year,1,1,0,tzinfo=timezone.utc), TOUCHPOINT_KEYS[0]),
        _conversion("reject_start", datetime(year,1,2,0,tzinfo=timezone.utc), 1),
        _touch("reject_gap", datetime(year,1,5,0,tzinfo=timezone.utc), TOUCHPOINT_KEYS[1]),
        _conversion("reject_gap", datetime(year,1,19,0,0,1,tzinfo=timezone.utc), 2),
    ])
    return rows

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=AMC_TOUCHPOINT_EVENTS_FILE)
    args = parser.parse_args()
    rows = generate_rows()
    write_csv_atomic(args.output, rows, FIELDS)
    print(f"Wrote {args.output} ({len(rows)} rows)")

if __name__ == "__main__":
    main()
