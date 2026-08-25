"""Derive the master-data catalogue from the committed platform reports.

The Budget Manager's entity sections -- Ad Providers, Products, Campaigns, Ad
Groups, Touchpoints, Product Economics -- describe the account the reports
were pulled from. Those reports are tracked, so the catalogue they imply is
available in every deployment and does not depend on an optional sidecar being
configured.

Derivation rather than a second tracked file is deliberate: a catalogue
committed beside the reports would be free to disagree with them; one read out
of the reports cannot. Where a report does not carry a field -- a Product's
category, a unit price, a Campaign's baseline budget -- the field stays None
rather than being invented, and the interface renders it as missing.

Data flow:
    modules/&#42;/data/simulated/&#42;.csv -> here -> backend/repository/research.py
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

#: The four Amazon ad products are the vocabulary `mta_common` defines for
#: `Provider.AMAZON_ADS`; anything else is reported under `GENERIC` rather than
#: being dropped, so an added provider surfaces instead of vanishing.
AMAZON_AD_PRODUCTS = frozenset(
    {"SPONSORED_PRODUCTS", "SPONSORED_BRANDS", "SPONSORED_DISPLAY", "AMAZON_DSP"}
)


def _total(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    """Sum a numeric column across rows, treating blanks as zero."""
    running = 0.0
    for row in rows:
        try:
            running += float(row.get(field) or 0)
        except (TypeError, ValueError):
            continue
    return running


def _distinct(rows: Sequence[Mapping[str, Any]], field: str) -> list:
    """Distinct non-empty values of `field`, in first-seen order."""
    seen: list = []
    for row in rows:
        value = row.get(field)
        if value not in (None, "") and value not in seen:
            seen.append(value)
    return seen


def _round(value: float, digits: int) -> float:
    """Round without carrying float noise into the interface."""
    return round(value, digits)


def _split_key(key: str) -> dict:
    """The five-segment touchpoint key's parts.

    `UNSPECIFIED` is the pipeline's marker for a segment the platform does not
    report, and is mapped back to None so the interface shows it as absent
    rather than as a literal value the account actually uses.
    """
    segments = str(key).split(":")
    segments += [None] * (5 - len(segments))
    ad_product, fmt, placement, creative, interaction = segments[:5]

    def clean(value):
        return value if value and value != "UNSPECIFIED" else None

    return {
        "ad_product": ad_product or None,
        "format": clean(fmt),
        "placement": clean(placement),
        "creative": clean(creative),
        "interaction_type": interaction or None,
    }


def _provider_of(ad_product: Any) -> str:
    """The provider a five-segment key belongs to."""
    return "AMAZON_ADS" if ad_product in AMAZON_AD_PRODUCTS else "GENERIC"


def _availability(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    """`AVAILABLE` when any row reports the segment, `NOT_PROVIDED` when none do."""
    return "AVAILABLE" if any(row.get(field) for row in rows) else "NOT_PROVIDED"


def derive_master_data(
    ads_rows: Sequence[Mapping[str, Any]],
    bridge_rows: Sequence[Mapping[str, Any]],
    request: Mapping[str, Any] | None = None,
) -> dict:
    """Build the catalogue.

    Returns the same shape the research sidecar and the database produce, so
    the views cannot tell which source filled it.
    """
    request = request or {}
    touchpoints = _derive_touchpoints(ads_rows)
    campaigns = _derive_campaigns(bridge_rows, touchpoints, request)
    # The account reports one currency; it is read from the data rather than
    # assumed, so a non-USD account is not silently relabelled.
    currencies = _distinct(ads_rows, "currency")
    currency = (
        currencies[0]
        if currencies
        else (request.get("campaign_group") or {}).get("currency")
    )
    return {
        "providers": _derive_providers(touchpoints),
        "products": _derive_products(bridge_rows),
        "campaigns": campaigns,
        "adGroups": _derive_ad_groups(bridge_rows),
        "touchpoints": touchpoints,
        "productEconomics": _derive_product_economics(bridge_rows, currency),
        "campaignProductLinks": _derive_campaign_product_links(bridge_rows),
    }


def _derive_touchpoints(ads_rows: Sequence[Mapping[str, Any]]) -> list[dict]:
    """One record per distinct five-segment key, with its observed economics.

    Cost per click and cost per thousand impressions are computed from the
    report's own totals rather than assumed, and each is reported only for the
    billing type that produced it: a cost-per-mille touchpoint has no
    meaningful cost per click even when a stray click was recorded against it.
    """
    by_key: dict[str, list] = {}
    for row in ads_rows:
        key = row.get("touchpoint") or row.get("normalizedTouchpoint")
        if not key:
            continue
        by_key.setdefault(key, []).append(row)

    by_identifier: dict[str, dict] = {}
    for key, rows in by_key.items():
        parts = _split_key(key)
        # The identifier drops the interaction segment: IMPRESSION and CLICK on
        # one placement are two interactions of a single touchpoint, which is
        # the grouping `supported_interactions` exists to express.
        identifier = ":".join(
            [
                str(parts["ad_product"]),
                parts["format"] or "UNSPECIFIED",
                parts["placement"] or "UNSPECIFIED",
                parts["creative"] or "UNSPECIFIED",
            ]
        )
        record = by_identifier.get(identifier) or {
            "identifier": identifier,
            "provider": _provider_of(parts["ad_product"]),
            "ad_product": parts["ad_product"],
            "format": parts["format"],
            "placement": parts["placement"],
            "placement_availability": (
                "AVAILABLE" if parts["placement"] else "NOT_PROVIDED"
            ),
            "creative": parts["creative"],
            "creative_availability": (
                "AVAILABLE" if parts["creative"] else "NOT_PROVIDED"
            ),
            "interaction_type_availability": "AVAILABLE",
            "supported_interactions": [],
            "impression_enabled": False,
            "click_enabled": False,
            "billing_type": None,
            "cost_per_click": None,
            "cost_per_thousand_impressions": None,
            "base_impressions": None,
            "click_through_rate": None,
            "platform_conversion_rate": None,
            "conversion_log_odds_effect": None,
            "compatibility_keys": [],
            "active": True,
            "_billed": {},
            "_totals": {"impressions": 0.0, "clicks": 0.0, "cost": 0.0},
        }

        interaction = parts["interaction_type"]
        if interaction and interaction not in record["supported_interactions"]:
            record["supported_interactions"].append(interaction)
        record["impression_enabled"] = "IMPRESSION" in record["supported_interactions"]
        record["click_enabled"] = "CLICK" in record["supported_interactions"]
        record["compatibility_keys"].append(key)

        # One touchpoint is commonly billed both ways -- per click on its
        # clicks and per mille on its impressions -- so cost is accumulated
        # against the billing type that produced it rather than against the
        # touchpoint as a whole. Dividing a mixed total by either denominator
        # would report a rate the platform never charged.
        for row in rows:
            cost_type = row.get("cost_type")
            if not cost_type:
                continue
            bucket = record["_billed"].setdefault(
                cost_type, {"cost": 0.0, "clicks": 0.0, "impressions": 0.0}
            )
            bucket["cost"] += float(row.get("cost") or 0)
            bucket["clicks"] += float(row.get("clicks") or 0)
            bucket["impressions"] += float(row.get("impressions") or 0)

        record["_totals"]["impressions"] += _total(rows, "impressions")
        record["_totals"]["clicks"] += _total(rows, "clicks")
        record["_totals"]["cost"] += _total(rows, "cost")
        by_identifier[identifier] = record

    finished = []
    for record in by_identifier.values():
        billed = record.pop("_billed")
        totals = record.pop("_totals")
        per_click = billed.get("CPC")
        per_mille = billed.get("CPM")
        record.update(
            {
                # Both types when the platform bills both, so the row states
                # what it is rather than naming one and hiding the other.
                "billing_type": " + ".join(sorted(billed)) if billed else None,
                # A rate only where cost was actually charged against that
                # denominator. An impression row that delivered volume at no
                # recorded cost yields no rate rather than a rate of zero,
                # which would read as "free".
                "cost_per_click": (
                    _round(per_click["cost"] / per_click["clicks"], 4)
                    if per_click and per_click["cost"] > 0 and per_click["clicks"] > 0
                    else None
                ),
                "cost_per_thousand_impressions": (
                    _round((per_mille["cost"] / per_mille["impressions"]) * 1000, 4)
                    if per_mille
                    and per_mille["cost"] > 0
                    and per_mille["impressions"] > 0
                    else None
                ),
                "observed_impressions": int(totals["impressions"]),
                "observed_clicks": int(totals["clicks"]),
                "observed_cost": _round(totals["cost"], 2),
                # Deliberately not derived. The report records impressions and
                # clicks in separate per-interaction rows that share no
                # denominator, so dividing one by the other does not produce
                # this touchpoint's click-through rate; the observed counts
                # above are what the platform actually states.
                "click_through_rate": None,
                # JavaScript's nullish fallback preserves a measured zero.
                # Do the same here: zero means the report observed no
                # impressions, whereas None means the source had no field.
                "base_impressions": int(totals["impressions"]),
            }
        )
        finished.append(record)
    return finished


def _derive_providers(touchpoints: Sequence[Mapping[str, Any]]) -> list[dict]:
    """One record per provider actually present in the reports."""
    by_provider: dict[str, list] = {}
    for touchpoint in touchpoints:
        by_provider.setdefault(touchpoint["provider"], []).append(touchpoint)
    return [
        {
            "provider": provider,
            "supported_ad_products": _distinct(rows, "ad_product"),
            "format_availability": _availability(rows, "format"),
            "placement_availability": _availability(rows, "placement"),
            "creative_availability": _availability(rows, "creative"),
            "interaction_type_availability": "AVAILABLE",
            "active": True,
        }
        for provider, rows in by_provider.items()
    ]


def _derive_products(bridge_rows: Sequence[Mapping[str, Any]]) -> list[dict]:
    """One record per advertised stock-keeping unit.

    The reports identify a product by its Amazon Standard Identification Number
    and its stock-keeping unit and carry nothing else about it. Those fields
    are present and None, which is what lets the Form editor show the whole
    shape of a Product while being honest that the report does not describe it.
    """
    by_sku: dict[str, dict] = {}
    for row in bridge_rows:
        sku = row.get("sku_id")
        if not sku or sku in by_sku:
            continue
        by_sku[sku] = {
            "product_id": sku,
            "name": None,
            "sku_id": sku,
            "advertised_asin": row.get("advertised_asin"),
            "category": None,
            "brand": None,
            "inventory_units": None,
            "salable": None,
            "status": "ADVERTISED",
        }
    return list(by_sku.values())


def _derive_campaigns(
    bridge_rows: Sequence[Mapping[str, Any]],
    touchpoints: Sequence[Mapping[str, Any]],
    request: Mapping[str, Any],
) -> list[dict]:
    """One record per Campaign, with the ad product it runs and its reach.

    `baseline_daily_budget` comes from the strategy request when that artifact
    names one, and is otherwise None: the platform report records spend, not
    the budget cap that governed it, and presenting observed spend as a budget
    would misstate what the number is.
    """
    declared = {
        item.get("campaign_id"): item for item in (request.get("campaigns") or [])
    }
    ad_product_of = {item["identifier"]: item["ad_product"] for item in touchpoints}

    by_campaign: dict[str, list] = {}
    for row in bridge_rows:
        campaign_id = row.get("campaign_id")
        if not campaign_id:
            continue
        by_campaign.setdefault(campaign_id, []).append(row)

    campaigns = []
    for campaign_id, rows in by_campaign.items():
        from_request = declared.get(campaign_id) or {}
        # The Campaign's ad product is whichever its touchpoints report; the
        # reports keep one ad product per Campaign, and the first is taken
        # rather than a guess if that ever stops holding.
        observed = _distinct(
            [
                {
                    "ad_product": ad_product_of.get(
                        ":".join(str(row.get("touchpoint") or "").split(":")[:4])
                    )
                }
                for row in rows
            ],
            "ad_product",
        )
        ad_product = from_request.get("ad_product") or (observed[0] if observed else None)
        campaigns.append(
            {
                "campaign_id": campaign_id,
                "campaign_name": from_request.get("campaign_name"),
                "campaign_group_id": rows[0].get("campaign_group_id"),
                "provider": _provider_of(ad_product),
                "ad_product": ad_product,
                "marketplace": rows[0].get("marketplace"),
                "baseline_daily_budget": from_request.get("baseline_daily_budget"),
                "observed_cost": _round(_total(rows, "cost"), 2),
                "status": from_request.get("status"),
            }
        )
    return campaigns


def _derive_ad_groups(bridge_rows: Sequence[Mapping[str, Any]]) -> list[dict]:
    """One record per Ad Group, with the targeting it carries.

    `initial_daily_budget` is left None: an Ad Group's budget is what the
    recommendation proposes, not something the historical report states, and
    the Budget Manager shows the proposal in its own section.
    """
    by_ad_group: dict[str, list] = {}
    for row in bridge_rows:
        ad_group_id = row.get("ad_group_id")
        if not ad_group_id:
            continue
        by_ad_group.setdefault(ad_group_id, []).append(row)

    return [
        {
            "ad_group_id": ad_group_id,
            "name": None,
            "campaign_id": rows[0].get("campaign_id"),
            "keyword_count": len(_distinct(rows, "keyword_id")),
            "target_count": len(_distinct(rows, "target_id")),
            "audience_count": len(_distinct(rows, "audience_id")),
            "sku_count": len(_distinct(rows, "sku_id")),
            "allocation_basis": None,
            "budget_seed_share": None,
            "initial_daily_budget": None,
            "status": None,
        }
        for ad_group_id, rows in by_ad_group.items()
    ]


def _derive_product_economics(
    bridge_rows: Sequence[Mapping[str, Any]], currency: Any
) -> list[dict]:
    """Per-product unit economics, as far as the reports actually establish them.

    Attributed revenue divided by attributed purchases gives an observed
    average selling price, which is a real measurement of the account. Cost of
    goods and the variable costs beneath it are not in any advertising report
    -- they come from the merchant's own books -- so they stay None, and the
    contribution margin that depends on them stays None with them rather than
    being computed from a cost silently assumed to be zero. `margin_source` is
    therefore left unset: nothing here sourced a margin.
    """
    by_sku: dict[str, dict] = {}
    for row in bridge_rows:
        sku = row.get("sku_id")
        if not sku:
            continue
        bucket = by_sku.setdefault(sku, {"revenue": 0.0, "purchases": 0.0})
        bucket["revenue"] += float(row.get("assisted_revenue") or 0)
        bucket["purchases"] += float(row.get("assisted_purchase_count") or 0)

    return [
        {
            "product_id": sku,
            "currency": currency,
            "unit_price": (
                _round(totals["revenue"] / totals["purchases"], 2)
                if totals["purchases"] > 0
                else None
            ),
            "unit_cogs": None,
            "variable_cost_per_unit": None,
            "variable_fulfillment_cost_per_unit": None,
            "variable_platform_fee_per_unit": None,
            "other_variable_cost_per_unit": None,
            "unit_contribution_margin": None,
            "margin_source": None,
            "observed_revenue": _round(totals["revenue"], 2),
            "observed_purchases": totals["purchases"],
        }
        for sku, totals in by_sku.items()
    ]


def _derive_campaign_product_links(
    bridge_rows: Sequence[Mapping[str, Any]],
) -> list[dict]:
    """Which Products each Campaign advertised, as observed in the reports."""
    pairs: set[tuple] = set()
    links = []
    for row in bridge_rows:
        campaign_id = row.get("campaign_id")
        sku = row.get("sku_id")
        if not campaign_id or not sku:
            continue
        if (campaign_id, sku) in pairs:
            continue
        pairs.add((campaign_id, sku))
        links.append({"campaign_id": campaign_id, "product_id": sku})
    return links
