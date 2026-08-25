"""The three model endpoints: attribution, recommendation, evaluation.

Each route runs the project's own module code and returns its result in one
response. They compute and answer; they write no artifact, so a caller can ask
what a model would say without changing what the dashboard reads. The
long-running commands that do publish artifacts are the job routes.

A refusal here is always specific. A model that is not registered names the
ones that are; an input that is absent names the configuration that would
supply it; a layer that is specified but not built says so rather than
returning an empty result a reader would mistake for an answer.

Data flow:
    a caller -> here -> backend/services/models.py -> modules/&#42;/src
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.services.models import (
    ModelRequestError,
    ModelUnavailableError,
    attribute,
    catalogue,
    compare,
    evaluate,
    optimize,
    recommend,
)
from backend.services.settings import log

blueprint = Blueprint("models", __name__)


def _run(name: str, action):
    """Run one model call and translate its refusals into status codes.

    A bad request is 400 -- the caller asked for something that does not exist
    or supplied a value that is not allowed. An unavailable capability is 409:
    the request is well formed and would succeed on a deployment configured
    with the input it needs, so it is a conflict with this deployment's state
    rather than a fault in the request. A failure inside a model is 500 with
    its type and message, because that is a defect worth seeing rather than
    hiding behind a generic error.
    """
    try:
        result = action()
        log("INFO", "models", f"{name} completed")
        return jsonify(result)
    except ModelRequestError as error:
        return jsonify({"error": "invalid_request", "message": str(error)}), 400
    except ModelUnavailableError as error:
        return jsonify({"error": "model_unavailable", "message": str(error)}), 409
    except (ValueError, KeyError, FileNotFoundError) as error:
        # The module layer raises these for a contract violation in the data:
        # a table that disagrees with its scope, a share that is not finite, a
        # named file that is not there. They are the caller's to act on.
        log("ERROR", "models", f"{name}: {type(error).__name__}: {error}")
        return (
            jsonify(
                {
                    "error": "model_failed",
                    "message": f"{type(error).__name__}: {str(error)[:400]}",
                }
            ),
            400,
        )
    except Exception as error:  # noqa: BLE001 - reported rather than hidden
        log("ERROR", "models", f"{name}: {type(error).__name__}: {error}")
        return (
            jsonify(
                {
                    "error": "model_error",
                    "message": f"{type(error).__name__}: {str(error)[:400]}",
                }
            ),
            500,
        )


@blueprint.get("/api/models")
def list_models():
    """What the three model endpoints can do in this deployment.

    Ask this before committing to a request: it reports which attribution
    models are registered, whether the optimizer has evidence to fit against,
    and whether ground truth is present, each with the remedy when it is not.
    """
    return _run("catalogue", catalogue)


@blueprint.post("/api/models/<model_id>/attribute")
def attribute_route(model_id: str):
    """Fit one registered attribution model and return its standard rows."""
    body = request.get_json(silent=True) or {}
    return _run(f"attribute:{model_id}", lambda: attribute(model_id, body))


@blueprint.post("/api/models/compare")
def compare_route():
    """Run several registered models over one dataset under identical conditions."""
    body = request.get_json(silent=True) or {}
    model_ids = body.get("modelIds") or []
    return _run("compare", lambda: compare(model_ids, body))


@blueprint.post("/api/models/recommend")
def recommend_route():
    """Produce the deterministic Ad Group count and budget seed.

    Needs no research snapshot: the allocation is derived from historical
    attribution evidence by a fixed formula. `is_optimized` is false for every
    result it returns.
    """
    body = request.get_json(silent=True) or {}
    return _run("recommend", lambda: recommend(body))


@blueprint.post("/api/models/optimize")
def optimize_route():
    """Fit Campaign response models and solve the constrained allocation.

    Needs the same Campaign observed at several budget levels, which only a
    research snapshot carries; without one it refuses with that remedy rather
    than fitting a curve through a single point.
    """
    body = request.get_json(silent=True) or {}
    return _run("optimize", lambda: optimize(body))


@blueprint.post("/api/models/evaluate")
def evaluate_route():
    """Score attribution models against simulator ground truth.

    Ground truth reaches the evaluator only, never `fit` or `attribute`, so no
    model can observe the answer it is scored against.
    """
    body = request.get_json(silent=True) or {}
    return _run("evaluate", lambda: evaluate(body))
