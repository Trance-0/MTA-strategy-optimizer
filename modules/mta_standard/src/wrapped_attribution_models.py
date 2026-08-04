"""Concrete models built on the standardized interface.

Three implementations, chosen to prove the interface admits genuinely different
kinds of model:

- ``MarkovRemovalEffectModel`` and ``PathLevelShapleyModel`` wrap the existing
  five-segment estimators in ``mta_attribution``. They perform no arithmetic of
  their own; they forward path rows and relabel results, so their numbers are
  bit-identical to a direct call.
- ``UniformCreditModel`` shares no code with either and exists as a reference
  baseline, and to exercise the ``requires_fit`` and unsupported-persistence
  branches of the contract.

The learned model lives separately in ``dnn_attribution_model``. All four are
registered in ``model_registry``.
"""

from __future__ import annotations

from typing import ClassVar

from attribution_model_interface import (
    ModelCapabilities,
    MtaAttributionModel,
    _JsonPersistedModel,
    standard_rows_from_attribution_results,
)
from attribution_src_path import ensure_attribution_src_on_path
from dataloader import MtaSimDataset
from output_contract import (
    SUPPORTED_OUTCOMES,
    ZERO_OUTCOME_WARNING,
    StandardAttributionRow,
)

ensure_attribution_src_on_path()

from markov_attribution_model import run_markov_attribution  # noqa: E402
from shapley_attribution_model import run_shapley_attribution  # noqa: E402


class MarkovRemovalEffectModel(_JsonPersistedModel):
    """Standardized wrapper around the existing first-order Markov estimator.

    The wrapper performs no arithmetic of its own: it forwards the five-segment
    path rows to ``run_markov_attribution`` and relabels the results. Removal
    effects, convergence thresholds, and share normalisation are therefore
    unchanged.
    """

    model_id: ClassVar[str] = "markov_removal_effect"
    model_version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[ModelCapabilities] = ModelCapabilities(
        requires_fit=False,
        supports_persistence=True,
        deterministic=True,
    )

    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Attribute outcomes with the unchanged Markov removal-effect model.

        Args:
            dataset: The model-facing dataset.

        Returns:
            list[StandardAttributionRow]: Standard four-segment rows.

        Raises:
            RuntimeError: if the Markov chain does not converge, propagated
                unchanged from the wrapped implementation.
        """
        self._require_fitted(dataset)
        results = run_markov_attribution(list(dataset.path_rows))
        return standard_rows_from_attribution_results(self, dataset, results)


class PathLevelShapleyModel(_JsonPersistedModel):
    """Standardized wrapper around the existing path-level Shapley estimator.

    Like the Markov wrapper this only relabels results; the closed-form
    unanimity-game solution in ``AggregatedShapleyAttribution`` is untouched.
    """

    model_id: ClassVar[str] = "path_level_shapley"
    model_version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[ModelCapabilities] = ModelCapabilities(
        requires_fit=False,
        supports_persistence=True,
        deterministic=True,
    )

    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Attribute outcomes with the unchanged path-level Shapley model.

        Args:
            dataset: The model-facing dataset.

        Returns:
            list[StandardAttributionRow]: Standard four-segment rows.
        """
        self._require_fitted(dataset)
        results = run_shapley_attribution(list(dataset.path_rows))
        return standard_rows_from_attribution_results(self, dataset, results)


class UniformCreditModel(MtaAttributionModel):
    """A minimal pluggable model that splits every outcome equally.

    It exists to prove the interface admits an implementation that shares no
    code with the wrapped estimators, and to exercise the ``requires_fit`` and
    unsupported-persistence branches of the contract.
    """

    model_id: ClassVar[str] = "uniform_credit"
    model_version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[ModelCapabilities] = ModelCapabilities(
        requires_fit=True,
        supports_persistence=False,
        deterministic=True,
    )

    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Split each observed outcome equally across the dataset touchpoints.

        Args:
            dataset: The model-facing dataset.

        Returns:
            list[StandardAttributionRow]: Standard four-segment rows.

        Raises:
            RuntimeError: if the model was not fitted on this scope.
            ValueError: if the dataset contains no touchpoint.

        Invariants:
            The final touchpoint absorbs the residual of the equal split so
            that shares and attributed values conserve exactly rather than to
            within repeated-addition error.
        """
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
                            (1.0 - share * (count - 1)) if is_last and has_outcome
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
