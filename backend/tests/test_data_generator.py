"""Tests for the bounded dashboard MTA-SIM generation workflow."""

from __future__ import annotations

import tempfile
import time
import unittest
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
        with patch.object(
            data_generator,
            "generator_overview",
            return_value={"available": True, "reason": ""},
        ):
            configuration["extends"] = "../../private.json"
            with self.assertRaisesRegex(ValueError, "self-contained"):
                data_generator.start_generation("baseline", configuration)
            configuration.pop("extends")
            configuration["report_end_date"] = "2030-01-01"
            with self.assertRaisesRegex(ValueError, "1 to 366"):
                data_generator.start_generation("baseline", configuration)

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
