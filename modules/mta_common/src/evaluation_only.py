"""Evaluation-only simulator ground truth, isolated from model-facing types.

This is the only module in the canonical data model allowed to define a
field carrying simulator-known ground truth (true incremental effect, true
counterfactual). ``CampaignEpisode`` in ``episode.py`` has no such field by
construction; nothing here modifies that class or subclasses it, so a
function typed to accept ``CampaignEpisode`` has no attribute path into
ground truth even if an ``EvaluationEpisode`` is passed by mistake, since
``EvaluationEpisode`` composes a ``CampaignEpisode`` rather than extending
it.

Precedent: ``docs/en/market-simulation/index.md`` documents that
`simulation_ground_truth` is evaluation-only and that both existing loaders
reject a header carrying it. ``assert_no_ground_truth_fields`` gives that
same guarantee an automated, reusable check for the canonical model,
following the recursive-key-absence pattern
``hierarchy_validator._all_keys``/``FORBIDDEN_OUTPUT_FIELDS`` already uses
for `sku_id`/`sku_ids`.

Data flow: only a simulator-backed evaluation harness constructs
``EvaluationGroundTruth``/``EvaluationEpisode``. Every other consumer of
campaign data uses ``CampaignEpisode`` directly.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from .episode import CampaignEpisode

# Field names that, if they ever appeared on a model-facing dataclass, would
# constitute a ground-truth leak. Kept in one place so the isolation test and
# any future model-facing class can check against the same list.
FORBIDDEN_MODEL_FACING_FIELDS = frozenset(
    {
        "true_incremental_units",
        "true_incremental_revenue",
        "true_causal_effect",
        "simulator_ground_truth_id",
    }
)


@dataclass(frozen=True)
class EvaluationGroundTruth:
    """Simulator-known truth for one campaign episode. Evaluation-only.

    Attributes:
        true_incremental_units: The simulator's true causal effect on units,
            known only because the simulator generated the data.
        true_incremental_revenue: The simulator's true causal effect on
            revenue.
        true_causal_effect: Free-text description of the simulator mechanism
            that produced the above, for evaluation reporting.
        simulator_ground_truth_id: Identifier tying this record back to the
            simulator's own ground-truth table.
    """

    true_incremental_units: float
    true_incremental_revenue: float
    true_causal_effect: str
    simulator_ground_truth_id: str


@dataclass(frozen=True)
class EvaluationEpisode:
    """A CampaignEpisode paired with its simulator ground truth.

    Composition, not inheritance: this class holds a ``CampaignEpisode`` as a
    field rather than subclassing it, so passing an ``EvaluationEpisode``
    where a ``CampaignEpisode`` is expected is a type error, not a silent
    structural match.

    Attributes:
        episode: The model-facing campaign episode.
        ground_truth: The simulator's ground truth for that episode.
    """

    episode: CampaignEpisode
    ground_truth: EvaluationGroundTruth


def assert_no_ground_truth_fields(model_facing_type: type) -> None:
    """Verify a dataclass carries no field named for evaluation-only truth.

    Args:
        model_facing_type: A dataclass type intended to be model-facing.

    Raises:
        ValueError: if any of the type's field names appear in
            ``FORBIDDEN_MODEL_FACING_FIELDS``.
    """
    field_names = {f.name for f in dataclasses.fields(model_facing_type)}
    leaked = field_names & FORBIDDEN_MODEL_FACING_FIELDS
    if leaked:
        raise ValueError(
            f"{model_facing_type.__name__} carries evaluation-only field(s): "
            f"{sorted(leaked)}"
        )
