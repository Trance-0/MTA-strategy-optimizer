"""Bidirectional bridge between today's Amazon-specific shapes and the canonical model.

This is the only module that imports from ``modules.mta_attribution`` or
``modules.mta_standard``. Every existing algorithm keeps reading and writing
its native shape (the five-segment touchpoint key, ``AttributionResult``,
``TouchpointSpend``, ``StandardAttributionRow``, ``strategy_request.json``'s
Campaign/Ad-Group JSON shapes); this module only adapts between those shapes
and the canonical dataclasses, and reuses the existing validators
(``touchpoint_key.canonicalize_touchpoint_key``,
``touchpoint_adapter.canonicalize_four_segment_key``,
``touchpoint_adapter.SimulatorConfig``) rather than restating their rules.

Lossy conversions, documented once here rather than per function:

- The five-segment key's ``UNSPECIFIED`` placeholder collapses whatever the
  source actually meant (not applicable, not provided, unknown, redacted)
  into a single legacy sentinel. Adapting a legacy ``UNSPECIFIED`` component
  into the canonical model can therefore only produce
  ``FieldAvailability.NOT_PROVIDED``, never ``NOT_APPLICABLE``, ``UNKNOWN``,
  or ``REDACTED`` — those three states have no legacy representation to
  adapt from.
- A four-segment MTA-SIM key carries no ``interaction_type`` at all.
  Adapting one without a ``SimulatorConfig`` therefore always produces
  ``interaction_type=None`` with ``FieldAvailability.NOT_PROVIDED``; this
  module never guesses the interaction type from delivery metrics, matching
  ``touchpoint_adapter.py``'s existing policy of rejecting rather than
  inferring a missing cost type.
- Projecting a canonical ``Touchpoint`` back to a five-segment key
  (:func:`touchpoint_to_five_segment_key`) requires ``interaction_type`` to
  be present, because the legacy key format has no representation for a
  touchpoint whose interaction type is inapplicable or unknown; such a
  ``Touchpoint`` cannot be projected and the function raises rather than
  silently choosing a default.
- ``AttributionResult`` reports three outcomes (``converted_users``,
  ``purchase_count``, ``revenue``) on one object; adapting it produces three
  ``AttributionEvidence`` records, one per outcome, since the canonical
  shape is one evidence row per outcome (matching ``StandardAttributionRow``,
  which already reports one outcome per row).
- ``StandardAttributionRow`` carries no ``advertiser_id`` or ``currency``;
  callers must supply the ``ReportingScope`` those fields come from
  separately. This module only cross-checks the row's ``marketplace`` and
  report window against the given scope; it never fabricates the missing
  fields.
- Adapting a ``strategy_request.json`` Campaign Group into a
  ``BudgetObservation`` can only ever populate ``configured_budget`` (from
  ``campaign_budget_seed``, itself only present once a budget baseline is
  given). No field in ``modules/mta_strategy_recommendation`` today
  represents actual spend, so ``actual_spend`` is always left ``None``.
  ``BudgetUsagePolicy`` is not represented in that schema either, so
  :func:`budget_constraints_from_campaign_output` requires the caller to
  supply one explicitly rather than defaulting or inferring it.
"""

from __future__ import annotations

from typing import Mapping

from modules.mta_attribution.src.attribution_contract import (
    AttributionResult,
    TouchpointSpend,
)
from modules.mta_attribution.src.touchpoint_key import (
    UNSPECIFIED,
    canonical_touchpoint_key,
    canonicalize_touchpoint_key,
)
from modules.mta_standard.src.output_contract import StandardAttributionRow
from modules.mta_standard.src.touchpoint_adapter import (
    SimulatorConfig,
    canonicalize_four_segment_key,
)

from .attribution_evidence import AttributionEvidence
from .budget import BudgetConstraints, BudgetObservation
from .campaign import AdGroup, Campaign
from .delivery import DeliveryObservation
from .enums import BudgetUsagePolicy, FieldAvailability, Provider
from .outcome import OutcomeObservation
from .reporting_scope import ReportingScope
from .touchpoint import Touchpoint, TouchpointFieldAvailability


def _optional_component(value: str) -> tuple[str | None, FieldAvailability]:
    """Map a legacy component to (value, availability), collapsing UNSPECIFIED.

    Args:
        value: A placement or creative component already split out of a
            canonicalized key.

    Returns:
        tuple[str | None, FieldAvailability]: ``(None, NOT_PROVIDED)`` when
        the legacy component is the ``UNSPECIFIED`` sentinel, otherwise
        ``(value, AVAILABLE)``.
    """
    if value == UNSPECIFIED:
        return None, FieldAvailability.NOT_PROVIDED
    return value, FieldAvailability.AVAILABLE


def touchpoint_from_five_segment_key(
    key: object, *, provider: Provider = Provider.AMAZON_ADS
) -> Touchpoint:
    """Adapt an existing canonical five-segment key into a Touchpoint.

    Args:
        key: A ``AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`` key,
            already canonicalizable by
            ``touchpoint_key.canonicalize_touchpoint_key``.
        provider: The provider this key was reported by. Defaults to
            ``AMAZON_ADS``, the only provider this key format is defined
            for today.

    Returns:
        Touchpoint: The canonical touchpoint. ``interaction_type`` is always
        populated, since the five-segment key requires it.

    Raises:
        ValueError: if ``key`` is not a valid five-segment key.
    """
    canonical = canonicalize_touchpoint_key(key)
    ad_product, format_value, placement, creative, interaction_type = canonical.split(":")
    placement_value, placement_availability = _optional_component(placement)
    creative_value, creative_availability = _optional_component(creative)
    return Touchpoint(
        provider=provider,
        ad_product=ad_product,
        format=format_value,
        placement=placement_value,
        creative=creative_value,
        interaction_type=interaction_type,
        field_availability=TouchpointFieldAvailability(
            placement=placement_availability,
            creative=creative_availability,
            interaction_type=FieldAvailability.AVAILABLE,
        ),
    )


def touchpoint_to_five_segment_key(touchpoint: Touchpoint) -> str:
    """Project a canonical Touchpoint back to the legacy five-segment key.

    Args:
        touchpoint: The touchpoint to project. Missing ``placement`` and
            ``creative`` are rendered as the legacy ``UNSPECIFIED``
            placeholder, regardless of which of the five
            ``FieldAvailability`` states caused the field to be missing —
            the legacy format cannot distinguish them.

    Returns:
        str: The canonical five-segment key.

    Raises:
        ValueError: if ``touchpoint.interaction_type`` is ``None``, since
            the legacy key format has no representation for a touchpoint
            whose interaction type is inapplicable or unknown.
    """
    if touchpoint.interaction_type is None:
        raise ValueError(
            "touchpoint has no interaction_type and cannot be projected to a "
            "five-segment key"
        )
    return canonical_touchpoint_key(
        touchpoint.ad_product,
        touchpoint.format,
        touchpoint.placement,
        touchpoint.creative,
        touchpoint.interaction_type,
    )


def touchpoint_from_four_segment_key(
    key: object, *, provider: Provider = Provider.AMAZON_ADS
) -> Touchpoint:
    """Adapt an MTA-SIM four-segment key into a Touchpoint.

    Args:
        key: A ``AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE`` key, already
            canonicalizable by
            ``touchpoint_adapter.canonicalize_four_segment_key``.
        provider: The provider this key was reported by.

    Returns:
        Touchpoint: The canonical touchpoint, with ``interaction_type=None``
        and ``FieldAvailability.NOT_PROVIDED`` for it, since a four-segment
        key carries no interaction type and none is guessed here. Use
        :func:`touchpoint_from_five_segment_key` on
        ``SimulatorConfig.to_five_segment(key)`` instead when a
        ``SimulatorConfig`` is available and the interaction type should be
        populated.

    Raises:
        ValueError: if ``key`` is not a valid four-segment key.
    """
    canonical = canonicalize_four_segment_key(key)
    ad_product, format_value, placement, creative = canonical.split(":")
    placement_value, placement_availability = _optional_component(placement)
    creative_value, creative_availability = _optional_component(creative)
    return Touchpoint(
        provider=provider,
        ad_product=ad_product,
        format=format_value,
        placement=placement_value,
        creative=creative_value,
        interaction_type=None,
        field_availability=TouchpointFieldAvailability(
            placement=placement_availability,
            creative=creative_availability,
            interaction_type=FieldAvailability.NOT_PROVIDED,
        ),
    )


_ATTRIBUTION_RESULT_OUTCOME_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("converted_users", "converted_user_share", "attributed_converted_users"),
    ("purchase_count", "purchase_count_share", "attributed_purchase_count"),
    ("revenue", "revenue_share", "attributed_revenue"),
)


def attribution_evidence_from_attribution_result(
    result: AttributionResult,
    *,
    model_id: str,
    model_version: str,
    reporting_scope: ReportingScope,
    provider: Provider = Provider.AMAZON_ADS,
) -> tuple[AttributionEvidence, ...]:
    """Adapt one AttributionResult into one AttributionEvidence per outcome.

    Args:
        result: The model's result for one five-segment touchpoint, carrying
            all three outcomes at once.
        model_id: Stable identifier of the producing model, not carried by
            ``AttributionResult`` itself.
        model_version: Version of that model, not carried by
            ``AttributionResult`` itself.
        reporting_scope: The scope the result was computed over, not carried
            by ``AttributionResult`` itself.
        provider: The provider ``result.touchpoint`` was reported by.

    Returns:
        tuple[AttributionEvidence, ...]: Exactly three records, one for
        ``converted_users``, one for ``purchase_count``, one for ``revenue``,
        in that order.
    """
    touchpoint = touchpoint_from_five_segment_key(result.touchpoint, provider=provider)
    return tuple(
        AttributionEvidence(
            model_id=model_id,
            model_version=model_version,
            reporting_scope=reporting_scope,
            touchpoint=touchpoint,
            outcome=outcome,
            attribution_share=getattr(result, share_field),
            attributed_value=getattr(result, value_field),
        )
        for outcome, share_field, value_field in _ATTRIBUTION_RESULT_OUTCOME_FIELDS
    )


def attribution_evidence_from_standard_row(
    row: StandardAttributionRow,
    *,
    reporting_scope: ReportingScope,
    simulator_config: SimulatorConfig | None = None,
    provider: Provider = Provider.AMAZON_ADS,
) -> AttributionEvidence:
    """Adapt one StandardAttributionRow into one AttributionEvidence.

    Args:
        row: The standardized row, normally carrying a native five-segment
            MTA-SIM interaction key.
        reporting_scope: The scope to attach. ``row`` carries no
            ``advertiser_id`` or ``currency``, so this cannot be derived
            from ``row`` alone; it is cross-checked, not filled in, against
            ``row.marketplace`` and ``row``'s report window.
        simulator_config: Compatibility mapping used only when a historical
            caller supplies a four-segment row.
        provider: The provider ``row.touchpoint`` was reported by.

    Returns:
        AttributionEvidence: The adapted record.

    Raises:
        ValueError: if ``row``'s marketplace or report window does not
            match ``reporting_scope``.
    """
    if row.marketplace != reporting_scope.marketplace:
        raise ValueError("row.marketplace does not match reporting_scope.marketplace")
    if (
        row.report_start_date != reporting_scope.report_start_date
        or row.report_end_date != reporting_scope.report_end_date
    ):
        raise ValueError("row report window does not match reporting_scope window")

    segment_count = len(row.touchpoint.split(":"))
    if segment_count == 5:
        touchpoint = touchpoint_from_five_segment_key(
            row.touchpoint, provider=provider
        )
    elif segment_count == 4 and simulator_config is not None:
        touchpoint = touchpoint_from_five_segment_key(
            simulator_config.to_five_segment(row.touchpoint), provider=provider
        )
    elif segment_count == 4:
        touchpoint = touchpoint_from_four_segment_key(row.touchpoint, provider=provider)
    else:
        raise ValueError("row.touchpoint must contain four or five segments")

    return AttributionEvidence(
        model_id=row.model_id,
        model_version=row.model_version,
        reporting_scope=reporting_scope,
        touchpoint=touchpoint,
        outcome=row.outcome,
        attribution_share=row.attribution_share,
        attributed_value=row.attributed_value,
        valid=row.valid,
        warnings=row.warnings,
    )


def delivery_observation_from_touchpoint_spend(
    spend: TouchpointSpend,
    *,
    reporting_scope: ReportingScope,
    provider: Provider = Provider.AMAZON_ADS,
) -> DeliveryObservation:
    """Adapt a TouchpointSpend into a DeliveryObservation.

    Args:
        spend: Aggregated spend and delivery metrics for one five-segment
            touchpoint, as produced by
            ``attribution_contract.aggregate_spend_by_touchpoint``.
        reporting_scope: The scope the spend was aggregated over, not
            carried by ``TouchpointSpend`` itself.
        provider: The provider ``spend.touchpoint`` was reported by.

    Returns:
        DeliveryObservation: The adapted record. Whichever of
        ``impressions``/``clicks`` is not applicable to the touchpoint's
        ``interaction_type`` is set to ``None`` rather than the ``0`` that
        ``aggregate_spend_by_touchpoint`` stores for it, since the existing
        contract already enforces that metric is always zero for a
        non-matching interaction type; ``None`` distinguishes "not
        applicable" from "observed zero" for the metric that does apply.
    """
    touchpoint = touchpoint_from_five_segment_key(spend.touchpoint, provider=provider)
    impressions = spend.impressions if touchpoint.interaction_type == "IMPRESSION" else None
    clicks = spend.clicks if touchpoint.interaction_type == "CLICK" else None
    return DeliveryObservation(
        touchpoint=touchpoint,
        reporting_scope=reporting_scope,
        cost=spend.cost,
        reported_purchases=spend.reported_purchases,
        reported_sales=spend.reported_sales,
        impressions=impressions,
        clicks=clicks,
    )


def outcome_observation_from_touchpoint_spend(
    spend: TouchpointSpend,
    *,
    reporting_scope: ReportingScope,
    provider: Provider = Provider.AMAZON_ADS,
) -> OutcomeObservation:
    """Adapt a TouchpointSpend into an OutcomeObservation's total-only fields.

    Args:
        spend: Aggregated spend and delivery metrics for one five-segment
            touchpoint, as produced by
            ``attribution_contract.aggregate_spend_by_touchpoint``.
        reporting_scope: The scope the spend was aggregated over, not
            carried by ``TouchpointSpend`` itself.
        provider: The provider ``spend.touchpoint`` was reported by.

    Returns:
        OutcomeObservation: ``total_units``/``total_revenue`` populated from
        ``spend.reported_purchases``/``spend.reported_sales`` — the only
        outcome figures ``TouchpointSpend`` carries. Every organic-baseline
        and incremental field is left ``None``: no field on ``TouchpointSpend``
        or anywhere else in the current pipeline separates organic from
        ad-driven demand, so this function must not and does not fabricate
        one.
    """
    touchpoint = touchpoint_from_five_segment_key(spend.touchpoint, provider=provider)
    return OutcomeObservation(
        touchpoint=touchpoint,
        reporting_scope=reporting_scope,
        total_units=spend.reported_purchases,
        total_revenue=spend.reported_sales,
    )


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def reporting_scope_from_campaign_group(
    campaign_group: Mapping[str, object], *, mta_source: Mapping[str, object]
) -> ReportingScope:
    """Adapt a strategy_request.json Campaign Group into a ReportingScope.

    Args:
        campaign_group: The ``campaign_group`` object, supplying
            ``marketplace``, ``advertiser_id``, ``currency``, and
            ``campaign_group_id``.
        mta_source: The ``mta_source`` object, supplying
            ``report_start_date`` and ``report_end_date``. Its own
            ``marketplace``/``advertiser_id`` are not read here;
            ``hierarchy_validator.load_aligned_strategy_inputs`` already
            cross-validates them against ``campaign_group``'s.

    Returns:
        ReportingScope: The adapted scope.
    """
    return ReportingScope(
        marketplace=str(campaign_group["marketplace"]),
        advertiser_id=str(campaign_group["advertiser_id"]),
        currency=str(campaign_group["currency"]),
        report_start_date=str(mta_source["report_start_date"]),
        report_end_date=str(mta_source["report_end_date"]),
        campaign_group_id=str(campaign_group["campaign_group_id"]),
    )


def campaign_from_strategy_request_row(
    campaign_row: Mapping[str, object],
    *,
    reporting_scope: ReportingScope,
    provider: Provider = Provider.AMAZON_ADS,
) -> Campaign:
    """Adapt one strategy_request.json ``campaigns[]`` entry into a Campaign.

    Args:
        campaign_row: One entry with ``campaign_id``, ``campaign_name``,
            ``ad_product``, ``status``.
        reporting_scope: The scope this campaign was read under, typically
            from :func:`reporting_scope_from_campaign_group`.
        provider: The provider this campaign runs on.

    Returns:
        Campaign: The adapted record.
    """
    return Campaign(
        campaign_id=str(campaign_row["campaign_id"]),
        campaign_name=str(campaign_row["campaign_name"]),
        provider=provider,
        ad_product=str(campaign_row["ad_product"]),
        status=str(campaign_row["status"]),
        reporting_scope=reporting_scope,
    )


def ad_group_from_recommended_slot(
    slot: Mapping[str, object], *, campaign_id: str
) -> AdGroup:
    """Adapt one ``initial_budget_recommendation.json`` Ad Group slot.

    Args:
        slot: One entry of a campaign output's ``recommended_ad_groups``,
            carrying ``ad_group_slot_id``, ``allocation_basis``,
            ``budget_seed_share``, and optionally ``initial_daily_budget``.
        campaign_id: The owning Campaign's id, not carried by the slot
            itself.

    Returns:
        AdGroup: The adapted record. ``initial_daily_budget`` stays ``None``
        when the recommendation carried no budget baseline, matching
        ``budget_recommender.py``'s own conditional inclusion of that field.
    """
    return AdGroup(
        ad_group_id=str(slot["ad_group_slot_id"]),
        campaign_id=campaign_id,
        allocation_basis=(
            None if slot.get("allocation_basis") is None else str(slot["allocation_basis"])
        ),
        budget_seed_share=_optional_float(slot.get("budget_seed_share")),
        initial_daily_budget=_optional_float(slot.get("initial_daily_budget")),
    )


def budget_constraints_from_campaign_output(
    campaign_output: Mapping[str, object], *, budget_usage_policy: BudgetUsagePolicy
) -> BudgetConstraints:
    """Adapt one campaign output into BudgetConstraints.

    Args:
        campaign_output: One entry of ``initial_budget_recommendation.json``
            ``campaigns[]``, supplying ``campaign_id`` and, when a budget
            baseline was given, ``minimum_required_daily_budget``.
        budget_usage_policy: Not represented anywhere in
            ``strategy_request.json`` or its output today; the caller must
            supply it explicitly rather than have it defaulted or inferred.

    Returns:
        BudgetConstraints: The adapted record. ``maximum_daily_budget``
        stays ``None``; no field in the current schema represents an
        authorized ceiling distinct from the total Campaign Group budget.
    """
    return BudgetConstraints(
        campaign_id=str(campaign_output["campaign_id"]),
        budget_usage_policy=budget_usage_policy,
        minimum_daily_budget=_optional_float(
            campaign_output.get("minimum_required_daily_budget")
        ),
    )


def budget_observation_from_campaign_output(
    campaign_output: Mapping[str, object], *, reporting_scope: ReportingScope
) -> BudgetObservation:
    """Adapt one campaign output into a BudgetObservation.

    Args:
        campaign_output: One entry of ``initial_budget_recommendation.json``
            ``campaigns[]``, supplying ``campaign_id`` and, when a budget
            baseline was given, ``campaign_budget_seed``.
        reporting_scope: The scope this observation covers.

    Returns:
        BudgetObservation: The adapted record. ``actual_spend`` is always
        ``None``: no field anywhere in ``modules/mta_strategy_recommendation``
        represents actual spend today, only a forward-looking budget seed.
    """
    return BudgetObservation(
        campaign_id=str(campaign_output["campaign_id"]),
        reporting_scope=reporting_scope,
        configured_budget=_optional_float(campaign_output.get("campaign_budget_seed")),
    )
