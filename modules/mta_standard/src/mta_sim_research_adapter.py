"""Adapt MTA-SIM research sidecars into canonical ``mta_common`` objects.

The simulator and optimizer remain independent repositories. This module is
the file-contract boundary: it reads simulator-owned JSON values, constructs
the optimizer's existing canonical dataclasses, and keeps simulator-only join
or profile metadata in parallel context mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from modules.mta_common.src.budget import BudgetObservation
from modules.mta_common.src.campaign import AdGroup, Campaign
from modules.mta_common.src.delivery import DeliveryObservation
from modules.mta_common.src.enums import (
    AssignmentType,
    FieldAvailability,
    MarginSource,
    Provider,
    RecordClassification,
)
from modules.mta_common.src.lineage import DataLineage
from modules.mta_common.src.outcome import OutcomeObservation
from modules.mta_common.src.product import (
    CampaignProductLink,
    Product,
    ProductEconomics,
)
from modules.mta_common.src.provider_capabilities import ProviderCapabilities
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_common.src.touchpoint import Touchpoint, TouchpointFieldAvailability


@dataclass(frozen=True)
class MtaSimResearchSnapshot:
    """Canonical records plus simulator-only context from one sidecar file."""

    run_ids: tuple[str, ...]
    provider_profile_names: tuple[str, ...]
    provider_capabilities: tuple[ProviderCapabilities, ...]
    products: tuple[Product, ...]
    product_economics: tuple[ProductEconomics, ...]
    campaigns: tuple[Campaign, ...]
    ad_groups: tuple[AdGroup, ...]
    campaign_product_links: tuple[CampaignProductLink, ...]
    budget_observations: tuple[BudgetObservation, ...]
    delivery_observations: tuple[DeliveryObservation, ...]
    outcome_observations: tuple[OutcomeObservation, ...]
    evaluation_outcome_observations: tuple[OutcomeObservation, ...]
    observed_touchpoints: tuple[Touchpoint, ...]
    evaluation_latent_touchpoints: tuple[Touchpoint, ...]
    data_lineage: tuple[DataLineage, ...]
    effective_configurations: tuple[Mapping[str, Any], ...]
    campaign_contexts: tuple[Mapping[str, Any], ...]
    ad_group_contexts: tuple[Mapping[str, Any], ...]
    product_contexts: tuple[Mapping[str, Any], ...]
    budget_contexts: tuple[Mapping[str, Any], ...]
    delivery_contexts: tuple[Mapping[str, Any], ...]
    outcome_contexts: tuple[Mapping[str, Any], ...]
    lineage_contexts: tuple[Mapping[str, Any], ...]


def load_mta_sim_research_snapshot(path: str | Path) -> MtaSimResearchSnapshot:
    """Read one MTA-SIM ``simulation_research.json`` integration sidecar."""

    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MTA-SIM research snapshot must be a JSON object")

    runs = _object_list(payload, "simulation_runs")
    capabilities: list[ProviderCapabilities] = []
    products: list[Product] = []
    economics: list[ProductEconomics] = []
    campaigns: list[Campaign] = []
    ad_groups: list[AdGroup] = []
    links: list[CampaignProductLink] = []
    profile_names: list[str] = []
    campaign_contexts: list[Mapping[str, Any]] = []
    ad_group_contexts: list[Mapping[str, Any]] = []
    product_contexts: list[Mapping[str, Any]] = []

    for run in runs:
        for item in _object_list(run, "providers"):
            profile_names.append(str(item["provider"]))
            capabilities.append(_provider_capabilities(item))
        for item in _object_list(run, "products"):
            products.append(_product(item))
            product_contexts.append(
                _context(
                    simulator_provider_ad_identifiers=item.get(
                        "provider_ad_identifiers", {}
                    )
                )
            )
        economics.extend(
            _product_economics(item)
            for item in _object_list(run, "product_economics")
        )
        for item in _object_list(run, "campaigns"):
            campaigns.append(_campaign(item))
            campaign_contexts.append(
                _context(
                    baseline_daily_budget=item.get("baseline_daily_budget"),
                    touchpoint_identifiers=tuple(
                        item.get("touchpoint_identifiers", [])
                    ),
                )
            )
        for item in _object_list(run, "ad_groups"):
            ad_groups.append(_ad_group(item))
            ad_group_contexts.append(
                _context(name=item.get("name"), status=item.get("status"))
            )
        links.extend(
            _campaign_product_link(item)
            for item in _object_list(run, "campaign_product_links")
        )

    campaign_baselines = {
        campaign.campaign_id: context.get("baseline_daily_budget")
        for campaign, context in zip(campaigns, campaign_contexts, strict=True)
    }
    budget_items = _object_list(payload, "budget_observations")
    budgets = tuple(
        _budget_observation(item, campaign_baselines) for item in budget_items
    )
    delivery_items = _object_list(payload, "delivery_observations")
    outcome_items = _object_list(payload, "outcome_observations")
    evaluation_outcome_items = _object_list(
        payload, "evaluation_outcome_observations"
    )
    touchpoint_pairs = _object_list(payload, "touchpoint_observations")
    lineage_items = _object_list(payload, "data_lineage")

    return MtaSimResearchSnapshot(
        run_ids=tuple(str(run["run_id"]) for run in runs),
        provider_profile_names=tuple(profile_names),
        provider_capabilities=tuple(capabilities),
        products=tuple(products),
        product_economics=tuple(economics),
        campaigns=tuple(campaigns),
        ad_groups=tuple(ad_groups),
        campaign_product_links=tuple(links),
        budget_observations=budgets,
        delivery_observations=tuple(
            _delivery_observation(item) for item in delivery_items
        ),
        outcome_observations=tuple(
            _outcome_observation(item) for item in outcome_items
        ),
        evaluation_outcome_observations=tuple(
            _outcome_observation(item) for item in evaluation_outcome_items
        ),
        observed_touchpoints=tuple(
            _touchpoint(_required_object(item, "observed"))
            for item in touchpoint_pairs
        ),
        evaluation_latent_touchpoints=tuple(
            _touchpoint(_required_object(item, "latent"))
            for item in touchpoint_pairs
        ),
        data_lineage=tuple(_data_lineage(item) for item in lineage_items),
        effective_configurations=tuple(
            _context(**_required_object(run, "effective_configuration"))
            for run in runs
        ),
        campaign_contexts=tuple(campaign_contexts),
        ad_group_contexts=tuple(ad_group_contexts),
        product_contexts=tuple(product_contexts),
        budget_contexts=tuple(
            _context(budget_level=item.get("budget_level")) for item in budget_items
        ),
        delivery_contexts=tuple(
            _context(campaign_id=item.get("campaign_id"))
            for item in delivery_items
        ),
        outcome_contexts=tuple(
            _context(
                classification=RecordClassification.OBSERVED_AFTER_TREATMENT.value,
                campaign_id=item.get("campaign_id"),
                product_id=item.get("product_id"),
                budget_level=item.get("budget_level"),
                contribution_profit=item.get("contribution_profit"),
            )
            for item in outcome_items
        )
        + tuple(
            _context(
                classification=RecordClassification.EVALUATION_ONLY_GROUND_TRUTH.value,
                campaign_id=item.get("campaign_id"),
                product_id=item.get("product_id"),
                budget_level=item.get("budget_level"),
                contribution_profit=item.get("contribution_profit"),
            )
            for item in evaluation_outcome_items
        ),
        lineage_contexts=tuple(
            _context(
                configuration_sha256=item.get("configuration_sha256"),
                seed=item.get("seed"),
            )
            for item in lineage_items
        ),
    )


def _provider(value: Any) -> Provider:
    """Map simulator profiles to the canonical provider vocabulary lossily."""

    return Provider.AMAZON_ADS if str(value) == "AMAZON_ADS" else Provider.GENERIC


def _availability(value: Any) -> FieldAvailability:
    return FieldAvailability(str(value))


def _scope(item: Mapping[str, Any]) -> ReportingScope:
    return ReportingScope(
        marketplace=str(item["marketplace"]),
        advertiser_id=str(item["advertiser_id"]),
        currency=str(item["currency"]),
        report_start_date=str(item["report_start_date"]),
        report_end_date=str(item["report_end_date"]),
        campaign_group_id=_optional_string(item.get("campaign_group_id")),
    )


def _touchpoint(item: Mapping[str, Any]) -> Touchpoint:
    availability = _required_object(item, "field_availability")
    return Touchpoint(
        provider=_provider(item["provider"]),
        ad_product=str(item["ad_product"]),
        format=str(item["format"]),
        placement=_optional_string(item.get("placement")),
        creative=_optional_string(item.get("creative")),
        interaction_type=_optional_string(item.get("interaction_type")),
        field_availability=TouchpointFieldAvailability(
            placement=_availability(availability["placement"]),
            creative=_availability(availability["creative"]),
            interaction_type=_availability(availability["interaction_type"]),
        ),
    )


def _provider_capabilities(item: Mapping[str, Any]) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider=_provider(item["provider"]),
        supported_ad_products=tuple(str(value) for value in item["supported_ad_products"]),
        format_availability=_availability(item["format_availability"]),
        placement_availability=_availability(item["placement_availability"]),
        creative_availability=_availability(item["creative_availability"]),
        interaction_type_availability=_availability(
            item["interaction_type_availability"]
        ),
    )


def _product(item: Mapping[str, Any]) -> Product:
    identifiers = {
        _provider(provider): str(identifier)
        for provider, identifier in _required_object(
            item, "provider_ad_identifiers"
        ).items()
    }
    return Product(
        product_id=str(item["product_id"]),
        provider_ad_identifiers=identifiers,
        sku_id=_optional_string(item.get("sku_id", item.get("sku"))),
        name=_optional_string(item.get("name")),
        category=_optional_string(item.get("category")),
        brand=_optional_string(item.get("brand")),
        status=_optional_string(item.get("status")),
        inventory_units=_optional_int(item.get("inventory_units")),
        salable=item.get("salable"),
    )


def _product_economics(item: Mapping[str, Any]) -> ProductEconomics:
    return ProductEconomics(
        product_id=str(item["product_id"]),
        currency=str(item["currency"]),
        unit_price=_optional_float(item.get("unit_price")),
        unit_cogs=_optional_float(item.get("unit_cogs")),
        variable_cost_per_unit=_optional_float(item.get("variable_cost_per_unit")),
        variable_fulfillment_cost_per_unit=_optional_float(
            item.get("variable_fulfillment_cost_per_unit")
        ),
        variable_platform_fee_per_unit=_optional_float(
            item.get("variable_platform_fee_per_unit")
        ),
        other_variable_cost_per_unit=_optional_float(
            item.get("other_variable_cost_per_unit")
        ),
        unit_contribution_margin=_optional_float(
            item.get("unit_contribution_margin")
        ),
        margin_source=(
            None
            if item.get("margin_source") is None
            else MarginSource(str(item["margin_source"]))
        ),
    )


def _campaign(item: Mapping[str, Any]) -> Campaign:
    return Campaign(
        campaign_id=str(item["campaign_id"]),
        campaign_name=str(item["campaign_name"]),
        provider=_provider(item["provider"]),
        ad_product=str(item["ad_product"]),
        status=str(item["status"]),
        reporting_scope=_scope(_required_object(item, "reporting_scope")),
    )


def _ad_group(item: Mapping[str, Any]) -> AdGroup:
    return AdGroup(
        ad_group_id=str(item["ad_group_id"]),
        campaign_id=str(item["campaign_id"]),
        initial_daily_budget=_optional_float(item.get("initial_daily_budget")),
    )


def _campaign_product_link(item: Mapping[str, Any]) -> CampaignProductLink:
    return CampaignProductLink(
        campaign_id=str(item["campaign_id"]),
        product_id=str(item["product_id"]),
        eligibility_status=_optional_string(item.get("eligibility_status")),
        link_status=_optional_string(item.get("link_status")),
    )


def _budget_observation(
    item: Mapping[str, Any], campaign_baselines: Mapping[str, Any]
) -> BudgetObservation:
    campaign_id = str(item["campaign_id"])
    configured = _optional_float(item.get("configured_budget"))
    baseline = _optional_float(campaign_baselines.get(campaign_id))
    budget_level = _optional_float(item.get("budget_level"))
    return BudgetObservation(
        campaign_id=campaign_id,
        reporting_scope=_scope(_required_object(item, "reporting_scope")),
        configured_budget=configured,
        actual_spend=_optional_float(item.get("actual_spend")),
        intervention_id=(
            None
            if budget_level is None
            else f"MTA_SIM_BUDGET_LEVEL:{budget_level:g}"
        ),
        baseline_budget=baseline,
        budget_delta=(
            None if configured is None or baseline is None else configured - baseline
        ),
        assignment_type=(
            None if budget_level is None else AssignmentType.RULE_BASED
        ),
        randomized=(None if budget_level is None else False),
    )


def _delivery_observation(item: Mapping[str, Any]) -> DeliveryObservation:
    return DeliveryObservation(
        touchpoint=_touchpoint(_required_object(item, "touchpoint")),
        reporting_scope=_scope(_required_object(item, "reporting_scope")),
        cost=float(item["cost"]),
        reported_purchases=int(item["reported_purchases"]),
        reported_sales=float(item["reported_sales"]),
        impressions=_optional_int(item.get("impressions")),
        clicks=_optional_int(item.get("clicks")),
    )


def _outcome_observation(item: Mapping[str, Any]) -> OutcomeObservation:
    return OutcomeObservation(
        touchpoint=_touchpoint(_required_object(item, "touchpoint")),
        reporting_scope=_scope(_required_object(item, "reporting_scope")),
        total_units=_optional_int(item.get("total_units")),
        total_revenue=_optional_float(item.get("total_revenue")),
        expected_organic_units=_optional_float(item.get("expected_organic_units")),
        expected_organic_revenue=_optional_float(
            item.get("expected_organic_revenue")
        ),
        incremental_units=_optional_float(item.get("incremental_units")),
        incremental_revenue=_optional_float(item.get("incremental_revenue")),
        incrementality_evidence_source=_optional_string(
            item.get("incrementality_evidence_source")
        ),
    )


def _data_lineage(item: Mapping[str, Any]) -> DataLineage:
    return DataLineage(
        source_system=str(item["source_system"]),
        provider=(
            None if item.get("provider") is None else _provider(item["provider"])
        ),
        source_reference=str(item["source_reference"]),
        schema_version=str(item["schema_version"]),
        transformation_version=str(item["transformation_version"]),
        classification=RecordClassification(str(item["classification"])),
        is_synthetic=bool(item["is_synthetic"]),
    )


def _object_list(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of objects")
    return value


def _required_object(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _context(**values: Any) -> Mapping[str, Any]:
    return MappingProxyType(dict(values))


def _optional_string(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
