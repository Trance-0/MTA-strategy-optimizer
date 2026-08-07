"""The public interface every standardized attribution model implements.

This file defines the contract and nothing that computes attribution. A caller
holds a ``MtaAttributionModel`` and never needs to know whether the object
behind it wraps a closed-form estimator or trains a network.

Contents:

- ``ModelCapabilities`` — machine-readable declaration of what a model supports,
  so callers can branch on capability instead of on model identity.
- ``MtaAttributionModel`` — the ``fit`` / ``attribute`` / ``save`` / ``load``
  contract, plus the fitted-scope guard that stops a model from attributing a
  report it was not prepared for.
- ``_JsonPersistedModel`` — persistence for models whose only state is identity
  and fitted scope.
- ``standard_rows_from_attribution_results`` — the output half of the key
  adaptation boundary, converting five-segment estimator results back to
  MTA-SIM's four-segment grain.

Data flow: ``MtaSimDataset`` -> ``fit`` -> ``attribute`` -> list of
``StandardAttributionRow`` -> ``output_contract.validate_standard_output``.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, Sequence

from attribution_src_path import ensure_attribution_src_on_path
from dataloader import MtaSimDataset
from output_contract import (
    SUPPORTED_OUTCOMES,
    ZERO_OUTCOME_WARNING,
    StandardAttributionRow,
)
from touchpoint_adapter import to_four_segment

ensure_attribution_src_on_path()

from attribution_contract import AttributionResult  # noqa: E402
from attribution_model_comparison import OUTCOME_FIELDS  # noqa: E402


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

