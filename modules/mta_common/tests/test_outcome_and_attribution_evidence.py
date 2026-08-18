"""Tests for OutcomeObservation, AttributionEvidence, and DataLineage.

Covers: total outcomes are never used to fabricate incremental outcomes,
incrementality_evidence_source is required whenever an incremental field is
populated, AttributionEvidence carries no marginal-return/incrementality/
optimal-budget/profit field, and DataLineage's required text fields.
"""

from __future__ import annotations

import dataclasses
import unittest

from modules.mta_common.src.attribution_evidence import AttributionEvidence
from modules.mta_common.src.enums import Provider, RecordClassification
from modules.mta_common.src.lineage import DataLineage
from modules.mta_common.src.outcome import OutcomeObservation
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_common.src.touchpoint import Touchpoint, TouchpointFieldAvailability


def _scope() -> ReportingScope:
    return ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-31",
    )


def _touchpoint() -> Touchpoint:
    return Touchpoint(
        provider=Provider.AMAZON_ADS,
        ad_product="SPONSORED_PRODUCTS",
        format="SP",
        placement="TOP_OF_SEARCH",
        creative="VIDEO",
        interaction_type="CLICK",
        field_availability=TouchpointFieldAvailability.all_available(),
    )


class OutcomeObservationTests(unittest.TestCase):
    def test_total_only_observation_is_valid_and_leaves_incremental_none(self) -> None:
        outcome = OutcomeObservation(
            touchpoint=_touchpoint(),
            reporting_scope=_scope(),
            total_units=10,
            total_revenue=250.0,
        )
        self.assertEqual(outcome.total_units, 10)
        self.assertIsNone(outcome.incremental_units)
        self.assertIsNone(outcome.incremental_revenue)
        self.assertIsNone(outcome.expected_organic_units)

    def test_incremental_units_without_evidence_source_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OutcomeObservation(
                touchpoint=_touchpoint(),
                reporting_scope=_scope(),
                total_units=10,
                incremental_units=4.0,
            )

    def test_incremental_units_with_evidence_source_is_valid(self) -> None:
        outcome = OutcomeObservation(
            touchpoint=_touchpoint(),
            reporting_scope=_scope(),
            total_units=10,
            incremental_units=4.0,
            incrementality_evidence_source="HOLDOUT_EXPERIMENT_2026Q1",
        )
        self.assertEqual(outcome.incremental_units, 4.0)

    def test_negative_total_units_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OutcomeObservation(
                touchpoint=_touchpoint(), reporting_scope=_scope(), total_units=-1
            )


class AttributionEvidenceScopeTests(unittest.TestCase):
    FORBIDDEN_FIELD_NAME_FRAGMENTS = (
        "marginal",
        "incremental",
        "causal",
        "optimal_budget",
        "contribution_profit",
    )

    def test_no_field_carries_a_marginal_or_causal_optimization_claim(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AttributionEvidence)}
        for name in field_names:
            for fragment in self.FORBIDDEN_FIELD_NAME_FRAGMENTS:
                self.assertNotIn(
                    fragment,
                    name,
                    msg=f"AttributionEvidence.{name} looks like an optimization claim",
                )

    def test_attribution_share_above_one_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AttributionEvidence(
                model_id="MODEL",
                model_version="1.0",
                reporting_scope=_scope(),
                touchpoint=_touchpoint(),
                outcome="revenue",
                attribution_share=1.5,
                attributed_value=10.0,
            )

    def test_negative_attributed_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AttributionEvidence(
                model_id="MODEL",
                model_version="1.0",
                reporting_scope=_scope(),
                touchpoint=_touchpoint(),
                outcome="revenue",
                attribution_share=0.5,
                attributed_value=-1.0,
            )

    def test_duplicate_warnings_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AttributionEvidence(
                model_id="MODEL",
                model_version="1.0",
                reporting_scope=_scope(),
                touchpoint=_touchpoint(),
                outcome="revenue",
                attribution_share=0.5,
                attributed_value=10.0,
                warnings=("ZERO_OUTCOME_TOTAL", "ZERO_OUTCOME_TOTAL"),
            )


class DataLineageTests(unittest.TestCase):
    def test_required_text_fields_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            DataLineage(
                source_system="",
                source_reference="daily_performance",
                schema_version="4.0",
                transformation_version="1.0",
                classification=RecordClassification.OBSERVED_AFTER_TREATMENT,
                is_synthetic=True,
            )

    def test_lineage_accepts_a_logical_table_name_as_source_reference(self) -> None:
        lineage = DataLineage(
            source_system="MTA_SIM_GENERATOR",
            source_reference="amazon_ads_daily_touchpoint_performance",
            schema_version="4.0",
            transformation_version="1.0",
            classification=RecordClassification.DECISION_TIME,
            is_synthetic=True,
        )
        self.assertEqual(
            lineage.source_reference, "amazon_ads_daily_touchpoint_performance"
        )


if __name__ == "__main__":
    unittest.main()
