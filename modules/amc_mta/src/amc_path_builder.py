from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Mapping, Sequence

from touchpoint_key import canonical_amc_touchpoint_key


REQUIRED_FIELDS = {"journey_id", "event_type", "event_time"}
CONVERSION_REQUIRED_FIELDS = {
    "marketplace",
    "advertiser_id",
    "users",
    "converted_users",
    "purchase_count",
    "revenue",
}
TOUCHPOINT = "TOUCHPOINT"
CONVERSION = "CONVERSION"


def _parse_date(value: object, field: str) -> date:
    if value in (None, ""):
        raise ValueError(f"{field} is required")
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date: {value!r}") from exc


def _parse_datetime(value: object, field: str) -> datetime:
    if value in (None, ""):
        raise ValueError(f"{field} is required")
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO datetime: {value!r}") from exc
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _number(row: Mapping[str, object], field: str, *, integer: bool = False) -> float | int:
    value = row.get(field, "")
    if value in (None, ""):
        return 0 if integer else 0.0
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number: {value!r}")
    if integer and not number.is_integer():
        raise ValueError(f"{field} must be an integer: {value!r}")
    return int(number) if integer else number


def _validated_events(event_rows: Sequence[Mapping[str, object]]) -> list[dict]:
    events = []
    for row_number, row in enumerate(event_rows, start=2):
        missing = [
            field
            for field in REQUIRED_FIELDS
            if row.get(field) in (None, "") or not str(row.get(field, "")).strip()
        ]
        if missing:
            raise ValueError(f"row {row_number}: required field(s) missing: {', '.join(sorted(missing))}")
        event_type = str(row["event_type"]).strip().upper()
        if event_type not in {TOUCHPOINT, CONVERSION}:
            raise ValueError(
                f"row {row_number}: event_type must be TOUCHPOINT or CONVERSION: {event_type!r}"
            )
        touchpoint = ""
        if event_type == TOUCHPOINT:
            if row.get("touchpoint") not in (None, "") and str(row.get("touchpoint")).strip():
                raise ValueError(
                    f"row {row_number}: legacy touchpoint key is not accepted; "
                    "use ad_product/format/placement/creative columns"
                )
            try:
                touchpoint = canonical_amc_touchpoint_key(
                    row.get("ad_product"),
                    row.get("format"),
                    row.get("placement"),
                    row.get("creative"),
                    row.get("interaction_type"),
                )
            except ValueError as exc:
                raise ValueError(f"row {row_number}: {exc}") from exc
        if event_type == CONVERSION:
            missing_conversion = [
                field
                for field in CONVERSION_REQUIRED_FIELDS
                if row.get(field) in (None, "") or not str(row.get(field, "")).strip()
            ]
            if missing_conversion:
                raise ValueError(
                    f"row {row_number}: CONVERSION required field(s) missing: "
                    f"{', '.join(sorted(missing_conversion))}"
                )
            users = int(_number(row, "users", integer=True))
            converted_users = int(_number(row, "converted_users", integer=True))
            purchase_count = int(_number(row, "purchase_count", integer=True))
            revenue = float(_number(row, "revenue"))
            ntb = int(_number(row, "new_to_brand_purchases", integer=True))
            if converted_users > users:
                raise ValueError(f"row {row_number}: converted_users must be <= users")
            if purchase_count < converted_users:
                raise ValueError(
                    f"row {row_number}: purchase_count must be >= converted_users"
                )
            if ntb > purchase_count:
                raise ValueError(
                    f"row {row_number}: new_to_brand_purchases must be <= purchase_count"
                )
            if any(value > 0 for value in (purchase_count, revenue, ntb)) and converted_users == 0:
                raise ValueError(
                    f"row {row_number}: non-zero outcomes require converted_users > 0"
                )
        events.append(
            {
                **row,
                "journey_id": str(row["journey_id"]).strip(),
                "event_type": event_type,
                "event_time_parsed": _parse_datetime(row["event_time"], f"row {row_number} event_time"),
                "touchpoint": touchpoint,
            }
        )
    return events


def _contiguous_path(touchpoints: Sequence[dict], max_gap: timedelta) -> list[dict]:
    if not touchpoints:
        return []
    ordered = sorted(
        touchpoints,
        key=lambda event: (event["event_time_parsed"], event["touchpoint"]),
    )
    start = len(ordered) - 1
    for index in range(len(ordered) - 1, 0, -1):
        gap = ordered[index]["event_time_parsed"] - ordered[index - 1]["event_time_parsed"]
        if gap > max_gap:
            start = index
            break
        start = index - 1
    return ordered[start:]


def build_aggregated_path_rows(
    event_rows: Sequence[Mapping[str, object]],
    report_start_date: str | date,
    report_end_date: str | date,
    max_gap_days: int = 14,
) -> list[dict]:
    """Build anonymous path aggregates from synthetic/internal journey events.

    Paths start strictly after report_start_date and end with a purchase no later than
    report_end_date. Every adjacent node, including final touchpoint-to-purchase, must
    be within max_gap_days. Prior purchases split a journey into non-reusable segments.
    """
    start = (
        report_start_date
        if isinstance(report_start_date, date)
        else _parse_date(report_start_date, "report_start_date")
    )
    end = (
        report_end_date
        if isinstance(report_end_date, date)
        else _parse_date(report_end_date, "report_end_date")
    )
    if start > end:
        raise ValueError("report_start_date must be on or before report_end_date")
    if max_gap_days < 0:
        raise ValueError("max_gap_days must be non-negative")

    journeys: dict[str, list[dict]] = defaultdict(list)
    for event in _validated_events(event_rows):
        journeys[event["journey_id"]].append(event)

    for journey_id, journey_events in journeys.items():
        for event_type in (TOUCHPOINT, CONVERSION):
            timestamps = [
                event["event_time_parsed"]
                for event in journey_events
                if event["event_type"] == event_type
            ]
            if len(timestamps) != len(set(timestamps)):
                raise ValueError(
                    f"journey {journey_id!r}: duplicate {event_type} event_time is not allowed"
                )

    aggregates: dict[tuple[str, str, str], dict] = {}
    max_gap = timedelta(days=max_gap_days)
    start_boundary = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    for journey_events in journeys.values():
        touchpoints = [event for event in journey_events if event["event_type"] == TOUCHPOINT]
        conversions = [event for event in journey_events if event["event_type"] == CONVERSION]
        previous_conversion_time: datetime | None = None
        for conversion in sorted(conversions, key=lambda event: event["event_time_parsed"]):
            conversion_date = conversion["event_time_parsed"].date()
            eligible = [
                event
                for event in touchpoints
                if (previous_conversion_time is None or event["event_time_parsed"] > previous_conversion_time)
                and event["event_time_parsed"] <= conversion["event_time_parsed"]
            ]
            previous_conversion_time = conversion["event_time_parsed"]
            if conversion_date > end:
                continue
            path_events = _contiguous_path(eligible, max_gap)
            if not path_events:
                continue
            if path_events[0]["event_time_parsed"] <= start_boundary:
                continue
            if conversion["event_time_parsed"] - path_events[-1]["event_time_parsed"] > max_gap:
                continue

            path = " > ".join(event["touchpoint"] for event in path_events)
            marketplace = str(conversion.get("marketplace", "")).strip()
            advertiser_id = str(conversion.get("advertiser_id", "")).strip()
            if not marketplace or not advertiser_id:
                raise ValueError("marketplace and advertiser_id are required for CONVERSION")
            key = (marketplace, advertiser_id, path)
            users = int(_number(conversion, "users", integer=True))
            converted_users = int(_number(conversion, "converted_users", integer=True))
            purchase_count = int(_number(conversion, "purchase_count", integer=True))
            revenue = float(_number(conversion, "revenue"))
            aggregate = aggregates.setdefault(
                key,
                {
                    "report_start_date": start.isoformat(),
                    "report_end_date": end.isoformat(),
                    "marketplace": marketplace,
                    "advertiser_id": advertiser_id,
                    "path": path,
                    "users": 0,
                    "converted_users": 0,
                    "purchase_count": 0,
                    "revenue": 0.0,
                },
            )
            aggregate["users"] += users
            aggregate["converted_users"] += converted_users
            aggregate["purchase_count"] += purchase_count
            aggregate["revenue"] += revenue

    rows = []
    for aggregate in aggregates.values():
        aggregate["revenue"] = round(aggregate["revenue"], 2)
        rows.append(aggregate)
    return sorted(rows, key=lambda row: (row["marketplace"], row["advertiser_id"], row["path"]))


PATH_REPORT_FIELDS = [
    "report_start_date",
    "report_end_date",
    "marketplace",
    "advertiser_id",
    "path",
    "users",
    "converted_users",
    "purchase_count",
    "revenue",
]
