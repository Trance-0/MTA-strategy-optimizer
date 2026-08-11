"""Run registered attribution models through the shared framework.

This module owns orchestration only. Concrete model mathematics remain in
``modules.mta_attribution`` while this pipeline builds models by identifier,
fits them, validates their standard rows, and returns immutable run results.

Data flow: model identifiers + ``MtaSimDataset`` -> registry -> fit/attribute
-> standard-output validation -> ``ModelRun`` objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from .dataloader import MtaSimDataset
from .model_registry import build_model
from .output_contract import StandardAttributionRow, validate_standard_output


@dataclass(frozen=True)
class ModelRun:
    """Validated output from one registered model execution."""

    model_id: str
    rows: tuple[StandardAttributionRow, ...]


def run_registered_models(
    dataset: MtaSimDataset, model_ids: Sequence[str]
) -> Mapping[str, ModelRun]:
    """Fit, execute, and validate independently registered models.

    Args:
        dataset: Model-facing dataset with ground truth structurally excluded.
        model_ids: Ordered model identifiers; duplicates are rejected.

    Returns:
        Mapping[str, ModelRun]: Immutable results in caller-supplied order.

    Raises:
        ValueError: If no models are requested or an identifier is repeated.
        KeyError: If an identifier is not registered.
    """

    ordered_ids = tuple(model_ids)
    if not ordered_ids:
        raise ValueError("run_registered_models requires at least one model_id")
    if len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError("run_registered_models requires distinct model_ids")

    runs: dict[str, ModelRun] = {}
    for model_id in ordered_ids:
        model = build_model(model_id)
        rows = tuple(model.fit(dataset).attribute(dataset))
        validate_standard_output(rows, outcome_totals=dataset.outcome_totals)
        runs[model_id] = ModelRun(model_id=model_id, rows=rows)
    return MappingProxyType(runs)
