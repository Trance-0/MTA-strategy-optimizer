"""Provide a uniform-credit reference model through the shared contract.

Data flow: ``MtaSimDataset`` -> equal outcome shares at four-segment grain ->
``StandardAttributionRow`` records used as a deterministic baseline.
"""

from __future__ import annotations

from typing import ClassVar

from modules.mta_standard.src.dataloader import MtaSimDataset
from modules.mta_standard.src.output_contract import (
    SUPPORTED_OUTCOMES,
    ZERO_OUTCOME_WARNING,
    StandardAttributionRow,
)

from .attribution_model_interface import ModelCapabilities, MtaAttributionModel


class UniformCreditModel(MtaAttributionModel):
    """Split every observed outcome equally across dataset touchpoints."""

    model_id: ClassVar[str] = "uniform_credit"
    model_version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[ModelCapabilities] = ModelCapabilities(
        requires_fit=True,
        supports_persistence=False,
        deterministic=True,
    )

    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Return an exact, conservation-preserving equal split."""
        self._require_fitted(dataset)
        touchpoints = sorted(dataset.touchpoints)
        if not touchpoints:
            raise ValueError("dataset contains no touchpoint to attribute")

        rows: list[StandardAttributionRow] = []
        count = len(touchpoints)
        for outcome in SUPPORTED_OUTCOMES:
            total = float(dataset.outcome_totals[outcome])
            has_outcome = total != 0
            share = 1.0 / count if has_outcome else 0.0
            value = total / count
            for index, touchpoint in enumerate(touchpoints):
                is_last = index == count - 1
                rows.append(
                    StandardAttributionRow(
                        model_id=self.model_id,
                        model_version=self.model_version,
                        report_start_date=dataset.scope.report_start_date,
                        report_end_date=dataset.scope.report_end_date,
                        marketplace=dataset.scope.marketplace,
                        touchpoint=touchpoint,
                        outcome=outcome,
                        attribution_share=(
                            (1.0 - share * (count - 1))
                            if is_last and has_outcome
                            else share
                        ),
                        attributed_value=(
                            (total - value * (count - 1)) if is_last else value
                        ),
                        valid=True,
                        warnings=() if has_outcome else (ZERO_OUTCOME_WARNING,),
                    )
                )
        return sorted(rows, key=lambda row: (row.touchpoint, row.outcome))
