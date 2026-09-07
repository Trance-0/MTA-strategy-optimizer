"""Tests for the bounded dashboard MTA-SIM generation workflow."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app
from backend.services import data_generator


MTA_SIM_AVAILABLE = not data_generator._generator_unavailability_reason()


def _bounded_configuration() -> dict:
    """Return the smallest request object needed by boundary validation."""

    return {
        "seed": 41,
        "advertiser_id": "synthetic_test_advertiser",
        "report_start_date": "2026-01-01",
        "report_end_date": "2026-01-07",
        "base_product_price": 25.0,
        "marketplaces": [{"code": "US", "currency_code": "USD"}],
        "touchpoints": [{}],
        "path_scenarios": [{}],
        "campaign_replications": 1,
    }


def _baseline_configuration() -> dict:
    """Return a self-contained baseline configuration valid at this boundary."""

    return {
        "seed": 41,
        "advertiser_id": "synthetic_test_advertiser",
        "report_start_date": "2026-01-01",
        "report_end_date": "2026-01-07",
        "base_product_price": 25.0,
        "baseline_conversion_log_odds": -3.0,
        "campaign_replications": 1,
        "global_behavior": {
            "weekly_traffic_multipliers": [1.0] * 7,
            "daily_traffic_trend": 0.0,
            "conversion_probability_daily_noise_standard_deviation": 0.0,
            "performance_volume_noise_standard_deviation": 0.0,
            "path_audience_noise_standard_deviation": 0.0,
            "performance_revenue_noise_standard_deviation": 0.0,
            "path_revenue_noise_standard_deviation": 0.0,
            "additional_unit_probability": 0.0,
            "repeat_purchase_probability": 0.0,
        },
        "marketplaces": [
            {
                "code": "US",
                "currency_code": "USD",
                "traffic_multiplier": 1.0,
                "price_multiplier": 1.0,
            }
        ],
        "touchpoints": [
            {
                "identifier": "display_ad",
                "base_impressions": 1000,
                "click_through_rate": 0.02,
                "platform_conversion_rate": 0.03,
                "cost_per_click": None,
                "cost_per_thousand_impressions": 12.5,
                "conversion_log_odds_effect": 0.1,
            },
            {
                "identifier": "sponsored_product",
                "base_impressions": 1000,
                "click_through_rate": 0.02,
                "platform_conversion_rate": 0.03,
                "cost_per_click": 0.75,
                "cost_per_thousand_impressions": None,
                "conversion_log_odds_effect": 0.1,
            },
        ],
        "path_scenarios": [
            {
                "identifier": "display_then_product",
                "touchpoint_identifiers": ["display_ad", "sponsored_product"],
                "base_users": 100,
                "adjacent_synergy_log_odds": 0.0,
            }
        ],
    }


def _regional_configuration() -> dict:
    """Return a self-contained regional configuration valid at this boundary."""

    configuration = _baseline_configuration()
    configuration["marketplaces"][0].update(
        {
            "internet_reach_rate": 0.8,
            "target_audience_density": 0.6,
            "economic_willingness_multiplier": 1.0,
            "income_inequality_gini": 0.4,
        }
    )
    configuration["regional_behavior"] = {
        "reference_internet_reach_rate": 0.8,
        "reference_target_audience_density": 0.6,
        "reference_income_inequality_gini": 0.4,
        "economic_willingness_log_odds_weight": 0.0,
        "income_inequality_noise_weight": 0.0,
    }
    return configuration


@contextmanager
def _available_generator():
    """Expose only the capability boundary needed by hermetic validation tests."""

    with patch.object(data_generator, "_generator_unavailability_reason", return_value=""):
        yield


@contextmanager
def _accepted_by_pinned_loader():
    """Accept one valid configuration without requiring the pinned checkout."""

    with (
        _available_generator(),
        patch.object(data_generator, "load_resolved_mta_sim_configuration"),
    ):
        yield


class GeneratorServiceTests(unittest.TestCase):
    """Exercise a real toy run and the request-boundary refusals."""

    def setUp(self) -> None:
        """Give each test isolated ignored output and service state."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output_patch = patch.object(
            data_generator, "OUTPUT_ROOT", Path(self.temporary.name)
        )
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)
        with data_generator._lock:
            data_generator._runs.clear()
            data_generator._active_operation = None

    @unittest.skipUnless(
        MTA_SIM_AVAILABLE,
        "the pinned MTA-SIM checkout is not initialized",
    )
    def test_default_run_returns_only_two_bounded_public_previews(self) -> None:
        """The browser sees two tables and no path, configuration, or truth."""

        overview = data_generator.generator_overview()
        self.assertTrue(overview["available"])
        started = data_generator.start_generation("baseline", overview["configuration"])
        state = self._wait(started["runId"])
        self.assertEqual(state["status"], "completed")
        self.assertEqual(
            [item["key"] for item in state["previews"]], ["path", "performance"]
        )
        self.assertTrue(all(len(item["rows"]) <= 20 for item in state["previews"]))
        rendered = repr(state).lower()
        self.assertNotIn("simulation_ground_truth", rendered)
        self.assertNotIn("configuration_path", rendered)
        self.assertNotIn(str(Path(self.temporary.name)).lower(), rendered)
        path, name = data_generator.download_path(started["runId"], "path")
        self.assertTrue(path.is_file())
        self.assertEqual(name, "amc_path_report.csv")

    def test_client_paths_and_unbounded_configuration_are_refused(self) -> None:
        """A request cannot make the server read a path or create huge work."""

        configuration = _bounded_configuration()
        with _available_generator():
            configuration["extends"] = "../../private.json"
            with self.assertRaisesRegex(ValueError, "self-contained"):
                data_generator.start_generation("baseline", configuration)
            configuration.pop("extends")
            configuration["report_end_date"] = "2030-01-01"
            with self.assertRaisesRegex(ValueError, "1 to 366"):
                data_generator.start_generation("baseline", configuration)

    def test_generation_persists_the_submitted_unknown_configuration_fields(
        self,
    ) -> None:
        """Loader normalization must not remove accepted unknown input fields."""

        configuration = _baseline_configuration()
        configuration["touchpoint_overrides"] = {
            "display_ad": {"cost_per_thousand_impressions": 12.5}
        }
        configuration["provenance"] = {"source": "preserved user input"}
        with (
            _accepted_by_pinned_loader(),
            patch("backend.services.data_generator.threading.Thread"),
        ):
            started = data_generator.start_generation("baseline", configuration)
        with data_generator._lock:
            run = data_generator._runs[started["runId"]]
        persisted = json.loads(run.configuration_path.read_text(encoding="utf-8"))
        configuration["touchpoint_overrides"]["display_ad"][
            "cost_per_thousand_impressions"
        ] = 999.0
        configuration["provenance"]["source"] = "mutated after submission"
        self.assertEqual(
            persisted["touchpoint_overrides"],
            {"display_ad": {"cost_per_thousand_impressions": 12.5}},
        )
        self.assertEqual(persisted["provenance"], {"source": "preserved user input"})

    def test_postgresql_fields_are_validated_and_absent_from_public_state(self) -> None:
        """Connection secrets are accepted only at the backend boundary."""

        values = data_generator._validate_connection(
            {
                "host": "db.example.test",
                "port": "5432",
                "database": "mta",
                "user": "writer",
                "password": "not-a-real-password",
                "sslmode": "require",
                "schema": "generated_run",
            }
        )
        self.assertEqual(values["password"], "not-a-real-password")
        run = data_generator.GeneratorRun(
            "0" * 32,
            "baseline",
            Path(self.temporary.name),
            Path(self.temporary.name) / "configuration.json",
        )
        self.assertNotIn("password", repr(run.public_state()).lower())
        with self.assertRaisesRegex(ValueError, "SSL mode"):
            data_generator._validate_connection(
                {
                    "host": "db.example.test",
                    "database": "mta",
                    "user": "writer",
                    "password": "secret",
                    "sslmode": "disable",
                    "schema": "generated_run",
                }
            )

    def _wait(self, run_id: str) -> dict:
        """Wait briefly for the toy generator thread."""

        for _ in range(200):
            state = data_generator.get_run(run_id)
            if state["status"] in {"completed", "failed"}:
                return state
            time.sleep(0.025)
        self.fail("toy generator did not finish")


class GeneratorRouteTests(unittest.TestCase):
    """Pin route registration and the secure credential transport gate."""

    def setUp(self) -> None:
        """Create a local Flask client without any external service."""

        self.client = create_app().test_client()

    def test_overview_and_preset_are_registered(self) -> None:
        """A live backend serves a self-contained reviewed configuration."""

        with patch(
            "backend.api.data_generator.preset_configuration",
            return_value=_bounded_configuration(),
        ):
            preset = self.client.get("/api/data-generator/presets/baseline/toy")
        self.assertEqual(preset.status_code, 200)
        self.assertNotIn("extends", preset.get_json()["configuration"])

    def test_preflight_accepts_reviewed_baseline_and_regional_configurations(
        self,
    ) -> None:
        """Preflight accepts both self-contained reviewed generator variants."""

        with _accepted_by_pinned_loader():
            for variant, configuration in (
                ("baseline", _baseline_configuration()),
                ("regional", _regional_configuration()),
            ):
                response = self.client.post(
                    "/api/data-generator/validate",
                    json={"variant": variant, "configuration": configuration},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), {"valid": True, "issues": []})

    def test_preflight_returns_a_precise_structured_field_issue(self) -> None:
        """A malformed seed must identify its field and owning editor section."""

        configuration = _baseline_configuration()
        configuration["seed"] = "not-an-integer"
        with _available_generator():
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": configuration},
            )
        payload = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error"], "invalid_configuration")
        self.assertFalse(payload["valid"])
        self.assertIn(
            {
                "path": "/seed",
                "section": "basics",
                "message": "Seed must be an integer.",
            },
            payload["issues"],
        )

    def test_preflight_reports_duplicate_touchpoint_identifier_at_duplicate_item(
        self,
    ) -> None:
        """A duplicate identifier must point to the second editable card."""

        configuration = _baseline_configuration()
        configuration["touchpoints"][1]["identifier"] = configuration["touchpoints"][0][
            "identifier"
        ]
        with _available_generator():
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": configuration},
            )
        issue_paths = {issue["path"] for issue in response.get_json()["issues"]}
        self.assertEqual(response.status_code, 400)
        self.assertIn("/touchpoints/1/identifier", issue_paths)

    def test_preflight_reports_invalid_path_reference_at_reference_element(
        self,
    ) -> None:
        """An unknown path member must identify the exact scenario list element."""

        configuration = _baseline_configuration()
        configuration["path_scenarios"][0]["touchpoint_identifiers"][1] = "missing"
        with _available_generator():
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": configuration},
            )
        issue_paths = {issue["path"] for issue in response.get_json()["issues"]}
        self.assertEqual(response.status_code, 400)
        self.assertIn("/path_scenarios/0/touchpoint_identifiers/1", issue_paths)

    def test_preflight_structures_non_string_path_references(self) -> None:
        """Non-string path members must not escape validation as a TypeError."""

        for invalid_reference in ([], {}):
            with self.subTest(invalid_reference=invalid_reference):
                configuration = _baseline_configuration()
                configuration["path_scenarios"][0]["touchpoint_identifiers"][0] = (
                    invalid_reference
                )
                with _available_generator():
                    response = self.client.post(
                        "/api/data-generator/validate",
                        json={"variant": "baseline", "configuration": configuration},
                    )
                payload = response.get_json()
                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    "/path_scenarios/0/touchpoint_identifiers/0",
                    {issue["path"] for issue in payload["issues"]},
                )

    def test_preflight_requires_exactly_one_touchpoint_billing_basis(self) -> None:
        """A card with CPC and CPM must be rejected at its billing field."""

        configuration = _baseline_configuration()
        configuration["touchpoints"][0]["cost_per_click"] = 1.0
        with _available_generator():
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": configuration},
            )
        issue_paths = {issue["path"] for issue in response.get_json()["issues"]}
        self.assertEqual(response.status_code, 400)
        self.assertIn("/touchpoints/0/cost_per_click", issue_paths)

    def test_preflight_points_an_invalid_cpm_to_the_cpm_field(self) -> None:
        """A malformed CPM must not be reported against the null CPC field."""

        configuration = _baseline_configuration()
        configuration["touchpoints"][0]["cost_per_thousand_impressions"] = "bad"
        with _available_generator():
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": configuration},
            )
        issue_paths = {issue["path"] for issue in response.get_json()["issues"]}
        self.assertEqual(response.status_code, 400)
        self.assertIn("/touchpoints/0/cost_per_thousand_impressions", issue_paths)
        self.assertNotIn("/touchpoints/0/cost_per_click", issue_paths)

    def test_preflight_rejects_extreme_numbers_and_depth_without_a_500(self) -> None:
        """Finite checks and traversal limits must remain structured at extremes."""

        extreme = _baseline_configuration()
        extreme["base_product_price"] = 10**400
        nested: dict = {}
        cursor = nested
        for _ in range(70):
            cursor["nested"] = {}
            cursor = cursor["nested"]
        deep = _baseline_configuration()
        deep["unknown_extension"] = nested
        with _available_generator():
            responses = [
                self.client.post(
                    "/api/data-generator/validate",
                    json={"variant": "baseline", "configuration": configuration},
                )
                for configuration in (extreme, deep)
            ]
        for response in responses:
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json()["error"], "invalid_configuration")

    def test_preflight_caps_reference_validation_and_returned_issues(self) -> None:
        """One hostile path list cannot create an input-sized issue response."""

        configuration = _baseline_configuration()
        configuration["path_scenarios"][0]["touchpoint_identifiers"] = [
            f"missing_{index}" for index in range(500)
        ]
        with _available_generator():
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": configuration},
            )
        payload = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertLessEqual(len(payload["issues"]), 128)
        self.assertIn(
            "/path_scenarios/0/touchpoint_identifiers",
            {issue["path"] for issue in payload["issues"]},
        )

    def test_invalid_variant_precedes_missing_generator_capability(self) -> None:
        """A client variant error remains a 400 even when the checkout is absent."""

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(data_generator, "SUBMODULE_ROOT", Path(directory) / "missing"):
                response = self.client.post(
                    "/api/data-generator/validate",
                    json={"variant": "unknown", "configuration": _baseline_configuration()},
                )
        self.assertEqual(response.status_code, 400)
        self.assertIn("/variant", {item["path"] for item in response.get_json()["issues"]})

    def test_validation_requires_only_the_selected_loader_not_example_files(self) -> None:
        """Self-contained preflight must not depend on either reviewed preset file."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loader = root / "ZheyuanWu" / "simulations" / "baseline" / "mta_dataset"
            loader.mkdir(parents=True)
            (root / "ZheyuanWu" / "simulations" / "__init__.py").touch()
            (loader / "__init__.py").touch()
            (loader / "configuration.py").touch()
            with (
                patch.object(data_generator, "SUBMODULE_ROOT", root),
                patch.object(data_generator, "load_resolved_mta_sim_configuration"),
            ):
                response = self.client.post(
                    "/api/data-generator/validate",
                    json={"variant": "baseline", "configuration": _baseline_configuration()},
                )
        self.assertEqual(response.status_code, 200)

    def test_baseline_preset_does_not_require_the_regional_preset(self) -> None:
        """A missing sibling preset cannot disable the selected reviewed file."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loader = root / "ZheyuanWu" / "simulations" / "baseline" / "mta_dataset"
            examples = root / "ZheyuanWu" / "examples"
            loader.mkdir(parents=True)
            examples.mkdir()
            (root / "ZheyuanWu" / "simulations" / "__init__.py").touch()
            (loader / "__init__.py").touch()
            (loader / "configuration.py").touch()
            (examples / "baseline.toy.json").write_text("{}", encoding="utf-8")
            with (
                patch.object(data_generator, "SUBMODULE_ROOT", root),
                patch.object(
                    data_generator,
                    "load_resolved_mta_sim_configuration",
                    return_value=_baseline_configuration(),
                ),
            ):
                response = self.client.get("/api/data-generator/presets/baseline/toy")
        self.assertEqual(response.status_code, 200)

    def test_preflight_storage_failures_are_bounded_unavailability(self) -> None:
        """Temporary storage failures are infrastructure state, not client errors."""

        with (
            _available_generator(),
            patch(
                "backend.services.data_generator.tempfile.NamedTemporaryFile",
                side_effect=OSError("private path must not escape"),
            ),
        ):
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": _baseline_configuration()},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "generator_unavailable")
        self.assertNotIn("private path", response.get_data(as_text=True))

    def test_preflight_cleanup_failures_are_bounded_unavailability(self) -> None:
        """Temporary cleanup failures cannot expose paths or become HTTP 500."""

        temporary_paths: list[Path] = []

        def fail_cleanup(path: Path, *, missing_ok: bool = False) -> None:
            del missing_ok
            temporary_paths.append(path)
            raise OSError("private cleanup path must not escape")

        try:
            with (
                _accepted_by_pinned_loader(),
                patch.object(Path, "unlink", fail_cleanup),
            ):
                response = self.client.post(
                    "/api/data-generator/validate",
                    json={"variant": "baseline", "configuration": _baseline_configuration()},
                )
        finally:
            for path in temporary_paths:
                path.unlink(missing_ok=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "generator_unavailable")
        self.assertNotIn("private cleanup path", response.get_data(as_text=True))

    def test_run_route_does_not_default_an_omitted_variant(self) -> None:
        """Run creation must pass the same missing variant that preflight rejects."""

        with patch(
            "backend.api.data_generator.start_generation", return_value={}
        ) as start:
            response = self.client.post(
                "/api/data-generator/runs",
                json={"configuration": _baseline_configuration()},
            )
        self.assertEqual(response.status_code, 202)
        start.assert_called_once_with(None, _baseline_configuration())

    def test_preflight_reports_regional_ranges_at_regional_property(self) -> None:
        """Regional reach outside its allowed range must retain field context."""

        configuration = _regional_configuration()
        configuration["regional_behavior"]["reference_internet_reach_rate"] = 0
        with _available_generator():
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "regional", "configuration": configuration},
            )
        issue_paths = {issue["path"] for issue in response.get_json()["issues"]}
        self.assertEqual(response.status_code, 400)
        self.assertIn("/regional_behavior/reference_internet_reach_rate", issue_paths)

    def test_preflight_unavailable_capability_is_bounded(self) -> None:
        """Missing pinned source returns the established 503 capability response."""

        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing-submodule"
            with patch.object(data_generator, "SUBMODULE_ROOT", missing):
                response = self.client.post(
                    "/api/data-generator/validate",
                    json={"variant": "baseline", "configuration": {}},
                )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "generator_unavailable")
        self.assertNotIn(str(missing), response.get_data(as_text=True))

    def test_preflight_missing_variant_loader_is_a_bounded_capability_failure(
        self,
    ) -> None:
        """A partial pinned checkout cannot be attributed to client configuration."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "partial-submodule"
            project = root / "ZheyuanWu"
            (project / "simulations").mkdir(parents=True)
            (project / "simulations" / "__init__.py").touch()
            examples = project / "examples"
            examples.mkdir()
            for filename in ("baseline.toy.json", "regional.toy.json"):
                (examples / filename).write_text("{}", encoding="utf-8")
            with patch.object(data_generator, "SUBMODULE_ROOT", root):
                response = self.client.post(
                    "/api/data-generator/validate",
                    json={"variant": "baseline", "configuration": {}},
                )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "generator_unavailable")
        self.assertNotIn(str(root), response.get_data(as_text=True))

    def test_successful_preflight_creates_no_state_thread_or_output_and_cleans_tempfile(
        self,
    ) -> None:
        """Successful direct validation must leave no observable service residue."""

        configuration = _baseline_configuration()
        real_named_temporary_file = tempfile.NamedTemporaryFile
        created_paths: list[Path] = []

        def track_temporary_file(*args, **kwargs):
            temporary = real_named_temporary_file(*args, **kwargs)
            created_paths.append(Path(temporary.name))
            return temporary

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "output"
            output_root.mkdir()
            with patch.object(data_generator, "OUTPUT_ROOT", output_root):
                with data_generator._lock:
                    data_generator._runs.clear()
                    data_generator._active_operation = None
                with (
                    _accepted_by_pinned_loader(),
                    patch(
                        "backend.services.data_generator.tempfile.NamedTemporaryFile",
                        side_effect=track_temporary_file,
                    ),
                    patch(
                        "backend.services.data_generator.threading.Thread",
                        side_effect=AssertionError("preflight must not start a thread"),
                    ),
                ):
                    response = self.client.post(
                        "/api/data-generator/validate",
                        json={"variant": "baseline", "configuration": configuration},
                    )
                with data_generator._lock:
                    self.assertEqual(data_generator._runs, {})
                    self.assertIsNone(data_generator._active_operation)
                self.assertEqual(list(output_root.iterdir()), [])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(created_paths)
        self.assertTrue(all(not path.exists() for path in created_paths))

    def test_loader_failure_cleans_preflight_temporary_file_without_state(
        self,
    ) -> None:
        """A failed loader validation must remove its temporary input file."""

        configuration = _baseline_configuration()
        real_named_temporary_file = tempfile.NamedTemporaryFile
        created_paths: list[Path] = []

        def track_temporary_file(*args, **kwargs):
            temporary = real_named_temporary_file(*args, **kwargs)
            created_paths.append(Path(temporary.name))
            return temporary

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "output"
            output_root.mkdir()
            with patch.object(data_generator, "OUTPUT_ROOT", output_root):
                with data_generator._lock:
                    data_generator._runs.clear()
                    data_generator._active_operation = None
                with (
                    _available_generator(),
                    patch(
                        "backend.services.data_generator.tempfile.NamedTemporaryFile",
                        side_effect=track_temporary_file,
                    ),
                    patch(
                        "backend.services.data_generator.load_resolved_mta_sim_configuration",
                        side_effect=ValueError("forced loader failure"),
                    ),
                ):
                    response = self.client.post(
                        "/api/data-generator/validate",
                        json={"variant": "baseline", "configuration": configuration},
                    )
                with data_generator._lock:
                    self.assertEqual(data_generator._runs, {})
                    self.assertIsNone(data_generator._active_operation)
                self.assertEqual(list(output_root.iterdir()), [])
        self.assertEqual(response.status_code, 400)
        self.assertTrue(created_paths)
        self.assertTrue(all(not path.exists() for path in created_paths))

    def test_preflight_scrubs_upstream_paths_from_invalid_configuration_issue(
        self,
    ) -> None:
        """An upstream loader failure cannot disclose a server-side pathname."""

        configuration = _baseline_configuration()
        with (
            _available_generator(),
            patch(
                "backend.services.data_generator.load_resolved_mta_sim_configuration",
                side_effect=ValueError("cannot load /private/service/configuration.json"),
            ),
        ):
            response = self.client.post(
                "/api/data-generator/validate",
                json={"variant": "baseline", "configuration": configuration},
            )
        payload = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            {"path": "/", "section": "configuration"},
            [
                {"path": issue["path"], "section": issue["section"]}
                for issue in payload["issues"]
            ],
        )
        self.assertNotIn("/private/service", response.get_data(as_text=True))

    def test_invalid_run_reuses_preflight_before_creating_runtime_state(self) -> None:
        """A rejected run request must not allocate a run, directory, or thread."""

        configuration = _baseline_configuration()
        configuration["campaign_replications"] = 0
        with tempfile.TemporaryDirectory() as directory:
            with (
                _available_generator(),
                patch.object(data_generator, "OUTPUT_ROOT", Path(directory)),
            ):
                with data_generator._lock:
                    data_generator._runs.clear()
                    data_generator._active_operation = None
                response = self.client.post(
                    "/api/data-generator/runs",
                    json={"variant": "baseline", "configuration": configuration},
                )
                with data_generator._lock:
                    self.assertEqual(data_generator._runs, {})
                    self.assertIsNone(data_generator._active_operation)
                self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_configuration")

    def test_uninitialized_submodule_is_bounded_capability_state(self) -> None:
        """Missing pinned source returns availability and 503, never a 500."""

        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing-submodule"
            with patch.object(data_generator, "SUBMODULE_ROOT", missing):
                response = self.client.get("/api/data-generator")
                preset = self.client.get("/api/data-generator/presets/baseline/toy")
            rendered = preset.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["available"])
        self.assertEqual(response.get_json()["configuration"], {})
        self.assertEqual(preset.status_code, 503)
        self.assertEqual(preset.get_json()["error"], "generator_unavailable")
        self.assertNotIn(str(missing), rendered)

    def test_remote_plain_http_never_accepts_postgresql_credentials(self) -> None:
        """Credential submission is refused before run or body inspection."""

        response = self.client.post(
            f"/api/data-generator/runs/{'0' * 32}/postgresql",
            json={"connection": {"password": "not-a-real-password"}},
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "secure_transport_required")
        self.assertNotIn("not-a-real-password", response.get_data(as_text=True))

    def test_untrusted_forwarded_protocol_cannot_impersonate_https(self) -> None:
        """The default application ignores a caller-supplied proxy header."""

        response = self.client.post(
            f"/api/data-generator/runs/{'0' * 32}/postgresql",
            json={"connection": {"password": "not-a-real-password"}},
            headers={"X-Forwarded-Proto": "https"},
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
        )
        self.assertEqual(response.status_code, 403)

    def test_one_configured_proxy_hop_may_declare_https(self) -> None:
        """A managed TLS-terminating deployment reaches route validation."""

        with patch("backend.app.trust_proxy_headers", return_value=True):
            client = create_app().test_client()
        response = client.post(
            f"/api/data-generator/runs/{'0' * 32}/postgresql",
            json={"connection": {}},
            headers={"X-Forwarded-Proto": "https"},
            environ_base={"REMOTE_ADDR": "10.0.0.10"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_connection")


if __name__ == "__main__":
    unittest.main()
