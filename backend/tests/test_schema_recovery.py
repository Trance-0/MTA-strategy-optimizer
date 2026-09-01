"""Tests for the read-only dashboard schema-recovery catalogue."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.services.schema_recovery import recovery_state


class RecoveryServiceTests(unittest.TestCase):
    """Prove that only safe, actionable remedies reach the browser."""

    def test_catalogue_excludes_active_unsafe_and_disabled_write_options(self) -> None:
        """A protected setup flag removes writes but leaves another ready schema."""

        census = {
            "selected": "broken",
            "error": None,
            "schemas": [
                {
                    "name": "broken",
                    "kind": "dashboard",
                    "tableCount": 13,
                    "remedy": {"action": "select", "label": "Load", "summary": "Ready"},
                },
                {
                    "name": "ready",
                    "kind": "dashboard",
                    "tableCount": 14,
                    "remedy": {"action": "select", "label": "Load", "summary": "Ready"},
                },
                {
                    "name": "source",
                    "kind": "source",
                    "tableCount": 20,
                    "remedy": {
                        "action": "derive",
                        "label": "Build",
                        "summary": "Source",
                    },
                },
                {
                    "name": "other",
                    "kind": "other",
                    "tableCount": 2,
                    "remedy": {"action": "none", "label": "", "summary": "Other"},
                },
            ],
        }
        with (
            patch("backend.services.schema_recovery.use_database", return_value=True),
            patch("backend.services.schema_recovery.is_hosted", return_value=False),
            patch(
                "backend.services.schema_recovery.schema_setup_enabled",
                return_value=False,
            ),
            patch(
                "backend.services.schema_recovery.available_schemas",
                return_value=census,
            ),
        ):
            state = recovery_state()

        self.assertTrue(state["available"])
        self.assertEqual(state["active"], "broken")
        self.assertEqual(
            [(item["action"], item["schema"]) for item in state["options"]],
            [("select", "ready")],
        )
        self.assertFalse(state["options"][0]["replace"])

    def test_enabled_setup_offers_only_additive_write_actions(self) -> None:
        """Source derivation and empty initialization never request replacement."""

        census = {
            "selected": "broken",
            "error": None,
            "schemas": [
                {
                    "name": "source",
                    "kind": "source",
                    "tableCount": 20,
                    "remedy": {
                        "action": "derive",
                        "label": "Build",
                        "summary": "Source",
                    },
                },
                {
                    "name": "empty",
                    "kind": "empty",
                    "tableCount": 0,
                    "remedy": {
                        "action": "initialize",
                        "label": "Load",
                        "summary": "Empty",
                    },
                },
            ],
        }
        with (
            patch("backend.services.schema_recovery.use_database", return_value=True),
            patch("backend.services.schema_recovery.is_hosted", return_value=False),
            patch(
                "backend.services.schema_recovery.schema_setup_enabled",
                return_value=True,
            ),
            patch(
                "backend.services.schema_recovery.available_schemas",
                return_value=census,
            ),
        ):
            state = recovery_state()

        self.assertEqual(
            {item["action"] for item in state["options"]}, {"derive", "initialize"}
        )
        self.assertTrue(all(item["replace"] is False for item in state["options"]))


class RecoveryRouteTests(unittest.TestCase):
    """Pin the read-only route registration."""

    def test_route_returns_service_state(self) -> None:
        """The route carries the catalogue without accepting mutations."""

        expected = {
            "available": False,
            "reason": "file mode",
            "active": None,
            "setupEnabled": False,
            "options": [],
        }
        with patch("backend.api.schema_recovery.recovery_state", return_value=expected):
            response = create_app().test_client().get("/api/schema-recovery")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)


if __name__ == "__main__":
    unittest.main()
