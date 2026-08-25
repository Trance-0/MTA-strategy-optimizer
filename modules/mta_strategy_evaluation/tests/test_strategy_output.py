"""Tests for the canonical strategy output data class.

Covers construction, every ``__post_init__`` rejection, the four conservation
constraints at and just outside tolerance, relative-shares-only mode, and the
ground-truth field check.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.enums import Provider, RecordClassification
from modules.mta_common.src.evaluation_only import assert_no_ground_truth_fields
from modules.mta_common.src.lineage import DataLineage
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_strategy_evaluation.src.strategy_output import (
    BUDGET_ABSOLUTE_TOLERANCE,
    SHARE_ABSOLUTE_TOLERANCE,
    AdGroupBudgetSlot,
    CampaignBudgetDecision,
    ConservationReport,
    StrategyOutput,
)


def _scope() -> ReportingScope:
    return ReportingScope(
        marketplace="TOY",
        advertiser_id="adv_demo_001",
        currency="USD",
        report_start_date="2026-01-01",
        report_end_date="2026-01-20",
    )


_DEFAULT_CAMPAIGNS = (
    CampaignBudgetDecision(campaign_id="C-1", budget_share=0.25, budget=25.0),
    CampaignBudgetDecision(campaign_id="C-2", budget_share=0.75, budget=75.0),
)


def _output(
    campaigns: tuple[CampaignBudgetDecision, ...] = _DEFAULT_CAMPAIGNS,
    total_budget: float | None = 100.0,
) -> StrategyOutput:
    return StrategyOutput(
        strategy_id="campaign_response_optimizer",
        strategy_version="1.0.0",
        allocation_type="OPTIMIZED",
        scope=_scope(),
        campaigns=campaigns,
        total_budget=total_budget,
    )


class ConstructionTest(unittest.TestCase):
    """A well-formed allocation constructs and keeps the order it was given."""

    def test_campaign_order_is_preserved(self) -> None:
        """Campaigns serialize in the supplied order, never alphabetically."""

        output = _output(
            campaigns=(
                CampaignBudgetDecision(campaign_id="Z-1", budget_share=0.5),
                CampaignBudgetDecision(campaign_id="A-1", budget_share=0.5),
            ),
            total_budget=None,
        )

        self.assertEqual(
            [row["campaign_id"] for row in output.to_dict()["campaigns"]],
            ["Z-1", "A-1"],
        )

    def test_to_dict_preserves_none_rather_than_zero_filling(self) -> None:
        """An absent budget stays absent, because None and zero differ."""

        payload = _output(total_budget=None).to_dict()

        self.assertIsNone(payload["total_budget"])
        self.assertIsNone(payload["lineage"])

    def test_to_dict_projects_provider_to_its_string_value(self) -> None:
        """A Provider enum becomes its value, so the payload is JSON-ready."""

        decision = CampaignBudgetDecision(
            campaign_id="C-1", budget_share=1.0, provider=Provider.AMAZON_ADS
        )

        self.assertEqual(decision.to_dict()["provider"], Provider.AMAZON_ADS.value)

    def test_lineage_serializes_when_present(self) -> None:
        """A populated lineage reaches the payload as plain values."""

        output = StrategyOutput(
            strategy_id="deterministic_budget_seed",
            strategy_version="1.0.0",
            allocation_type="INITIAL_SEED",
            scope=_scope(),
            campaigns=(
                CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0),
            ),
            lineage=DataLineage(
                source_system="MTA_AMC_CAMPAIGN_BRIDGE",
                source_reference="initial_budget_recommendation.json",
                schema_version="1.0.0",
                transformation_version="STRATEGY_PROJECTION_V1",
                classification=RecordClassification.DECISION_TIME,
                is_synthetic=True,
            ),
        )

        lineage = output.to_dict()["lineage"]
        self.assertEqual(lineage["classification"], "DECISION_TIME")
        self.assertTrue(lineage["is_synthetic"])
        self.assertIsNone(lineage["provider"])


class RejectionTest(unittest.TestCase):
    """Structurally impossible allocations are rejected at construction."""

    def test_empty_campaigns_are_rejected(self) -> None:
        """Allocating to no Campaign is no decision to evaluate."""

        with self.assertRaises(ValueError):
            _output(campaigns=())

    def test_duplicate_campaign_id_is_rejected(self) -> None:
        """A duplicate would silently double-count in the conservation sums."""

        with self.assertRaises(ValueError):
            _output(
                campaigns=(
                    CampaignBudgetDecision(campaign_id="C-1", budget_share=0.5),
                    CampaignBudgetDecision(campaign_id="C-1", budget_share=0.5),
                ),
                total_budget=None,
            )

    def test_duplicate_ad_group_slot_id_is_rejected(self) -> None:
        """The same rule applies one level down."""

        with self.assertRaises(ValueError):
            CampaignBudgetDecision(
                campaign_id="C-1",
                budget_share=1.0,
                ad_groups=(
                    AdGroupBudgetSlot(ad_group_slot_id="S-1", budget_share=0.5),
                    AdGroupBudgetSlot(ad_group_slot_id="S-1", budget_share=0.5),
                ),
            )

    def test_unknown_allocation_type_is_rejected(self) -> None:
        """Only INITIAL_SEED and OPTIMIZED exist."""

        with self.assertRaises(ValueError):
            StrategyOutput(
                strategy_id="s",
                strategy_version="1.0.0",
                allocation_type="GUESSED",
                scope=_scope(),
                campaigns=(
                    CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0),
                ),
            )

    def test_unknown_execution_status_is_rejected(self) -> None:
        """Execution status is a closed vocabulary."""

        with self.assertRaises(ValueError):
            CampaignBudgetDecision(
                campaign_id="C-1", budget_share=1.0, execution_status="MAYBE"
            )

    def test_blank_identifiers_are_rejected(self) -> None:
        """Whitespace is not an identifier."""

        with self.assertRaises(ValueError):
            CampaignBudgetDecision(campaign_id="   ", budget_share=1.0)
        with self.assertRaises(ValueError):
            AdGroupBudgetSlot(ad_group_slot_id="", budget_share=1.0)

    def test_negative_budget_is_rejected(self) -> None:
        """Money is non-negative."""

        with self.assertRaises(ValueError):
            CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0, budget=-1.0)
        with self.assertRaises(ValueError):
            _output(total_budget=-1.0)

    def test_share_outside_the_unit_interval_is_rejected(self) -> None:
        """A share is a fraction of a whole."""

        with self.assertRaises(ValueError):
            CampaignBudgetDecision(campaign_id="C-1", budget_share=1.5)
        with self.assertRaises(ValueError):
            CampaignBudgetDecision(campaign_id="C-1", budget_share=-0.1)

    def test_non_finite_values_are_rejected(self) -> None:
        """An infinity or a not-a-number is not a budget."""

        with self.assertRaises(ValueError):
            CampaignBudgetDecision(campaign_id="C-1", budget_share=float("nan"))
        with self.assertRaises(ValueError):
            CampaignBudgetDecision(
                campaign_id="C-1", budget_share=1.0, budget=float("inf")
            )


class ConservationTest(unittest.TestCase):
    """The four constraints, at and just outside their tolerances."""

    def test_a_conserving_allocation_reports_no_violation(self) -> None:
        """The happy path reports zero residuals."""

        report = _output().conservation()

        self.assertTrue(report.is_conserving)
        self.assertEqual(report.violations, ())
        self.assertEqual(report.budget_overrun, 0.0)

    def test_campaign_shares_must_sum_to_one(self) -> None:
        """Constraint (2) fails when the shares do not close."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(campaign_id="C-1", budget_share=0.25),
                CampaignBudgetDecision(campaign_id="C-2", budget_share=0.25),
            ),
            total_budget=None,
        ).conservation()

        self.assertFalse(report.is_conserving)
        self.assertAlmostEqual(report.campaign_share_error, 0.5)

    def test_share_residual_inside_tolerance_passes(self) -> None:
        """A residual below the share tolerance is not a violation."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1", budget_share=0.5 + SHARE_ABSOLUTE_TOLERANCE / 4
                ),
                CampaignBudgetDecision(campaign_id="C-2", budget_share=0.5),
            ),
            total_budget=None,
        ).conservation()

        self.assertTrue(report.is_conserving)
        self.assertLessEqual(report.campaign_share_error, SHARE_ABSOLUTE_TOLERANCE)

    def test_share_residual_outside_tolerance_fails(self) -> None:
        """A residual an order of magnitude above the tolerance is a violation."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1", budget_share=0.5 + SHARE_ABSOLUTE_TOLERANCE * 100
                ),
                CampaignBudgetDecision(campaign_id="C-2", budget_share=0.5),
            ),
            total_budget=None,
        ).conservation()

        self.assertFalse(report.is_conserving)

    def test_within_campaign_share_conservation_is_checked(self) -> None:
        """Constraint (1) compares slot shares against the Campaign's share."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1",
                    budget_share=1.0,
                    ad_groups=(
                        AdGroupBudgetSlot(ad_group_slot_id="S-1", budget_share=0.3),
                        AdGroupBudgetSlot(ad_group_slot_id="S-2", budget_share=0.3),
                    ),
                ),
            ),
            total_budget=None,
        ).conservation()

        self.assertFalse(report.is_conserving)
        self.assertAlmostEqual(report.within_campaign_share_error, 0.4)

    def test_a_campaign_without_slots_conserves_trivially(self) -> None:
        """Constraints (1) and (3) skip Campaigns that divide no further."""

        report = _output().conservation()

        self.assertEqual(report.within_campaign_share_error, 0.0)
        self.assertEqual(report.within_campaign_budget_error, 0.0)

    def test_within_campaign_budget_conservation_is_checked(self) -> None:
        """Constraint (3) compares slot budgets against the Campaign's budget."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1",
                    budget_share=1.0,
                    budget=100.0,
                    ad_groups=(
                        AdGroupBudgetSlot(
                            ad_group_slot_id="S-1", budget_share=0.5, budget=40.0
                        ),
                        AdGroupBudgetSlot(
                            ad_group_slot_id="S-2", budget_share=0.5, budget=40.0
                        ),
                    ),
                ),
            )
        ).conservation()

        self.assertFalse(report.is_conserving)
        self.assertAlmostEqual(report.within_campaign_budget_error, 20.0)

    def test_budget_residual_inside_tolerance_passes(self) -> None:
        """A monetary residual at the absolute tolerance is not a violation."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1",
                    budget_share=1.0,
                    budget=100.0,
                    ad_groups=(
                        AdGroupBudgetSlot(
                            ad_group_slot_id="S-1",
                            budget_share=1.0,
                            budget=100.0 + BUDGET_ABSOLUTE_TOLERANCE,
                        ),
                    ),
                ),
            )
        ).conservation()

        self.assertTrue(report.is_conserving)

    def test_exceeding_the_authorized_total_is_a_violation(self) -> None:
        """Constraint (4) is an inequality that overspend breaks."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1", budget_share=0.5, budget=80.0
                ),
                CampaignBudgetDecision(
                    campaign_id="C-2", budget_share=0.5, budget=80.0
                ),
            )
        ).conservation()

        self.assertFalse(report.is_conserving)
        self.assertAlmostEqual(report.budget_overrun, 60.0)

    def test_leaving_budget_unallocated_is_permitted(self) -> None:
        """Underspend is not a violation and is never reported as overrun."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1", budget_share=0.5, budget=10.0
                ),
                CampaignBudgetDecision(
                    campaign_id="C-2", budget_share=0.5, budget=10.0
                ),
            )
        ).conservation()

        self.assertTrue(report.is_conserving)
        self.assertEqual(report.budget_overrun, 0.0)

    def test_relative_shares_only_mode_skips_the_monetary_constraints(self) -> None:
        """A None total relaxes (3) and (4) to the share constraints alone."""

        report = _output(
            campaigns=(
                CampaignBudgetDecision(
                    campaign_id="C-1",
                    budget_share=1.0,
                    budget=1000.0,
                    ad_groups=(
                        AdGroupBudgetSlot(
                            ad_group_slot_id="S-1", budget_share=1.0, budget=1.0
                        ),
                    ),
                ),
            ),
            total_budget=None,
        ).conservation()

        self.assertTrue(report.is_conserving)
        self.assertEqual(report.within_campaign_budget_error, 0.0)

    def test_conservation_is_pure_and_repeatable(self) -> None:
        """Two calls on one value return equal reports and mutate nothing."""

        output = _output()

        self.assertEqual(output.conservation(), output.conservation())

    def test_report_is_conserving_cannot_disagree_with_its_violations(self) -> None:
        """``is_conserving`` is derived, so the two are one fact."""

        report = ConservationReport(
            within_campaign_share_error=0.0,
            campaign_share_error=0.0,
            within_campaign_budget_error=0.0,
            budget_overrun=0.0,
            violations=("something",),
        )

        self.assertFalse(report.is_conserving)
        self.assertFalse(report.to_dict()["is_conserving"])


class GroundTruthIsolationTest(unittest.TestCase):
    """No strategy output class may carry evaluation-only truth."""

    def test_no_class_carries_a_forbidden_field(self) -> None:
        """The decision types stay model-facing."""

        for model_facing in (StrategyOutput, CampaignBudgetDecision, AdGroupBudgetSlot):
            with self.subTest(model_facing=model_facing.__name__):
                assert_no_ground_truth_fields(model_facing)


if __name__ == "__main__":
    unittest.main()
