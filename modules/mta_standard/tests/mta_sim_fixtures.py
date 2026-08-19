"""Deterministic MTA-SIM shaped fixtures written to caller-supplied directories.

Every fixture is written outside the repository during tests, which is how the
suite proves the standardized loaders do not depend on repository location.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping, Sequence


REPORT_START = "2026-01-01"
REPORT_END = "2026-01-31"
MARKETPLACE = "US"
ADVERTISER_ID = "ENTITY123"
CURRENCY = "USD"

DISPLAY = "AMAZON_DSP:OTT:UNSPECIFIED:VIDEO"
SEARCH = "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED"
BRAND = "SPONSORED_BRANDS:VIDEO_AD:TOP_OF_SEARCH:UNSPECIFIED"

# DISPLAY is billed per thousand impressions, the two search products per click.
SIMULATOR_COST_TYPES: Mapping[str, str] = {
    DISPLAY: "CPM",
    SEARCH: "CPC",
    BRAND: "CPC",
}

FIVE_SEGMENT_TOUCHPOINTS: tuple[str, ...] = (
    f"{DISPLAY}:IMPRESSION",
    f"{SEARCH}:CLICK",
    f"{BRAND}:CLICK",
)

PATH_REPORT_FIELDS = (
    "report_start_date",
    "report_end_date",
    "marketplace",
    "advertiser_id",
    "path",
    "users",
    "converted_users",
    "purchase_count",
    "revenue",
)

ADS_FIELDS = (
    "reportDate",
    "marketplace",
    "accountId",
    "adProduct",
    "adType",
    "creativeType",
    "inventoryType",
    "placement",
    "normalizedTouchpoint",
    "currencyCode",
    "impressions",
    "clicks",
    "cost",
    "purchases",
    "sales",
    "unitsSold",
)

GROUND_TRUTH_FIELDS = (
    "report_start_date",
    "report_end_date",
    "marketplace",
    "path",
    "normalized_touchpoint",
    "causal_increment",
    "credit_share",
    "expected_conversion_probability",
)

# path, users, converted_users, purchase_count, revenue
PATH_ROWS: Sequence[tuple[str, int, int, int, str]] = (
    (f"{DISPLAY} > {SEARCH}", 100, 40, 50, "5000.00"),
    (SEARCH, 80, 20, 25, "2500.00"),
    (f"{DISPLAY} > {BRAND}", 60, 15, 18, "1800.00"),
    (f"{BRAND} > {SEARCH}", 50, 10, 12, "1200.00"),
)

# touchpoint -> (adProduct, adType, creativeType, inventoryType, placement)
_ADS_COMPONENTS: Mapping[str, tuple[str, str, str, str, str]] = {
    DISPLAY: ("AMAZON_DSP", "", "VIDEO", "OTT", ""),
    SEARCH: ("SPONSORED_PRODUCTS", "PRODUCT_AD", "", "", "TOP_OF_SEARCH"),
    BRAND: ("SPONSORED_BRANDS", "VIDEO_AD", "", "", "TOP_OF_SEARCH"),
}


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping]) -> Path:
    """Write a CSV with the exact header order the contract requires.

    Args:
        path: Destination file; parent directories are created.
        fieldnames: Header, written verbatim.
        rows: Row mappings keyed by field name.

    Returns:
        Path: The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_path_report(
    directory: Path,
    *,
    name: str = "amc_path_report.csv",
    rows: Sequence[tuple[str, int, int, int, str]] = PATH_ROWS,
    marketplace: str = MARKETPLACE,
) -> Path:
    """Write an ``amc_path_report`` fixture with four-segment paths.

    Args:
        directory: Destination directory.
        name: File name.
        rows: Path tuples of ``(path, users, converted, purchases, revenue)``.
        marketplace: Marketplace written to every row.

    Returns:
        Path: The written CSV.
    """
    return _write_csv(
        directory / name,
        PATH_REPORT_FIELDS,
        [
            {
                "report_start_date": REPORT_START,
                "report_end_date": REPORT_END,
                "marketplace": marketplace,
                "advertiser_id": ADVERTISER_ID,
                "path": path,
                "users": users,
                "converted_users": converted,
                "purchase_count": purchases,
                "revenue": revenue,
            }
            for path, users, converted, purchases, revenue in rows
        ],
    )


def write_ads_performance(
    directory: Path,
    *,
    name: str = "amazon_ads_daily_touchpoint_performance.csv",
    dates: Sequence[str] = (REPORT_START, "2026-01-02"),
) -> Path:
    """Write an ``amazon_ads_daily_touchpoint_performance`` fixture.

    Impressions and clicks are both populated because MTA-SIM aggregates them
    into one four-segment row; the fifth segment does not exist in this table.

    Args:
        directory: Destination directory.
        name: File name.
        dates: Report dates to emit, one block of touchpoints per date.

    Returns:
        Path: The written CSV.
    """
    rows = []
    for report_date in dates:
        for touchpoint, components in _ADS_COMPONENTS.items():
            ad_product, ad_type, creative_type, inventory_type, placement = components
            rows.append(
                {
                    "reportDate": report_date,
                    "marketplace": MARKETPLACE,
                    "accountId": ADVERTISER_ID,
                    "adProduct": ad_product,
                    "adType": ad_type,
                    "creativeType": creative_type,
                    "inventoryType": inventory_type,
                    "placement": placement,
                    "normalizedTouchpoint": touchpoint,
                    "currencyCode": CURRENCY,
                    "impressions": 1000,
                    "clicks": 40,
                    "cost": "120.00",
                    "purchases": 5,
                    "sales": "500.00",
                    "unitsSold": 6,
                }
            )
    return _write_csv(directory / name, ADS_FIELDS, rows)


def write_ground_truth(
    directory: Path,
    *,
    name: str = "simulation_ground_truth.csv",
    per_path: bool = False,
) -> Path:
    """Write a ``simulation_ground_truth`` fixture.

    Args:
        directory: Destination directory.
        name: File name.
        per_path: When true, emit one row per (path, touchpoint) pair with
            unnormalised shares, exercising the loader's aggregate-and-normalise
            rule. When false, emit one already-normalised row per touchpoint.

    Returns:
        Path: The written CSV.
    """
    if per_path:
        raw = [
            (f"{DISPLAY} > {SEARCH}", DISPLAY, 0.08, 0.30, 0.44),
            (f"{DISPLAY} > {SEARCH}", SEARCH, 0.12, 0.50, 0.44),
            (SEARCH, SEARCH, 0.05, 0.25, 0.22),
            (f"{DISPLAY} > {BRAND}", DISPLAY, 0.03, 0.10, 0.18),
            (f"{DISPLAY} > {BRAND}", BRAND, 0.04, 0.15, 0.18),
            (f"{BRAND} > {SEARCH}", BRAND, 0.02, 0.05, 0.12),
            (f"{BRAND} > {SEARCH}", SEARCH, 0.03, 0.15, 0.12),
        ]
    else:
        raw = [
            ("", DISPLAY, 0.11, 0.30, 0.44),
            ("", SEARCH, 0.20, 0.50, 0.30),
            ("", BRAND, 0.06, 0.20, 0.18),
        ]
    return _write_csv(
        directory / name,
        GROUND_TRUTH_FIELDS,
        [
            {
                "report_start_date": REPORT_START,
                "report_end_date": REPORT_END,
                "marketplace": MARKETPLACE,
                "path": path or touchpoint,
                "normalized_touchpoint": touchpoint,
                "causal_increment": increment,
                "credit_share": share,
                "expected_conversion_probability": probability,
            }
            for path, touchpoint, increment, share, probability in raw
        ],
    )


def write_dataset(directory: Path, *, per_path_ground_truth: bool = False) -> dict:
    """Write all three MTA-SIM tables into one directory.

    Args:
        directory: Destination directory.
        per_path_ground_truth: Forwarded to :func:`write_ground_truth`.

    Returns:
        dict: ``{"path_report", "ads_performance", "ground_truth"}`` paths.
    """
    return {
        "path_report": write_path_report(directory),
        "ads_performance": write_ads_performance(directory),
        "ground_truth": write_ground_truth(directory, per_path=per_path_ground_truth),
    }
