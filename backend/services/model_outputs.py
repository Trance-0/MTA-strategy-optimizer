"""Validate, publish, download, and persist dashboard model artifacts.

The browser may submit bytes only for a fixed complete stage manifest. It can
never name a server path, table, schema, or query. Validated files are
published below the pipeline runtime and become the same artifacts the normal
dashboard repositories already parse.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from backend.config import pipeline_output_directory, use_database
from backend.database import engine, orm_rows, table_exists
from dashboard.models import ModelArtifact
from modules.mta_attribution.src.attribution_model_comparison import (
    MODEL_OUTPUT_FIELDS,
    RECOMMENDED_FIELDS,
    SUMMARY_FIELDS,
    TOUCHPOINT_COMPARISON_FIELDS,
)

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_STAGE_BYTES = 25 * 1024 * 1024

ARTIFACTS: dict[str, tuple[tuple[str, str, tuple[str, ...] | None], ...]] = {
    "attribution": (
        ("amc_markov_attribution_results.csv", "text/csv", tuple(MODEL_OUTPUT_FIELDS)),
        ("amc_shapley_attribution_results.csv", "text/csv", tuple(MODEL_OUTPUT_FIELDS)),
        (
            "amc_mta_model_comparison_touchpoints.csv",
            "text/csv",
            tuple(TOUCHPOINT_COMPARISON_FIELDS),
        ),
        (
            "amc_mta_model_comparison_summary.csv",
            "text/csv",
            tuple(SUMMARY_FIELDS),
        ),
        ("amc_mta_recommended_attribution.csv", "text/csv", tuple(RECOMMENDED_FIELDS)),
    ),
    "optimization": (("campaign_strategy.json", "application/json", None),),
    "evaluation": (("strategy_evaluation.json", "application/json", None),),
}

DIRECTORIES = {
    "attribution": "attribution",
    "optimization": "strategy",
    "evaluation": "evaluation",
}


class ArtifactError(ValueError):
    """A bounded artifact request that failed validation."""


def artifact_names(stage: str) -> tuple[str, ...]:
    """Return the exact upload/download basenames for one known stage."""
    if stage not in ARTIFACTS:
        raise ArtifactError(f"Unknown stage: {stage}.")
    return tuple(item[0] for item in ARTIFACTS[stage])


def artifact_directory(stage: str) -> Path:
    """Return the fixed runtime directory for one known stage."""
    root = pipeline_output_directory()
    if stage not in ARTIFACTS:
        raise ArtifactError(f"Unknown stage: {stage}.")
    if root is None:
        raise ArtifactError(
            "PIPELINE_OUTPUT_DIR must name a writable runtime directory."
        )
    return root / DIRECTORIES[stage]


def artifact_manifest(stage: str, *, database_enabled: bool) -> dict:
    """Return public artifact names and server capabilities for one stage."""
    if stage not in ARTIFACTS:
        raise ArtifactError(f"Unknown stage: {stage}.")
    directory = restore_artifact_directory(stage, database_enabled=database_enabled)
    files = []
    for filename, media_type, _headers in ARTIFACTS[stage]:
        path = directory / filename
        files.append(
            {
                "filename": filename,
                "mediaType": media_type,
                "available": path.is_file(),
                "downloadUrl": f"/api/jobs/{stage}/artifacts/{filename}",
            }
        )
    return {
        "files": files,
        "complete": bool(files) and all(item["available"] for item in files),
        "canUpload": True,
        "canImport": database_enabled,
    }


def artifact_path(stage: str, filename: str) -> Path:
    """Resolve one exact allow-listed artifact that currently exists."""
    allowed = {item[0] for item in ARTIFACTS.get(stage, ())}
    if filename not in allowed or Path(filename).name != filename:
        raise ArtifactError(
            "The requested artifact is not allow-listed for this stage."
        )
    path = restore_artifact_directory(stage) / filename
    if not path.is_file():
        raise FileNotFoundError(filename)
    return path


def restored_artifact_path(stage: str, filename: str, fallback: Path) -> Path:
    """Prefer runtime or imported content, otherwise return a baseline file."""
    try:
        path = restore_artifact_directory(stage) / filename
    except (ArtifactError, OSError):
        return fallback
    return path if path.is_file() else fallback


def restore_artifact_directory(
    stage: str, *, database_enabled: bool | None = None
) -> Path:
    """Materialize a complete optional database set when runtime is empty."""
    directory = artifact_directory(stage)
    expected = {item[0]: item for item in ARTIFACTS[stage]}
    if all((directory / filename).is_file() for filename in expected):
        return directory
    database_mode = use_database() if database_enabled is None else database_enabled
    if not database_mode or not table_exists("model_artifact"):
        return directory
    rows = orm_rows(
        select(
            ModelArtifact.filename,
            ModelArtifact.content,
        )
        .where(ModelArtifact.stage == stage)
        .order_by(ModelArtifact.id)
    )
    documents = {str(row["filename"]): str(row["content"]) for row in rows}
    if set(documents) != set(expected):
        return directory
    for filename, text in documents.items():
        _validate_document(stage, filename, text, expected[filename][2])
    directory.mkdir(parents=True, exist_ok=True)
    for filename, text in documents.items():
        pending = (directory / filename).with_suffix(Path(filename).suffix + ".restore")
        pending.write_text(text, encoding="utf-8", newline="\n")
        pending.replace(directory / filename)
    return directory


def publish_artifacts(stage: str, submitted: list[tuple[str, bytes]]) -> dict:
    """Validate and publish one complete stage set from uploaded bytes."""
    expected = {item[0]: item for item in ARTIFACTS.get(stage, ())}
    if not expected:
        raise ArtifactError(f"Unknown stage: {stage}.")
    received: dict[str, bytes] = {}
    total = 0
    for filename, content in submitted:
        if Path(filename).name != filename or filename not in expected:
            raise ArtifactError(f"Unexpected artifact filename: {filename!r}.")
        if filename in received:
            raise ArtifactError(f"Duplicate artifact filename: {filename}.")
        if len(content) > MAX_FILE_BYTES:
            raise ArtifactError(f"{filename} exceeds the 10 MiB file limit.")
        total += len(content)
        if total > MAX_STAGE_BYTES:
            raise ArtifactError("The artifact set exceeds the 25 MiB request limit.")
        received[filename] = content
    missing = sorted(set(expected) - set(received))
    if missing:
        raise ArtifactError(
            "A complete stage set is required; missing " + ", ".join(missing) + "."
        )

    decoded: dict[str, str] = {}
    for filename, content in received.items():
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ArtifactError(f"{filename} is not valid UTF-8.") from error
        _validate_document(stage, filename, text, expected[filename][2])
        decoded[filename] = text

    directory = artifact_directory(stage)
    directory.mkdir(parents=True, exist_ok=True)
    temporary: list[tuple[Path, Path]] = []
    try:
        for filename, text in decoded.items():
            target = directory / filename
            pending = target.with_suffix(target.suffix + ".upload")
            pending.write_text(text, encoding="utf-8", newline="\n")
            temporary.append((pending, target))
        for pending, target in temporary:
            pending.replace(target)
    finally:
        for pending, _target in temporary:
            pending.unlink(missing_ok=True)
    return artifact_manifest(stage, database_enabled=False)


def import_artifacts(stage: str) -> int:
    """Replace one stage's optional database artifact set transactionally."""
    documents = []
    for filename, media_type, headers in ARTIFACTS.get(stage, ()):
        path = artifact_path(stage, filename)
        text = path.read_text(encoding="utf-8")
        _validate_document(stage, filename, text, headers)
        documents.append(
            {
                "stage": stage,
                "filename": filename,
                "media_type": media_type,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "content": text,
                "imported_at": datetime.now(timezone.utc).replace(tzinfo=None),
            }
        )
    if not documents:
        raise ArtifactError(f"Unknown stage: {stage}.")
    with engine().begin() as connection:
        ModelArtifact.__table__.create(bind=connection, checkfirst=True)
        connection.execute(delete(ModelArtifact).where(ModelArtifact.stage == stage))
        connection.execute(ModelArtifact.__table__.insert(), documents)
    return len(documents)


def _validate_document(
    stage: str, filename: str, text: str, headers: tuple[str, ...] | None
) -> None:
    """Parse one exact CSV or JSON contract without retaining user objects."""
    if headers is not None:
        reader = csv.reader(io.StringIO(text, newline=""))
        try:
            actual = tuple(next(reader))
        except StopIteration as error:
            raise ArtifactError(f"{filename} is empty.") from error
        if actual != headers:
            raise ArtifactError(f"{filename} has an unexpected CSV header.")
        row_count = 0
        try:
            for row_number, row in enumerate(reader, start=2):
                if not row:
                    continue
                if len(row) != len(headers):
                    raise ArtifactError(
                        f"{filename} row {row_number} has {len(row)} fields; "
                        f"expected {len(headers)}."
                    )
                row_count += 1
        except csv.Error as error:
            raise ArtifactError(f"{filename} is not valid CSV: {error}.") from error
        if row_count == 0:
            raise ArtifactError(f"{filename} contains no model output rows.")
        return
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ArtifactError(f"{filename} is not valid JSON.") from error
    if not isinstance(document, dict):
        raise ArtifactError(f"{filename} must contain a JSON object.")
    required = (
        {"currency", "initial_strategy", "optimized_strategy", "response_models"}
        if stage == "optimization"
        else {"strategies", "contributed_models", "summary"}
    )
    if not required.issubset(document):
        raise ArtifactError(
            f"{filename} is missing required keys: "
            + ", ".join(sorted(required - set(document)))
            + "."
        )
    if stage == "optimization":
        expected_types = {
            "currency": str,
            "initial_strategy": dict,
            "optimized_strategy": dict,
            "response_models": dict,
        }
    else:
        expected_types = {
            "strategies": list,
            "contributed_models": list,
            "summary": dict,
        }
    wrong = [
        key
        for key, expected_type in expected_types.items()
        if not isinstance(document.get(key), expected_type)
    ]
    if wrong:
        raise ArtifactError(
            f"{filename} has invalid value types for: {', '.join(wrong)}."
        )
