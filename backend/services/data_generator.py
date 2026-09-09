"""Run the pinned MTA-SIM generator for the dashboard workflow.

The service owns ignored runtime files, bounded public state, two preview
tables, declared downloads, and backend-only PostgreSQL export. Simulation and
storage semantics remain in the pinned external package.
"""

from __future__ import annotations

import csv
import json
import math
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from backend.config import REPO_ROOT, pipeline_runs_enabled, valid_schema_name
from backend.services.datasets import register_generated_dataset
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
MAX_PATH_REFERENCES = 64
MAX_CAMPAIGN_REPLICATIONS = 50
MAX_COMPLETED_RUNS = 8
MAX_CONFIGURATION_DEPTH = 64
MAX_CONFIGURATION_ISSUES = 128
DOWNLOADS = {
    "path": ("amc_path_report.csv", "source_path_report"),
    "performance": (
        "amazon_ads_daily_touchpoint_performance.csv",
        "performance_report",
    ),
}


class InvalidConfigurationError(ValueError):
    """Carry safe, structured preflight issues to the HTTP boundary."""

    def __init__(self, issues: list[dict[str, str]]) -> None:
        super().__init__(
            issues[0]["message"]
            if issues
            else "Configuration failed preflight validation."
        )
        self.issues = _bounded_issues(issues)


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
    dataset_id: str | None = None
    registration_error: str = ""

    def public_state(self) -> dict[str, Any]:
        """Return state with no path, configuration, or credential."""

        return {
            "runId": self.run_id,
            "variant": self.variant,
            "status": self.status,
            "phase": self.phase,
            "message": self.message,
            "summary": dict(self.summary),
            "datasetId": self.dataset_id,
            "registrationError": self.registration_error,
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
_loader_lock = threading.RLock()
_runs: dict[str, GeneratorRun] = {}
_active_operation: str | None = None


def generator_overview() -> dict[str, Any]:
    """Return reviewed presets and one self-contained initial configuration."""

    reason = _generator_unavailability_reason()
    available = not reason
    configuration: dict[str, Any] = {}
    if available:
        try:
            configuration = preset_configuration("baseline", "toy")
        except (FileNotFoundError, ImportError, RuntimeError):
            available = False
            reason = "The pinned MTA-SIM submodule is not initialized."
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
    reason = _generator_unavailability_reason(variant, (filename,))
    if reason:
        raise RuntimeError(reason)
    try:
        return load_resolved_mta_sim_configuration(
            submodule_root=SUBMODULE_ROOT,
            configuration_path=SUBMODULE_ROOT / "ZheyuanWu" / "examples" / filename,
            variant=variant,
        )
    except (FileNotFoundError, ImportError):
        raise RuntimeError("The pinned MTA-SIM submodule is not initialized.") from None


def start_generation(variant: object, configuration: object) -> dict[str, Any]:
    """Validate a configuration boundary and start one background run."""

    global _active_operation
    accepted = validate_configuration(variant, configuration)
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


def validate_configuration(variant: object, configuration: object) -> dict[str, Any]:
    """Preflight one self-contained configuration without creating run state.

    Project-owned checks produce field-level issues before the pinned MTA-SIM
    loader confirms that the same payload generation will consume.
    """

    if not isinstance(variant, str) or variant not in PRESETS:
        raise InvalidConfigurationError(
            [_issue("/variant", "configuration", "Variant must be baseline or regional.")]
        )

    reason = _generator_unavailability_reason(variant, ())
    if reason:
        raise RuntimeError(reason)

    issues = _configuration_issues(variant, configuration)
    if issues:
        raise InvalidConfigurationError(issues)

    assert isinstance(variant, str)
    assert isinstance(configuration, dict)
    accepted = _strict_json_copy(configuration)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as temporary:
            json.dump(accepted, temporary, ensure_ascii=False, allow_nan=False)
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        with _loader_lock:
            load_resolved_mta_sim_configuration(
                submodule_root=SUBMODULE_ROOT,
                configuration_path=temporary_path,
                variant=variant,
            )
        return accepted
    except InvalidConfigurationError:
        raise
    except (FileNotFoundError, ImportError):
        raise RuntimeError("The pinned MTA-SIM submodule is not initialized.") from None
    except OSError:
        raise RuntimeError("Generator preflight storage is unavailable.") from None
    except Exception:  # noqa: BLE001 - upstream errors are deliberately opaque
        raise InvalidConfigurationError(
            [
                _issue(
                    "/",
                    "configuration",
                    "The configuration could not be accepted by the generator.",
                )
            ]
        ) from None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                raise RuntimeError("Generator preflight storage is unavailable.") from None


def _generator_unavailability_reason(
    variant: str | None = None,
    preset_filenames: tuple[str, ...] | None = None,
) -> str:
    """Return one bounded capability reason without exposing checkout paths."""

    if not pipeline_runs_enabled():
        return "Pipeline runs are disabled on this backend."
    project_root = SUBMODULE_ROOT / "ZheyuanWu"
    required_paths = [
        project_root / "simulations",
        project_root / "simulations" / "__init__.py",
    ]
    filenames = (
        tuple(filename for presets in PRESETS.values() for filename in presets.values())
        if preset_filenames is None
        else preset_filenames
    )
    required_paths.extend(project_root / "examples" / filename for filename in filenames)
    variants = (variant,) if variant in PRESETS else tuple(PRESETS)
    for item in variants:
        loader_root = project_root / "simulations" / item / "mta_dataset"
        required_paths.extend(
            (
                loader_root,
                loader_root / "__init__.py",
                loader_root / "configuration.py",
            )
        )
    if any(not path.exists() for path in required_paths):
        return "The pinned MTA-SIM submodule is not initialized."
    return ""


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
        # Persist the analysis input before publishing completion, so generator
        # retention cannot remove data a reader has selected for later analysis.
        # A registry failure must not invalidate already generated downloads.
        try:
            descriptor = register_generated_dataset(
                generated, f"{run.variant.title()} simulation {run.run_id[:8]}"
            )
            run.dataset_id = descriptor["id"]
        except Exception:  # noqa: BLE001 - generator exports remain independent
            run.registration_error = (
                "Generation completed, but analysis registration failed. "
                "Download the reports and validate them in Import Data, or check runtime storage."
            )
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


def _configuration_issues(
    variant: object, configuration: object
) -> list[dict[str, str]]:
    """Return deterministic dashboard-boundary issues before the upstream loader."""

    issues: list[dict[str, str]] = []
    if not isinstance(variant, str) or variant not in PRESETS:
        issues.append(
            _issue("/variant", "configuration", "Variant must be baseline or regional.")
        )
    if not isinstance(configuration, dict):
        return issues + [
            _issue(
                "/configuration",
                "configuration",
                "Configuration must be a JSON object.",
            )
        ]
    if not _is_strict_json(configuration):
        return issues + [
            _issue(
                "/",
                "configuration",
                "Configuration must contain only finite JSON values.",
            )
        ]

    extends_path = _find_key_path(configuration, "extends")
    if extends_path is not None:
        issues.append(
            _issue(
                extends_path,
                "configuration",
                "Configuration must be self-contained; extends is not allowed.",
            )
        )

    _validate_basics(configuration, issues)
    _validate_global_behavior(configuration, issues)
    _validate_marketplaces(configuration, issues, variant == "regional")
    touchpoint_identifiers = _validate_touchpoints(configuration, issues)
    _validate_path_scenarios(configuration, issues, touchpoint_identifiers)
    if variant == "regional":
        _validate_regional_behavior(configuration, issues)
    return issues


def _validate_basics(
    configuration: dict[str, Any], issues: list[dict[str, str]]
) -> None:
    """Validate fields shown by the Run basics editor section."""

    seed = configuration.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        issues.append(_issue("/seed", "basics", "Seed must be an integer."))
    advertiser = configuration.get("advertiser_id")
    if (
        not isinstance(advertiser, str)
        or not advertiser.strip()
        or len(advertiser) > 128
    ):
        issues.append(
            _issue(
                "/advertiser_id",
                "basics",
                "Advertiser ID is required and must contain at most 128 characters.",
            )
        )
    start = _date_value(configuration.get("report_start_date"))
    end = _date_value(configuration.get("report_end_date"))
    if start is None:
        issues.append(
            _issue(
                "/report_start_date", "basics", "Report start date must be an ISO date."
            )
        )
    if end is None:
        issues.append(
            _issue("/report_end_date", "basics", "Report end date must be an ISO date.")
        )
    if start is not None and end is not None:
        days = (end - start).days + 1
        if not 1 <= days <= MAX_REPORT_DAYS:
            issues.append(
                _issue(
                    "/report_end_date",
                    "basics",
                    f"Report window must contain 1 to {MAX_REPORT_DAYS} days.",
                )
            )
    _positive_number(
        configuration,
        "base_product_price",
        "basics",
        "Base product price must be positive and finite.",
        issues,
    )
    _finite_number(
        configuration,
        "baseline_conversion_log_odds",
        "basics",
        "Baseline conversion log odds must be finite.",
        issues,
    )
    replications = configuration.get("campaign_replications", 1)
    if isinstance(replications, bool) or not isinstance(replications, int):
        issues.append(
            _issue(
                "/campaign_replications",
                "basics",
                "Campaign replications must be an integer.",
            )
        )
    elif not 1 <= replications <= MAX_CAMPAIGN_REPLICATIONS:
        issues.append(
            _issue(
                "/campaign_replications",
                "basics",
                f"Campaign replications must be between 1 and {MAX_CAMPAIGN_REPLICATIONS}.",
            )
        )


def _validate_global_behavior(
    configuration: dict[str, Any], issues: list[dict[str, str]]
) -> None:
    """Validate global behavior fields that are cheap and field-addressable."""

    behavior = configuration.get("global_behavior")
    if not isinstance(behavior, dict):
        issues.append(
            _issue(
                "/global_behavior",
                "global_behavior",
                "Global behavior must be an object.",
            )
        )
        return
    weekly = behavior.get("weekly_traffic_multipliers")
    if not isinstance(weekly, list) or len(weekly) != 7:
        issues.append(
            _issue(
                "/global_behavior/weekly_traffic_multipliers",
                "global_behavior",
                "Weekly traffic multipliers must contain seven values.",
            )
        )
    else:
        for index, value in enumerate(weekly):
            if not _number(value) or value <= 0:
                issues.append(
                    _issue(
                        f"/global_behavior/weekly_traffic_multipliers/{index}",
                        "global_behavior",
                        "Traffic multiplier must be positive and finite.",
                    )
                )
    _finite_number(
        behavior,
        "daily_traffic_trend",
        "global_behavior",
        "Daily traffic trend must be finite.",
        issues,
        prefix="/global_behavior",
    )
    for field_name in (
        "conversion_probability_daily_noise_standard_deviation",
        "performance_volume_noise_standard_deviation",
        "path_audience_noise_standard_deviation",
        "performance_revenue_noise_standard_deviation",
        "path_revenue_noise_standard_deviation",
    ):
        _nonnegative_number(
            behavior,
            field_name,
            "global_behavior",
            "Noise standard deviation must be non-negative and finite.",
            issues,
            prefix="/global_behavior",
        )
    for field_name in ("additional_unit_probability", "repeat_purchase_probability"):
        value = behavior.get(field_name)
        if not _number(value) or not 0 <= value <= 1:
            issues.append(
                _issue(
                    f"/global_behavior/{field_name}",
                    "global_behavior",
                    "Probability must be between 0 and 1.",
                )
            )


def _validate_marketplaces(
    configuration: dict[str, Any], issues: list[dict[str, str]], regional: bool
) -> None:
    """Validate the one-marketplace service boundary and visible market fields."""

    marketplaces = configuration.get("marketplaces")
    if not isinstance(marketplaces, list) or len(marketplaces) != 1:
        issues.append(
            _issue(
                "/marketplaces", "marketplace", "Exactly one marketplace is required."
            )
        )
        return
    marketplace = marketplaces[0]
    if not isinstance(marketplace, dict):
        issues.append(
            _issue("/marketplaces/0", "marketplace", "Marketplace must be an object.")
        )
        return
    code = marketplace.get("code")
    if not isinstance(code, str) or not code.strip():
        issues.append(
            _issue(
                "/marketplaces/0/code", "marketplace", "Marketplace code is required."
            )
        )
    currency = marketplace.get("currency_code")
    if (
        not isinstance(currency, str)
        or len(currency) != 3
        or any(character < "A" or character > "Z" for character in currency)
    ):
        issues.append(
            _issue(
                "/marketplaces/0/currency_code",
                "marketplace",
                "Currency code must be a three-letter uppercase ISO code.",
            )
        )
    for field_name, message in (
        ("traffic_multiplier", "Traffic multiplier must be positive and finite."),
        ("price_multiplier", "Price multiplier must be positive and finite."),
    ):
        _positive_number(
            marketplace,
            field_name,
            "marketplace",
            message,
            issues,
            prefix="/marketplaces/0",
        )
    if regional:
        for field_name in ("internet_reach_rate", "target_audience_density"):
            value = marketplace.get(field_name)
            if not _number(value) or not 0 < value <= 1:
                issues.append(
                    _issue(
                        f"/marketplaces/0/{field_name}",
                        "marketplace",
                        "Value must be greater than 0 and at most 1.",
                    )
                )
        _positive_number(
            marketplace,
            "economic_willingness_multiplier",
            "marketplace",
            "Economic willingness multiplier must be positive and finite.",
            issues,
            prefix="/marketplaces/0",
        )
        value = marketplace.get("income_inequality_gini")
        if not _number(value) or not 0 <= value <= 1:
            issues.append(
                _issue(
                    "/marketplaces/0/income_inequality_gini",
                    "marketplace",
                    "Income inequality Gini must be between 0 and 1.",
                )
            )


def _validate_touchpoints(
    configuration: dict[str, Any], issues: list[dict[str, str]]
) -> set[str]:
    """Validate touchpoint cardinality, identifiers, rates, and billing basis."""

    touchpoints = configuration.get("touchpoints")
    if (
        not isinstance(touchpoints, list)
        or not 1 <= len(touchpoints) <= MAX_TOUCHPOINTS
    ):
        issues.append(
            _issue(
                "/touchpoints",
                "touchpoints",
                f"Touchpoints must contain 1 to {MAX_TOUCHPOINTS} items.",
            )
        )
        return set()
    identifiers: set[str] = set()
    for index, touchpoint in enumerate(touchpoints):
        prefix = f"/touchpoints/{index}"
        if not isinstance(touchpoint, dict):
            issues.append(
                _issue(prefix, "touchpoints", "Touchpoint must be an object.")
            )
            continue
        identifier = touchpoint.get("identifier")
        if not isinstance(identifier, str) or not identifier.strip():
            issues.append(
                _issue(
                    f"{prefix}/identifier",
                    "touchpoints",
                    "Touchpoint identifier is required.",
                )
            )
        elif identifier in identifiers:
            issues.append(
                _issue(
                    f"{prefix}/identifier",
                    "touchpoints",
                    "Touchpoint identifier must be unique.",
                )
            )
        else:
            identifiers.add(identifier)
        _nonnegative_number(
            touchpoint,
            "base_impressions",
            "touchpoints",
            "Base impressions must be non-negative and finite.",
            issues,
            prefix=prefix,
        )
        for field_name in ("click_through_rate", "platform_conversion_rate"):
            value = touchpoint.get(field_name)
            if not _number(value) or not 0 <= value <= 1:
                issues.append(
                    _issue(
                        f"{prefix}/{field_name}",
                        "touchpoints",
                        "Rate must be between 0 and 1.",
                    )
                )
        _nonnegative_number(
            touchpoint,
            "conversion_log_odds_effect",
            "touchpoints",
            "Conversion log odds effect must be non-negative and finite.",
            issues,
            prefix=prefix,
        )
        cpc, cpm = (
            touchpoint.get("cost_per_click"),
            touchpoint.get("cost_per_thousand_impressions"),
        )
        valid_cpc = _number(cpc) and cpc >= 0
        valid_cpm = _number(cpm) and cpm >= 0
        if cpc is not None and not valid_cpc:
            issues.append(
                _issue(
                    f"{prefix}/cost_per_click",
                    "touchpoints",
                    "CPC must be a non-negative number or null.",
                )
            )
        elif cpm is not None and not valid_cpm:
            issues.append(
                _issue(
                    f"{prefix}/cost_per_thousand_impressions",
                    "touchpoints",
                    "CPM must be a non-negative number or null.",
                )
            )
        elif valid_cpc == valid_cpm:
            issues.append(
                _issue(
                    f"{prefix}/cost_per_click",
                    "touchpoints",
                    "Exactly one of CPC or CPM must be a non-negative number.",
                )
            )
    return identifiers


def _validate_path_scenarios(
    configuration: dict[str, Any],
    issues: list[dict[str, str]],
    touchpoint_identifiers: set[str],
) -> None:
    """Validate scenario identifiers and their exact touchpoint references."""

    scenarios = configuration.get("path_scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= MAX_PATH_SCENARIOS:
        issues.append(
            _issue(
                "/path_scenarios",
                "path_scenarios",
                f"Path scenarios must contain 1 to {MAX_PATH_SCENARIOS} items.",
            )
        )
        return
    identifiers: set[str] = set()
    for index, scenario in enumerate(scenarios):
        prefix = f"/path_scenarios/{index}"
        if not isinstance(scenario, dict):
            issues.append(
                _issue(prefix, "path_scenarios", "Path scenario must be an object.")
            )
            continue
        identifier = scenario.get("identifier")
        if not isinstance(identifier, str) or not identifier.strip():
            issues.append(
                _issue(
                    f"{prefix}/identifier",
                    "path_scenarios",
                    "Path scenario identifier is required.",
                )
            )
        elif identifier in identifiers:
            issues.append(
                _issue(
                    f"{prefix}/identifier",
                    "path_scenarios",
                    "Path scenario identifier must be unique.",
                )
            )
        else:
            identifiers.add(identifier)
        references = scenario.get("touchpoint_identifiers")
        if not isinstance(references, list) or not references:
            issues.append(
                _issue(
                    f"{prefix}/touchpoint_identifiers",
                    "path_scenarios",
                    "Path scenario requires one or more touchpoint identifiers.",
                )
            )
        elif len(references) > MAX_PATH_REFERENCES:
            issues.append(
                _issue(
                    f"{prefix}/touchpoint_identifiers",
                    "path_scenarios",
                    f"A path scenario may contain at most {MAX_PATH_REFERENCES} touchpoint references.",
                )
            )
        else:
            seen_references: set[str] = set()
            for reference_index, reference in enumerate(references):
                path = f"{prefix}/touchpoint_identifiers/{reference_index}"
                if (
                    not isinstance(reference, str)
                    or reference not in touchpoint_identifiers
                ):
                    issues.append(
                        _issue(
                            path,
                            "path_scenarios",
                            "Path scenario references an unknown touchpoint.",
                        )
                    )
                elif reference in seen_references:
                    issues.append(
                        _issue(
                            path,
                            "path_scenarios",
                            "Path scenario cannot repeat a touchpoint identifier.",
                        )
                    )
                if isinstance(reference, str):
                    seen_references.add(reference)
        _positive_number(
            scenario,
            "base_users",
            "path_scenarios",
            "Base users must be positive and finite.",
            issues,
            prefix=prefix,
        )
        _nonnegative_number(
            scenario,
            "adjacent_synergy_log_odds",
            "path_scenarios",
            "Adjacent synergy log odds must be non-negative and finite.",
            issues,
            prefix=prefix,
        )


def _validate_regional_behavior(
    configuration: dict[str, Any], issues: list[dict[str, str]]
) -> None:
    """Validate fields visible only in the regional configuration variant."""

    behavior = configuration.get("regional_behavior")
    if not isinstance(behavior, dict):
        issues.append(
            _issue(
                "/regional_behavior",
                "regional_behavior",
                "Regional behavior must be an object.",
            )
        )
        return
    for field_name in (
        "reference_internet_reach_rate",
        "reference_target_audience_density",
    ):
        value = behavior.get(field_name)
        if not _number(value) or not 0 < value <= 1:
            issues.append(
                _issue(
                    f"/regional_behavior/{field_name}",
                    "regional_behavior",
                    "Value must be greater than 0 and at most 1.",
                )
            )
    value = behavior.get("reference_income_inequality_gini")
    if not _number(value) or not 0 <= value <= 1:
        issues.append(
            _issue(
                "/regional_behavior/reference_income_inequality_gini",
                "regional_behavior",
                "Reference income inequality Gini must be between 0 and 1.",
            )
        )
    for field_name in (
        "economic_willingness_log_odds_weight",
        "income_inequality_noise_weight",
    ):
        _nonnegative_number(
            behavior,
            field_name,
            "regional_behavior",
            "Weight must be non-negative and finite.",
            issues,
            prefix="/regional_behavior",
        )


def _issue(path: str, section: str, message: str) -> dict[str, str]:
    """Build one client-safe issue in the documented response shape."""

    return {"path": path, "section": section, "message": message}


def _bounded_issues(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    """Cap one client response while retaining deterministic first-field order."""

    if len(issues) <= MAX_CONFIGURATION_ISSUES:
        return issues
    return issues[: MAX_CONFIGURATION_ISSUES - 1] + [
        _issue(
            "/",
            "configuration",
            "Additional configuration issues were omitted.",
        )
    ]


def _number(value: object) -> bool:
    """Return whether a value is a finite JSON number but not a Boolean."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _finite_number(
    values: dict[str, Any],
    field_name: str,
    section: str,
    message: str,
    issues: list[dict[str, str]],
    *,
    prefix: str = "",
) -> None:
    """Append a field issue unless a field is a finite JSON number."""

    if not _number(values.get(field_name)):
        issues.append(_issue(f"{prefix}/{field_name}", section, message))


def _positive_number(
    values: dict[str, Any],
    field_name: str,
    section: str,
    message: str,
    issues: list[dict[str, str]],
    *,
    prefix: str = "",
) -> None:
    """Append a field issue unless a field is a positive finite JSON number."""

    value = values.get(field_name)
    if not _number(value) or value <= 0:
        issues.append(_issue(f"{prefix}/{field_name}", section, message))


def _nonnegative_number(
    values: dict[str, Any],
    field_name: str,
    section: str,
    message: str,
    issues: list[dict[str, str]],
    *,
    prefix: str = "",
) -> None:
    """Append a field issue unless a field is a non-negative finite number."""

    value = values.get(field_name)
    if not _number(value) or value < 0:
        issues.append(_issue(f"{prefix}/{field_name}", section, message))


def _date_value(value: object) -> date | None:
    """Parse an ISO date only when the input is a JSON string."""

    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _is_strict_json(value: object, depth: int = 0) -> bool:
    """Reject non-string object keys, non-finite numbers, and Python-only values."""

    if depth > MAX_CONFIGURATION_DEPTH:
        return False
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_strict_json(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_strict_json(item, depth + 1)
            for key, item in value.items()
        )
    return False


def _strict_json_copy(configuration: dict[str, Any]) -> dict[str, Any]:
    """Detach an already checked configuration without widening JSON semantics."""

    return json.loads(json.dumps(configuration, allow_nan=False))


def _find_key_path(value: object, target: str, path: str = "") -> str | None:
    """Return the first JSON Pointer where a recursively prohibited key occurs."""

    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}/{key.replace('~', '~0').replace('/', '~1')}"
            if key == target:
                return child_path
            found = _find_key_path(item, target, child_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_key_path(item, target, f"{path}/{index}")
            if found is not None:
                return found
    return None


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
