"""Security and persistence tests for dashboard model artifact transfer."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select

from backend.services import model_outputs
from backend.app import create_app
from backend.services.model_outputs import (
    ARTIFACTS,
    ArtifactError,
    artifact_manifest,
    import_artifacts,
    publish_artifacts,
)
from dashboard.models import Base, ModelArtifact


class ModelOutputTests(unittest.TestCase):
    """Verify exact manifests, parsing, bounded paths, and explicit import."""

    def test_optional_artifact_table_is_outside_required_schema_metadata(self) -> None:
        self.assertNotIn("model_artifact", Base.metadata.tables)
        self.assertIsNot(ModelArtifact.metadata, Base.metadata)

    def test_complete_attribution_set_is_parsed_and_published(self) -> None:
        submitted = [
            (
                filename,
                (
                    ",".join(headers) + "\n" + ",".join("0" for _ in headers) + "\n"
                ).encode("utf-8"),
            )
            for filename, _media, headers in ARTIFACTS["attribution"]
        ]
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "backend.services.model_outputs.pipeline_output_directory",
                return_value=Path(temporary),
            ):
                result = publish_artifacts("attribution", submitted)

        self.assertTrue(result["complete"])
        self.assertEqual(len(result["files"]), 5)

    def test_missing_and_path_like_names_are_rejected(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "complete stage set"):
            publish_artifacts("optimization", [])
        with self.assertRaisesRegex(ArtifactError, "Unexpected artifact"):
            publish_artifacts("optimization", [("../campaign_strategy.json", b"{}")])

    def test_validated_json_set_can_be_imported_transactionally(self) -> None:
        content = (
            '{"currency":"USD","initial_strategy":{},"optimized_strategy":{},'
            '"response_models":{}}\n'
        ).encode("utf-8")
        database = create_engine("sqlite+pysqlite:///:memory:")
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch(
                    "backend.services.model_outputs.pipeline_output_directory",
                    return_value=Path(temporary),
                ),
                patch("backend.services.model_outputs.engine", return_value=database),
            ):
                publish_artifacts("optimization", [("campaign_strategy.json", content)])
                self.assertEqual(import_artifacts("optimization"), 1)
                result = artifact_manifest("optimization", database_enabled=True)

            with database.connect() as connection:
                count = connection.execute(
                    select(func.count()).select_from(ModelArtifact)
                ).scalar_one()

        self.assertEqual(count, 1)
        self.assertTrue(result["canImport"])

    def test_imported_set_is_restored_when_runtime_is_empty(self) -> None:
        content = (
            '{"strategies":[],"contributed_models":[],"summary":'
            '{"projected":0,"conserved":0,"skipped":[]}}\n'
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            with (
                patch.object(
                    model_outputs, "pipeline_output_directory", return_value=runtime
                ),
                patch.object(model_outputs, "use_database", return_value=True),
                patch.object(model_outputs, "table_exists", return_value=True),
                patch.object(
                    model_outputs,
                    "orm_rows",
                    return_value=[
                        {
                            "filename": "strategy_evaluation.json",
                            "content": content,
                        }
                    ],
                ),
            ):
                result = artifact_manifest("evaluation", database_enabled=True)

            restored = runtime / "evaluation" / "strategy_evaluation.json"
            self.assertTrue(restored.is_file())
            self.assertTrue(result["complete"])


class ModelOutputRouteTests(unittest.TestCase):
    """Exercise multipart, download, and database-gated HTTP boundaries."""

    def setUp(self) -> None:
        self.client = create_app().test_client()

    def test_upload_then_download_uses_only_declared_filename(self) -> None:
        content = (
            b'{"currency":"USD","initial_strategy":{},"optimized_strategy":{},'
            b'"response_models":{}}\n'
        )
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(
                model_outputs,
                "pipeline_output_directory",
                return_value=Path(temporary),
            ):
                uploaded = self.client.post(
                    "/api/jobs/optimization/artifacts",
                    data={"files": (io.BytesIO(content), "campaign_strategy.json")},
                    content_type="multipart/form-data",
                )
                downloaded = self.client.get(
                    "/api/jobs/optimization/artifacts/campaign_strategy.json"
                )
                downloaded_data = downloaded.get_data()
                downloaded.close()

        self.assertEqual(uploaded.status_code, 200, uploaded.get_json())
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded_data, content)

    def test_database_import_is_refused_in_file_mode(self) -> None:
        with patch("backend.api.jobs.use_database", return_value=False):
            response = self.client.post("/api/jobs/optimization/artifacts/import")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "database_required")


if __name__ == "__main__":
    unittest.main()
