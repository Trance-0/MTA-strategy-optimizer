"""Expose the Markov implementation through the shared model contract.

Data flow: ``MtaSimDataset`` -> the native Markov removal-effect estimator ->
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
from .markov_attribution_model import run_markov_attribution


class MarkovRemovalEffectModel(_JsonPersistedModel):
    """Standardized wrapper around the first-order Markov estimator."""

    model_id: ClassVar[str] = "markov_removal_effect"
    model_version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[ModelCapabilities] = ModelCapabilities(
        requires_fit=False,
        supports_persistence=True,
        deterministic=True,
    )

    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Attribute outcomes without changing the native Markov mathematics."""
        self._require_fitted(dataset)
        results = run_markov_attribution(list(dataset.path_rows))
        return standard_rows_from_attribution_results(self, dataset, results)
