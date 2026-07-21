from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path


AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from amc_mta_attribution import ADS_FIELD_DESCRIPTIONS, write_csv_atomic  # noqa: E402
from config import AMAZON_ADS_REPORT_FILE, REPORT_END_DATE, REPORT_START_DATE  # noqa: E402
from simulated_touchpoints import (  # noqa: E402
    ADVERTISER_ID, CURRENCY, MARKETPLACE, TOUCHPOINT_CATALOG,
    validate_touchpoint_catalog,
)


FIELDS = [
    "reportDate",
    "marketplace",
    "accountId",
    "adProduct",
    "adType",
    "creativeType",
    "inventoryType",
    "placement",
    "interaction_type",
    "cost_type",
    "normalizedTouchpoint",
    "currencyCode",
    "impressions",
    "clicks",
    "cost",
    "purchases",
    "sales",
]


FIELD_DESCRIPTIONS = ADS_FIELD_DESCRIPTIONS


def generate_rows(start: date, end: date) -> list[dict]:
    if start > end:
        raise ValueError("start date must be on or before end date")
    validate_touchpoint_catalog(TOUCHPOINT_CATALOG)
    rows: list[dict] = []
    day_count = (end - start).days + 1
    for day_index in range(day_count):
        report_date = start + timedelta(days=day_index)
        absolute_day_index = (report_date - date(2000, 1, 1)).days
        for spec in TOUCHPOINT_CATALOG:
            index = spec.metric_seed
            impressions = spec.base_impressions + ((absolute_day_index * 977 + index * 541) % 6800)
            clicks = max(1, round(impressions * spec.ctr * (0.94 + ((absolute_day_index + index) % 9) / 100)))
            purchases = round(clicks * spec.conversion_rate * (0.92 + ((absolute_day_index * 2 + index) % 11) / 100))
            cost = (
                impressions / 1000 * spec.price
                if spec.billed_interaction == "IMPRESSION"
                else clicks * spec.price
            )
            sales = purchases * spec.average_order_value * (
                0.96 + ((absolute_day_index * 3 + index) % 10) / 100
            )
            common = {
                    "reportDate": report_date.isoformat(),
                    "marketplace": MARKETPLACE,
                    "accountId": ADVERTISER_ID,
                    "adProduct": spec.ad_product,
                    "adType": spec.ad_type,
                    "creativeType": spec.creative_type,
                    "inventoryType": spec.inventory_type,
                    "placement": "" if spec.placement == "UNSPECIFIED" else spec.placement,
                    "currencyCode": CURRENCY,
            }
            is_click = spec.interaction_type == "CLICK"
            rows.append({
                **common,
                "interaction_type": spec.interaction_type,
                "cost_type": spec.cost_type,
                "normalizedTouchpoint": spec.key,
                "impressions": impressions if not is_click else 0,
                "clicks": clicks if is_click else 0,
                "cost": round(cost, 2) if spec.interaction_type == spec.billed_interaction else 0,
                "purchases": purchases if is_click else 0,
                "sales": round(sales, 2) if is_click else 0,
            })
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic Amazon Ads sample data.")
    parser.add_argument("--output", type=Path, default=AMAZON_ADS_REPORT_FILE)
    parser.add_argument("--start-date", default=REPORT_START_DATE)
    parser.add_argument("--end-date", default=REPORT_END_DATE)
    return parser.parse_args()


def generate_file(output: Path, start: date, end: date) -> None:
    """Validate and generate before atomically replacing an existing artifact."""
    rows = generate_rows(start, end)
    write_csv_atomic(output, [FIELD_DESCRIPTIONS, *rows], FIELDS)


def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    generate_file(args.output, start, end)
    print(f"Wrote {args.output} ({len(generate_rows(start, end))} rows)")


if __name__ == "__main__":
    main()
