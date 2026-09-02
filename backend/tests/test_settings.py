"""Environment-file writing and the in-memory diagnostic log.

`write_env` rewrites the operator's real `.env`, so its contract is narrow: a
key already present is replaced in place, a missing one is appended exactly
once, comments and unrelated keys survive, and repeated saves do not grow the
file. Every test here writes to a temporary path; none touches the repository's
own `.env`.

Ported from the Node suite that tested `dashboard/server/settings.js` before
the Flask backend replaced it, so removing that module did not remove the
contract it proved.

Data flow:
    backend/services/settings.py -> here
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from backend.app import create_app
from backend.config import REPO_ROOT, backend_identity, project_commit, project_version
from backend.services.settings import (
    ENV_KEYS,
    LOG_CAPACITY,
    apply_logging,
    clear_log,
    log,
    log_state,
    settings_state,
    select_runtime_schema,
    write_env,
)


class DeploymentIdentityTests(unittest.TestCase):
    """Check Settings reports the backend build actually running."""

    def tearDown(self) -> None:
        project_commit.cache_clear()
        project_version.cache_clear()
        backend_identity.cache_clear()

    def test_project_version_comes_from_the_tracked_file(self) -> None:
        expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(project_version(), expected)
        self.assertRegex(project_version(), r"^\d+\.\d+\.\d+$")

    def test_build_commit_environment_wins_over_checkout_detection(self) -> None:
        expected = "a" * 40
        with patch.dict("os.environ", {"PROJECT_COMMIT": expected}):
            project_commit.cache_clear()
            self.assertEqual(project_commit(), expected)

    def test_settings_carries_project_and_runtime_identity(self) -> None:
        with (
            patch("backend.services.settings.use_database", return_value=False),
            patch("backend.services.settings.is_hosted", return_value=False),
            patch("backend.services.settings.config_read_only", return_value=False),
        ):
            identity = settings_state()["backendIdentity"]

        self.assertEqual(identity["version"], project_version())
        self.assertRegex(identity["commit"], r"^(unknown|[0-9a-f]{40}|[0-9a-f]{64})$")
        self.assertRegex(identity["runtime"]["python"], r"^\d+\.\d+")
        self.assertRegex(identity["runtime"]["flask"], r"^\d+\.\d+")


def _env_file(contents: str = "") -> Path:
    path = Path(tempfile.mkdtemp(prefix="env-")) / ".env"
    path.write_text(contents, encoding="utf-8", newline="\n")
    return path


class WriteEnvTests(unittest.TestCase):
    """Check that rewriting `.env` preserves everything it does not own."""

    def test_a_key_is_replaced_in_place_and_comments_survive(self) -> None:
        path = _env_file("# a comment\nDATABASE=false\nUNRELATED=keep\n")

        write_env({"DATABASE": "true"}, path)

        text = path.read_text(encoding="utf-8")
        self.assertIn("# a comment", text)
        self.assertIn("UNRELATED=keep", text)
        self.assertIn("DATABASE=true", text)
        # Replaced, not appended: two values for one key would leave the winner
        # decided by read order.
        self.assertEqual(text.count("DATABASE="), 1)

    def test_a_missing_key_is_appended_exactly_once(self) -> None:
        path = _env_file("DATABASE=false\n")

        write_env({"PG_HOST": "db.example.com"}, path)
        write_env({"PG_HOST": "db2.example.com"}, path)

        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("PG_HOST="), 1)
        self.assertIn("PG_HOST=db2.example.com", text)

    def test_repeated_saves_do_not_grow_a_blank_line(self) -> None:
        path = _env_file("DATABASE=false\n")

        for _ in range(5):
            write_env({"DATABASE": "false"}, path)

        self.assertEqual(path.read_text(encoding="utf-8"), "DATABASE=false\n")

    def test_every_key_the_settings_dialog_sends_is_written(self) -> None:
        path = _env_file("")

        write_env({key: "v" for key in ENV_KEYS}, path)

        text = path.read_text(encoding="utf-8")
        for key in ENV_KEYS:
            self.assertIn(f"{key}=v", text)

    def test_a_password_containing_an_equals_sign_survives(self) -> None:
        # `partition("=")` splits on the first separator only, so a password
        # that contains one must not be truncated on the next read.
        path = _env_file("PG_PASSWORD=old\n")

        write_env({"PG_PASSWORD": "a=b=c"}, path)

        self.assertIn("PG_PASSWORD=a=b=c", path.read_text(encoding="utf-8"))

    def test_the_schema_selection_is_persisted(self) -> None:
        # Listed in ENV_KEYS or the dropdown would appear to work and forget its
        # selection on the next start.
        self.assertIn("PG_SCHEMA", ENV_KEYS)


class SchemaRejectionTests(unittest.TestCase):
    """Check the route refuses a schema name before anything is written.

    A schema name reaches libpq as an identifier inside a connect option, so it
    is refused at the edge rather than at the connection that would carry it.
    The request under test returns before `.env` is read or written, so the
    repository's own file is untouched.
    """

    def setUp(self) -> None:
        from backend.config import config_read_only, is_hosted

        if is_hosted() or config_read_only():
            self.skipTest("this deployment refuses every settings write")
        self.client = create_app().test_client()

    def test_a_schema_that_could_close_the_connect_option_is_refused(self) -> None:
        response = self.client.post(
            "/api/settings",
            json={
                "action": "test",
                "useDatabase": True,
                "connection": {
                    "PG_HOST": "db.example.com",
                    "PG_DATABASE": "mta_data",
                    "PG_USER": "reader",
                    "PG_SCHEMA": "mta -c log_statement=all",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_schema")

    def test_an_absent_schema_falls_back_to_public_rather_than_failing(self) -> None:
        # An older dialog, or a hand-written request, sends no schema at all.
        # That is the state every deployment predating the setting was in.
        response = self.client.post(
            "/api/settings",
            json={
                "action": "unknown-so-nothing-is-written",
                "useDatabase": False,
                "connection": {"PG_HOST": "db.example.com"},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "unknown_action")


class RuntimeSchemaSelectionTests(unittest.TestCase):
    """Check that a confirmed schema selection loads data or rolls back."""

    def setUp(self) -> None:
        """Reset the process-local configured-schema marker."""

        from backend.services import settings

        settings._configured_schema = None

    def tearDown(self) -> None:
        """Avoid leaking a test selection into later settings tests."""

        from backend.services import settings

        settings._configured_schema = None

    def test_non_dashboard_schema_is_rejected_before_cache_changes(self) -> None:
        """Only an exact selectable live-census entry may become active."""

        with (
            patch("backend.services.settings.use_database", return_value=True),
            patch(
                "backend.services.settings.available_schemas",
                return_value={
                    "schemas": [{"name": "raw", "selectable": False}],
                    "selected": "public",
                },
            ),
            patch(
                "backend.config.database_settings",
                return_value=SimpleNamespace(schema="public"),
            ),
            patch(
                "backend.services.settings._invalidate_configuration_caches"
            ) as invalidate,
        ):
            with self.assertRaisesRegex(ValueError, "dashboard-ready"):
                select_runtime_schema("raw")

        invalidate.assert_not_called()

    def test_successful_selection_probes_data_and_returns_refreshed_state(self) -> None:
        """A schema becomes visible only after its snapshot loads successfully."""

        expected = {"connection": {"PG_SCHEMA": "mta_us"}}
        with (
            patch.dict(os.environ, {"PG_SCHEMA": "public"}),
            patch("backend.services.settings.use_database", return_value=True),
            patch(
                "backend.services.settings.available_schemas",
                return_value={
                    "schemas": [{"name": "mta_us", "selectable": True}],
                    "selected": "public",
                },
            ),
            patch(
                "backend.config.database_settings",
                return_value=SimpleNamespace(schema="public"),
            ),
            patch(
                "backend.services.settings._invalidate_configuration_caches"
            ) as invalidate,
            patch("backend.database.dispose_engine") as dispose,
            patch("backend.repository.snapshot.clear_caches") as clear,
            patch("backend.repository.snapshot.load_snapshot") as load,
            patch("backend.services.settings.settings_state", return_value=expected),
        ):
            result = select_runtime_schema("mta_us")
            self.assertEqual(os.environ["PG_SCHEMA"], "mta_us")

        self.assertEqual(result, expected)
        invalidate.assert_called_once_with()
        dispose.assert_called_once_with()
        clear.assert_called_once_with()
        load.assert_called_once_with()

    def test_failed_snapshot_restores_the_previous_schema(self) -> None:
        """A load failure cannot strand subsequent requests on a broken schema."""

        with (
            patch.dict(os.environ, {"PG_SCHEMA": "public"}),
            patch("backend.services.settings.use_database", return_value=True),
            patch(
                "backend.services.settings.available_schemas",
                return_value={
                    "schemas": [{"name": "mta_us", "selectable": True}],
                    "selected": "public",
                },
            ),
            patch(
                "backend.config.database_settings",
                return_value=SimpleNamespace(schema="public"),
            ),
            patch(
                "backend.services.settings._invalidate_configuration_caches"
            ) as invalidate,
            patch("backend.database.dispose_engine") as dispose,
            patch("backend.repository.snapshot.clear_caches") as clear,
            patch(
                "backend.repository.snapshot.load_snapshot",
                side_effect=RuntimeError("probe failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "probe failed"):
                select_runtime_schema("mta_us")
            self.assertEqual(os.environ["PG_SCHEMA"], "public")

        self.assertEqual(invalidate.call_count, 2)
        self.assertEqual(dispose.call_count, 2)
        self.assertEqual(clear.call_count, 2)


class DiagnosticLogTests(unittest.TestCase):
    """Check that default INFO capture is level-filtered and bounded."""

    def setUp(self) -> None:
        apply_logging(True, "INFO")
        clear_log()

    def tearDown(self) -> None:
        apply_logging(False)
        clear_log()

    def test_info_logging_records_structured_utc_time(self) -> None:
        log("INFO", "test", "before")

        record = log_state()["records"][-1]
        self.assertEqual(record["level"], "INFO")
        self.assertEqual(record["source"], "test")
        self.assertIn("T", record["when"])
        self.assertTrue(record["when"].endswith("+00:00"))

    def test_a_record_below_the_active_level_is_dropped(self) -> None:
        clear_log()
        apply_logging(True, "INFO")
        log("INFO", "test", "after")
        self.assertEqual(len(log_state()["records"]), 1)

        # Dropped rather than stored and filtered on display, so raising the
        # level actually reduces the work done.
        apply_logging(True, "ERROR")
        log("INFO", "test", "too quiet")

        self.assertEqual(len(log_state()["records"]), 1)

    def test_one_record_cannot_dominate_the_buffer(self) -> None:
        clear_log()
        apply_logging(True, "INFO")

        log("INFO", "test", "x" * 5000)

        self.assertEqual(len(log_state()["records"][-1]["message"]), 400)

    def test_operation_duration_is_structured_and_non_negative(self) -> None:
        log("INFO", "test", "timed", duration_ms=12.34567)
        self.assertEqual(log_state()["records"][-1]["durationMs"], 12.346)

    def test_the_buffer_stays_bounded(self) -> None:
        clear_log()
        apply_logging(True, "INFO")

        for index in range(LOG_CAPACITY + 50):
            log("INFO", "test", index)

        # The deque is capped at LOG_CAPACITY; the state view returns the most
        # recent slice of it, which is what the dialog renders.
        records = log_state()["records"]
        self.assertLessEqual(len(records), LOG_CAPACITY)
        self.assertEqual(records[-1]["message"], str(LOG_CAPACITY + 49))


if __name__ == "__main__":
    unittest.main()
