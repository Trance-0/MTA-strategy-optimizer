"""Preflight check that the path and Ads reports describe the same report.

Attribution and cost metrics can only be joined when both sides agree, so this
runs before attribution in the pipeline and is also the public preflight command.

Checks: one marketplace/account/currency scope on each side, identical report
windows, a continuous date grid, the same touchpoint set on every day, no
duplicate touchpoint/date pairs, and billing consistency between `cost_type` and
`interaction_type`.

Data flow: path report + Ads report -> a summary dict, or a `ValueError` naming
the first disagreement. It writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path


AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from config import AMC_REPORT_FILE, DATA_DIR  # noqa: E402
from attribution_contract import (  # noqa: E402
    aggregate_spend_by_touchpoint,
    read_csv,
    validate_amc_aggregated_row,
)
from touchpoint_key import (  # noqa: E402
    canonicalize_amc_touchpoint_key,
    touchpoint_key_from_ads_row,
)


DEFAULT_AMAZON_ADS_REPORT = DATA_DIR / "amazon_ads_report_sample.csv"


def touchpoints_from_amc_path(path: str) -> set[str]:
    parts = path.split(">")
    if any(not part.strip() for part in parts):
        raise ValueError("path contains an empty touchpoint")
    states = [part.strip() for part in parts]
    if "Start" in states or "Conversion" in states:
        raise ValueError("path cannot contain reserved terminal states")
    if "Null" in states[:-1] or states == ["Null"]:
        raise ValueError("Null is allowed only after a touchpoint")
    if states[-1] == "Null":
        states = states[:-1]
    return {
        canonicalize_amc_touchpoint_key(state)
        for state in states
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that AMC path touchpoints align with Amazon Ads report touchpoints."
    )
    parser.add_argument(
        "--amc-report",
        default=AMC_REPORT_FILE,
        type=Path,
        help="AMC aggregated path report CSV.",
    )
    parser.add_argument(
        "--amazon-ads-report",
        default=DEFAULT_AMAZON_ADS_REPORT,
        type=Path,
        help="Amazon Ads report CSV.",
    )
    return parser.parse_args()


def _required_text(row: dict, field: str, context: str) -> str:
    raw = row.get(field)
    value = "" if raw is None else str(raw).strip()
    if not value:
        raise ValueError(f"{context}: {field} is required")
    return value


def _parse_report_date(value: str, context: str) -> date:
    if (
        len(value) != 10
        or value[4] != "-"
        or value[7] != "-"
        or not (value[:4] + value[5:7] + value[8:]).isdigit()
    ):
        raise ValueError(f"{context}: reportDate must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{context}: reportDate must be an ISO date") from exc


def infer_ads_report_window(ads_rows: list[dict]) -> tuple[date, date]:
    """Validate the Ads date grid and return its inclusive report window."""
    if not ads_rows:
        raise ValueError("Amazon Ads report must contain at least one row")

    dates: set[date] = set()
    touchpoint_dates: set[tuple[str, date]] = set()
    touchpoints_by_date: dict[date, set[str]] = {}
    scopes: set[tuple[str, str, str]] = set()
    for row_number, row in enumerate(ads_rows, start=2):
        touchpoint = touchpoint_key_from_ads_row(row, row_number=row_number)
        report_date = _required_text(row, "reportDate", f"Amazon Ads row {row_number}")
        parsed_date = _parse_report_date(report_date, f"Amazon Ads row {row_number}")

        touchpoint_date = (touchpoint, parsed_date)
        if touchpoint_date in touchpoint_dates:
            raise ValueError(
                f"Amazon Ads row {row_number}: duplicate touchpoint/reportDate: "
                f"{touchpoint} / {parsed_date.isoformat()}"
            )
        touchpoint_dates.add(touchpoint_date)
        dates.add(parsed_date)
        touchpoints_by_date.setdefault(parsed_date, set()).add(touchpoint)
        scopes.add(
            (
                _required_text(row, "marketplace", f"Amazon Ads row {row_number}"),
                _required_text(row, "accountId", f"Amazon Ads row {row_number}"),
                _required_text(row, "currencyCode", f"Amazon Ads row {row_number}"),
            )
        )

    if len(scopes) != 1:
        raise ValueError(
            "Amazon Ads report must contain one marketplace/account/currency scope; "
            f"found {len(scopes)}"
        )

    start_date = min(dates)
    end_date = max(dates)
    ordered_dates = sorted(dates)
    gaps = [
        (left, right)
        for left, right in zip(ordered_dates, ordered_dates[1:])
        if right - left != timedelta(days=1)
    ]
    if gaps:
        raise ValueError(
            "Amazon Ads report dates must be continuous; "
            f"first_gap={gaps[0][0]}..{gaps[0][1]}"
        )

    expected_touchpoints = touchpoints_by_date[start_date]
    inconsistent_dates = [
        report_date
        for report_date in ordered_dates
        if touchpoints_by_date[report_date] != expected_touchpoints
    ]
    if inconsistent_dates:
        raise ValueError(
            "incomplete daily touchpoint coverage; "
            "Amazon Ads report must contain the same touchpoint set every day; "
            f"inconsistent={inconsistent_dates[:10]}"
        )
    return start_date, end_date


def validate_data_alignment_rows(amc_rows: list[dict], ads_rows: list[dict]) -> dict:
    if not amc_rows:
        raise ValueError("AMC report must contain at least one row")
    inferred_start, inferred_end = infer_ads_report_window(ads_rows)

    amc_touchpoints = set()
    amc_windows = set()
    amc_scopes = set()
    for row_number, row in enumerate(amc_rows, start=2):
        validate_amc_aggregated_row(row, row_number)
        amc_touchpoints.update(touchpoints_from_amc_path(row["path"]))
        start_text = _required_text(row, "report_start_date", f"AMC row {row_number}")
        end_text = _required_text(row, "report_end_date", f"AMC row {row_number}")
        try:
            start_date = date.fromisoformat(start_text)
            end_date = date.fromisoformat(end_text)
        except ValueError as exc:
            raise ValueError(
                f"AMC row {row_number}: report dates must be ISO dates"
            ) from exc
        if start_date > end_date:
            raise ValueError(f"AMC row {row_number}: report window is inverted")
        amc_windows.add((start_date, end_date))
        amc_scopes.add(
            (
                _required_text(row, "marketplace", f"AMC row {row_number}"),
                _required_text(row, "advertiser_id", f"AMC row {row_number}"),
            )
        )

    if len(amc_windows) != 1:
        raise ValueError(f"AMC report must contain one window; found {len(amc_windows)}")
    if len(amc_scopes) != 1:
        raise ValueError(f"AMC report must contain one scope; found {len(amc_scopes)}")

    ads_touchpoints = set()
    ads_dates = set()
    ads_touchpoint_dates = set()
    ads_scopes = set()
    for row_number, row in enumerate(ads_rows, start=2):
        touchpoint = touchpoint_key_from_ads_row(row, row_number=row_number)
        ads_touchpoints.add(touchpoint)
        report_date = _required_text(row, "reportDate", f"Amazon Ads row {row_number}")
        try:
            parsed_date = date.fromisoformat(report_date)
        except ValueError as exc:
            raise ValueError(
                f"Amazon Ads row {row_number}: reportDate must be an ISO date"
            ) from exc
        ads_dates.add(parsed_date)
        touchpoint_date = (touchpoint, parsed_date)
        if touchpoint_date in ads_touchpoint_dates:
            raise ValueError(
                f"Amazon Ads row {row_number}: duplicate touchpoint/reportDate: "
                f"{touchpoint} / {parsed_date.isoformat()}"
            )
        ads_touchpoint_dates.add(touchpoint_date)
        ads_scopes.add(
            (
                _required_text(row, "marketplace", f"Amazon Ads row {row_number}"),
                _required_text(row, "accountId", f"Amazon Ads row {row_number}"),
                _required_text(row, "currencyCode", f"Amazon Ads row {row_number}"),
            )
        )

    # infer_ads_report_window already validates one Ads scope, a continuous
    # window, unique key/date pairs, and the same touchpoint set on every day.
    amc_scope = next(iter(amc_scopes))
    ads_scope = next(iter(ads_scopes))
    if amc_scope != ads_scope[:2]:
        raise ValueError(
            f"scope mismatch: AMC {amc_scope}, Amazon Ads {ads_scope[:2]}"
        )

    missing_in_ads = sorted(amc_touchpoints - ads_touchpoints)
    extra_in_ads = sorted(ads_touchpoints - amc_touchpoints)
    if missing_in_ads or extra_in_ads:
        raise ValueError(
            f"touchpoint mismatch; missing in Ads={missing_in_ads}, extra in Ads={extra_in_ads}"
        )

    start_date, end_date = next(iter(amc_windows))
    if (start_date, end_date) != (inferred_start, inferred_end):
        raise ValueError(
            "report date mismatch; "
            f"AMC={start_date.isoformat()}..{end_date.isoformat()}, "
            f"Ads={inferred_start.isoformat()}..{inferred_end.isoformat()}"
        )
    expected_dates = {
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    }
    missing_dates = sorted(expected_dates - ads_dates)
    extra_dates = sorted(ads_dates - expected_dates)
    if missing_dates or extra_dates:
        raise ValueError(
            f"report date mismatch; missing={missing_dates}, extra={extra_dates}"
        )

    expected_touchpoint_dates = {
        (touchpoint, report_date)
        for touchpoint in amc_touchpoints
        for report_date in expected_dates
    }
    missing_touchpoint_dates = sorted(
        expected_touchpoint_dates - ads_touchpoint_dates
    )
    if missing_touchpoint_dates:
        preview = missing_touchpoint_dates[:10]
        raise ValueError(
            "incomplete daily touchpoint coverage; "
            f"missing {len(missing_touchpoint_dates)} pair(s), first={preview}"
        )

    # Alignment is the public preflight command, so it validates billing and
    # platform-outcome ownership as well as keys, scope, and daily coverage.
    aggregate_spend_by_touchpoint(ads_rows)

    return {
        "amc_touchpoints": len(amc_touchpoints),
        "ads_touchpoints": len(ads_touchpoints),
        "report_start_date": start_date.isoformat(),
        "report_end_date": end_date.isoformat(),
        "marketplace": amc_scope[0],
        "advertiser_id": amc_scope[1],
        "currency": ads_scope[2],
    }


def main() -> None:
    args = parse_args()
    amc_rows = read_csv(args.amc_report)
    ads_rows = read_csv(args.amazon_ads_report)

    summary = validate_data_alignment_rows(amc_rows, ads_rows)
    print(f"AMC touchpoints: {summary['amc_touchpoints']}")
    print(f"Amazon Ads touchpoints: {summary['ads_touchpoints']}")
    print("Missing in Amazon Ads report: none")
    print("Extra in Amazon Ads report: none")
    print(
        f"Report window: {summary['report_start_date']} to "
        f"{summary['report_end_date']}"
    )
    print(
        f"Scope: {summary['marketplace']} / {summary['advertiser_id']} / "
        f"{summary['currency']}"
    )
    print("Report windows and daily coverage aligned")


if __name__ == "__main__":
    main()
