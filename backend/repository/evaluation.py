"""Strategy evaluation: the fourth pipeline stage's report artifact.

The report has no database representation because the evaluation command
produces it from strategy artifacts and optional research observations. File
and database modes therefore read the same JSON file, with an absent file
meaning the stage has not run.

Data flow: ``modules/mta_strategy_evaluation/outputs/strategy_evaluation.json``
-> here -> the ``strategyEvaluation`` dashboard snapshot key.
"""

from __future__ import annotations

from backend.config import REPO_ROOT, pipeline_artifact_path
from backend.repository.coercion import read_json


EVALUATION_OUTPUT = (
    REPO_ROOT
    / "modules"
    / "mta_strategy_evaluation"
    / "outputs"
    / "strategy_evaluation.json"
)


def strategy_evaluation() -> dict:
    """Return the evaluation artifact, or an empty object before its first run."""

    return read_json(
        pipeline_artifact_path("evaluation/strategy_evaluation.json", EVALUATION_OUTPUT)
    )
