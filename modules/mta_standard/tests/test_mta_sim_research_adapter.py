"""Cross-repository semantic tests for the MTA-SIM research-sidecar adapter."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from modules.mta_common.src.enums import (
    AssignmentType,
    FieldAvailability,
    Provider,
    RecordClassification,
)
from modules.mta_common.src.product import Product, ProductEconomics
from modules.mta_common.src.touchpoint import Touchpoint
from modules.mta_standard.src.mta_sim_research_adapter import (
    load_mta_sim_research_snapshot,
)


SCOPE = {
    "marketplace": "US",
    "advertiser_id": "SIM-ACCOUNT",
    "currency": "USD",
    "report_start_date": "2025-01-01",
    "report_end_date": "2025-01-01",
    "campaign_group_id": "SIM-GROUP",
}

OBSERVED_TOUCHPOINT = {
    "provider": "SYNTHETIC_LIMITED_PLACEMENT_CREATIVE",
    "ad_product": "DISPLAY",
    "format": "IMAGE",
    "placement": None,
    "creative": None,
    "interaction_type": "CLICK",
    "field_availability": {
        "placement": "NOT_PROVIDED",
        "creative": "REDACTED",
        "interaction_type": "AVAILABLE",
    },
}

LATENT_TOUCHPOINT = {
    **OBSERVED_TOUCHPOINT,
    "placement": "FEED",
    "creative": "VIDEO_123",
    "field_availability": {
        "placement": "AVAILABLE",
        "creative": "AVAILABLE",
        "interaction_type": "AVAILABLE",
    },
}


def _snapshot_payload() -> dict[str, object]:
    outcome = {
        "touchpoint": OBSERVED_TOUCHPOINT,
        "reporting_scope": SCOPE,
        "total_units": 5,
        "total_revenue": 100.0,
        "expected_organic_units": None,
        "expected_organic_revenue": None,
        "incremental_units": None,
        "incremental_revenue": None,
        "incrementality_evidence_source": None,
        "contribution_profit": 40.0,
        "campaign_id": "CAMP-1",
        "product_id": "PRODUCT-1",
        "budget_level": 0.5,
    }
    evaluation_outcome = {
        **outcome,
        "expected_organic_units": 2.0,
        "expected_organic_revenue": 40.0,
        "incremental_units": 3.0,
        "incremental_revenue": 60.0,
        "incrementality_evidence_source": "MTA_SIM_COUNTERFACTUAL",
    }
    return {
        "simulation_runs": [
            {
                "run_id": "run-1",
                "seed": 42,
                "configuration_sha256": "abc123",
                "providers": [
                    {
                        "provider": "SYNTHETIC_LIMITED_PLACEMENT_CREATIVE",
                        "supported_ad_products": ["DISPLAY"],
                        "format_availability": "AVAILABLE",
                        "placement_availability": "NOT_PROVIDED",
                        "creative_availability": "NOT_PROVIDED",
                        "interaction_type_availability": "AVAILABLE",
                    }
                ],
                "products": [
                    {
                        "product_id": "PRODUCT-1",
                        "provider_ad_identifiers": {
                            "SYNTHETIC_LIMITED_PLACEMENT_CREATIVE": "AD-PRODUCT-1"
                        },
                        "sku_id": "SKU-1",
                        "name": "Research product",
                        "category": "Research",
                        "brand": "Synthetic",
                        "status": "ACTIVE",
                        "inventory_units": 250,
                        "salable": True,
                    }
                ],
                "campaigns": [
                    {
                        "campaign_id": "CAMP-1",
                        "campaign_name": "Research campaign",
                        "provider": "SYNTHETIC_LIMITED_PLACEMENT_CREATIVE",
                        "ad_product": "DISPLAY",
                        "status": "ACTIVE",
                        "reporting_scope": SCOPE,
                        "baseline_daily_budget": 100.0,
                        "touchpoint_identifiers": ["display"],
                    }
                ],
                "effective_configuration": {"random_seed": 42},
                "ad_groups": [
                    {
                        "ad_group_id": "ADGROUP-1",
                        "campaign_id": "CAMP-1",
                        "name": "Research ad group",
                        "status": "ACTIVE",
                        "initial_daily_budget": 100.0,
                    }
                ],
                "campaign_product_links": [
                    {
                        "campaign_id": "CAMP-1",
                        "product_id": "PRODUCT-1",
                        "eligibility_status": "ELIGIBLE",
                        "link_status": "ACTIVE",
                    }
                ],
                "product_economics": [
                    {
                        "product_id": "PRODUCT-1",
                        "currency": "USD",
                        "unit_price": 20.0,
                        "unit_cogs": 8.0,
                        "variable_cost_per_unit": 2.0,
                        "variable_fulfillment_cost_per_unit": 1.0,
                        "variable_platform_fee_per_unit": 0.75,
                        "other_variable_cost_per_unit": 0.25,
                        "unit_contribution_margin": 10.0,
                        "margin_source": "DERIVED",
                    }
                ],
            }
        ],
        "budget_observations": [
            {
                "campaign_id": "CAMP-1",
                "reporting_scope": SCOPE,
                "configured_budget": 50.0,
                "actual_spend": 43.0,
                "budget_level": 0.5,
            }
        ],
        "delivery_observations": [
            {
                "touchpoint": OBSERVED_TOUCHPOINT,
                "reporting_scope": SCOPE,
                "cost": 43.0,
                "reported_purchases": 5,
                "reported_sales": 100.0,
                "impressions": None,
                "clicks": 20,
                "campaign_id": "CAMP-1",
            }
        ],
        "outcome_observations": [outcome],
        "evaluation_outcome_observations": [evaluation_outcome],
        "data_lineage": [
            {
                "source_system": "MTA_SIM_GENERATOR",
                "source_reference": "simulation_research",
                "schema_version": "2",
                "transformation_version": "2.0",
                "classification": "EVALUATION_ONLY_GROUND_TRUTH",
                "is_synthetic": True,
                "provider": "SYNTHETIC_LIMITED_PLACEMENT_CREATIVE",
                "configuration_sha256": "abc123",
                "seed": 42,
            }
        ],
        "touchpoint_observations": [
            {"latent": LATENT_TOUCHPOINT, "observed": OBSERVED_TOUCHPOINT}
        ],
    }


class MtaSimResearchAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "simulation_research.json"
        self.path.write_text(json.dumps(_snapshot_payload()), encoding="utf-8")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_constructs_existing_canonical_objects(self) -> None:
        snapshot = load_mta_sim_research_snapshot(self.path)
        self.assertIsInstance(snapshot.products[0], Product)
        self.assertIsInstance(snapshot.product_economics[0], ProductEconomics)
        self.assertIsInstance(snapshot.observed_touchpoints[0], Touchpoint)
        self.assertEqual(snapshot.products[0].sku_id, "SKU-1")
        self.assertEqual(snapshot.products[0].inventory_units, 250)
        self.assertEqual(
            snapshot.product_economics[0].variable_cost_per_unit, 2.0
        )

    def test_synthetic_profile_maps_lossily_but_name_is_retained(self) -> None:
        snapshot = load_mta_sim_research_snapshot(self.path)
        self.assertEqual(snapshot.provider_capabilities[0].provider, Provider.GENERIC)
        self.assertEqual(
            snapshot.provider_profile_names[0],
            "SYNTHETIC_LIMITED_PLACEMENT_CREATIVE",
        )
        self.assertEqual(snapshot.observed_touchpoints[0].provider, Provider.GENERIC)

    def test_structured_missingness_survives_without_unspecified_inference(self) -> None:
        snapshot = load_mta_sim_research_snapshot(self.path)
        observed = snapshot.observed_touchpoints[0]
        latent = snapshot.evaluation_latent_touchpoints[0]
        self.assertIsNone(observed.placement)
        self.assertEqual(
            observed.field_availability.placement,
            FieldAvailability.NOT_PROVIDED,
        )
        self.assertEqual(
            observed.field_availability.creative,
            FieldAvailability.REDACTED,
        )
        self.assertEqual(latent.placement, "FEED")
        self.assertEqual(latent.creative, "VIDEO_123")

    def test_budget_experiment_maps_to_canonical_intervention_fields(self) -> None:
        snapshot = load_mta_sim_research_snapshot(self.path)
        budget = snapshot.budget_observations[0]
        self.assertEqual(budget.configured_budget, 50.0)
        self.assertEqual(budget.actual_spend, 43.0)
        self.assertEqual(budget.baseline_budget, 100.0)
        self.assertEqual(budget.budget_delta, -50.0)
        self.assertEqual(budget.assignment_type, AssignmentType.RULE_BASED)
        self.assertFalse(budget.randomized)
        self.assertEqual(snapshot.budget_contexts[0]["budget_level"], 0.5)

    def test_evaluation_truth_is_separate_from_observed_outcomes(self) -> None:
        snapshot = load_mta_sim_research_snapshot(self.path)
        self.assertIsNone(snapshot.outcome_observations[0].incremental_units)
        self.assertEqual(
            snapshot.evaluation_outcome_observations[0].incremental_units, 3.0
        )
        self.assertEqual(
            snapshot.outcome_contexts[-1]["classification"],
            RecordClassification.EVALUATION_ONLY_GROUND_TRUTH.value,
        )

    def test_campaign_and_product_join_context_is_not_added_to_observations(self) -> None:
        snapshot = load_mta_sim_research_snapshot(self.path)
        self.assertFalse(hasattr(snapshot.delivery_observations[0], "campaign_id"))
        self.assertEqual(snapshot.delivery_contexts[0]["campaign_id"], "CAMP-1")
        self.assertEqual(snapshot.outcome_contexts[0]["product_id"], "PRODUCT-1")


if __name__ == "__main__":
    unittest.main()
