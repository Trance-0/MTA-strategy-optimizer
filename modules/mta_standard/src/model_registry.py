"""The identifier-to-class map for every shipped model.

Kept in its own file so a model implementation can import the interface without
the interface having to import every implementation, which would be circular.

Data flow: a model identifier -> `build_model` -> an unfitted model instance.
Contributors iterate `MODEL_REGISTRY` to compare implementations rather than
importing each estimator directly.
"""

from __future__ import annotations

from modules.mta_attribution.src.attribution_model_interface import MtaAttributionModel
from modules.mta_attribution.src.dnn_attribution_model import DeepNeuralAttributionModel
from modules.mta_attribution.src.markov_standard_attribution_model import (
    MarkovRemovalEffectModel,
)
from modules.mta_attribution.src.shapley_standard_attribution_model import (
    PathLevelShapleyModel,
)
from modules.mta_attribution.src.uniform_attribution_model import UniformCreditModel


# Registry of the models shipped with the standardized interface. Contributors
# compare implementations by iterating this mapping rather than by importing
# each estimator directly.
#
# The registry lives in its own module so that a model implementation can import
# the interface without the interface having to import every implementation.
MODEL_REGISTRY: dict[str, type[MtaAttributionModel]] = {
    model_class.model_id: model_class
    for model_class in (
        MarkovRemovalEffectModel,
        PathLevelShapleyModel,
        UniformCreditModel,
        DeepNeuralAttributionModel,
    )
}


def build_model(model_id: str) -> MtaAttributionModel:
    """Instantiate a registered model by identifier.

    Args:
        model_id: A key of :data:`MODEL_REGISTRY`.

    Returns:
        MtaAttributionModel: A new, unfitted model instance built with its
        default configuration.

    Raises:
        KeyError: if the identifier is not registered.
    """
    try:
        return MODEL_REGISTRY[model_id]()
    except KeyError as exc:
        raise KeyError(
            f"unknown model_id {model_id!r}; registered: {sorted(MODEL_REGISTRY)}"
        ) from exc
