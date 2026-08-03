from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, Sequence

from dataloader import MtaSimDataset
from legacy_paths import ensure_amc_mta_src_on_path
from output_contract import (
    SUPPORTED_OUTCOMES,
    ZERO_OUTCOME_WARNING,
    StandardAttributionRow,
)
from touchpoint_adapter import to_four_segment

ensure_amc_mta_src_on_path()

from amc_mta_attribution import (  # noqa: E402
    AttributionResult,
    run_markov_attribution,
    run_shapley_attribution,
)
from model_comparison import OUTCOME_FIELDS  # noqa: E402


@dataclass(frozen=True)
class ModelCapabilities:
    """Machine-readable description of what a standardized model supports.

    Attributes:
        requires_fit: Whether :meth:`MtaAttributionModel.attribute` refuses to
            run before :meth:`MtaAttributionModel.fit`.
        supports_persistence: Whether ``save``/``load`` are implemented.
        deterministic: Whether repeated runs on identical input produce
            byte-identical shares.
        supported_outcomes: Outcomes the model can attribute.
        grain: Touchpoint grain of the standard output.
    """

    requires_fit: bool
    supports_persistence: bool
    deterministic: bool
    supported_outcomes: tuple[str, ...] = SUPPORTED_OUTCOMES
    grain: str = "four_segment_touchpoint"


class MtaAttributionModel(ABC):
    """The public interface every standardized attribution model implements.

    Subclasses declare identity and capabilities as class attributes so a
    caller can compare models without instantiating them, then run any model
    through the same ``fit``/``attribute`` pair.

    Attributes:
        model_id: Stable identifier written into every standard row.
        model_version: Version of the model's contract and behaviour.
        capabilities: Static capability metadata.
    """

    model_id: ClassVar[str]
    model_version: ClassVar[str]
    capabilities: ClassVar[ModelCapabilities]

    def __init__(self) -> None:
        self._fitted_scope: dict | None = None

    def fit(self, dataset: MtaSimDataset) -> "MtaAttributionModel":
        """Prepare the model for a dataset.

        The wrapped closed-form estimators derive everything at attribution
        time, so the base implementation only records the scope it was prepared
        for. Subclasses that learn parameters override this.

        Args:
            dataset: The model-facing dataset. Ground truth is unreachable from
                it by construction.

        Returns:
            MtaAttributionModel: ``self``, so calls can be chained.
        """
        self._fitted_scope = asdict(dataset.scope)
        return self

    @property
    def fitted_scope(self) -> dict | None:
        """Return the scope this model was last fitted on, if any.

        Returns:
            dict | None: The recorded report scope, or ``None`` when unfitted.
        """
        return self._fitted_scope

    def _require_fitted(self, dataset: MtaSimDataset) -> None:
        """Enforce the ``requires_fit`` capability before attribution.

        Args:
            dataset: The dataset about to be attributed.

        Raises:
            RuntimeError: if the model requires fitting and was not fitted, or
                was fitted on a different report scope.
        """
        if not self.capabilities.requires_fit:
            return
        if self._fitted_scope is None:
            raise RuntimeError(
                f"{self.model_id} requires fit() before attribute()"
            )
        if self._fitted_scope != asdict(dataset.scope):
            raise RuntimeError(
                f"{self.model_id} was fitted on a different report scope"
            )

    @abstractmethod
    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Attribute outcomes to touchpoints.

        Args:
            dataset: The model-facing dataset.

        Returns:
            list[StandardAttributionRow]: Standard rows at the four-segment
            grain, ordered by touchpoint then outcome.
        """

    def save(self, path: str | Path) -> Path:
        """Persist the model.

        Args:
            path: Destination file.

        Returns:
            Path: The written path.

        Raises:
            NotImplementedError: if ``capabilities.supports_persistence`` is
                false, which is the honest answer for a model with no state.
        """
        raise NotImplementedError(f"{self.model_id} does not support save()")

    @classmethod
    def load(cls, path: str | Path) -> "MtaAttributionModel":
        """Restore a persisted model.

        Args:
            path: Source file.

        Returns:
            MtaAttributionModel: The restored model.

        Raises:
            NotImplementedError: if the model does not support persistence.
        """
        raise NotImplementedError(f"{cls.__name__} does not support load()")


class _JsonPersistedModel(MtaAttributionModel):
    """Persistence for models whose only state is identity plus fitted scope.

    The wrapped estimators are closed-form and stateless, so a persisted file
    records what produced a result rather than learned parameters. Loading
    refuses a file written by a different model or version, which keeps a
    restored model from silently changing a report's provenance.
    """

    def save(self, path: str | Path) -> Path:
        """Write model identity, capabilities, and fitted scope as JSON.

        Args:
            path: Destination file; parent directories are created.

        Returns:
            Path: The written path.
        """
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "capabilities": asdict(self.capabilities),
            "fitted_scope": self._fitted_scope,
        }
        destination.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "MtaAttributionModel":
        """Restore a model from a file written by :meth:`save`.

        Args:
            path: Source file.

        Returns:
            MtaAttributionModel: A model instance carrying the recorded scope.

        Raises:
            ValueError: if the file identifies a different model or version.
        """
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            payload.get("model_id") != cls.model_id
            or payload.get("model_version") != cls.model_version
        ):
            raise ValueError(
                f"{path}: expected {cls.model_id}/{cls.model_version}; got "
                f"{payload.get('model_id')}/{payload.get('model_version')}"
            )
        model = cls()
        model._fitted_scope = payload.get("fitted_scope")
        return model


def standard_rows_from_attribution_results(
    model: MtaAttributionModel,
    dataset: MtaSimDataset,
    results: Sequence[AttributionResult],
) -> list[StandardAttributionRow]:
    """Convert five-segment results back to the standard four-segment grain.

    This is the output half of the adaptation boundary. The wrapped algorithms
    keep working in five-segment keys; nothing outside this function and the
    loader sees that grain.

    Args:
        model: The model whose identity is stamped onto each row.
        dataset: The dataset the results were produced from, used for observed
            outcome totals.
        results: Results from an existing five-segment estimator.

    Returns:
        list[StandardAttributionRow]: Rows ordered by touchpoint then by the
        declared outcome order.

    Raises:
        ValueError: if two five-segment results reduce to the same four-segment
            key, which would silently merge two distinct touchpoints.
    """
    by_four_segment: dict[str, AttributionResult] = {}
    for result in results:
        four = to_four_segment(result.touchpoint)
        if four in by_four_segment:
            raise ValueError(
                "colliding output adaptation; "
                f"{by_four_segment[four].touchpoint} and {result.touchpoint} both "
                f"reduce to {four}"
            )
        by_four_segment[four] = result

    rows: list[StandardAttributionRow] = []
    for four in sorted(by_four_segment):
        result = by_four_segment[four]
        for outcome in SUPPORTED_OUTCOMES:
            share_field, value_field = OUTCOME_FIELDS[outcome]
            total = float(dataset.outcome_totals[outcome])
            rows.append(
                StandardAttributionRow(
                    model_id=model.model_id,
                    model_version=model.model_version,
                    report_start_date=dataset.scope.report_start_date,
                    report_end_date=dataset.scope.report_end_date,
                    marketplace=dataset.scope.marketplace,
                    touchpoint=four,
                    outcome=outcome,
                    attribution_share=float(getattr(result, share_field)),
                    attributed_value=float(getattr(result, value_field)),
                    valid=True,
                    warnings=(ZERO_OUTCOME_WARNING,) if total == 0 else (),
                )
            )
    return rows


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
