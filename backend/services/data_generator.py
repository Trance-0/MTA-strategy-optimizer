"""Run the pinned MTA-SIM generator for the dashboard workflow.

The service owns ignored runtime files, bounded public state, two preview
tables, declared downloads, and backend-only PostgreSQL export. Simulation and
storage semantics remain in the pinned external package.
"""

from __future__ import annotations

import csv
import json
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from backend.config import REPO_ROOT, pipeline_runs_enabled, valid_schema_name
from modules.mta_standard.src.mta_sim_generator_adapter import (
    GeneratedMtaSimRun,
    export_mta_sim_dataset_to_postgresql,
    generate_and_load_mta_sim_dataset,
    load_resolved_mta_sim_configuration,
)


SUBMODULE_ROOT = REPO_ROOT / "external" / "mta_sim_dataset"
OUTPUT_ROOT = REPO_ROOT / "generated" / "dashboard-generator"
PRESETS: dict[str, dict[str, str]] = {
    "baseline": {"toy": "baseline.toy.json"},
    "regional": {"toy": "regional.toy.json"},
}
PREVIEW_LIMIT = 20
MAX_REPORT_DAYS = 366
MAX_TOUCHPOINTS = 64
MAX_PATH_SCENARIOS = 256
MAX_CAMPAIGN_REPLICATIONS = 50
MAX_COMPLETED_RUNS = 8
DOWNLOADS = {
    "path": ("amc_path_report.csv", "source_path_report"),
    "performance": (
        "amazon_ads_daily_touchpoint_performance.csv",
        "performance_report",
    ),
}


@dataclass
class GeneratorRun:
    """Hold backend-private paths and bounded public state for one run."""

    run_id: str
    variant: str
    directory: Path
    configuration_path: Path
    status: str = "queued"
    phase: str = "Waiting to start"
    message: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    previews: list[dict[str, Any]] = field(default_factory=list)
    files: dict[str, Path] = field(default_factory=dict)
    export_status: str = "idle"
    export_message: str = ""

    def public_state(self) -> dict[str, Any]:
        """Return state with no path, configuration, or credential."""

        return {
            "runId": self.run_id,
            "variant": self.variant,
            "status": self.status,
            "phase": self.phase,
            "message": self.message,
            "summary": dict(self.summary),
            "previews": list(self.previews),
            "downloads": [
                {"key": key, "name": DOWNLOADS[key][0]}
                for key in self.files
                if key in DOWNLOADS
            ],
            "export": {
                "status": self.export_status,
                "message": self.export_message,
            },
        }


_lock = threading.RLock()
_runs: dict[str, GeneratorRun] = {}
_active_operation: str | None = None


def generator_overview() -> dict[str, Any]:
    """Return reviewed presets and one self-contained initial configuration."""

    available = (
        pipeline_runs_enabled()
        and (SUBMODULE_ROOT / "ZheyuanWu" / "simulations").is_dir()
    )
    reason = ""
    if not pipeline_runs_enabled():
        reason = "Pipeline runs are disabled on this backend."
    elif not available:
        reason = "The pinned MTA-SIM submodule is not initialized."
    configuration: dict[str, Any] = {}
    if available:
        configuration = preset_configuration("baseline", "toy")
    return {
        "available": available,
        "reason": reason,
        "variants": [
            {
                "key": variant,
                "presets": [
                    {"key": key, "label": key.replace("-", " ").title()}
                    for key in presets
                ],
            }
            for variant, presets in PRESETS.items()
        ],
        "defaultVariant": "baseline",
        "defaultPreset": "toy",
        "configuration": configuration,
        "limits": {
            "reportDays": MAX_REPORT_DAYS,
            "touchpoints": MAX_TOUCHPOINTS,
            "pathScenarios": MAX_PATH_SCENARIOS,
            "campaignReplications": MAX_CAMPAIGN_REPLICATIONS,
        },
    }


def preset_configuration(variant: str, preset: str) -> dict[str, Any]:
    """Resolve one allow-listed external preset into a path-free object."""

    try:
        filename = PRESETS[variant][preset]
    except KeyError as error:
        raise ValueError("Unknown generator variant or preset.") from error
    return load_resolved_mta_sim_configuration(
        submodule_root=SUBMODULE_ROOT,
        configuration_path=SUBMODULE_ROOT / "ZheyuanWu" / "examples" / filename,
        variant=variant,
    )


def start_generation(variant: str, configuration: object) -> dict[str, Any]:
    """Validate a configuration boundary and start one background run."""

    global _active_operation
    if not generator_overview()["available"]:
        raise RuntimeError(generator_overview()["reason"])
    if variant not in PRESETS:
        raise ValueError("Unknown generator variant.")
    accepted = _validate_configuration(configuration)
    with _lock:
        if _active_operation is not None:
            raise RuntimeError(
                f"Another generator operation is active: {_active_operation}"
            )
        run_id = uuid.uuid4().hex
        directory = OUTPUT_ROOT / run_id
        directory.mkdir(parents=True, exist_ok=False)
        configuration_path = directory / "input_configuration.json"
        configuration_path.write_text(
            json.dumps(accepted, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        run = GeneratorRun(run_id, variant, directory, configuration_path)
        _runs[run_id] = run
        _active_operation = f"generation:{run_id}"
        _trim_runs()
    threading.Thread(target=_run_generation, args=(run,), daemon=True).start()
    return run.public_state()


def _run_generation(run: GeneratorRun) -> None:
    """Execute MTA-SIM and publish only bounded result state."""

    global _active_operation
    try:
        with _lock:
            run.status = "running"
            run.phase = "Generating and validating data"
        generated = generate_and_load_mta_sim_dataset(
            submodule_root=SUBMODULE_ROOT,
            configuration_path=run.configuration_path,
            output_directory=run.directory,
            variant=run.variant,
        )
        previews = _build_previews(generated)
        with _lock:
            run.files = {
                "path": generated.source_path_report,
                "performance": generated.performance_report,
            }
            run.previews = previews
            run.summary = _summary(generated)
            run.status = "completed"
            run.phase = "Ready to export"
    except Exception as error:  # noqa: BLE001 - bounded for the dashboard
        with _lock:
            run.status = "failed"
            run.phase = "Generation failed"
            run.message = _safe_error(error)
    finally:
        with _lock:
            if _active_operation == f"generation:{run.run_id}":
                _active_operation = None


def get_run(run_id: str) -> dict[str, Any]:
    """Return one run's bounded public state."""

    with _lock:
        return _require_run(run_id).public_state()


def download_path(run_id: str, table: str) -> tuple[Path, str]:
    """Resolve one allow-listed completed CSV attachment."""

    if table not in DOWNLOADS:
        raise KeyError("Unknown generated table.")
    with _lock:
        run = _require_run(run_id)
        if run.status != "completed" or table not in run.files:
            raise RuntimeError("The generated table is not ready.")
        path = run.files[table]
    if not path.is_file() or run.directory.resolve() not in path.resolve().parents:
        raise RuntimeError("The generated file is unavailable.")
    return path, DOWNLOADS[table][0]


def start_postgresql_export(
    run_id: str,
    connection: object,
    *,
    replace: bool,
) -> dict[str, Any]:
    """Start backend-only export with credentials retained only by the thread."""

    global _active_operation
    values = _validate_connection(connection)
    with _lock:
        run = _require_run(run_id)
        if run.status != "completed":
            raise RuntimeError("Generation must complete before export.")
        if run.export_status == "running":
            raise RuntimeError("This run is already being exported.")
        if _active_operation is not None:
            raise RuntimeError(
                f"Another generator operation is active: {_active_operation}"
            )
        run.export_status = "running"
        run.export_message = "Validating the PostgreSQL target"
        _active_operation = f"export:{run_id}"
    threading.Thread(
        target=_run_postgresql_export,
        args=(run, values, replace),
        daemon=True,
    ).start()
    return run.public_state()


def _run_postgresql_export(
    run: GeneratorRun, values: dict[str, Any], replace: bool
) -> None:
    """Probe an existing schema and invoke MTA-SIM's explicit writer."""

    global _active_operation
    password = values.pop("password")
    try:
        import psycopg
        from psycopg.conninfo import make_conninfo

        schema = values["options_schema"]
        # ``options_schema`` is service metadata, not a libpq parameter.
        base_values = {
            key: value for key, value in values.items() if key != "options_schema"
        }
        base_dsn = make_conninfo(
            "", password=password, connect_timeout=10, **base_values
        )
        with psycopg.connect(base_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists(select 1 from pg_namespace where nspname = %s),
                           has_schema_privilege(current_user, %s, 'USAGE'),
                           has_schema_privilege(current_user, %s, 'CREATE')
                    """,
                    (schema, schema, schema),
                )
                exists, can_use, can_create = cursor.fetchone()
        if not exists:
            raise ValueError("The target PostgreSQL schema does not exist.")
        if not can_use or not can_create:
            raise ValueError(
                "The PostgreSQL role requires USAGE and CREATE on the target schema."
            )
        database_url = make_conninfo(base_dsn, options=f"-csearch_path={schema}")
        with _lock:
            run.export_message = "Writing the generated dataset"
        export_mta_sim_dataset_to_postgresql(
            submodule_root=SUBMODULE_ROOT,
            configuration_path=run.configuration_path,
            output_directory=run.directory / "postgresql-export",
            database_url=database_url,
            variant=run.variant,
            reset=replace,
        )
        database_url = ""
        base_dsn = ""
        with _lock:
            run.export_status = "completed"
            run.export_message = "PostgreSQL export completed."
    except Exception as error:  # noqa: BLE001 - bounded and scrubbed
        with _lock:
            run.export_status = "failed"
            run.export_message = _safe_error(error, password)
    finally:
        password = ""
        values.clear()
        with _lock:
            if _active_operation == f"export:{run.run_id}":
                _active_operation = None


def _validate_configuration(configuration: object) -> dict[str, Any]:
    """Enforce the HTTP boundary before MTA-SIM performs full validation."""

    if not isinstance(configuration, dict):
        raise ValueError("Configuration must be a JSON object.")
    if _contains_key(configuration, "extends"):
        raise ValueError(
            "Configuration must be self-contained; extends is not allowed."
        )
    seed = configuration.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Configuration seed must be an integer.")
    try:
        start = date.fromisoformat(str(configuration["report_start_date"]))
        end = date.fromisoformat(str(configuration["report_end_date"]))
    except (KeyError, ValueError) as error:
        raise ValueError(
            "Configuration requires valid report start and end dates."
        ) from error
    days = (end - start).days + 1
    if not 1 <= days <= MAX_REPORT_DAYS:
        raise ValueError(f"Report window must contain 1 to {MAX_REPORT_DAYS} days.")
    advertiser = str(configuration.get("advertiser_id") or "").strip()
    if not advertiser or len(advertiser) > 128:
        raise ValueError(
            "Synthetic advertiser identifier is required and bounded to 128 characters."
        )
    price = configuration.get("base_product_price")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise ValueError("Base product price must be numeric.")
    if not math.isfinite(float(price)) or not 0 < float(price) <= 1_000_000_000:
        raise ValueError("Base product price must be positive and finite.")
    marketplaces = configuration.get("marketplaces")
    if not isinstance(marketplaces, list) or len(marketplaces) != 1:
        raise ValueError("The dashboard generator requires exactly one marketplace.")
    touchpoints = configuration.get("touchpoints")
    if (
        not isinstance(touchpoints, list)
        or not 1 <= len(touchpoints) <= MAX_TOUCHPOINTS
    ):
        raise ValueError(f"Configuration requires 1 to {MAX_TOUCHPOINTS} touchpoints.")
    scenarios = configuration.get("path_scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= MAX_PATH_SCENARIOS:
        raise ValueError(
            f"Configuration requires 1 to {MAX_PATH_SCENARIOS} path scenarios."
        )
    replications = configuration.get("campaign_replications", 1)
    if isinstance(replications, bool) or not isinstance(replications, int):
        raise ValueError("Campaign replications must be an integer.")
    if not 1 <= replications <= MAX_CAMPAIGN_REPLICATIONS:
        raise ValueError(
            f"Campaign replications must be between 1 and {MAX_CAMPAIGN_REPLICATIONS}."
        )
    # JSON round-trip returns a detached value and rejects non-JSON objects.
    return json.loads(json.dumps(configuration, allow_nan=False))


def _validate_connection(connection: object) -> dict[str, Any]:
    """Validate connection fields without retaining or rendering a DSN."""

    if not isinstance(connection, dict):
        raise ValueError("PostgreSQL connection must be an object.")
    required = ("host", "database", "user", "password", "schema")
    missing = [key for key in required if not str(connection.get(key) or "").strip()]
    if missing:
        raise ValueError(f"PostgreSQL connection is missing {', '.join(missing)}.")
    try:
        port = int(connection.get("port") or 5432)
    except (TypeError, ValueError) as error:
        raise ValueError("PostgreSQL port must be an integer.") from error
    if not 1 <= port <= 65535:
        raise ValueError("PostgreSQL port is outside 1 to 65535.")
    sslmode = str(connection.get("sslmode") or "require")
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise ValueError(
            "Remote export requires require, verify-ca, or verify-full SSL mode."
        )
    schema = str(connection["schema"]).strip()
    if not valid_schema_name(schema):
        raise ValueError("PostgreSQL schema is not a valid identifier.")
    bounded = {
        "host": str(connection["host"]).strip(),
        "port": port,
        "dbname": str(connection["database"]).strip(),
        "user": str(connection["user"]).strip(),
        "password": str(connection["password"]),
        "sslmode": sslmode,
        "options_schema": schema,
    }
    if any(len(str(value)) > 512 for value in bounded.values()):
        raise ValueError("A PostgreSQL connection field exceeds 512 characters.")
    return bounded


def _build_previews(generated: GeneratedMtaSimRun) -> list[dict[str, Any]]:
    """Read at most 20 rows from each public model-facing source table."""

    return [
        _preview(
            "path", "Amazon Marketing Cloud path report", generated.source_path_report
        ),
        _preview(
            "performance",
            "Amazon Ads daily touchpoint performance",
            generated.performance_report,
        ),
    ]


def _preview(key: str, label: str, path: Path) -> dict[str, Any]:
    """Preserve physical columns and bound one CSV preview."""

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Generated table has no header: {path.name}")
        rows = []
        for index, row in enumerate(reader):
            if index >= PREVIEW_LIMIT:
                break
            rows.append(dict(row))
    return {
        "key": key,
        "label": label,
        "columns": list(reader.fieldnames),
        "rows": rows,
    }


def _summary(generated: GeneratedMtaSimRun) -> dict[str, Any]:
    """Select non-sensitive manifest and model-scope fields."""

    return {
        "generator": generated.manifest.get("generator"),
        "generatorVersion": generated.manifest.get("generator_version"),
        "pathRows": len(generated.dataset.path_rows),
        "performanceRows": len(generated.dataset.ads_rows),
        "touchpoints": len(generated.dataset.touchpoints),
        "reportStartDate": generated.dataset.scope.report_start_date,
        "reportEndDate": generated.dataset.scope.report_end_date,
        "marketplace": generated.dataset.scope.marketplace,
        "groundTruthRole": "evaluation_only",
    }


def _contains_key(value: object, target: str) -> bool:
    """Find a prohibited key recursively without interpreting its value."""

    if isinstance(value, dict):
        return target in value or any(
            _contains_key(item, target) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False


def _require_run(run_id: str) -> GeneratorRun:
    """Resolve an opaque hexadecimal run identifier."""

    if len(run_id) != 32 or any(
        character not in "0123456789abcdef" for character in run_id
    ):
        raise KeyError("Unknown generator run.")
    try:
        return _runs[run_id]
    except KeyError as error:
        raise KeyError("Unknown generator run.") from error


def _trim_runs() -> None:
    """Bound in-memory completed state without deleting ignored artifacts."""

    completed = [
        run_id for run_id, run in _runs.items() if run.status in {"completed", "failed"}
    ]
    for run_id in completed[:-MAX_COMPLETED_RUNS]:
        _runs.pop(run_id, None)


def _safe_error(error: Exception, secret: str = "") -> str:
    """Bound an error and remove the only submitted secret defensively."""

    message = f"{type(error).__name__}: {error}"
    if secret:
        message = message.replace(secret, "[redacted]")
    return message[:400]
