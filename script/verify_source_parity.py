"""Assert that the dashboard reads identically from files and the database.

`dashboard/data_source.py` promises that every loader returns the same
columns, dtypes, and values whether `DATABASE` is true or false. A view is
written once against that contract, so a silent drift between the two modes
would surface as a broken chart only after the demo switched sources.

This command loads each loader twice in separate subprocesses -- the mode is
fixed at import time by an `lru_cache`, so one process cannot hold both -- and
compares the results.

Usage:
    uv run --extra dashboard python script/verify_source_parity.py

Exits non-zero when any loader differs, naming the loader and the field.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Loader name -> (sort keys, numeric columns whose totals must agree).
#: The sort keys make the comparison independent of each source's row order.
CHECKS: dict[str, tuple[list[str], list[str]]] = {
    "load_ads_daily": (
        ["report_date", "touchpoint"],
        ["impressions", "clicks", "cost", "purchases", "sales"],
    ),
    "load_attribution_results": (
        ["attribution_model", "touchpoint"],
        ["attributed_revenue", "attributed_converted_users", "cost", "roas"],
    ),
    "load_comparison_touchpoints": (
        ["outcome", "touchpoint"],
        ["markov_share", "shapley_share", "gap_pp"],
    ),
    "load_comparison_summary": (["outcome"], ["tvd", "touchpoint_count"]),
    "load_recommended_attribution": (
        ["outcome", "touchpoint"],
        ["official_share", "benchmark_share", "gap_pp"],
    ),
    "load_entity_bridge": (
        ["campaign_id", "ad_group_id", "touchpoint"],
        ["assisted_revenue", "assisted_converted_users", "cost"],
    ),
    "load_path_report": (["path"], ["users", "revenue", "path_length"]),
}

#: Reliability flags must be real booleans in both modes, not the strings the
#: pipeline writes: the non-empty string "false" is truthy.
BOOLEAN_COLUMNS = (
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
)

#: Loaders returning a nested mapping rather than a table. Only the top-level
#: keys are compared; the nested shapes are rebuilt field by field.
DOCUMENT_LOADERS = (
    "load_budget_recommendation",
    "load_strategy_request",
    "load_candidate_pool",
)

# The child process runs this to describe one mode. Kept as source text so the
# parent can set DATABASE before the dashboard package is imported.
_PROBE = """
import json, os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, {root!r})
os.environ["DATABASE"] = sys.argv[1]
import pandas as pd
from dashboard import data_source as ds

CHECKS = {checks!r}
BOOLEAN_COLUMNS = {booleans!r}
DOCUMENT_LOADERS = {documents!r}

result = {{}}
for name, (keys, numeric) in CHECKS.items():
    frame = getattr(ds, name)()
    present = [key for key in keys if key in frame.columns]
    if present:
        frame = frame.sort_values(present).reset_index(drop=True)
    entry = {{
        "rows": int(len(frame)),
        "columns": sorted(map(str, frame.columns)),
        "dtypes": {{str(c): str(t) for c, t in frame.dtypes.items()}},
        "sums": {{
            column: round(float(pd.to_numeric(frame[column], errors="coerce").sum()), 4)
            for column in numeric
            if column in frame.columns
        }},
        "first_key": [str(frame.iloc[0][key]) for key in present] if len(frame) else [],
    }}
    entry["booleans"] = {{
        column: [str(frame[column].dtype), int(frame[column].sum())]
        for column in BOOLEAN_COLUMNS
        if column in frame.columns
    }}
    result[name] = entry

for name in DOCUMENT_LOADERS:
    document = getattr(ds, name)()
    result[name] = {{"keys": sorted(document)}}

sys.stdout.write("JSON:" + json.dumps(result, default=str))
"""


def describe(mode: str) -> dict:
    """Run the probe in a subprocess with `DATABASE` fixed to `mode`."""
    script = _PROBE.format(
        root=str(REPO_ROOT),
        checks=CHECKS,
        booleans=BOOLEAN_COLUMNS,
        documents=DOCUMENT_LOADERS,
    )
    process = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script, mode],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    marker = process.stdout.find("JSON:")
    if process.returncode != 0 or marker < 0:
        detail = (process.stderr or process.stdout).strip()[-1200:]
        raise SystemExit(f"Probe failed for DATABASE={mode}:\n{detail}")
    return json.loads(process.stdout[marker + len("JSON:") :])


def compare(files: dict, database: dict) -> list[str]:
    """Return one message per difference; an empty list means parity holds."""
    problems: list[str] = []
    for name in sorted(set(files) | set(database)):
        left, right = files.get(name), database.get(name)
        if left is None or right is None:
            problems.append(f"{name}: missing from {'files' if left is None else 'database'}")
            continue
        for field in ("keys", "columns", "rows", "dtypes", "sums", "booleans", "first_key"):
            if field not in left and field not in right:
                continue
            if left.get(field) != right.get(field):
                problems.append(
                    f"{name}.{field}: files={left.get(field)!r} database={right.get(field)!r}"
                )
    return problems


def main() -> int:
    print("Reading with DATABASE=false ...")
    files = describe("false")
    print("Reading with DATABASE=true ...")
    database = describe("true")

    problems = compare(files, database)
    if problems:
        print(f"\n{len(problems)} difference(s) between the two modes:\n")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print(f"\nParity holds across {len(files)} loaders.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
