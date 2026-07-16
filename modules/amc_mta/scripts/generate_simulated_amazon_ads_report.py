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
from touchpoint_key import canonical_amc_touchpoint_key  # noqa: E402


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


TOUCHPOINTS = [
    ("AMAZON_DSP", "", "", "AUDIO", "UNSPECIFIED", "UNSPECIFIED", "CPM", 42000, 0.0022, 18.0, 0.018, 95.0),
    ("AMAZON_DSP", "", "IMAGE", "DISPLAY", "UNSPECIFIED", "IMAGE", "CPM", 51000, 0.0031, 12.5, 0.020, 105.0),
    ("AMAZON_DSP", "", "VIDEO", "ONLINE_VIDEO", "UNSPECIFIED", "VIDEO", "CPM", 38000, 0.0025, 20.0, 0.021, 118.0),
    ("AMAZON_DSP", "", "VIDEO", "STREAMING_TV", "UNSPECIFIED", "VIDEO", "CPM", 46000, 0.0012, 28.0, 0.025, 132.0),
    ("SPONSORED_BRANDS", "COMPONENT", "IMAGE", "", "TOP_OF_SEARCH", "IMAGE", "CPC", 18000, 0.0080, 1.20, 0.055, 82.0),
    ("SPONSORED_BRANDS", "DISPLAY", "IMAGE", "", "REST_OF_SEARCH", "IMAGE", "CPC", 21000, 0.0062, 1.05, 0.048, 79.0),
    ("SPONSORED_BRANDS", "VIDEO", "VIDEO", "", "TOP_OF_SEARCH", "VIDEO", "CPC", 16000, 0.0071, 1.38, 0.050, 91.0),
    ("SPONSORED_DISPLAY", "DISPLAY", "IMAGE", "", "PRODUCT_PAGE", "IMAGE", "CPC", 24000, 0.0058, 0.92, 0.045, 76.0),
    ("SPONSORED_DISPLAY", "DISPLAY", "VIDEO", "", "PRODUCT_PAGE", "VIDEO", "CPC", 19000, 0.0065, 1.08, 0.047, 84.0),
    ("SPONSORED_DISPLAY", "VIDEO", "VIDEO", "", "PRODUCT_PAGE", "VIDEO", "CPC", 17000, 0.0069, 1.18, 0.049, 88.0),
    ("SPONSORED_PRODUCTS", "PRODUCT_AD", "", "", "PRODUCT_PAGE", "UNSPECIFIED", "CPC", 33000, 0.0105, 0.88, 0.075, 68.0),
    ("SPONSORED_PRODUCTS", "PRODUCT_AD", "", "", "REST_OF_SEARCH", "UNSPECIFIED", "CPC", 36000, 0.0094, 0.82, 0.069, 65.0),
    ("SPONSORED_PRODUCTS", "PRODUCT_AD", "", "", "TOP_OF_SEARCH", "UNSPECIFIED", "CPC", 40000, 0.0120, 1.02, 0.082, 72.0),
]

# The Ads sample covers exactly the five-part interactions present in the AMC
# path sample. A non-billed counterpart is emitted only when that interaction
# actually participates in a path.
SAMPLE_INTERACTIONS = {
    "AMAZON_DSP:AUDIO:UNSPECIFIED:UNSPECIFIED:IMPRESSION",
    "AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE:IMPRESSION",
    "AMAZON_DSP:ONLINE_VIDEO:UNSPECIFIED:VIDEO:IMPRESSION",
    "AMAZON_DSP:STREAMING_TV:UNSPECIFIED:VIDEO:IMPRESSION",
    "SPONSORED_BRANDS:COMPONENT:TOP_OF_SEARCH:IMAGE:CLICK",
    "SPONSORED_BRANDS:COMPONENT:TOP_OF_SEARCH:IMAGE:IMPRESSION",
    "SPONSORED_BRANDS:DISPLAY:REST_OF_SEARCH:IMAGE:IMPRESSION",
    "SPONSORED_BRANDS:VIDEO:TOP_OF_SEARCH:VIDEO:CLICK",
    "SPONSORED_BRANDS:VIDEO:TOP_OF_SEARCH:VIDEO:IMPRESSION",
    "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:IMAGE:CLICK",
    "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:IMAGE:IMPRESSION",
    "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:VIDEO:IMPRESSION",
    "SPONSORED_DISPLAY:VIDEO:PRODUCT_PAGE:VIDEO:CLICK",
    "SPONSORED_PRODUCTS:PRODUCT_AD:PRODUCT_PAGE:UNSPECIFIED:CLICK",
    "SPONSORED_PRODUCTS:PRODUCT_AD:REST_OF_SEARCH:UNSPECIFIED:CLICK",
    "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK",
    "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:IMPRESSION",
}


def generate_rows(start: date, end: date) -> list[dict]:
    if start > end:
        raise ValueError("start date must be on or before end date")
    rows: list[dict] = []
    day_count = (end - start).days + 1
    for day_index in range(day_count):
        report_date = start + timedelta(days=day_index)
        for index, config in enumerate(TOUCHPOINTS, start=1):
            (
                ad_product,
                ad_type,
                creative_type,
                inventory_type,
                placement,
                creative_key,
                cost_type,
                base_impressions,
                ctr,
                price,
                conversion_rate,
                average_order_value,
            ) = config
            format_value = inventory_type if ad_product == "AMAZON_DSP" else ad_type
            impressions = base_impressions + ((day_index * 977 + index * 541) % 6800)
            clicks = max(1, round(impressions * ctr * (0.94 + ((day_index + index) % 9) / 100)))
            purchases = round(clicks * conversion_rate * (0.92 + ((day_index * 2 + index) % 11) / 100))
            cost = (
                impressions / 1000 * price
                if cost_type == "CPM"
                else clicks * price
            )
            sales = purchases * average_order_value * (
                0.96 + ((day_index * 3 + index) % 10) / 100
            )
            common = {
                    "reportDate": report_date.isoformat(),
                    "marketplace": "US",
                    "accountId": "adv_demo_001",
                    "adProduct": ad_product,
                    "adType": ad_type,
                    "creativeType": creative_type,
                    "inventoryType": inventory_type,
                    "placement": "" if placement == "UNSPECIFIED" else placement,
                    "currencyCode": "USD",
            }
            for interaction_type in ("IMPRESSION", "CLICK"):
                billed_interaction = (
                    "IMPRESSION" if cost_type == "CPM" else "CLICK"
                )
                is_click = interaction_type == "CLICK"
                normalized_touchpoint = canonical_amc_touchpoint_key(
                    ad_product,
                    format_value,
                    placement,
                    creative_key,
                    interaction_type,
                )
                if normalized_touchpoint not in SAMPLE_INTERACTIONS:
                    continue
                rows.append(
                    {
                        **common,
                        "interaction_type": interaction_type,
                        "cost_type": "CPC" if is_click else "CPM",
                        "normalizedTouchpoint": normalized_touchpoint,
                        "impressions": impressions if not is_click else 0,
                        "clicks": clicks if is_click else 0,
                        "cost": round(cost, 2)
                        if interaction_type == billed_interaction
                        else 0,
                        "purchases": purchases if is_click else 0,
                        "sales": round(sales, 2) if is_click else 0,
                    }
                )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic Amazon Ads sample data.")
    parser.add_argument("--output", type=Path, default=AMAZON_ADS_REPORT_FILE)
    parser.add_argument("--start-date", default=REPORT_START_DATE)
    parser.add_argument("--end-date", default=REPORT_END_DATE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = generate_rows(date.fromisoformat(args.start_date), date.fromisoformat(args.end_date))
    write_csv_atomic(args.output, [FIELD_DESCRIPTIONS, *rows], FIELDS)
    print(f"Wrote {args.output} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
