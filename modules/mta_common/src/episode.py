"""CampaignEpisode: one campaign's decision-time and observed-after-treatment
fields, composed for a future response model or optimizer to consume.

Classifies every field it carries into exactly one of two groups so a reader
does not have to infer, per field, whether it was knowable before budget was
committed:

- decision-time-available: ``campaign``, ``budget_constraints``,
  ``reporting_scope`` — known before treatment.
- observed-after-treatment: ``budget_observation``, ``delivery_observations``,
  ``outcome_observations``, ``attribution_evidence`` — known only from normal
  reporting once the campaign has run.

``CampaignEpisode`` has no field that can hold evaluation-only simulator
ground truth. That type, ``EvaluationGroundTruth``, is defined in the
separate ``evaluation_only.py`` module and only ``EvaluationEpisode`` there
may compose it with a ``CampaignEpisode``. This mirrors the isolation
``docs/en/market-simulation/index.md`` already documents for
`simulation_ground_truth`: `MtaSimDataset` has no field that can hold it, and
the loaders reject a header carrying it. See
``evaluation_only.assert_no_ground_truth_fields`` for the automated proof.

Data flow: a model-facing consumer (a future response model, a future
optimizer) is typed to accept ``CampaignEpisode``, never
``EvaluationEpisode``, so it cannot read ground truth even by accident.
Evaluation code that legitimately needs both reads ``EvaluationEpisode`` and
extracts ``.episode`` when it needs to call model-facing code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .attribution_evidence import AttributionEvidence
from .budget import BudgetConstraints, BudgetObservation
from .campaign import Campaign
from .delivery import DeliveryObservation
from .outcome import OutcomeObservation


@dataclass(frozen=True)
class CampaignEpisode:
    """One campaign's model-facing record: decision-time plus observed.

    Also referred to as an optimization observation: one row a future
    strategy optimizer's evaluation loop would consume. Holds no field that
    can carry evaluation-only ground truth.

    Attributes:
        campaign: Decision-time-available campaign identity.
        budget_constraints: Decision-time-available budget bounds and usage
            policy.
        budget_observation: Observed-after-treatment configured budget and
            actual spend.
        delivery_observations: Observed-after-treatment delivery metrics, one
            entry per touchpoint.
        outcome_observations: Observed-after-treatment outcomes, one entry
            per touchpoint.
        attribution_evidence: Observed-after-treatment historical attribution
            evidence, one entry per touchpoint and outcome.
    """

    campaign: Campaign
    budget_constraints: BudgetConstraints
    budget_observation: BudgetObservation | None = None
    delivery_observations: tuple[DeliveryObservation, ...] = field(default_factory=tuple)
    outcome_observations: tuple[OutcomeObservation, ...] = field(default_factory=tuple)
    attribution_evidence: tuple[AttributionEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.campaign.campaign_id != self.budget_constraints.campaign_id:
            raise ValueError(
                "budget_constraints.campaign_id must match campaign.campaign_id"
            )
        if (
            self.budget_observation is not None
            and self.budget_observation.campaign_id != self.campaign.campaign_id
        ):
            raise ValueError(
                "budget_observation.campaign_id must match campaign.campaign_id"
            )
        currency = self.campaign.reporting_scope.currency
        other_scopes = [
            observation.reporting_scope for observation in self.delivery_observations
        ] + [
            observation.reporting_scope for observation in self.outcome_observations
        ] + [
            evidence.reporting_scope for evidence in self.attribution_evidence
        ]
        if self.budget_observation is not None:
            other_scopes.append(self.budget_observation.reporting_scope)
        mismatched = {scope.currency for scope in other_scopes} - {currency}
        if mismatched:
            raise ValueError(
                "all reporting scopes within a CampaignEpisode must share "
                f"campaign.reporting_scope.currency ({currency!r}); found "
                f"{sorted(mismatched)}"
            )
