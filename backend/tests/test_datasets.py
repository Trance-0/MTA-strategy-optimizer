"""Verify immutable ingestion, canonical validation and isolated dataset reads."""

from __future__ import annotations

import copy
import csv
import importlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services import datasets
from modules.mta_standard.tests.test_mta_sim_research_adapter import _snapshot_payload


def envelope(cost=12.5):
    """One complete native report, optionally paired with the canonical sidecar."""
    return {
        "name": "Observed example",
        "performance": [{
            "reportDate": "2025-01-01", "marketplace": "US",
            "accountId": "SIM-ACCOUNT", "adProduct": "SPONSORED_PRODUCTS",
            "adType": "AUTO", "creativeType": "", "inventoryType": "",
            "placement": "", "normalizedTouchpoint":
            "SPONSORED_PRODUCTS:AUTO:UNSPECIFIED:UNSPECIFIED:CLICK",
            "currencyCode": "USD", "impressions": 100, "clicks": 10,
            "cost": cost, "purchases": 2, "sales": 30, "unitsSold": 2,
        }],
        "paths": [{
            "report_start_date": "2025-01-01", "report_end_date": "2025-01-01",
            "marketplace": "US", "advertiser_id": "SIM-ACCOUNT",
            "path": "SPONSORED_PRODUCTS:AUTO:UNSPECIFIED:UNSPECIFIED:CLICK",
            "users": 5, "converted_users": 2, "purchase_count": 2, "revenue": 30,
        }],
    }


class DatasetTests(unittest.TestCase):
    """Use private temporary storage, never a configured project dataset."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = patch.object(datasets, "pipeline_output_directory", return_value=self.root)
        self.runtime.start()
        self.addCleanup(self.runtime.stop)

    def test_preview_does_not_publish_and_bounds_rows(self):
        payload = envelope()
        payload["performance"] *= 21
        for i, row in enumerate(payload["performance"]):
            payload["performance"][i] = {**row, "reportDate": f"2025-01-{i+1:02}"}
        preview = datasets.validate_dataset(payload)
        self.assertEqual(preview["counts"]["performance"], 21)
        self.assertEqual(len(preview["preview"]["performance"]), 20)
        self.assertEqual(datasets.list_datasets(), [])

    def test_registration_digest_restart_and_no_paths(self):
        first = datasets.register_dataset(envelope())
        second = datasets.register_dataset(envelope(), source="file")
        self.assertRegex(first["id"], r"^ds_[0-9a-f]{32}$")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(datasets.get_dataset(first["id"]), first)
        # Reloading the service discards any accidental process-local state.
        importlib.reload(datasets)
        with patch.object(datasets, "pipeline_output_directory", return_value=self.root):
            self.assertEqual(len(datasets.list_datasets()), 2)
            self.assertEqual(datasets.dataset_inputs(first["id"])["performance"][0]["cost"], 12.5)
        self.assertNotIn(str(self.root), json.dumps(first))

    def test_optional_inputs_have_honest_capabilities(self):
        payload = envelope()
        payload.pop("paths")
        preview = datasets.validate_dataset(payload)
        self.assertTrue(preview["capabilities"]["performance"]["available"])
        for key in ("attribution", "history", "optimization", "evaluation"):
            self.assertFalse(preview["capabilities"][key]["available"])
            self.assertTrue(preview["capabilities"][key]["reason"])

    def test_scope_preserves_sparse_reports_but_attribution_requires_alignment(self):
        payload = envelope()
        payload["paths"][0]["report_end_date"] = "2025-01-03"
        preview = datasets.validate_dataset(payload)
        self.assertEqual(preview["scope"]["end"], "2025-01-03")
        self.assertFalse(preview["capabilities"]["attribution"]["available"])
        valid = envelope(); valid["performance"][0]["impressions"] = 0
        self.assertTrue(datasets.validate_dataset(valid)["capabilities"]["attribution"]["available"])
        self.assertFalse(datasets.validate_dataset(envelope())["capabilities"]["attribution"]["available"])

    def test_validation_rejects_invalid_input_without_publication(self):
        changes = [
            ("cost", float("nan")), ("cost", -1), ("clicks", 1.1),
            ("clicks", True), ("sales", ""), ("reportDate", "2025-02-30"),
            ("normalizedTouchpoint", "SPONSORED_PRODUCTS:AUTO::X:CLICK"),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                payload = envelope()
                payload["performance"][0][key] = value
                with self.assertRaises(datasets.DatasetValidationError) as found:
                    datasets.register_dataset(payload)
                self.assertTrue(found.exception.issues)
                self.assertEqual(datasets.list_datasets(), [])

    def test_duplicates_scope_and_paths_are_checked(self):
        variants = []
        payload = envelope(); payload["performance"] *= 2; variants.append(payload)
        payload = envelope(); payload["paths"][0]["converted_users"] = 6; variants.append(payload)
        payload = envelope(); payload["paths"][0]["advertiser_id"] = "OTHER"; variants.append(payload)
        payload = envelope(); payload["performance"].append({**payload["performance"][0], "currencyCode": "EUR"}); variants.append(payload)
        payload = envelope(); payload["performance"][0]["true_causal_effect"] = 1; variants.append(payload)
        for payload in variants:
            with self.subTest(payload=payload), self.assertRaises(datasets.DatasetValidationError):
                datasets.validate_dataset(payload)

    def test_unknown_identity_and_atomic_failure_preserve_existing_data(self):
        original = datasets.register_dataset(envelope())
        for identity in ("../secret", "ds_" + "0" * 32):
            with self.assertRaises(datasets.DatasetNotFoundError):
                datasets.get_dataset(identity)
        with patch.object(datasets.os, "replace", side_effect=OSError("private path")):
            with self.assertRaises(datasets.DatasetStorageError):
                datasets.register_dataset(envelope(90))
        self.assertEqual([row["id"] for row in datasets.list_datasets()], [original["id"]])

    def test_research_uses_real_evidence_and_excludes_truth_from_public_preview(self):
        payload = envelope()
        payload["research"] = _snapshot_payload()
        preview = datasets.validate_dataset(payload)
        self.assertTrue(preview["capabilities"]["history"]["available"])
        self.assertFalse(preview["capabilities"]["optimization"]["available"])
        self.assertNotIn("evaluation_outcome_observations", json.dumps(preview))
        self.assertNotIn("incremental_revenue", json.dumps(preview))
        payload["research"]["budget_observations"][0]["campaign_id"] = "MISSING"
        with self.assertRaises(datasets.DatasetValidationError):
            datasets.validate_dataset(payload)

    def test_research_rejects_nonfinite_strings_and_observed_truth(self):
        for field, value in (("total_revenue", "NaN"), ("incremental_revenue", 40)):
            payload = envelope()
            payload["research"] = _snapshot_payload()
            payload["research"]["outcome_observations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(datasets.DatasetValidationError):
                datasets.validate_dataset(payload)

    def test_duplicate_research_observation_identities_are_rejected(self):
        for role in ("budget_observations", "delivery_observations", "outcome_observations", "evaluation_outcome_observations"):
            payload = envelope(); payload["research"] = _snapshot_payload()
            duplicate = copy.deepcopy(payload["research"][role][0])
            if role == "budget_observations":
                duplicate["actual_spend"] = 999
                duplicate["budget_level"] = "0.5"
            payload["research"][role].append(duplicate)
            with self.subTest(role=role), self.assertRaises(datasets.DatasetValidationError) as found:
                datasets.register_dataset(payload)
            self.assertTrue(any(role in issue["path"] for issue in found.exception.issues))
            self.assertEqual([], datasets.list_datasets())

    def test_malformed_research_collections_are_bounded_validation_errors(self):
        for field, value in (("simulation_runs", [None]), ("data_lineage", [None]), ("budget_observations", ["bad"]), ("outcome_observations", {})):
            payload = envelope(); payload["research"] = _snapshot_payload()
            payload["research"][field] = value
            with self.subTest(field=field), self.assertRaises(datasets.DatasetValidationError):
                datasets.register_dataset(payload)
            self.assertEqual([], datasets.list_datasets())

    def test_file_changes_are_not_silently_accepted(self):
        saved = datasets.register_dataset(envelope())
        (datasets.dataset_directory(saved["id"]) / "inputs.json").write_text("{}")
        with self.assertRaises(datasets.DatasetStorageError):
            datasets.dataset_inputs(saved["id"])

    def test_research_with_sufficient_observed_variation_is_eligible(self):
        payload = envelope()
        research = _snapshot_payload()
        for key in ("performance",):
            payload[key] = [{**payload[key][0], "reportDate": f"2025-01-0{i+1}"} for i in range(4)]
        for key in ("budget_observations", "delivery_observations", "outcome_observations"):
            base = research[key][0]
            research[key] = []
            for i in range(4):
                row = copy.deepcopy(base)
                row["reporting_scope"].update(report_start_date=f"2025-01-0{i+1}", report_end_date=f"2025-01-0{i+1}")
                if key == "budget_observations":
                    row.update(configured_budget=(i+1)*30, actual_spend=(i+1)*20)
                elif key == "delivery_observations":
                    row.update(cost=(i+1)*20, impressions=100, clicks=20)
                else:
                    row.update(total_revenue=(i+1)*50)
                research[key].append(row)
        payload["research"] = research
        self.assertTrue(datasets.validate_dataset(payload)["capabilities"]["optimization"]["available"])


class DatasetRouteTests(unittest.TestCase):
    """Transport shares validation and never accepts filesystem paths."""

    def setUp(self):
        from flask import Flask
        from backend.api.datasets import blueprint
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(datasets, "pipeline_output_directory", return_value=Path(self.temp.name))
        self.patch.start(); self.addCleanup(self.patch.stop)
        app = Flask(__name__)
        app.register_blueprint(blueprint)
        self.client = app.test_client()

    def test_json_import_and_templates(self):
        response = self.client.post("/api/datasets", json=envelope())
        self.assertEqual(response.status_code, 201)
        identifier = response.json["id"]
        self.assertEqual(self.client.get(f"/api/datasets/{identifier}").json["id"], identifier)
        self.assertEqual(len(self.client.get("/api/datasets").json["datasets"]), 1)
        templates = self.client.get("/api/datasets/templates").json
        self.assertIn("rows", templates["performance"])

    def test_csv_and_json_use_same_validation_and_digest(self):
        payload = envelope()
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=list(payload["performance"][0]))
        writer.writeheader(); writer.writerows(payload["performance"])
        response = self.client.post("/api/datasets", data={
            "name": payload["name"], "performance": (io.BytesIO(text.getvalue().encode()), "performance.csv"),
            "paths": (io.BytesIO(json.dumps(payload["paths"]).encode()), "paths.json"),
        })
        self.assertEqual(response.status_code, 201)
        other = self.client.post("/api/datasets", json=payload)
        self.assertEqual(response.json["digest"], other.json["digest"])

    def test_invalid_unknown_roles_and_storage_errors_are_bounded(self):
        response = self.client.post("/api/datasets/validate", json={**envelope(), "path": "/secret"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json["issues"])
        self.assertEqual(self.client.get("/api/datasets/not-an-id").status_code, 404)
        with patch.object(datasets, "pipeline_output_directory", return_value=None):
            response = self.client.post("/api/datasets", json=envelope())
            self.assertEqual(response.status_code, 503)


class DatasetResourceTests(unittest.TestCase):
    """Selected resources must bypass every legacy data and truth fallback."""

    setUp = DatasetTests.setUp

    def test_two_resources_never_mix_or_require_legacy_database(self):
        from backend.app import create_app
        first = datasets.register_dataset(envelope())
        second = datasets.register_dataset(envelope(99))
        client = create_app().test_client()
        with patch("backend.api.dashboard.database_available", side_effect=AssertionError("Legacy probe")), patch("backend.api.dashboard.use_database", return_value=True):
            for descriptor, expected in ((first, 12.5), (second, 99)):
                response = client.get(f"/api/dashboard/resources/performance?datasetId={descriptor['id']}&stream=1")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["adsDaily"][0]["cost"], expected)
                self.assertEqual(response.json["dataset"]["id"], descriptor["id"])
        response = client.get("/api/dashboard/resources/performance?datasetId=missing")
        self.assertEqual(response.status_code, 404)

    def test_projection_has_no_research_fallback_and_preserves_bounds(self):
        from backend.repository.datasets import load_dataset_resource
        payload = envelope()
        payload["performance"].append({**payload["performance"][0], "reportDate": "2025-01-02"})
        descriptor = datasets.register_dataset(payload)
        resource = load_dataset_resource(descriptor["id"], "performance", "2025-01-02", "2025-01-02")
        self.assertEqual(len(resource["adsDaily"]), 1)
        self.assertEqual(resource["dataset"]["scope"]["start"], "2025-01-01")
        self.assertIsNone(resource["adsDaily"][0]["cost_type"])
        research = load_dataset_resource(descriptor["id"], "research-campaign-history")["simulationResearch"]
        self.assertEqual(research["history"], [])
        self.assertEqual(research["campaigns"], [])

    def test_research_projection_uses_ordinary_outcomes_not_truth(self):
        from backend.repository.datasets import load_dataset_resource
        payload = envelope(); payload["research"] = _snapshot_payload()
        payload["research"]["evaluation_outcome_observations"][0]["total_revenue"] = 999999
        descriptor = datasets.register_dataset(payload)
        resource = load_dataset_resource(descriptor["id"], "research-campaign-history")
        self.assertEqual(resource["simulationResearch"]["history"][0]["total_revenue"], 100)
        encoded = json.dumps(resource)
        self.assertNotIn("999999", encoded)
        self.assertNotIn("incremental_revenue", encoded)
        self.assertNotIn("latent", encoded)

    def test_research_projection_keeps_distinct_end_dates_separate(self):
        from backend.repository.datasets import load_dataset_resource
        payload = envelope(); payload["research"] = _snapshot_payload()
        for role in ("budget_observations", "outcome_observations"):
            original = payload["research"][role][0]
            row = copy.deepcopy(original)
            row["reporting_scope"]["report_end_date"] = "2025-01-02"
            if role == "outcome_observations":
                row["total_revenue"] = 250
            payload["research"][role].append(row)
        descriptor = datasets.register_dataset(payload)
        rows = load_dataset_resource(descriptor["id"], "research-campaign-history")["simulationResearch"]["history"]
        self.assertEqual([100, 250], [row["total_revenue"] for row in rows])


if __name__ == "__main__":
    unittest.main()
