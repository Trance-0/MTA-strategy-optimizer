"""Deep neural credit model, and the only model that generalizes.

Markov and Shapley score a touchpoint by its identity, so neither can say
anything about a touchpoint with no path history. This model scores the four
contract segments instead, which is what makes prediction for an unlaunched
campaign possible at all.

Architecture: a listwise scorer. It emits one logit per outcome for every
touchpoint in a report, then applies a softmax across the touchpoint set, once
per outcome. Because a softmax always sums to one, share conservation holds by
construction rather than by a post-hoc rescale.

Data flow:
    MtaSimDataset
      -> `build_touchpoint_features` : segment values + path-derived features
      -> `_FeatureEncoder`           : fixed-width vector, unknown bucket at 0
      -> `_MultiLayerPerceptron`     : tanh hidden layers, linear logits
      -> softmax per outcome         : attribution shares
      -> `StandardAttributionRow`

Targets are path-level Shapley shares computed from the observed path report, so
the model is supervised by data a contributor actually has and
`simulation_ground_truth` stays reserved for evaluation.

Implemented with the standard library only, matching the repository's
zero-dependency constraint. It is a genuine network trained by backpropagation,
sized for report-scale touchpoint counts rather than for large-scale training.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, Mapping, Sequence

from modules.mta_standard.src.dataloader import MtaSimDataset
from modules.mta_standard.src.output_contract import (
    SUPPORTED_OUTCOMES,
    ZERO_OUTCOME_WARNING,
    StandardAttributionRow,
)
from modules.mta_standard.src.touchpoint_adapter import (
    canonicalize_four_segment_key,
    to_four_segment,
)

from .attribution_contract import NULL, safe_float
from .attribution_model_interface import ModelCapabilities, MtaAttributionModel
from .attribution_model_comparison import OUTCOME_FIELDS
from .shapley_attribution_model import run_shapley_attribution


SEGMENT_NAMES: tuple[str, ...] = ("ad_product", "format", "placement", "creative")
NUMERIC_FEATURE_NAMES: tuple[str, ...] = (
    "appearance_ratio",
    "mean_relative_position",
    "mean_path_length_ratio",
    "user_share",
)
UNKNOWN_INDEX = 0

DEFAULT_HIDDEN_SIZES: tuple[int, ...] = (16, 8)
DEFAULT_EPOCHS = 400
DEFAULT_LEARNING_RATE = 0.5
DEFAULT_SEED = 20260803


@dataclass(frozen=True)
class TouchpointFeatures:
    """Model-facing features for one four-segment touchpoint.

    Attributes:
        touchpoint: Canonical four-segment key.
        segments: The four segment values, in contract order.
        numeric: Path-derived numeric features, in
            :data:`NUMERIC_FEATURE_NAMES` order.
    """

    touchpoint: str
    segments: tuple[str, ...]
    numeric: tuple[float, ...]


def build_touchpoint_features(
    dataset: MtaSimDataset,
) -> dict[str, TouchpointFeatures]:
    """Derive per-touchpoint features from the observed path report.

    Every feature comes from the model-facing path rows. Ground truth is not
    reachable from ``dataset``, so no feature can encode the answer.

    Args:
        dataset: The model-facing dataset.

    Returns:
        dict[str, TouchpointFeatures]: Features keyed by four-segment touchpoint.

    Invariants:
        A single-touchpoint path reports a relative position of 0.5 so that a
        solo touchpoint is treated as neither first nor last.
    """
    appearances: dict[str, int] = {}
    positions: dict[str, list[float]] = {}
    lengths: dict[str, list[int]] = {}
    users: dict[str, float] = {}

    total_paths = 0
    total_users = 0.0
    max_length = 1
    for row in dataset.path_rows:
        touchpoints = [
            to_four_segment(part.strip())
            for part in str(row.get("path", "")).split(">")
            if part.strip() and part.strip() != NULL
        ]
        if not touchpoints:
            continue
        total_paths += 1
        row_users = safe_float(row.get("users"))
        total_users += row_users
        length = len(touchpoints)
        max_length = max(max_length, length)
        for index, touchpoint in enumerate(touchpoints):
            appearances[touchpoint] = appearances.get(touchpoint, 0) + 1
            relative = 0.5 if length == 1 else index / (length - 1)
            positions.setdefault(touchpoint, []).append(relative)
            lengths.setdefault(touchpoint, []).append(length)
            users[touchpoint] = users.get(touchpoint, 0.0) + row_users

    features: dict[str, TouchpointFeatures] = {}
    for touchpoint in dataset.touchpoints:
        seen = appearances.get(touchpoint, 0)
        touchpoint_positions = positions.get(touchpoint, [0.5])
        touchpoint_lengths = lengths.get(touchpoint, [1])
        features[touchpoint] = TouchpointFeatures(
            touchpoint=touchpoint,
            segments=tuple(touchpoint.split(":")),
            numeric=(
                seen / total_paths if total_paths else 0.0,
                sum(touchpoint_positions) / len(touchpoint_positions),
                (sum(touchpoint_lengths) / len(touchpoint_lengths)) / max_length,
                users.get(touchpoint, 0.0) / total_users if total_users else 0.0,
            ),
        )
    return features


class _FeatureEncoder:
    """Turns segment values and numeric features into a fixed-width vector.

    Each of the four contract segments gets its own vocabulary with index 0
    reserved for an unseen value. A touchpoint from a campaign that did not
    exist during training therefore still encodes, which is what makes new
    campaign prediction possible at all.
    """

    def __init__(
        self,
        vocabularies: Sequence[Mapping[str, int]],
        numeric_means: Sequence[float],
    ) -> None:
        self.vocabularies = [dict(vocabulary) for vocabulary in vocabularies]
        self.numeric_means = tuple(numeric_means)

    @classmethod
    def fit(cls, features: Mapping[str, TouchpointFeatures]) -> "_FeatureEncoder":
        """Build vocabularies and numeric fallbacks from training features.

        Args:
            features: Training features keyed by touchpoint.

        Returns:
            _FeatureEncoder: A deterministic encoder; vocabularies are sorted.
        """
        vocabularies: list[dict[str, int]] = []
        for position in range(len(SEGMENT_NAMES)):
            values = sorted({item.segments[position] for item in features.values()})
            vocabularies.append(
                {value: index for index, value in enumerate(values, start=1)}
            )
        count = len(features) or 1
        means = [
            sum(item.numeric[index] for item in features.values()) / count
            for index in range(len(NUMERIC_FEATURE_NAMES))
        ]
        return cls(vocabularies, means)

    @property
    def width(self) -> int:
        """Return the encoded vector width.

        Returns:
            int: One-hot width across all segments plus the numeric features.
        """
        return sum(len(vocabulary) + 1 for vocabulary in self.vocabularies) + len(
            NUMERIC_FEATURE_NAMES
        )

    def encode(
        self, segments: Sequence[str], numeric: Sequence[float] | None = None
    ) -> list[float]:
        """Encode one touchpoint.

        Args:
            segments: The four segment values.
            numeric: Path-derived features; the training means are substituted
                when a touchpoint has no observed path history.

        Returns:
            list[float]: The encoded feature vector.

        Raises:
            ValueError: if the segment count is not four.
        """
        if len(segments) != len(SEGMENT_NAMES):
            raise ValueError(
                f"expected {len(SEGMENT_NAMES)} segments; got {len(segments)}"
            )
        vector: list[float] = []
        for position, vocabulary in enumerate(self.vocabularies):
            block = [0.0] * (len(vocabulary) + 1)
            block[vocabulary.get(segments[position], UNKNOWN_INDEX)] = 1.0
            vector.extend(block)
        vector.extend(self.numeric_means if numeric is None else numeric)
        return vector

    def to_payload(self) -> dict:
        """Render the encoder for persistence.

        Returns:
            dict: A JSON-serialisable representation.
        """
        return {
            "vocabularies": self.vocabularies,
            "numeric_means": list(self.numeric_means),
        }

    @classmethod
    def from_payload(cls, payload: Mapping) -> "_FeatureEncoder":
        """Restore an encoder written by :meth:`to_payload`.

        Args:
            payload: The persisted mapping.

        Returns:
            _FeatureEncoder: The restored encoder.
        """
        return cls(payload["vocabularies"], payload["numeric_means"])


class _MultiLayerPerceptron:
    """A dense feed-forward network with tanh hidden layers and linear outputs.

    Weights are initialised with Glorot bounds from a seeded generator and the
    training loop is a fixed number of full-batch steps, so two runs on the same
    dataset produce bit-identical parameters.
    """

    def __init__(
        self,
        layer_sizes: Sequence[int],
        weights: Sequence[Sequence[Sequence[float]]] | None = None,
        biases: Sequence[Sequence[float]] | None = None,
        *,
        seed: int = DEFAULT_SEED,
    ) -> None:
        self.layer_sizes = tuple(layer_sizes)
        if weights is not None and biases is not None:
            self.weights = [[list(row) for row in layer] for layer in weights]
            self.biases = [list(layer) for layer in biases]
            return

        generator = random.Random(seed)
        self.weights = []
        self.biases = []
        for fan_in, fan_out in zip(self.layer_sizes, self.layer_sizes[1:]):
            # Glorot uniform keeps activation variance stable across depth.
            limit = math.sqrt(6.0 / (fan_in + fan_out))
            self.weights.append(
                [
                    [generator.uniform(-limit, limit) for _ in range(fan_in)]
                    for _ in range(fan_out)
                ]
            )
            self.biases.append([0.0] * fan_out)

    def forward(self, vector: Sequence[float]) -> list[list[float]]:
        """Run one forward pass, keeping every activation for backpropagation.

        Args:
            vector: One encoded touchpoint.

        Returns:
            list[list[float]]: Activations per layer, input first, logits last.
        """
        activations = [list(vector)]
        last = len(self.weights) - 1
        for index, (layer_weights, layer_biases) in enumerate(
            zip(self.weights, self.biases)
        ):
            current = activations[-1]
            output = [
                bias + math.fsum(weight * value for weight, value in zip(row, current))
                for row, bias in zip(layer_weights, layer_biases)
            ]
            # Hidden layers squash; the output layer stays linear so its values
            # can be read as softmax logits.
            activations.append(output if index == last else [math.tanh(v) for v in output])
        return activations

    def logits(self, vector: Sequence[float]) -> list[float]:
        """Return only the output layer for one encoded touchpoint.

        Args:
            vector: One encoded touchpoint.

        Returns:
            list[float]: One logit per outcome.
        """
        return self.forward(vector)[-1]

    def apply_gradients(
        self,
        activations_batch: Sequence[Sequence[Sequence[float]]],
        output_gradients: Sequence[Sequence[float]],
        learning_rate: float,
    ) -> None:
        """Backpropagate a batch and update parameters in place.

        Args:
            activations_batch: Forward activations for each sample.
            output_gradients: dLoss/dLogit for each sample.
            learning_rate: Step size applied to the averaged gradient.

        Invariants:
            Samples are accumulated before the update, so the step does not
            depend on sample order.
        """
        weight_gradients = [
            [[0.0] * len(row) for row in layer] for layer in self.weights
        ]
        bias_gradients = [[0.0] * len(layer) for layer in self.biases]

        for activations, output_gradient in zip(activations_batch, output_gradients):
            delta = list(output_gradient)
            for layer in range(len(self.weights) - 1, -1, -1):
                inputs = activations[layer]
                for unit, unit_delta in enumerate(delta):
                    bias_gradients[layer][unit] += unit_delta
                    row = weight_gradients[layer][unit]
                    for index, value in enumerate(inputs):
                        row[index] += unit_delta * value
                if layer == 0:
                    break
                # tanh'(x) = 1 - tanh(x)^2, and `inputs` already holds tanh(x).
                previous = []
                for index, activation in enumerate(inputs):
                    total = math.fsum(
                        self.weights[layer][unit][index] * delta[unit]
                        for unit in range(len(delta))
                    )
                    previous.append(total * (1.0 - activation * activation))
                delta = previous

        scale = learning_rate / max(len(activations_batch), 1)
        for layer, (layer_weights, layer_biases) in enumerate(
            zip(self.weights, self.biases)
        ):
            for unit in range(len(layer_weights)):
                layer_biases[unit] -= scale * bias_gradients[layer][unit]
                row = layer_weights[unit]
                gradient_row = weight_gradients[layer][unit]
                for index in range(len(row)):
                    row[index] -= scale * gradient_row[index]


def _softmax(values: Sequence[float]) -> list[float]:
    """Return a numerically stable softmax over a touchpoint set.

    Args:
        values: Logits, one per touchpoint.

    Returns:
        list[float]: Probabilities summing to 1.0; an empty input returns [].
    """
    if not values:
        return []
    largest = max(values)
    exponentials = [math.exp(value - largest) for value in values]
    total = math.fsum(exponentials)
    return [value / total for value in exponentials]


class DeepNeuralAttributionModel(MtaAttributionModel):
    """A deep model that learns touchpoint credit from segment structure.

    The network is a listwise ranker: it scores every touchpoint in a report and
    normalises those scores with a softmax across the touchpoint set, once per
    outcome. Because a softmax always sums to one, share conservation holds by
    construction rather than by a post-hoc rescale.

    Training targets are path-level Shapley shares computed from the observed
    path report. That keeps the model supervised by data a contributor actually
    has, and leaves ``simulation_ground_truth`` for evaluation only.

    Unlike the two wrapped estimators, this model generalises beyond the
    touchpoints it was trained on: it consumes the four contract segments rather
    than a touchpoint identity, so a campaign that has no historical path can
    still be scored through :meth:`predict_new_campaign`.
    """

    model_id: ClassVar[str] = "dnn_credit"
    model_version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[ModelCapabilities] = ModelCapabilities(
        requires_fit=True,
        supports_persistence=True,
        deterministic=True,
    )

    def __init__(
        self,
        *,
        hidden_sizes: Sequence[int] = DEFAULT_HIDDEN_SIZES,
        epochs: int = DEFAULT_EPOCHS,
        learning_rate: float = DEFAULT_LEARNING_RATE,
        seed: int = DEFAULT_SEED,
    ) -> None:
        """Configure the network.

        Args:
            hidden_sizes: Widths of the tanh hidden layers.
            epochs: Number of full-batch gradient steps.
            learning_rate: Step size for plain gradient descent.
            seed: Seed for weight initialisation.

        Raises:
            ValueError: if any hyperparameter is non-positive.
        """
        super().__init__()
        if epochs <= 0 or learning_rate <= 0 or not hidden_sizes:
            raise ValueError(
                "hidden_sizes must be non-empty and epochs/learning_rate positive"
            )
        if any(size <= 0 for size in hidden_sizes):
            raise ValueError("every hidden layer must have at least one unit")
        self.hidden_sizes = tuple(hidden_sizes)
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.seed = seed
        self._encoder: _FeatureEncoder | None = None
        self._network: _MultiLayerPerceptron | None = None
        self._trained_outcomes: tuple[str, ...] = ()

    def _shapley_targets(self, dataset: MtaSimDataset) -> dict[str, dict[str, float]]:
        """Compute per-outcome training targets from observed paths.

        Args:
            dataset: The model-facing dataset.

        Returns:
            dict: ``outcome -> {touchpoint: target share}``. An outcome whose
            observed total is zero is omitted, since it has no distribution to
            learn.
        """
        targets: dict[str, dict[str, float]] = {}
        results = run_shapley_attribution(list(dataset.path_rows))
        for outcome in SUPPORTED_OUTCOMES:
            if dataset.outcome_totals[outcome] == 0:
                continue
            share_field, _ = OUTCOME_FIELDS[outcome]
            targets[outcome] = {
                to_four_segment(result.touchpoint): float(
                    getattr(result, share_field)
                )
                for result in results
            }
        return targets

    def fit(self, dataset: MtaSimDataset) -> "DeepNeuralAttributionModel":
        """Train the network on the dataset's observed credit distribution.

        Args:
            dataset: The model-facing dataset.

        Returns:
            DeepNeuralAttributionModel: ``self``.

        Raises:
            ValueError: if the dataset has no touchpoint.

        Invariants:
            Training is full-batch, fixed-length, and seeded, so fitting the
            same dataset twice yields identical parameters.
        """
        super().fit(dataset)
        touchpoints = sorted(dataset.touchpoints)
        if not touchpoints:
            raise ValueError("dataset contains no touchpoint to train on")

        features = build_touchpoint_features(dataset)
        self._encoder = _FeatureEncoder.fit(features)
        encoded = [
            self._encoder.encode(features[key].segments, features[key].numeric)
            for key in touchpoints
        ]
        targets = self._shapley_targets(dataset)
        self._trained_outcomes = tuple(
            outcome for outcome in SUPPORTED_OUTCOMES if outcome in targets
        )
        self._network = _MultiLayerPerceptron(
            (self._encoder.width, *self.hidden_sizes, len(SUPPORTED_OUTCOMES)),
            seed=self.seed,
        )

        if not self._trained_outcomes:
            # Every outcome is zero, so there is no distribution to learn and
            # the initial weights are left untouched.
            return self

        for _ in range(self.epochs):
            activations_batch = [self._network.forward(vector) for vector in encoded]
            logits = [activations[-1] for activations in activations_batch]
            gradients = [[0.0] * len(SUPPORTED_OUTCOMES) for _ in touchpoints]
            for position, outcome in enumerate(SUPPORTED_OUTCOMES):
                if outcome not in targets:
                    continue
                predicted = _softmax([row[position] for row in logits])
                for index, touchpoint in enumerate(touchpoints):
                    # d(cross entropy)/d(logit) for a softmax over touchpoints.
                    gradients[index][position] = (
                        predicted[index] - targets[outcome].get(touchpoint, 0.0)
                    )
            self._network.apply_gradients(
                activations_batch, gradients, self.learning_rate
            )
        return self

    def _require_trained(self) -> tuple[_FeatureEncoder, _MultiLayerPerceptron]:
        """Return the fitted encoder and network.

        Returns:
            tuple: The encoder and network.

        Raises:
            RuntimeError: if the model has not been fitted.
        """
        if self._encoder is None or self._network is None:
            raise RuntimeError(f"{self.model_id} requires fit() before attribute()")
        return self._encoder, self._network

    def predicted_shares(
        self, dataset: MtaSimDataset
    ) -> dict[str, dict[str, float]]:
        """Predict a share distribution per outcome for a dataset.

        Args:
            dataset: The dataset whose touchpoints are scored.

        Returns:
            dict: ``outcome -> {touchpoint: share}``. An outcome with a zero
            observed total returns zeros rather than a redistributed softmax.

        Raises:
            RuntimeError: if the model has not been fitted.
        """
        encoder, network = self._require_trained()
        touchpoints = sorted(dataset.touchpoints)
        features = build_touchpoint_features(dataset)
        logits = [
            network.logits(
                encoder.encode(features[key].segments, features[key].numeric)
            )
            for key in touchpoints
        ]

        shares: dict[str, dict[str, float]] = {}
        for position, outcome in enumerate(SUPPORTED_OUTCOMES):
            if dataset.outcome_totals[outcome] == 0:
                shares[outcome] = {key: 0.0 for key in touchpoints}
                continue
            predicted = _softmax([row[position] for row in logits])
            shares[outcome] = dict(zip(touchpoints, predicted))
        return shares

    def predict_new_campaign(
        self, touchpoints: Sequence[str]
    ) -> dict[str, dict[str, float]]:
        """Predict credit shares for campaign touchpoints with no path history.

        The network scores the four contract segments, so a touchpoint that
        never appeared in training still receives a prediction: unseen segment
        values fall into the reserved unknown bucket and the path-derived
        numeric features fall back to their training means.

        Args:
            touchpoints: Four-segment keys of the planned campaign.

        Returns:
            dict: ``outcome -> {touchpoint: predicted share}``, each outcome
            normalised across the supplied touchpoints.

        Raises:
            RuntimeError: if the model has not been fitted.
            ValueError: if the sequence is empty or holds a duplicate or
                non-canonical key.

        Invariants:
            The prediction is a relative split of the planned campaign only. It
            is not a forecast of conversions and carries no observed outcome.
        """
        encoder, network = self._require_trained()
        if not touchpoints:
            raise ValueError("predict_new_campaign requires at least one touchpoint")
        canonical = [canonicalize_four_segment_key(key) for key in touchpoints]
        if len(set(canonical)) != len(canonical):
            raise ValueError("predict_new_campaign requires distinct touchpoints")

        ordered = sorted(canonical)
        logits = [
            network.logits(encoder.encode(tuple(key.split(":")))) for key in ordered
        ]
        return {
            outcome: dict(
                zip(ordered, _softmax([row[position] for row in logits]))
            )
            for position, outcome in enumerate(SUPPORTED_OUTCOMES)
        }

    def attribute(self, dataset: MtaSimDataset) -> list[StandardAttributionRow]:
        """Attribute observed outcomes using the learned share distribution.

        Args:
            dataset: The model-facing dataset.

        Returns:
            list[StandardAttributionRow]: Standard four-segment rows.

        Raises:
            RuntimeError: if the model was not fitted on this report scope.

        Invariants:
            The last touchpoint of each outcome absorbs the floating-point
            residual so shares and attributed values conserve exactly.
        """
        self._require_fitted(dataset)
        shares = self.predicted_shares(dataset)

        rows: list[StandardAttributionRow] = []
        for outcome in SUPPORTED_OUTCOMES:
            total = float(dataset.outcome_totals[outcome])
            has_outcome = total != 0
            ordered = sorted(shares[outcome])
            values = [shares[outcome][key] for key in ordered]
            attributed = [share * total for share in values]
            if has_outcome:
                values[-1] = 1.0 - math.fsum(values[:-1])
                attributed[-1] = total - math.fsum(attributed[:-1])
            for key, share, value in zip(ordered, values, attributed):
                rows.append(
                    StandardAttributionRow(
                        model_id=self.model_id,
                        model_version=self.model_version,
                        report_start_date=dataset.scope.report_start_date,
                        report_end_date=dataset.scope.report_end_date,
                        marketplace=dataset.scope.marketplace,
                        touchpoint=key,
                        outcome=outcome,
                        attribution_share=share,
                        attributed_value=value,
                        valid=True,
                        warnings=() if has_outcome else (ZERO_OUTCOME_WARNING,),
                    )
                )
        return sorted(rows, key=lambda row: (row.touchpoint, row.outcome))

    def save(self, path: str | Path) -> Path:
        """Persist hyperparameters, encoder vocabularies, and learned weights.

        Args:
            path: Destination file; parent directories are created.

        Returns:
            Path: The written path.

        Raises:
            RuntimeError: if the model has not been fitted.
        """
        encoder, network = self._require_trained()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                {
                    "model_id": self.model_id,
                    "model_version": self.model_version,
                    "capabilities": asdict(self.capabilities),
                    "fitted_scope": self._fitted_scope,
                    "hyperparameters": {
                        "hidden_sizes": list(self.hidden_sizes),
                        "epochs": self.epochs,
                        "learning_rate": self.learning_rate,
                        "seed": self.seed,
                    },
                    "encoder": encoder.to_payload(),
                    "layer_sizes": list(network.layer_sizes),
                    "weights": network.weights,
                    "biases": network.biases,
                    "trained_outcomes": list(self._trained_outcomes),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "DeepNeuralAttributionModel":
        """Restore a network written by :meth:`save`.

        Args:
            path: Source file.

        Returns:
            DeepNeuralAttributionModel: A fitted model with the stored weights.

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
        hyperparameters = payload["hyperparameters"]
        model = cls(
            hidden_sizes=hyperparameters["hidden_sizes"],
            epochs=hyperparameters["epochs"],
            learning_rate=hyperparameters["learning_rate"],
            seed=hyperparameters["seed"],
        )
        model._fitted_scope = payload.get("fitted_scope")
        model._encoder = _FeatureEncoder.from_payload(payload["encoder"])
        model._network = _MultiLayerPerceptron(
            payload["layer_sizes"], payload["weights"], payload["biases"]
        )
        model._trained_outcomes = tuple(payload.get("trained_outcomes", ()))
        return model
