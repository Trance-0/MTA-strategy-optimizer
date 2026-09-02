"""Validation and bounded logging for dashboard database-schema operations.

The tests use recorded census entries and never connect to PostgreSQL or start
a child process. They prove that browser values become fixed argument vectors
only after the live capability contract has accepted them.

Data flow:
    backend/services/schema_operations.py -> here
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.services.schema_operations import (
    MAX_LINES,
    OperationError,
    SchemaOperation,
    arguments_for,
    validate_request,
)


def _schema(name: str, kind: str, initialize: bool, derive: bool) -> dict:
    return {
        "name": name,
        "kind": kind,
        "canInitialize": initialize,
        "canDerive": derive,
    }


class ArgumentTests(unittest.TestCase):
    """Check every command is a fixed vector with explicit replacement."""

    def test_initializer_targets_the_requested_schema(self) -> None:
        args = arguments_for("initialize", "public")

        self.assertEqual(args[:4], [sys.executable, "-X", "utf8", "-B"])
        self.assertIn("script/import_to_database.py", args)
        self.assertEqual(args[args.index("--schema") + 1], "public")
        self.assertNotIn("--replace", args)

    def test_parser_reads_every_scenario_and_replacement_is_explicit(self) -> None:
        args = arguments_for("derive", "mta", replace=True)

        self.assertEqual(args[:4], [sys.executable, "-X", "utf8", "-B"])
        self.assertIn("script/derive_scenario_schemas.py", args)
        self.assertEqual(args[args.index("--source") + 1], "mta")
        self.assertIn("--all", args)
        self.assertIn("--replace", args)


class CapabilityTests(unittest.TestCase):
    """Check unsafe targets fail before a process could start."""

    def test_a_new_schema_may_be_initialized(self) -> None:
        args = validate_request("initialize", "new_scenario", False, [])
        self.assertIn("new_scenario", args)

    def test_an_unrelated_populated_schema_is_never_initialized(self) -> None:
        with self.assertRaisesRegex(OperationError, "mix unrelated data"):
            validate_request(
                "initialize",
                "billing",
                True,
                [_schema("billing", "other", False, False)],
            )

    def test_a_dashboard_schema_requires_explicit_replacement(self) -> None:
        census = [_schema("public", "dashboard", True, False)]
        with self.assertRaisesRegex(OperationError, "Enable replacement"):
            validate_request("initialize", "public", False, census)
        self.assertIn(
            "--replace", validate_request("initialize", "public", True, census)
        )

    def test_only_a_complete_source_may_be_parsed(self) -> None:
        census = [_schema("mta", "source", False, True)]
        self.assertIn("--all", validate_request("derive", "mta", False, census))
        with self.assertRaisesRegex(OperationError, "complete.*source"):
            validate_request("derive", "partial", False, census)

    def test_an_invalid_identifier_is_rejected(self) -> None:
        with self.assertRaises(OperationError) as raised:
            validate_request("initialize", "public --replace", False, [])
        self.assertEqual(raised.exception.code, "invalid_schema")

    def test_a_census_failure_becomes_a_bounded_refusal(self) -> None:
        with patch(
            "backend.services.schema_operations._read_schemas",
            side_effect=RuntimeError("x" * 1000),
        ):
            with self.assertRaises(OperationError) as raised:
                validate_request("initialize", "new_schema", False)

        self.assertEqual(raised.exception.code, "schema_census_failed")
        self.assertLess(len(str(raised.exception)), 400)


class LogTests(unittest.TestCase):
    """Check operation output is detailed but memory-bounded."""

    def test_lines_are_timestamped_truncated_and_bounded(self) -> None:
        operation = SchemaOperation(1, "derive", "mta", ["uv", "run"])
        for index in range(MAX_LINES + 4):
            operation.append("stdout", f"{index}:" + "x" * 700)

        view = operation.public_view()
        self.assertEqual(len(view["lines"]), MAX_LINES)
        self.assertEqual(view["droppedLines"], 4)
        self.assertLessEqual(len(view["lines"][-1]["text"]), 500)
        self.assertTrue(view["lines"][-1]["at"])


class RouteTests(unittest.TestCase):
    """Check route registration and protection without a database."""

    def setUp(self) -> None:
        self.client = create_app().test_client()

    def test_poll_route_is_registered(self) -> None:
        response = self.client.get("/api/schema-operations")
        self.assertEqual(response.status_code, 200)
        self.assertIn("current", response.get_json())
        self.assertIn("available", response.get_json())

    def test_file_mode_refuses_before_validation_or_spawn(self) -> None:
        with (
            patch("backend.api.schema_operations.is_hosted", return_value=False),
            patch("backend.api.schema_operations.use_database", return_value=False),
        ):
            response = self.client.post(
                "/api/schema-operations",
                json={"action": "initialize", "schema": "new_schema"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "schema_operations_unavailable")

    def test_protected_configuration_does_not_refuse_schema_setup(self) -> None:
        # Configuration protection governs whether a browser may rewrite the
        # credentials the platform issued. Setup writes tables into the
        # database that platform already pointed this service at and rewrites
        # no credential, so it is not what that flag governs. Refusing it here
        # made the one deployment whose readers have no shell the one
        # deployment with no way to populate a schema at all.
        with (
            patch("backend.api.schema_operations.is_hosted", return_value=False),
            patch("backend.api.schema_operations.use_database", return_value=True),
            patch(
                "backend.api.schema_operations.schema_setup_enabled", return_value=True
            ),
            patch("backend.config.config_read_only", return_value=True),
            patch(
                "backend.api.schema_operations.start_operation",
                side_effect=OperationError("invalid_schema", "refused after the gate"),
            ),
        ):
            response = self.client.post(
                "/api/schema-operations",
                json={"action": "initialize", "schema": "not a name"},
            )

        # Reached validation rather than being turned away at the door.
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_schema")

    def test_an_operator_can_still_withhold_schema_setup(self) -> None:
        with (
            patch("backend.api.schema_operations.is_hosted", return_value=False),
            patch("backend.api.schema_operations.use_database", return_value=True),
            patch(
                "backend.api.schema_operations.schema_setup_enabled", return_value=False
            ),
        ):
            response = self.client.post(
                "/api/schema-operations",
                json={"action": "initialize", "schema": "new_schema"},
            )
            poll = self.client.get("/api/schema-operations")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "schema_setup_disabled")
        # The refusal travels with the poll as well, so the dialog disables its
        # buttons from what the route would accept rather than from a rule it
        # reconstructed from the deployment flags.
        self.assertFalse(poll.get_json()["available"])
        self.assertIn("SCHEMA_SETUP_ENABLED", poll.get_json()["reason"])

    def test_replace_must_be_a_boolean(self) -> None:
        with (
            patch("backend.api.schema_operations.is_hosted", return_value=False),
            patch("backend.api.schema_operations.use_database", return_value=True),
            patch(
                "backend.api.schema_operations.schema_setup_enabled", return_value=True
            ),
        ):
            response = self.client.post(
                "/api/schema-operations",
                json={
                    "action": "initialize",
                    "schema": "new_schema",
                    "replace": "yes",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_replace")


if __name__ == "__main__":
    unittest.main()
