"""Tests for the adapter that runs the contributed ASIN-free GMV network.

The pivot and admissibility cases always run, because they are plain Python
over plain dictionaries. Everything that fits a network is skipped when NumPy
is absent, so a checkout without the ``strategy-evaluation`` extra still runs
this file rather than erroring in collection.
"""

from __future__ import annotations

import importlib.util
import unittest

from modules.mta_common.src.budget import BudgetConstraints, BudgetObservation
from modules.mta_common.src.campaign import Campaign
from modules.mta_common.src.enums import BudgetUsagePolicy, FieldAvailability, Provider
from modules.mta_common.src.episode import CampaignEpisode
from modules.mta_common.src.outcome import OutcomeObservation
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_common.src.touchpoint import Touchpoint, TouchpointFieldAvailability
from modules.mta_strategy_evaluation.adapters.asin_gmv_nn_adapter import (
    AD_TYPE_BY_AD_PRODUCT,
    AD_TYPES,
    DEFAULT_NETWORK,
    MINIMUM_PANEL_ROWS,
    NETWORK_MLP,
    QUALITY_CAVEAT,
    SOURCE_CANONICAL,
    SOURCE_CONTRIBUTOR_PANEL,
    STATUS_AUXILIARY_LABELS_UNAVAILABLE,
    STATUS_FITTED,
    STATUS_INSUFFICIENT_DATA,
    ContributedModelError,
    contributed_model_report,
    fit_contributed_model,
    load_contributed_trainer,
    panel_from_contributor_file,
    panel_from_response_dataset,
    recorded_contributor_quality,
)
from modules.mta_strategy_recommendation.src.response_dataset import (
    build_campaign_response_dataset,
)

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
NEEDS_NUMPY = unittest.skipUnless(
    HAS_NUMPY, "NumPy is an opt-in dependency: uv sync --extra strategy-evaluation"
)


def _touchpoint(ad_product: str) -> Touchpoint:
    return Touchpoint(
        provider=Provider.AMAZON_ADS,
        ad_product=ad_product,
        format="PRODUCT_AD",
        placement="TOP_OF_SEARCH",
        creative=None,
        interaction_type="CLICK",
        field_availability=TouchpointFieldAvailability(
            placement=FieldAvailability.AVAILABLE,
            creative=FieldAvailability.NOT_PROVIDED,
            interaction_type=FieldAvailability.AVAILABLE,
        ),
    )


def _episode(
    campaign_id: str = "C-SP",
    ad_product: str = "SPONSORED_PRODUCTS",
    date: str = "2026-01-01",
    marketplace: str = "US",
    configured_budget: float = 100.0,
    revenue: float = 400.0,
) -> CampaignEpisode:
    scope = ReportingScope(
        marketplace=marketplace,
        advertiser_id="adv_demo_001",
        currency="USD",
        report_start_date=date,
        report_end_date=date,
    )
    return CampaignEpisode(
        campaign=Campaign(
            campaign_id=campaign_id,
            campaign_name=f"Name {campaign_id}",
            provider=Provider.AMAZON_ADS,
            ad_product=ad_product,
            status="ACTIVE",
            reporting_scope=scope,
        ),
        budget_constraints=BudgetConstraints(
            campaign_id=campaign_id,
            budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
        ),
        budget_observation=BudgetObservation(
            campaign_id=campaign_id,
            reporting_scope=scope,
            configured_budget=configured_budget,
            actual_spend=configured_budget,
        ),
        outcome_observations=(
            OutcomeObservation(
                touchpoint=_touchpoint(ad_product),
                reporting_scope=scope,
                total_units=5,
                total_revenue=revenue,
            ),
        ),
    )


def _dataset(episodes):
    return build_campaign_response_dataset(episodes)


class PivotTest(unittest.TestCase):
    """Campaign-period rows become marketplace-day rows."""

    def test_two_campaigns_on_one_day_become_one_row(self) -> None:
        """The whole day's advertising mix is one row, as their model expects."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode("C-SP", "SPONSORED_PRODUCTS", configured_budget=60.0),
                    _episode("C-DSP", "AMAZON_DSP", configured_budget=40.0),
                ]
            )
        )

        self.assertEqual(len(panel), 1)
        self.assertEqual(panel.rows[0]["budget_sp"], 60.0)
        self.assertEqual(panel.rows[0]["budget_dsp"], 40.0)

    def test_ad_product_selects_the_budget_slot(self) -> None:
        """Every one of the four products lands in its own slot."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode(f"C-{product}", product, configured_budget=10.0)
                    for product in AD_TYPE_BY_AD_PRODUCT
                ]
            )
        )

        for ad_type in AD_TYPES:
            with self.subTest(ad_type=ad_type):
                self.assertEqual(panel.rows[0][f"budget_{ad_type}"], 10.0)

    def test_shares_are_derived_from_the_day_total(self) -> None:
        """Shares sum to one when anything was spent."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode("C-SP", "SPONSORED_PRODUCTS", configured_budget=75.0),
                    _episode("C-DSP", "AMAZON_DSP", configured_budget=25.0),
                ]
            )
        )
        row = panel.rows[0]

        self.assertAlmostEqual(row["share_sp"], 0.75)
        self.assertAlmostEqual(row["share_dsp"], 0.25)
        self.assertAlmostEqual(sum(row[f"share_{name}"] for name in AD_TYPES), 1.0)

    def test_revenue_sums_across_the_campaigns_of_one_day(self) -> None:
        """Their target is the day's attributed revenue, not one Campaign's."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode("C-SP", "SPONSORED_PRODUCTS", revenue=400.0),
                    _episode("C-DSP", "AMAZON_DSP", revenue=150.0),
                ]
            )
        )

        self.assertAlmostEqual(panel.rows[0]["revenue"], 550.0)

    def test_an_empty_slot_is_named_rather_than_read_as_observed_zero(self) -> None:
        """A product this Campaign Group does not run is not zero spend."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode("C-SP", "SPONSORED_PRODUCTS"),
                    _episode("C-DSP", "AMAZON_DSP"),
                ]
            )
        )

        self.assertEqual(panel.absent_ad_types, ("sb", "sd"))
        self.assertEqual(panel.rows[0]["budget_sb"], 0.0)

    def test_rows_are_sorted_by_marketplace_then_date(self) -> None:
        """The same dataset must always yield the same design matrix."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode(date="2026-01-02", marketplace="US"),
                    _episode(date="2026-01-01", marketplace="US"),
                    _episode(date="2026-01-01", marketplace="CA"),
                ]
            )
        )

        self.assertEqual(
            [(row["country"], row["date"]) for row in panel.rows],
            [("CA", "2026-01-01"), ("US", "2026-01-01"), ("US", "2026-01-02")],
        )

    def test_calendar_features_are_derived_from_the_period_start(self) -> None:
        """2026-01-03 is a Saturday, so is_weekend is one."""

        panel = panel_from_response_dataset(_dataset([_episode(date="2026-01-03")]))

        self.assertEqual(panel.rows[0]["dow"], 5.0)
        self.assertEqual(panel.rows[0]["is_weekend"], 1.0)
        self.assertEqual(panel.rows[0]["has_ad"], 1.0)

    def test_a_day_with_no_budget_has_no_advertising(self) -> None:
        """has_ad is zero and shares fall back to zero rather than dividing."""

        panel = panel_from_response_dataset(
            _dataset([_episode(configured_budget=0.0)])
        )

        self.assertEqual(panel.rows[0]["has_ad"], 0.0)
        self.assertEqual(panel.rows[0]["share_sp"], 0.0)

    def test_an_unknown_ad_product_raises(self) -> None:
        """The model knows four advertising types and this adapter guesses none."""

        with self.assertRaises(ContributedModelError) as raised:
            panel_from_response_dataset(
                _dataset([_episode("C-X", "STREAMING_TELEVISION")])
            )

        self.assertIn("STREAMING_TELEVISION", str(raised.exception))

    def test_a_non_iso_period_start_raises(self) -> None:
        """Day-of-week features cannot be derived from a date that is not one."""

        dataset = _dataset([_episode()])
        broken = type(dataset)(
            observations=(
                type(dataset.observations[0])(
                    **{
                        **dataset.observations[0].__dict__,
                        "report_start_date": "week 1",
                    }
                ),
            )
        )

        with self.assertRaises(ContributedModelError):
            panel_from_response_dataset(broken)

    def test_the_panel_records_its_own_provenance(self) -> None:
        """A result carries which mode produced it."""

        panel = panel_from_response_dataset(_dataset([_episode()]))

        self.assertEqual(panel.source, SOURCE_CANONICAL)
        self.assertFalse(panel.has_auxiliary_labels)
        self.assertFalse(panel.recorded_split)
        self.assertEqual(panel.campaign_ids, ("C-SP",))


class AdmissibilityTest(unittest.TestCase):
    """No forbidden response feature can reach the contributed model."""

    def test_the_feature_names_are_budgets_shares_and_calendar_only(self) -> None:
        """Nineteen columns on a two-market catalog, none of them attribution."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode(marketplace="US"),
                    _episode(marketplace="CA"),
                ]
            )
        )

        self.assertEqual(len(panel.feature_names), 19)
        self.assertIn("log1p_budget_sp", panel.feature_names)
        self.assertIn("country_US", panel.feature_names)
        self.assertNotIn("attributed_revenue", panel.feature_names)

    def test_no_feature_name_is_an_attribution_or_ground_truth_field(self) -> None:
        """Building a panel calls the admissibility check itself."""

        panel = panel_from_response_dataset(_dataset([_episode()]))
        forbidden = {
            "attributed_revenue",
            "credit_share",
            "markov_share",
            "shapley_share",
            "true_incremental_revenue",
        }

        self.assertFalse(set(panel.feature_names) & forbidden)


class RefusalTest(unittest.TestCase):
    """A refusal is a reported result, not a raised error."""

    def test_too_few_rows_returns_insufficient_data(self) -> None:
        """Twenty marketplace-days cannot support a nineteen-column network."""

        fit = fit_contributed_model(
            panel_from_response_dataset(
                _dataset(
                    [
                        _episode(date=f"2026-01-{day:02d}")
                        for day in range(1, 21)
                    ]
                )
            )
        )

        self.assertEqual(fit.status, STATUS_INSUFFICIENT_DATA)
        self.assertFalse(fit.is_usable)
        self.assertIsNone(fit.holdout_r_squared)

    def test_the_refusal_names_the_row_count_it_needed(self) -> None:
        """A reader must be able to tell how far short the data fell."""

        fit = fit_contributed_model(
            panel_from_response_dataset(_dataset([_episode()]))
        )

        self.assertIn(str(MINIMUM_PANEL_ROWS), " ".join(fit.notes))

    def test_every_result_carries_the_quality_caveat(self) -> None:
        """The negative held-out fit travels with every number."""

        fit = fit_contributed_model(
            panel_from_response_dataset(_dataset([_episode()]))
        )

        self.assertIn(QUALITY_CAVEAT, fit.notes)

    def test_an_unknown_network_raises(self) -> None:
        """The contributed model provides two networks and no others."""

        with self.assertRaises(ContributedModelError):
            fit_contributed_model(
                panel_from_response_dataset(_dataset([_episode()])),
                network="transformer",
            )

    def test_the_default_network_is_the_better_of_the_two(self) -> None:
        """Multitask, whose held-out R-squared is the less negative."""

        self.assertEqual(DEFAULT_NETWORK, "multitask")


class ReportTest(unittest.TestCase):
    """The single entry point the evaluation stage calls."""

    def test_the_report_is_json_compatible(self) -> None:
        """Every value in it is a plain type the artifact can carry."""

        report = contributed_model_report(_dataset([_episode()]))

        self.assertEqual(report["contrib_folder"], "mlp")
        self.assertEqual(report["caveat"], QUALITY_CAVEAT)
        self.assertEqual(report["fit"]["status"], STATUS_INSUFFICIENT_DATA)
        self.assertFalse(report["fit"]["is_usable"])

    def test_the_contributors_own_recorded_quality_is_read_not_restated(self) -> None:
        """Their negative held-out R-squared comes from their own file."""

        recorded = recorded_contributor_quality()

        self.assertIsNotNone(recorded)
        self.assertLess(recorded["test"]["multitask"]["R2"], 0.0)
        self.assertLess(recorded["test"]["mlp"]["R2"], 0.0)

    def test_the_recorded_monotonicity_is_the_usable_signal(self) -> None:
        """Direction is sound even though magnitude is not."""

        recorded = recorded_contributor_quality()

        self.assertGreater(
            recorded["monotonicity"]["multitask"]["share_pred_up"], 0.9
        )


@NEEDS_NUMPY
class ContributedTrainerTest(unittest.TestCase):
    """Their code is imported in place and never copied."""

    def test_importing_the_trainer_trains_nothing(self) -> None:
        """Their main() is guarded, so an import has no side effect on results."""

        trainer = load_contributed_trainer()

        self.assertEqual(trainer.SEED, 42)
        self.assertEqual(trainer.AD_TYPES, AD_TYPES)

    def test_the_trainer_is_cached_rather_than_re_executed(self) -> None:
        """Two calls return the same module object."""

        self.assertIs(load_contributed_trainer(), load_contributed_trainer())

    def test_the_contributor_panel_loads_through_their_own_reader(self) -> None:
        """Their experiment is reproduced rather than re-parsed here."""

        panel = panel_from_contributor_file()

        self.assertEqual(panel.source, SOURCE_CONTRIBUTOR_PANEL)
        self.assertTrue(panel.recorded_split)
        self.assertTrue(panel.has_auxiliary_labels)
        self.assertGreater(len(panel), MINIMUM_PANEL_ROWS)


@NEEDS_NUMPY
class FitTest(unittest.TestCase):
    """Fitting on the contributor's own panel, which is the only panel that can."""

    def test_the_multitask_network_fits_their_panel(self) -> None:
        """Their recorded split is used, so this reproduces their experiment."""

        fit = fit_contributed_model(panel_from_contributor_file())

        self.assertEqual(fit.status, STATUS_FITTED)
        self.assertIsNotNone(fit.holdout_metrics)
        self.assertIsNotNone(fit.epochs)

    def test_a_negative_held_out_fit_is_not_usable(self) -> None:
        """The measurement decides usability; no caller can override it."""

        fit = fit_contributed_model(panel_from_contributor_file())

        self.assertLess(fit.holdout_r_squared, 0.0)
        self.assertFalse(fit.is_usable)

    def test_the_monotonicity_check_reports_direction(self) -> None:
        """Raise every budget ten percent and most predictions rise."""

        fit = fit_contributed_model(panel_from_contributor_file())

        self.assertGreater(fit.monotonicity["share_pred_up"], 0.5)

    def test_fitting_is_deterministic(self) -> None:
        """Seeded from their own SEED, so two fits agree."""

        first = fit_contributed_model(panel_from_contributor_file())
        second = fit_contributed_model(panel_from_contributor_file())

        self.assertEqual(first.holdout_metrics, second.holdout_metrics)

    def test_the_multitask_network_refuses_a_canonical_panel(self) -> None:
        """Its auxiliary heads have no labels in this project's dataset."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode(date=f"2026-{month:02d}-{day:02d}")
                    for month in range(1, 7)
                    for day in range(1, 29)
                ]
            )
        )
        fit = fit_contributed_model(panel)

        self.assertGreaterEqual(len(panel), MINIMUM_PANEL_ROWS)
        self.assertEqual(fit.status, STATUS_AUXILIARY_LABELS_UNAVAILABLE)
        self.assertFalse(fit.is_usable)

    def test_the_revenue_only_network_fits_a_canonical_panel(self) -> None:
        """The MLP needs only revenue, which this project does record."""

        panel = panel_from_response_dataset(
            _dataset(
                [
                    _episode(
                        date=f"2026-{month:02d}-{day:02d}",
                        configured_budget=50.0 + day,
                        revenue=200.0 + 4.0 * day,
                    )
                    for month in range(1, 7)
                    for day in range(1, 29)
                ]
            )
        )
        fit = fit_contributed_model(panel, network=NETWORK_MLP)

        self.assertEqual(fit.status, STATUS_FITTED)
        self.assertEqual(fit.panel.source, SOURCE_CANONICAL)
        self.assertIsNotNone(fit.holdout_r_squared)


if __name__ == "__main__":
    unittest.main()
