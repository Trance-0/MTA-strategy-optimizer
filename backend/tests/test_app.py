"""Application-level routing and error-shaping tests."""

from __future__ import annotations

import unittest

from backend.app import MAX_CONTENT_LENGTH, create_app


class ApplicationTests(unittest.TestCase):
    """Check health, routing, request limits, and JSON error responses."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = create_app().test_client()

    def test_health_does_not_depend_on_the_database(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_unknown_api_route_is_json(self) -> None:
        response = self.client.get("/api/not-a-route")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "not_found")

    def test_oversized_request_is_refused_as_json(self) -> None:
        response = self.client.post(
            "/api/models/recommend",
            data=b"x" * (MAX_CONTENT_LENGTH + 1),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json()["error"], "payload_too_large")


if __name__ == "__main__":
    unittest.main()
