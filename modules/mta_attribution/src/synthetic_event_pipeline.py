"""Deterministic synthetic user-event source and privacy-safe derived samples."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import math
import re
from typing import Iterable, Mapping, Sequence

from simulated_touchpoints import (
    ADVERTISER_ID,
    CAMPAIGN_BY_AD_PRODUCT,
    CAMPAIGN_GROUP_ID,
    CURRENCY,
    EXPECTED_TOUCHPOINT_KEYS,
    MARKETPLACE,
    TOUCHPOINT_CATALOG,
    TouchpointSpec,
    historical_entity_for_touchpoint,
    validate_touchpoint_catalog,
)
from touchpoint_key import canonical_amc_touchpoint_key


SYNTHETIC_EVENT_FIELDS = [
    "synthetic_user_id",
    "journey_instance_id",
    "path_cohort_id",
    "event_id",
    "event_type",
    "event_time",
    "touch_position",
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
    "marketplace",
    "advertiser_id",
    "campaign_group_id",
    "campaign_id",
    "ad_group_id",
    "keyword_id",
    "keyword_text",
    "match_type",
    "target_id",
    "audience_id",
    "advertised_asin",
    "sku_id",
    "currency",
    "cost",
    "converted",
    "purchase_count",
    "revenue",
    "new_to_brand_purchase",
]

AMC_EVENT_FIELDS = [
    "journey_id",
    "event_type",
    "event_time",
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
    "marketplace",
    "advertiser_id",
    "users",
    "converted_users",
    "purchase_count",
    "revenue",
    "new_to_brand_purchases",
]

ADS_FIELDS = [
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

ENTITY_AGGREGATE_FIELDS = [
    "report_start_date",
    "report_end_date",
    "marketplace",
    "advertiser_id",
    "touchpoint",
    "campaign_group_id",
    "campaign_id",
    "ad_group_id",
    "keyword_id",
    "keyword_text",
    "match_type",
    "target_id",
    "audience_id",
    "advertised_asin",
    "sku_id",
    "unique_users",
    "journey_count",
    "impressions",
    "clicks",
    "cost",
    "assisted_converted_users",
    "assisted_purchase_count",
    "assisted_revenue",
    "reported_purchases",
    "reported_sales",
]

STANDARD_COHORT_COUNT = 136
SYNTHETIC_USER_POOL_SIZE = 2400
MAX_SYNTHETIC_EVENT_ROWS = 20_000
MAX_OUTCOME_GAP_DAYS = 14

_SPEC_BY_KEY = {spec.key: spec for spec in TOUCHPOINT_CATALOG}


def _as_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _as_datetime(value: object) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _touchpoint_key(row: Mapping[str, object]) -> str:
    return canonical_amc_touchpoint_key(
        row.get("ad_product"),
        row.get("format"),
        row.get("placement"),
        row.get("creative"),
        row.get("interaction_type"),
    )


def _path_indices(cohort_index: int) -> list[int]:
    first = cohort_index % len(TOUCHPOINT_CATALOG)
    batch = cohort_index // len(TOUCHPOINT_CATALOG)
    length = 2 + cohort_index % 3
    candidates = [
        first,
        (first + 1 + batch) % len(TOUCHPOINT_CATALOG),
        (first + 5 + batch * 2) % len(TOUCHPOINT_CATALOG),
        (first + 9 + batch * 3) % len(TOUCHPOINT_CATALOG),
    ]
    result: list[int] = []
    for candidate in candidates:
        while candidate in result:
            candidate = (candidate + 1) % len(TOUCHPOINT_CATALOG)
        result.append(candidate)
    return result[:length]


def _event_cost(spec: TouchpointSpec, seed: int) -> float:
    if spec.interaction_type != spec.billed_interaction:
        return 0.0
    variation = 0.94 + (seed % 7) * 0.02
    unit_price = spec.price if spec.interaction_type == "CLICK" else spec.price / 1000
    # The public Ads and attribution contracts use cent-denominated cost. Keeping
    # every synthetic billed event on that same unit makes all later groupings
    # exactly reconcilable without hidden rounding residuals.
    return round(unit_price * variation, 2)


def _base_row(
    *,
    user_id: str,
    journey_id: str,
    cohort_id: str,
    event_id: str,
    event_type: str,
    when: datetime,
) -> dict[str, object]:
    return {
        field: ""
        for field in SYNTHETIC_EVENT_FIELDS
    } | {
        "synthetic_user_id": user_id,
        "journey_instance_id": journey_id,
        "path_cohort_id": cohort_id,
        "event_id": event_id,
        "event_type": event_type,
        "event_time": _iso(when),
        "marketplace": MARKETPLACE,
        "advertiser_id": ADVERTISER_ID,
        "campaign_group_id": CAMPAIGN_GROUP_ID,
        "currency": CURRENCY,
        "cost": "0.000000",
        "converted": 0,
        "purchase_count": 0,
        "revenue": "0.00",
        "new_to_brand_purchase": 0,
    }


def _touch_row(
    *,
    user_id: str,
    journey_id: str,
    cohort_id: str,
    event_id: str,
    when: datetime,
    position: int,
    spec: TouchpointSpec,
    variant: int,
    seed: int,
) -> dict[str, object]:
    entity = historical_entity_for_touchpoint(spec, variant)
    return _base_row(
        user_id=user_id,
        journey_id=journey_id,
        cohort_id=cohort_id,
        event_id=event_id,
        event_type="TOUCHPOINT",
        when=when,
    ) | {
        "touch_position": position,
        "ad_product": spec.ad_product,
        "format": spec.format_value,
        "placement": "" if spec.placement == "UNSPECIFIED" else spec.placement,
        "creative": "" if spec.creative_key == "UNSPECIFIED" else spec.creative_key,
        "interaction_type": spec.interaction_type,
        **entity,
        "cost": f"{_event_cost(spec, seed):.6f}",
    }


def _outcome_row(
    *,
    user_id: str,
    journey_id: str,
    cohort_id: str,
    event_id: str,
    when: datetime,
    converted: bool,
    purchase_count: int,
    revenue: float,
    new_to_brand_purchase: int,
    sku_id: str,
    advertised_asin: str,
) -> dict[str, object]:
    return _base_row(
        user_id=user_id,
        journey_id=journey_id,
        cohort_id=cohort_id,
        event_id=event_id,
        event_type="OUTCOME",
        when=when,
    ) | {
        "advertised_asin": advertised_asin,
        "sku_id": sku_id,
        "converted": int(converted),
        "purchase_count": purchase_count,
        "revenue": f"{revenue:.2f}",
        "new_to_brand_purchase": new_to_brand_purchase,
    }


def generate_synthetic_user_events(
    report_start_date: str | date,
    report_end_date: str | date,
) -> list[dict[str, object]]:
    """Generate the sole source for every simulated dynamic metric."""
    start = _as_date(report_start_date)
    end = _as_date(report_end_date)
    if start > end:
        raise ValueError("report_start_date must be on or before report_end_date")
    if (end - start).days < 14:
        raise ValueError("synthetic user-event window must contain at least 15 days")
    validate_touchpoint_catalog(TOUCHPOINT_CATALOG)

    standard_row_count = sum(
        (12 + cohort_index % 7) * (len(_path_indices(cohort_index)) + 1)
        for cohort_index in range(STANDARD_COHORT_COUNT)
    )
    coverage_row_count = (end - start).days * len(TOUCHPOINT_CATALOG) * 2
    if standard_row_count + coverage_row_count > MAX_SYNTHETIC_EVENT_ROWS:
        raise ValueError(
            f"synthetic user-event source exceeds {MAX_SYNTHETIC_EVENT_ROWS} rows"
        )

    rows: list[dict[str, object]] = []
    event_number = 0
    journey_number = 0
    available_outcome_offsets = (end - start).days - 4

    for cohort_index in range(STANDARD_COHORT_COUNT):
        cohort_id = f"cohort_{cohort_index + 1:03d}"
        path_specs = [TOUCHPOINT_CATALOG[index] for index in _path_indices(cohort_index)]
        outcome_offset = 5 + (cohort_index * 11) % available_outcome_offsets
        outcome_date = start + timedelta(days=outcome_offset)
        cohort_size = 12 + cohort_index % 7
        for member_index in range(cohort_size):
            journey_number += 1
            user_id = f"SYN_U{1 + (journey_number - 1) % SYNTHETIC_USER_POOL_SIZE:05d}"
            journey_id = f"J_STD_{cohort_index + 1:03d}_{member_index + 1:02d}"
            last_entity: dict[str, str] = {}
            for position, spec in enumerate(path_specs, start=1):
                event_number += 1
                days_before_outcome = len(path_specs) - position + 1
                when = datetime.combine(
                    outcome_date - timedelta(days=days_before_outcome),
                    time(8 + position, (member_index * 7) % 60),
                    tzinfo=timezone.utc,
                )
                variant = (cohort_index + member_index + position) % 2
                last_entity = historical_entity_for_touchpoint(spec, variant)
                rows.append(
                    _touch_row(
                        user_id=user_id,
                        journey_id=journey_id,
                        cohort_id=cohort_id,
                        event_id=f"EVT_{event_number:06d}",
                        when=when,
                        position=position,
                        spec=spec,
                        variant=variant,
                        seed=cohort_index * 101 + member_index * 7 + position,
                    )
                )

            conversion_score = (member_index * 7 + cohort_index * 3) % 10
            converted = conversion_score < 3 + cohort_index % 4
            purchase_count = 0 if not converted else 1 + int(
                (member_index + cohort_index) % 9 == 0
            )
            aov = path_specs[-1].average_order_value * (
                0.90 + ((member_index + cohort_index) % 9) * 0.025
            )
            revenue = 0.0 if not converted else purchase_count * aov
            ntb = int(converted and (member_index + cohort_index) % 4 == 0)
            event_number += 1
            rows.append(
                _outcome_row(
                    user_id=user_id,
                    journey_id=journey_id,
                    cohort_id=cohort_id,
                    event_id=f"EVT_{event_number:06d}",
                    when=datetime.combine(
                        outcome_date,
                        time(18, member_index % 60),
                        tzinfo=timezone.utc,
                    ),
                    converted=converted,
                    purchase_count=purchase_count,
                    revenue=revenue,
                    new_to_brand_purchase=ntb,
                    sku_id=last_entity["sku_id"],
                    advertised_asin=last_entity["advertised_asin"],
                )
            )

    # One non-converting journey for every touchpoint/day after the strict
    # report-start boundary keeps the Ads grid and Null paths representative.
    for day_offset in range(1, (end - start).days + 1):
        event_date = start + timedelta(days=day_offset)
        for spec_index, spec in enumerate(TOUCHPOINT_CATALOG):
            journey_number += 1
            user_id = f"SYN_U{1 + (journey_number - 1) % SYNTHETIC_USER_POOL_SIZE:05d}"
            journey_id = f"J_COV_{event_date:%Y%m%d}_{spec_index + 1:02d}"
            cohort_id = f"coverage_{event_date:%Y%m}_{spec_index + 1:02d}"
            variant = (day_offset + spec_index) % 2
            entity = historical_entity_for_touchpoint(spec, variant)
            event_number += 1
            rows.append(
                _touch_row(
                    user_id=user_id,
                    journey_id=journey_id,
                    cohort_id=cohort_id,
                    event_id=f"EVT_{event_number:06d}",
                    when=datetime.combine(event_date, time(8), tzinfo=timezone.utc),
                    position=1,
                    spec=spec,
                    variant=variant,
                    seed=day_offset * 31 + spec_index,
                )
            )
            event_number += 1
            rows.append(
                _outcome_row(
                    user_id=user_id,
                    journey_id=journey_id,
                    cohort_id=cohort_id,
                    event_id=f"EVT_{event_number:06d}",
                    when=datetime.combine(event_date, time(18), tzinfo=timezone.utc),
                    converted=False,
                    purchase_count=0,
                    revenue=0.0,
                    new_to_brand_purchase=0,
                    sku_id=entity["sku_id"],
                    advertised_asin=entity["advertised_asin"],
                )
            )

    rows.sort(
        key=lambda row: (
            str(row["event_time"]),
            str(row["journey_instance_id"]),
            int(row["touch_position"] or 999),
        )
    )
    validate_synthetic_user_events(rows, start, end)
    return rows


def validate_synthetic_user_events(
    rows: Sequence[Mapping[str, object]],
    report_start_date: str | date,
    report_end_date: str | date,
    max_rows: int = 20_000,
) -> dict[str, int]:
    start = _as_date(report_start_date)
    end = _as_date(report_end_date)
    if not rows:
        raise ValueError("synthetic user-event source must not be empty")
    if len(rows) > max_rows:
        raise ValueError(f"synthetic user-event source exceeds {max_rows} rows")
    event_ids: set[str] = set()
    journeys: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    users: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        if set(row) != set(SYNTHETIC_EVENT_FIELDS):
            raise ValueError(f"synthetic row {row_number}: schema does not match contract")
        missing = [
            field
            for field in (
                "synthetic_user_id",
                "journey_instance_id",
                "path_cohort_id",
                "event_id",
                "event_type",
                "event_time",
                "marketplace",
                "advertiser_id",
                "currency",
            )
            if not str(row.get(field, "")).strip()
        ]
        if missing:
            raise ValueError(f"synthetic row {row_number}: missing {sorted(missing)}")
        event_id = str(row["event_id"])
        if event_id in event_ids:
            raise ValueError(f"synthetic row {row_number}: duplicate event_id {event_id}")
        event_ids.add(event_id)
        when = _as_datetime(row["event_time"])
        if not start <= when.date() <= end:
            raise ValueError(f"synthetic row {row_number}: event_time outside report window")
        event_type = str(row["event_type"]).upper()
        if event_type not in {"TOUCHPOINT", "OUTCOME"}:
            raise ValueError(f"synthetic row {row_number}: invalid event_type {event_type}")
        cost = float(row.get("cost", 0) or 0)
        if not math.isfinite(cost) or cost < 0:
            raise ValueError(
                f"synthetic row {row_number}: cost must be finite and non-negative"
            )
        expected_scope = (MARKETPLACE, ADVERTISER_ID, CURRENCY, CAMPAIGN_GROUP_ID)
        actual_scope = tuple(
            str(row.get(field, ""))
            for field in ("marketplace", "advertiser_id", "currency", "campaign_group_id")
        )
        if actual_scope != expected_scope:
            raise ValueError(f"synthetic row {row_number}: simulation scope is inconsistent")
        if event_type == "TOUCHPOINT":
            key = _touchpoint_key(row)
            if key not in EXPECTED_TOUCHPOINT_KEYS:
                raise ValueError(f"synthetic row {row_number}: unapproved touchpoint {key}")
            spec = _SPEC_BY_KEY[key]
            keyword_id = str(row.get("keyword_id", ""))
            keyword_text = str(row.get("keyword_text", ""))
            match_type = str(row.get("match_type", ""))
            if spec.ad_product in {"SPONSORED_PRODUCTS", "SPONSORED_BRANDS"}:
                if (
                    not keyword_id
                    or not keyword_text
                    or match_type not in {"EXACT", "PHRASE", "BROAD"}
                ):
                    raise ValueError(
                        f"synthetic row {row_number}: search ads require keyword text and match type"
                    )
                if str(row.get("audience_id", "")):
                    raise ValueError(
                        f"synthetic row {row_number}: search ads cannot carry audience_id"
                    )
            elif keyword_id or keyword_text or match_type:
                raise ValueError(
                    f"synthetic row {row_number}: {spec.ad_product} cannot carry keyword fields"
                )
            elif not str(row.get("audience_id", "")):
                raise ValueError(
                    f"synthetic row {row_number}: {spec.ad_product} requires audience_id"
                )
            for field in (
                "campaign_id",
                "ad_group_id",
                "target_id",
                "advertised_asin",
                "sku_id",
            ):
                if not str(row.get(field, "")):
                    raise ValueError(f"synthetic row {row_number}: {field} is required")
            if row["campaign_id"] != CAMPAIGN_BY_AD_PRODUCT[spec.ad_product]:
                raise ValueError(
                    f"synthetic row {row_number}: campaign_id does not match ad_product"
                )
            if not str(row["ad_group_id"]).startswith(f"{row['campaign_id']}_AG"):
                raise ValueError(
                    f"synthetic row {row_number}: ad_group_id does not belong to campaign"
                )
            if spec.interaction_type != spec.billed_interaction and float(row["cost"]) != 0:
                raise ValueError(f"synthetic row {row_number}: non-billed interaction has cost")
            if any(
                float(row.get(field, 0) or 0) != 0
                for field in ("converted", "purchase_count", "revenue")
            ):
                raise ValueError(f"synthetic row {row_number}: touchpoint has outcome metrics")
        else:
            converted = int(row.get("converted", 0) or 0)
            purchases = int(row.get("purchase_count", 0) or 0)
            revenue = float(row.get("revenue", 0) or 0)
            ntb = int(row.get("new_to_brand_purchase", 0) or 0)
            if converted not in {0, 1}:
                raise ValueError(f"synthetic row {row_number}: converted must be 0 or 1")
            if purchases < 0 or ntb < 0 or not math.isfinite(revenue) or revenue < 0:
                raise ValueError(
                    f"synthetic row {row_number}: outcome metrics must be finite and non-negative"
                )
            if converted and (purchases < 1 or revenue <= 0):
                raise ValueError(
                    f"synthetic row {row_number}: converted outcome requires purchases and revenue"
                )
            if not converted and (purchases or revenue or ntb):
                raise ValueError(f"synthetic row {row_number}: non-converted outcome has value")
            if ntb > purchases:
                raise ValueError(
                    f"synthetic row {row_number}: new-to-brand exceeds purchases"
                )
            if float(row.get("cost", 0) or 0) != 0:
                raise ValueError(f"synthetic row {row_number}: outcome event has cost")
            forbidden = (
                "touch_position",
                "ad_product",
                "format",
                "placement",
                "creative",
                "interaction_type",
                "campaign_id",
                "ad_group_id",
                "keyword_id",
                "keyword_text",
                "match_type",
                "target_id",
                "audience_id",
            )
            if any(str(row.get(field, "")) for field in forbidden):
                raise ValueError(
                    f"synthetic row {row_number}: outcome carries touchpoint fields"
                )
        journey_id = str(row["journey_instance_id"])
        journeys[journey_id].append(row)
        users.add(str(row["synthetic_user_id"]))

    for journey_id, journey_rows in journeys.items():
        outcomes = [row for row in journey_rows if row["event_type"] == "OUTCOME"]
        touches = [row for row in journey_rows if row["event_type"] == "TOUCHPOINT"]
        if len(outcomes) != 1 or not touches:
            raise ValueError(
                f"journey {journey_id}: exactly one OUTCOME and at least one TOUCHPOINT required"
            )
        if len({str(row["synthetic_user_id"]) for row in journey_rows}) != 1:
            raise ValueError(f"journey {journey_id}: rows must belong to one user")
        positions = sorted(int(row["touch_position"]) for row in touches)
        if positions != list(range(1, len(positions) + 1)):
            raise ValueError(f"journey {journey_id}: touch_position must be contiguous")
        ordered_touches = sorted(touches, key=lambda row: int(row["touch_position"]))
        ordered_times = [_as_datetime(row["event_time"]) for row in ordered_touches]
        if ordered_times != sorted(ordered_times):
            raise ValueError(f"journey {journey_id}: touch timestamps contradict positions")
        outcome_time = _as_datetime(outcomes[0]["event_time"])
        timeline = [*ordered_times, outcome_time]
        if any(right < left for left, right in zip(timeline, timeline[1:])):
            raise ValueError(f"journey {journey_id}: touchpoint occurs after outcome")
        max_gap = timedelta(days=MAX_OUTCOME_GAP_DAYS)
        if any(right - left > max_gap for left, right in zip(timeline, timeline[1:])):
            raise ValueError(f"journey {journey_id}: path gap exceeds 14 days")
    return {"rows": len(rows), "users": len(users), "journeys": len(journeys)}


def _journeys(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, list[Mapping[str, object]]]:
    result: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        result[str(row["journey_instance_id"])].append(row)
    return result


def derive_amc_touchpoint_events(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Aggregate user journeys into anonymous path cohorts for AMC simulation."""
    if not rows:
        raise ValueError("synthetic user-event source must not be empty")
    cohort_journeys: dict[str, dict[str, list[Mapping[str, object]]]] = defaultdict(dict)
    for journey_id, journey_rows in _journeys(rows).items():
        cohort_id = str(journey_rows[0]["path_cohort_id"])
        if any(str(row["path_cohort_id"]) != cohort_id for row in journey_rows):
            raise ValueError(f"journey {journey_id}: path_cohort_id is inconsistent")
        cohort_journeys[cohort_id][journey_id] = journey_rows

    derived: list[dict[str, object]] = []
    for cohort_id in sorted(cohort_journeys):
        journeys = cohort_journeys[cohort_id]
        cohort_users = {
            str(journey_rows[0]["synthetic_user_id"])
            for journey_rows in journeys.values()
        }
        if len(cohort_users) != len(journeys):
            raise ValueError(
                f"cohort {cohort_id}: one user cannot appear in multiple cohort journeys"
            )
        sequences: dict[str, tuple[str, ...]] = {}
        for journey_id, journey_rows in journeys.items():
            touches = sorted(
                (row for row in journey_rows if row["event_type"] == "TOUCHPOINT"),
                key=lambda row: int(row["touch_position"]),
            )
            sequences[journey_id] = tuple(_touchpoint_key(row) for row in touches)
        if len(set(sequences.values())) != 1:
            raise ValueError(f"cohort {cohort_id}: journeys do not share one touchpoint path")
        sequence = next(iter(sequences.values()))
        for position, touchpoint in enumerate(sequence, start=1):
            position_rows = [
                row
                for journey_rows in journeys.values()
                for row in journey_rows
                if row["event_type"] == "TOUCHPOINT"
                and int(row["touch_position"]) == position
            ]
            if {_touchpoint_key(row) for row in position_rows} != {touchpoint}:
                raise ValueError(f"cohort {cohort_id}: inconsistent touchpoint position")
            representative = min(position_rows, key=lambda row: _as_datetime(row["event_time"]))
            derived.append(
                {field: "" for field in AMC_EVENT_FIELDS}
                | {
                    "journey_id": cohort_id,
                    "event_type": "TOUCHPOINT",
                    "event_time": representative["event_time"],
                    "ad_product": representative["ad_product"],
                    "format": representative["format"],
                    "placement": representative["placement"],
                    "creative": representative["creative"],
                    "interaction_type": representative["interaction_type"],
                }
            )

        outcomes = [
            row
            for journey_rows in journeys.values()
            for row in journey_rows
            if row["event_type"] == "OUTCOME"
        ]
        converted_users = sum(int(row["converted"]) for row in outcomes)
        purchases = sum(int(row["purchase_count"]) for row in outcomes)
        revenue = sum(float(row["revenue"]) for row in outcomes)
        derived.append(
            {field: "" for field in AMC_EVENT_FIELDS}
            | {
                "journey_id": cohort_id,
                "event_type": "CONVERSION",
                "event_time": min(outcomes, key=lambda row: _as_datetime(row["event_time"]))[
                    "event_time"
                ],
                "marketplace": MARKETPLACE,
                "advertiser_id": ADVERTISER_ID,
                "users": len(cohort_users),
                "converted_users": converted_users,
                "purchase_count": purchases,
                "revenue": f"{revenue:.2f}",
                "new_to_brand_purchases": sum(
                    int(row["new_to_brand_purchase"]) for row in outcomes
                ),
            }
        )
    return derived


def _platform_outcome_owners(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    owners: dict[str, Mapping[str, object]] = {}
    for journey_id, journey_rows in _journeys(rows).items():
        outcome = next(row for row in journey_rows if row["event_type"] == "OUTCOME")
        if not int(outcome["converted"]):
            continue
        clicks = [
            row
            for row in journey_rows
            if row["event_type"] == "TOUCHPOINT"
            and row["interaction_type"] == "CLICK"
            and _as_datetime(row["event_time"]) <= _as_datetime(outcome["event_time"])
        ]
        if clicks:
            owner = max(clicks, key=lambda row: _as_datetime(row["event_time"]))
            if (
                _as_datetime(outcome["event_time"]) - _as_datetime(owner["event_time"])
                <= timedelta(days=MAX_OUTCOME_GAP_DAYS)
            ):
                owners[journey_id] = owner
    return owners


def derive_amazon_ads_rows(
    rows: Sequence[Mapping[str, object]],
    report_start_date: str | date,
    report_end_date: str | date,
) -> list[dict[str, object]]:
    start = _as_date(report_start_date)
    end = _as_date(report_end_date)
    if start > end:
        raise ValueError("report_start_date must be on or before report_end_date")
    if not rows:
        raise ValueError("synthetic user-event source must not be empty")
    metrics = {
        (start + timedelta(days=offset), spec.key): {
            "impressions": 0,
            "clicks": 0,
            "cost": Decimal("0"),
            "purchases": 0,
            "sales": 0.0,
        }
        for offset in range((end - start).days + 1)
        for spec in TOUCHPOINT_CATALOG
    }
    journeys = _journeys(rows)
    for row in rows:
        if row["event_type"] != "TOUCHPOINT":
            continue
        when = _as_datetime(row["event_time"])
        if not start <= when.date() <= end:
            continue
        metric = metrics[(when.date(), _touchpoint_key(row))]
        if row["interaction_type"] == "CLICK":
            metric["clicks"] += 1
        else:
            metric["impressions"] += 1
        metric["cost"] += Decimal(str(row["cost"]))

    for journey_id, owner in _platform_outcome_owners(rows).items():
        outcome = next(row for row in journeys[journey_id] if row["event_type"] == "OUTCOME")
        owner_date = _as_datetime(owner["event_time"]).date()
        outcome_date = _as_datetime(outcome["event_time"]).date()
        if not start <= owner_date <= end or not start <= outcome_date <= end:
            continue
        metric = metrics[(owner_date, _touchpoint_key(owner))]
        metric["purchases"] += int(outcome["purchase_count"])
        metric["sales"] += float(outcome["revenue"])

    result: list[dict[str, object]] = []
    for (report_date, touchpoint), metric in sorted(metrics.items()):
        spec = _SPEC_BY_KEY[touchpoint]
        result.append(
            {
                "reportDate": report_date.isoformat(),
                "marketplace": MARKETPLACE,
                "accountId": ADVERTISER_ID,
                "adProduct": spec.ad_product,
                "adType": spec.ad_type,
                "creativeType": spec.creative_type,
                "inventoryType": spec.inventory_type,
                "placement": "" if spec.placement == "UNSPECIFIED" else spec.placement,
                "interaction_type": spec.interaction_type,
                "cost_type": spec.cost_type,
                "normalizedTouchpoint": touchpoint,
                "currencyCode": CURRENCY,
                "impressions": metric["impressions"],
                "clicks": metric["clicks"],
                "cost": round(float(metric["cost"]), 2),
                "purchases": metric["purchases"],
                "sales": round(metric["sales"], 2),
            }
        )
    return result


def _entity_key(row: Mapping[str, object]) -> tuple[str, ...]:
    return (
        _touchpoint_key(row),
        str(row["campaign_group_id"]),
        str(row["campaign_id"]),
        str(row["ad_group_id"]),
        str(row["keyword_id"]),
        str(row["keyword_text"]),
        str(row["match_type"]),
        str(row["target_id"]),
        str(row["audience_id"]),
        str(row["advertised_asin"]),
        str(row["sku_id"]),
    )


def derive_touchpoint_entity_aggregate(
    rows: Sequence[Mapping[str, object]],
    report_start_date: str | date,
    report_end_date: str | date,
    privacy_min_users: int,
) -> list[dict[str, object]]:
    if privacy_min_users < 1:
        raise ValueError("privacy_min_users must be positive")
    start = _as_date(report_start_date)
    end = _as_date(report_end_date)
    if start > end:
        raise ValueError("report_start_date must be on or before report_end_date")
    if not rows:
        raise ValueError("synthetic user-event source must not be empty")
    states: dict[tuple[str, ...], dict[str, object]] = {}
    journeys = _journeys(rows)
    for row in rows:
        if row["event_type"] != "TOUCHPOINT":
            continue
        when = _as_datetime(row["event_time"])
        if not start <= when.date() <= end:
            continue
        key = _entity_key(row)
        state = states.setdefault(
            key,
            {
                "users": set(),
                "journeys": set(),
                "journey_touch_times": {},
                "impressions": 0,
                "clicks": 0,
                "cost": Decimal("0"),
                "reported_purchases": 0,
                "reported_sales": 0.0,
            },
        )
        state["users"].add(str(row["synthetic_user_id"]))
        state["journeys"].add(str(row["journey_instance_id"]))
        journey_id = str(row["journey_instance_id"])
        prior_time = state["journey_touch_times"].get(journey_id)
        if prior_time is None or when > prior_time:
            state["journey_touch_times"][journey_id] = when
        state["impressions"] += int(row["interaction_type"] == "IMPRESSION")
        state["clicks"] += int(row["interaction_type"] == "CLICK")
        state["cost"] += Decimal(str(row["cost"]))

    for journey_id, owner in _platform_outcome_owners(rows).items():
        outcome = next(row for row in journeys[journey_id] if row["event_type"] == "OUTCOME")
        owner_time = _as_datetime(owner["event_time"])
        outcome_time = _as_datetime(outcome["event_time"])
        if not start <= owner_time.date() <= end or not start <= outcome_time.date() <= end:
            continue
        state = states.get(_entity_key(owner))
        if state is None:
            continue
        state["reported_purchases"] += int(outcome["purchase_count"])
        state["reported_sales"] += float(outcome["revenue"])

    output: list[dict[str, object]] = []
    for key in sorted(states):
        state = states[key]
        if len(state["users"]) < privacy_min_users:
            continue
        outcomes = []
        for journey_id in state["journeys"]:
            outcome = next(
                row for row in journeys[journey_id] if row["event_type"] == "OUTCOME"
            )
            outcome_time = _as_datetime(outcome["event_time"])
            touch_time = state["journey_touch_times"][journey_id]
            if (
                start <= outcome_time.date() <= end
                and timedelta(0)
                <= outcome_time - touch_time
                <= timedelta(days=MAX_OUTCOME_GAP_DAYS)
            ):
                outcomes.append(outcome)
        (
            touchpoint,
            campaign_group_id,
            campaign_id,
            ad_group_id,
            keyword_id,
            keyword_text,
            match_type,
            target_id,
            audience_id,
            advertised_asin,
            sku_id,
        ) = key
        output.append(
            {
                "report_start_date": start.isoformat(),
                "report_end_date": end.isoformat(),
                "marketplace": MARKETPLACE,
                "advertiser_id": ADVERTISER_ID,
                "touchpoint": touchpoint,
                "campaign_group_id": campaign_group_id,
                "campaign_id": campaign_id,
                "ad_group_id": ad_group_id,
                "keyword_id": keyword_id,
                "keyword_text": keyword_text,
                "match_type": match_type,
                "target_id": target_id,
                "audience_id": audience_id,
                "advertised_asin": advertised_asin,
                "sku_id": sku_id,
                "unique_users": len(state["users"]),
                "journey_count": len(state["journeys"]),
                "impressions": state["impressions"],
                "clicks": state["clicks"],
                "cost": round(float(state["cost"]), 2),
                "assisted_converted_users": len(
                    {
                        str(row["synthetic_user_id"])
                        for row in outcomes
                        if int(row["converted"])
                    }
                ),
                "assisted_purchase_count": sum(int(row["purchase_count"]) for row in outcomes),
                "assisted_revenue": round(sum(float(row["revenue"]) for row in outcomes), 2),
                "reported_purchases": state["reported_purchases"],
                "reported_sales": round(state["reported_sales"], 2),
            }
        )
    return output


def _normalized_rows(
    rows: Iterable[Mapping[str, object]], fields: Sequence[str]
) -> list[tuple[str, ...]]:
    return [tuple(str(row.get(field, "")) for field in fields) for row in rows]


def validate_no_user_identifiers(
    label: str,
    rows: Sequence[Mapping[str, object]],
) -> None:
    for row_number, row in enumerate(rows, start=2):
        if any(
            field == "user_id" or field.endswith("_user_id")
            for field in (str(key).lower() for key in row)
        ):
            raise ValueError(f"{label} row {row_number} contains a user identifier field")
        if any(re.search(r"SYN_U\d{5}", str(value)) for value in row.values()):
            raise ValueError(f"{label} row {row_number} leaks a synthetic user identifier")


def validate_derivations(
    source_rows: Sequence[Mapping[str, object]],
    amc_rows: Sequence[Mapping[str, object]],
    ads_rows: Sequence[Mapping[str, object]],
    entity_rows: Sequence[Mapping[str, object]],
    report_start_date: str | date,
    report_end_date: str | date,
    privacy_min_users: int,
    max_rows: int = 20_000,
) -> dict[str, int]:
    source_summary = validate_synthetic_user_events(
        source_rows, report_start_date, report_end_date, max_rows
    )
    expected_amc = derive_amc_touchpoint_events(source_rows)
    expected_ads = derive_amazon_ads_rows(source_rows, report_start_date, report_end_date)
    expected_entities = derive_touchpoint_entity_aggregate(
        source_rows, report_start_date, report_end_date, privacy_min_users
    )
    comparisons = (
        ("AMC events", amc_rows, expected_amc, AMC_EVENT_FIELDS),
        ("Amazon Ads", ads_rows, expected_ads, ADS_FIELDS),
        ("entity aggregate", entity_rows, expected_entities, ENTITY_AGGREGATE_FIELDS),
    )
    for label, actual, expected, fields in comparisons:
        if any(set(row) != set(fields) for row in actual):
            raise ValueError(f"{label} schema does not match its contract")
        if _normalized_rows(actual, fields) != _normalized_rows(expected, fields):
            raise ValueError(f"{label} is not a deterministic derivation of source events")
        validate_no_user_identifiers(label, actual)
    if any(int(row["unique_users"]) < privacy_min_users for row in entity_rows):
        raise ValueError("entity aggregate violates simulated privacy threshold")
    source_cost = sum(
        (Decimal(str(row["cost"])) for row in source_rows), Decimal("0")
    )
    ads_cost = sum((Decimal(str(row["cost"])) for row in ads_rows), Decimal("0"))
    if source_cost != ads_cost:
        raise ValueError("Amazon Ads cost does not reconcile to source events")
    source_impressions = sum(
        row["event_type"] == "TOUCHPOINT"
        and row["interaction_type"] == "IMPRESSION"
        for row in source_rows
    )
    source_clicks = sum(
        row["event_type"] == "TOUCHPOINT" and row["interaction_type"] == "CLICK"
        for row in source_rows
    )
    if source_impressions != sum(int(row["impressions"]) for row in ads_rows):
        raise ValueError("Amazon Ads impressions do not reconcile to source events")
    if source_clicks != sum(int(row["clicks"]) for row in ads_rows):
        raise ValueError("Amazon Ads clicks do not reconcile to source events")
    source_touch_count = sum(row["event_type"] == "TOUCHPOINT" for row in source_rows)
    published_entity_touch_count = sum(
        int(row["impressions"]) + int(row["clicks"]) for row in entity_rows
    )
    if published_entity_touch_count == source_touch_count:
        entity_cost = sum(
            (Decimal(str(row["cost"])) for row in entity_rows), Decimal("0")
        )
        if entity_cost != source_cost:
            raise ValueError("entity aggregate cost does not reconcile to source events")
    amc_outcomes = [row for row in amc_rows if row["event_type"] == "CONVERSION"]
    if sum(int(row["users"]) for row in amc_outcomes) != source_summary["journeys"]:
        raise ValueError("AMC cohort users do not reconcile to source journeys")
    return {
        **source_summary,
        "amc_rows": len(amc_rows),
        "ads_rows": len(ads_rows),
        "entity_rows": len(entity_rows),
    }
