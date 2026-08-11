"""Expose the path-level Shapley implementation through the shared contract.

Data flow: ``MtaSimDataset`` -> native path-level Shapley attribution ->
four-segment ``StandardAttributionRow`` records for framework validation.
"""

from __future__ import annotations

from typing import ClassVar

from modules.mta_standard.src.dataloader import MtaSimDataset
from modules.mta_standard.src.output_contract import StandardAttributionRow

from .attribution_model_interface import (
    ModelCapabilities,
    _JsonPersistedModel,
    standard_rows_from_attribution_results,
)
from .shapley_attribution_model import run_shapley_attribution


class PathLevelShapleyModel(_JsonPersistedModel):
    """Standardized wrapper around the path-level Shapley estimator."""

    model_id: ClassVar[str] = "path_level_shapley"
    model_version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[ModelCapabilities] = ModelCapabilities(
        requires_fit=False,
        supports_persistence=True,
        deterministic=True,
    )

    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Attribute outcomes without changing the native Shapley mathematics."""
        self._require_fitted(dataset)
        results = run_shapley_attribution(list(dataset.path_rows))
        return standard_rows_from_attribution_results(self, dataset, results)
