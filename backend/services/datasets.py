"""Validate observed reports and publish immutable workbench datasets.

Inputs use the existing simulator report contracts. Validation is shared by
file import, pushed data and generation; only complete directories become
selectable. Private inputs never change the legacy database or environment.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from backend.config import pipeline_output_directory
from modules.mta_attribution.src.attribution_contract import NULL, validate_amc_aggregated_row
from modules.mta_attribution.src.touchpoint_key import canonicalize_touchpoint_key
from modules.mta_standard.src.dataloader import MTA_SIM_ADS_FIELDS, MTA_SIM_PATH_REPORT_FIELDS
from modules.mta_standard.src.touchpoint_adapter import four_segment_key_from_ads_row
from modules.mta_standard.src.mta_sim_research_adapter import load_mta_sim_research_snapshot
from modules.mta_strategy_recommendation.src.episode_bridge import campaign_episodes_from_research_snapshot
from modules.mta_strategy_recommendation.src.response_dataset import build_campaign_response_dataset
from modules.mta_strategy_recommendation.src.response_model import fit_campaign_response_models

ID_PATTERN = re.compile(r"ds_[0-9a-f]{32}\Z")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
PREVIEW_LIMIT = 20
ISSUE_LIMIT = 128
PERFORMANCE_NUMBERS = ("impressions", "clicks", "cost", "purchases", "sales", "unitsSold")
PATH_NUMBERS = ("users", "converted_users", "purchase_count", "revenue")
TRUTH_FIELDS = frozenset({
    "expected_organic_units", "expected_organic_revenue", "incremental_units",
    "incremental_revenue", "true_incremental_units", "true_incremental_revenue",
    "true_causal_effect", "simulator_ground_truth_id", "latent",
    "evaluation_outcome_observations", "ground_truth", "simulation_ground_truth",
})


class DatasetValidationError(ValueError):
    """Bounded field issues suitable for an untrusted input response."""

    def __init__(self, issues):
        self.issues = issues[:ISSUE_LIMIT]
        super().__init__(self.issues[0]["message"] if issues else "Invalid dataset.")


class DatasetNotFoundError(KeyError):
    """No published dataset exists for the supplied opaque identity."""


class DatasetStorageError(RuntimeError):
    """Runtime storage is unavailable without exposing a private path."""


def _issue(path, message):
    return {"path": path, "message": str(message)[:300]}


def _date(value):
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        raise ValueError("Use a calendar date in YYYY-MM-DD format.")
    return date.fromisoformat(value).isoformat()


def _number(value, integer=False):
    if value is None or value == "" or isinstance(value, bool):
        raise ValueError("A finite nonnegative number is required.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("A finite nonnegative number is required.") from None
    if not math.isfinite(number) or number < 0 or (integer and not number.is_integer()):
        raise ValueError("A finite nonnegative integer is required." if integer else "A finite nonnegative number is required.")
    return int(number) if integer else number


def _rows(value, role, fields, numbers, issues):
    if not isinstance(value, list) or (role == "performance" and not value):
        issues.append(_issue(role, "Provide a nonempty row array." if role == "performance" else "Provide a row array."))
        return []
    accepted = []
    seen = set()
    for index, raw in enumerate(value, 1):
        at = f"{role}/{index}"
        if not isinstance(raw, dict):
            issues.append(_issue(at, "Each row must be an object.")); continue
        extras = set(raw) - set(fields)
        missing = set(fields) - set(raw)
        if extras or missing:
            issues.append(_issue(at, f"Unexpected fields: {sorted(extras)}; missing fields: {sorted(missing)}."))
            continue
        row = {field: raw[field] for field in fields}
        for field in numbers:
            # unitsSold is optional diagnostic content in the existing report.
            if field == "unitsSold" and row[field] in (None, ""):
                row[field] = None
                continue
            try:
                row[field] = _number(row[field], field not in {"cost", "sales", "revenue"})
            except ValueError as error:
                issues.append(_issue(f"{at}/{field}", error))
        try:
            if role == "performance":
                row["reportDate"] = _date(row["reportDate"])
                for field in ("marketplace", "accountId", "currencyCode"):
                    if not isinstance(row[field], str) or not row[field].strip():
                        raise ValueError(f"{field} must be nonempty text.")
                    row[field] = row[field].strip()
                key = canonicalize_touchpoint_key(row["normalizedTouchpoint"])
                if key.rsplit(":", 1)[0] != four_segment_key_from_ads_row(row):
                    raise ValueError("normalizedTouchpoint disagrees with its component fields.")
                row["normalizedTouchpoint"] = key
                identity = tuple(row[f] for f in ("reportDate", "marketplace", "accountId", "normalizedTouchpoint", "currencyCode"))
            else:
                row["report_start_date"] = _date(row["report_start_date"])
                row["report_end_date"] = _date(row["report_end_date"])
                if row["report_start_date"] > row["report_end_date"]:
                    raise ValueError("The report end must not precede its start.")
                for field in ("marketplace", "advertiser_id"):
                    if not isinstance(row[field], str) or not row[field].strip():
                        raise ValueError(f"{field} must be nonempty text.")
                    row[field] = row[field].strip()
                row["path"] = " > ".join(validate_amc_aggregated_row(row, index))
                identity = tuple(row[f] for f in ("report_start_date", "report_end_date", "marketplace", "advertiser_id", "path"))
            if identity in seen:
                raise ValueError("Duplicate observation key; provide one row per key.")
            seen.add(identity)
        except (TypeError, ValueError, OverflowError) as error:
            issues.append(_issue(at, error))
        accepted.append(row)
    return accepted


def _walk(value, path="research"):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value, 1):
            yield from _walk(child, f"{path}/{index}")


def research_observation_key(row):
    """Identify one campaign budget period using every reporting-scope field."""
    scope = row.get("reporting_scope") or {}
    level = row.get("budget_level")
    return (row.get("campaign_id"), float(level) if level is not None else None,
            *(scope.get(field) for field in ("advertiser_id", "marketplace", "currency",
              "campaign_group_id", "report_start_date", "report_end_date")))


def _validate_research(research, scope, issues):
    if research is None:
        return None
    if not isinstance(research, dict):
        issues.append(_issue("research", "Research must be a JSON object.")); return None
    # Scope and referential checks supplement the canonical type adapter, which
    # intentionally accepts flat objects without enforcing the full graph.
    for path, value in _walk(research):
        if isinstance(value, float) and not math.isfinite(value):
            issues.append(_issue(path, "Nonfinite values are not permitted."))
        if isinstance(value, dict):
            for field in ("configured_budget", "actual_spend", "cost", "reported_purchases", "reported_sales", "impressions", "clicks", "total_units", "total_revenue", "baseline_daily_budget"):
                if value.get(field) is not None:
                    try:
                        _number(value[field], field in {"impressions", "clicks", "reported_purchases"})
                    except ValueError as error:
                        issues.append(_issue(f"{path}/{field}", error))
            for field in ("contribution_profit", "budget_delta", "budget_level", "unit_price", "unit_cogs", "unit_contribution_margin", "variable_cost_per_unit", "variable_fulfillment_cost_per_unit", "variable_platform_fee_per_unit", "other_variable_cost_per_unit"):
                if value.get(field) is not None:
                    try:
                        if isinstance(value[field], bool) or not math.isfinite(float(value[field])):
                            raise ValueError
                    except (TypeError, ValueError, OverflowError):
                        issues.append(_issue(f"{path}/{field}", "A finite numeric value is required."))
            if path.startswith("research/outcome_observations/"):
                for field in TRUTH_FIELDS:
                    if value.get(field) is not None:
                        issues.append(_issue(f"{path}/{field}", "Simulation truth does not belong in ordinary observations."))
        if isinstance(value, dict) and "reporting_scope" in value:
            item = value["reporting_scope"]
            if not isinstance(item, dict):
                issues.append(_issue(path, "reporting_scope must be an object.")); continue
            try:
                if (item.get("advertiser_id"), item.get("marketplace"), item.get("currency")) != (scope["advertiserId"], scope["marketplace"], scope["currency"]):
                    raise ValueError("Research scope differs from performance; split mixed datasets.")
                start, end = _date(item.get("report_start_date")), _date(item.get("report_end_date"))
                if start > end:
                    raise ValueError("Research dates must form an ordered window.")
                scope["start"], scope["end"] = min(scope["start"], start), max(scope["end"], end)
            except ValueError as error:
                issues.append(_issue(path + "/reporting_scope", error))
    try:
        # Measured values are deliberately excluded from identity: a repeated
        # observation with different spend/revenue is a conflict, not new data.
        for role in ("budget_observations", "delivery_observations", "outcome_observations", "evaluation_outcome_observations"):
            seen = set()
            for index, row in enumerate(research.get(role, []), 1):
                key = research_observation_key(row)
                if role != "budget_observations":
                    touchpoint = row.get("touchpoint") or {}
                    key += tuple(touchpoint.get(field) for field in ("provider", "ad_product", "format", "placement", "creative", "interaction_type"))
                if role in {"outcome_observations", "evaluation_outcome_observations"}:
                    key += (row.get("product_id"),)
                if key in seen:
                    issues.append(_issue(f"research/{role}/{index}", "Duplicate observation identity."))
                seen.add(key)
        runs = research.get("simulation_runs") or []
        campaign_ids = [item["campaign_id"] for run in runs for item in run.get("campaigns", [])]
        product_ids = [item["product_id"] for run in runs for item in run.get("products", [])]
        ad_group_ids = [item["ad_group_id"] for run in runs for item in run.get("ad_groups", [])]
        for name, ids in (("campaign", campaign_ids), ("product", product_ids), ("ad_group", ad_group_ids)):
            if len(ids) != len(set(ids)):
                issues.append(_issue("research", f"Duplicate {name} identity."))
        for path, value in _walk(research):
            if not isinstance(value, dict):
                continue
            for field, known in (("campaign_id", campaign_ids), ("product_id", product_ids), ("ad_group_id", ad_group_ids)):
                if field in value and value[field] is not None and value[field] not in known:
                    issues.append(_issue(f"{path}/{field}", "Reference does not identify a declared entity."))
            if "currency" in value and value["currency"] != scope["currency"]:
                issues.append(_issue(f"{path}/currency", "Research currencies must match performance."))
        # Only a temporary parser file is needed: no published directory exists
        # before every input passes the same canonical research reader.
        with tempfile.TemporaryDirectory(prefix="dataset-validation-") as temporary:
            path = Path(temporary) / "simulation_research.json"
            path.write_text(json.dumps(research, allow_nan=False), encoding="utf-8")
            snapshot = load_mta_sim_research_snapshot(path)
        return snapshot
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        issues.append(_issue("research", "Research does not satisfy the canonical sidecar contract."))
        return None


def _validated(payload):
    issues = []
    if not isinstance(payload, dict) or set(payload) - {"name", "performance", "paths", "research"}:
        raise DatasetValidationError([_issue("/", "Use only name, performance, paths and research roles.")])
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 160:
        issues.append(_issue("name", "Provide a name between 1 and 160 characters."))
    performance = _rows(payload.get("performance"), "performance", MTA_SIM_ADS_FIELDS, PERFORMANCE_NUMBERS, issues)
    paths = _rows(payload.get("paths", []), "paths", MTA_SIM_PATH_REPORT_FIELDS, PATH_NUMBERS, issues)
    if issues:
        raise DatasetValidationError(issues)
    scopes = {(r["accountId"], r["marketplace"], r["currencyCode"]) for r in performance}
    if len(scopes) != 1:
        raise DatasetValidationError([_issue("performance", "Provide one account, marketplace and currency; split mixed datasets.")])
    advertiser, marketplace, currency = next(iter(scopes))
    scope = {"advertiserId": advertiser, "marketplace": marketplace, "currency": currency,
             "start": min(r["reportDate"] for r in performance), "end": max(r["reportDate"] for r in performance)}
    touchpoints = {r["normalizedTouchpoint"] for r in performance}
    for index, row in enumerate(paths, 1):
        if (row["advertiser_id"], row["marketplace"]) != (advertiser, marketplace):
            issues.append(_issue(f"paths/{index}", "Path account and marketplace must match performance."))
        scope["start"] = min(scope["start"], row["report_start_date"])
        scope["end"] = max(scope["end"], row["report_end_date"])
        if any(key.strip() != NULL and key.strip() not in touchpoints for key in row["path"].split(">")):
            issues.append(_issue(f"paths/{index}/path", "Every path touchpoint needs matching performance."))
    research = copy.deepcopy(payload.get("research"))
    snapshot = _validate_research(research, scope, issues)
    if issues:
        raise DatasetValidationError(issues)
    def capability(available, reason):
        return {"available": bool(available), "reason": "" if available else reason}
    has_history = bool(snapshot and snapshot.budget_observations)
    can_optimize = False
    if has_history:
        try:
            response = build_campaign_response_dataset(campaign_episodes_from_research_snapshot(snapshot))
            models = fit_campaign_response_models(response)
            can_optimize = bool(models) and all(model.is_usable for model in models.values())
        except (ValueError, TypeError):
            # Valid observations may lack fit evidence; retain them for analysis.
            can_optimize = False
    attribution = _attribution_capability(performance, paths)
    capabilities = {
        "performance": capability(True, ""),
        "attribution": attribution,
        "history": capability(has_history, "Add research budget observations for Campaign history."),
        "optimization": capability(can_optimize, "Add sufficient ordinary Campaign outcomes and varying budget observations for response fitting."),
        "evaluation": capability(has_history and snapshot.outcome_observations, "Add research budget and ordinary outcome observations, then select a completed strategy run."),
    }
    counts = {"performance": len(performance), "paths": len(paths),
              "campaigns": len(snapshot.campaigns) if snapshot else 0,
              "budgetObservations": len(snapshot.budget_observations) if snapshot else 0}
    preview = {"valid": True, "name": name.strip(), "scope": scope, "counts": counts,
               "capabilities": capabilities, "preview": {"performance": performance[:PREVIEW_LIMIT], "paths": paths[:PREVIEW_LIMIT]}}
    return {"performance": performance, "paths": paths, "research": research}, preview


def _attribution_capability(performance, paths):
    """Reuse the actual command preflight; report-only inputs may be sparse."""
    if not paths:
        return {"available": False, "reason": "Add matching aggregated paths."}
    from modules.mta_attribution.src.run_attribution_models import read_attribution_ads_rows
    from modules.mta_attribution.src.validate_data_alignment import validate_data_alignment_rows
    from modules.mta_standard.src.mta_sim_generator_adapter import prepare_single_scope_path_report
    with tempfile.TemporaryDirectory(prefix="dataset-attribution-") as temporary:
        path = Path(temporary) / "performance.csv"
        try:
            _write_csv(path, MTA_SIM_ADS_FIELDS, performance)
            source_paths = Path(temporary) / "paths.csv"
            model_paths = Path(temporary) / "model_paths.csv"
            _write_csv(source_paths, MTA_SIM_PATH_REPORT_FIELDS, paths)
            prepare_single_scope_path_report(source_paths, path, model_paths)
            ads = read_attribution_ads_rows(path)
            with model_paths.open(encoding="utf-8", newline="") as source:
                validate_data_alignment_rows(list(csv.DictReader(source)), ads)
        except ValueError as error:
            reason = str(error).replace(str(path), "performance").replace(str(temporary), "input")
            return {"available": False, "reason": reason[:300]}
    return {"available": True, "reason": ""}


def validate_dataset(payload):
    """Return a bounded preview without publishing or retaining inputs."""
    return _validated(payload)[1]


def _root():
    runtime = pipeline_output_directory()
    if runtime is None:
        raise DatasetStorageError("Dataset runtime storage is unavailable.")
    return runtime / "workbench" / "datasets"


def dataset_directory(dataset_id):
    """Resolve only a published, nonsymlinked server-issued directory."""
    if not isinstance(dataset_id, str) or not ID_PATTERN.fullmatch(dataset_id):
        raise DatasetNotFoundError("Dataset not found.")
    directory = _root() / dataset_id
    if directory.is_symlink() or not (directory / "manifest.json").is_file():
        raise DatasetNotFoundError("Dataset not found.")
    return directory


def get_dataset(dataset_id):
    """Read the durable descriptor rather than relying on process state."""
    directory = dataset_directory(dataset_id)
    try:
        descriptor = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if descriptor.get("id") != dataset_id:
            raise ValueError("Identity mismatch")
        return descriptor
    except (OSError, ValueError, TypeError, AttributeError):
        raise DatasetStorageError("The registered dataset metadata is unavailable.") from None


def dataset_inputs(dataset_id):
    """Return private canonical inputs after checking their immutable digest."""
    directory = dataset_directory(dataset_id)
    try:
        content = (directory / "inputs.json").read_bytes()
        if hashlib.sha256(content).hexdigest() != get_dataset(dataset_id)["digest"]:
            raise ValueError("Input digest mismatch")
        return json.loads(content)
    except (OSError, ValueError, KeyError):
        raise DatasetStorageError("The registered dataset inputs are unavailable or changed.") from None


def list_datasets():
    """List complete descriptors, newest first with stable identity ordering."""
    root = _root()
    if not root.exists():
        return []
    try:
        result = [get_dataset(p.name) for p in root.iterdir() if ID_PATTERN.fullmatch(p.name) and p.is_dir() and not p.is_symlink() and (p / "manifest.json").is_file()]
    except OSError:
        raise DatasetStorageError("Dataset runtime storage is unavailable.") from None
    return sorted(result, key=lambda item: (item["createdAt"], item["id"]), reverse=True)


def _write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def register_dataset(payload, *, source="api"):
    """Publish all validated files together; a failed rename publishes none."""
    if source not in {"api", "file", "generated"}:
        raise DatasetValidationError([_issue("source", "Unknown dataset source.")])
    inputs, preview = _validated(payload)
    content = (json.dumps(inputs, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()
    identifier = "ds_" + uuid.uuid4().hex
    descriptor = {"id": identifier, "name": preview["name"], "source": source,
                  "isSynthetic": source == "generated" or any(item.get("is_synthetic") is True for item in (inputs["research"] or {}).get("data_lineage", [])),
                  "createdAt": datetime.now(timezone.utc).isoformat(), "digest": hashlib.sha256(content).hexdigest(),
                  **{key: preview[key] for key in ("scope", "counts", "capabilities")}}
    staging = None
    try:
        root = _root()
        root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=root))
        (staging / "inputs.json").write_bytes(content)
        _write_csv(staging / "amazon_ads_daily_touchpoint_performance.csv", MTA_SIM_ADS_FIELDS, inputs["performance"])
        _write_csv(staging / "amc_path_report.csv", MTA_SIM_PATH_REPORT_FIELDS, inputs["paths"])
        if inputs["research"] is not None:
            (staging / "simulation_research.json").write_text(json.dumps(inputs["research"], allow_nan=False), encoding="utf-8")
        (staging / "manifest.json").write_text(json.dumps(descriptor, allow_nan=False), encoding="utf-8")
        # Manifest and observations become visible in one filesystem operation.
        os.replace(staging, root / identifier)
        return descriptor
    except OSError:
        raise DatasetStorageError("Dataset runtime storage is unavailable; nothing was published.") from None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)


def register_generated_dataset(generated, name):
    """Register daily generator reports, adapting only historical key grain."""
    with generated.source_path_report.open(encoding="utf-8-sig", newline="") as source:
        paths = list(csv.DictReader(source))
    performance = [{field: row.get(field) for field in MTA_SIM_ADS_FIELDS} for row in generated.dataset.ads_rows]
    for row, annotated in zip(performance, generated.dataset.ads_rows):
        row["normalizedTouchpoint"] = annotated.get("five_segment_touchpoint", annotated.get("touchpoint", row["normalizedTouchpoint"]))
    for row in paths:
        if any(len(part.strip().split(":")) == 4 for part in row["path"].split(">") if part.strip() != NULL):
            row["path"] = generated.simulator_config.adapt_path(row["path"])
    research_file = generated.output_directory / "simulation_research.json"
    research = json.loads(research_file.read_text(encoding="utf-8")) if research_file.is_file() else None
    return register_dataset({"name": name, "performance": performance, "paths": paths, "research": research}, source="generated")


def templates():
    """Describe one exact report schema with a small valid downloadable example."""
    performance = dict(zip(MTA_SIM_ADS_FIELDS, ["2025-01-01", "US", "ACCOUNT-1", "SPONSORED_PRODUCTS", "AUTO", "", "", "", "SPONSORED_PRODUCTS:AUTO:UNSPECIFIED:UNSPECIFIED:CLICK", "USD", 0, 10, 12.5, 2, 30, 2]))
    paths = dict(zip(MTA_SIM_PATH_REPORT_FIELDS, ["2025-01-01", "2025-01-01", "US", "ACCOUNT-1", performance["normalizedTouchpoint"], 5, 2, 2, 30]))
    return {"performance": {"fields": list(MTA_SIM_ADS_FIELDS), "rows": [performance]},
            "paths": {"fields": list(MTA_SIM_PATH_REPORT_FIELDS), "rows": [paths]},
            "research": {"format": "simulation_research.json", "required": False}}
