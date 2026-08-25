"""Read the committed strategy artifacts into the one comparable decision type.

These are adapters in the same sense as ``modules/mta_common/src/legacy_adapters.py``:
they know the artifacts' own field names so that nothing else has to. The
recommendation module keeps writing its native shapes without knowing an
evaluation layer exists, and this module adapts to them. Reversing that
direction would make every strategy change a change to the evaluator too.

Three things the artifacts do not record about themselves have to be supplied
by the caller, and each is a keyword rather than a guess:

- ``initial_budget_recommendation.json`` carries no currency. It is required
  with no default, because mislabelling currency is exactly what
  ``ReportingScope`` exists to prevent and no conservative default exists.
  ``script/evaluate_strategies.py`` reads it from ``strategy_request.json``.
- ``campaign_strategy.json`` carries no advertiser. It defaults to the
  ``UNRECORDED_ADVERTISER`` sentinel, which is visibly not an identifier, so a
  reader cannot mistake it for one.
- Neither records whether its source was simulated. ``is_synthetic`` defaults
  to ``True``: claiming synthetic when the source was real understates
  confidence in a result, while the reverse overstates it, and only the second
  mistake misleads.

A refusal is never projected as an allocation of nothing. An optimizer run
whose ``is_optimized`` is false raises :class:`StrategyProjectionError` naming
its own infeasibility reasons, so a plan that declined to allocate cannot be
scored as a plan that allocated zero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from modules.mta_common.src.enums import Provider, RecordClassification
from modules.mta_common.src.lineage import DataLineage
from modules.mta_common.src.reporting_scope import ReportingScope

from .strategy_output import (
    ALLOCATION_TYPE_INITIAL_SEED,
    ALLOCATION_TYPE_OPTIMIZED,
    AdGroupBudgetSlot,
    CampaignBudgetDecision,
    StrategyOutput,
)

#: Stable identifiers for the two strategies this repository produces. Used as
#: `StrategyOutput.strategy_id` and as the key an evaluation report is filed
#: under, so a stored result names the strategy rather than the file.
STRATEGY_ID_DETERMINISTIC_SEED = "deterministic_budget_seed"
STRATEGY_ID_CAMPAIGN_RESPONSE_OPTIMIZER = "campaign_response_optimizer"

#: The two artifact file names, read from one directory.
INITIAL_BUDGET_ARTIFACT = "initial_budget_recommendation.json"
CAMPAIGN_STRATEGY_ARTIFACT = "campaign_strategy.json"

#: Stands in for an advertiser `campaign_strategy.json` does not record.
#: Deliberately not an identifier shape, so it cannot be mistaken for one.
UNRECORDED_ADVERTISER = "UNSPECIFIED"

#: Version recorded when the optimizer artifact names no response model
#: version. Not a real version, and labelled so.
UNVERSIONED = "UNVERSIONED"

#: This module's own version, recorded as the lineage transformation version
#: so a stored evaluation says which reader produced its inputs.
PROJECTION_VERSION = "STRATEGY_PROJECTION_V1"


class StrategyProjectionError(ValueError):
    """An artifact that cannot honestly be projected, with the reason."""


@dataclass(frozen=True)
class ProjectionAttempt:
    """One artifact's projection, whether it succeeded or not.

    Returned rather than raised by :func:`load_strategy_outputs` so a caller
    can report a skipped strategy with its reason instead of losing it.

    Attributes:
        artifact: The artifact file name that was read.
        strategy_id: Which strategy that artifact holds.
        output: The projected decision, or ``None`` when projection failed.
        error: Why projection failed, or ``None`` when it succeeded.
    """

    artifact: str
    strategy_id: str
    output: StrategyOutput | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether this artifact produced a decision."""

        return self.output is not None


def _number(value: Any) -> float | None:
    """Coerce a JSON number, distinguishing absent from zero."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    """Coerce a JSON string, treating an empty one as absent."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _provider(value: Any) -> Provider | None:
    """Coerce a provider name, leaving an unknown one unset rather than guessed."""

    name = _text(value)
    if name is None:
        return None
    try:
        return Provider(name)
    except ValueError:
        return None


def strategy_output_from_initial_budget(
    document: Mapping[str, Any], *, currency: str, is_synthetic: bool = True
) -> StrategyOutput:
    """Project ``initial_budget_recommendation.json`` into a StrategyOutput.

    Args:
        document: The parsed artifact.
        currency: The currency its monetary fields are denominated in. The
            artifact does not record one, and this reader will not guess.
        is_synthetic: Whether the underlying source was simulated.

    Returns:
        StrategyOutput: The deterministic seed's decision, keeping its Ad
        Group slots — the only place in this repository where the
        within-Campaign conservation constraints are non-trivial.

    Raises:
        StrategyProjectionError: If the document is empty, carries no
            Campaign, or records no reporting window.
    """

    if not document:
        raise StrategyProjectionError(
            f"{INITIAL_BUDGET_ARTIFACT} is empty; the initializer has not run"
        )
    campaigns = document.get("campaigns") or []
    if not campaigns:
        raise StrategyProjectionError(
            f"{INITIAL_BUDGET_ARTIFACT} allocates to no Campaign"
        )

    source = document.get("mta_source_snapshot") or {}
    start = _text(source.get("report_start_date"))
    end = _text(source.get("report_end_date"))
    if start is None or end is None:
        raise StrategyProjectionError(
            f"{INITIAL_BUDGET_ARTIFACT} records no reporting window in "
            "mta_source_snapshot, so its decision cannot be scoped"
        )

    scope = ReportingScope(
        marketplace=_text(source.get("marketplace")) or UNRECORDED_ADVERTISER,
        advertiser_id=_text(source.get("advertiser_id")) or UNRECORDED_ADVERTISER,
        currency=currency,
        report_start_date=start,
        report_end_date=end,
        campaign_group_id=_text(document.get("campaign_group_id")),
    )

    decisions = tuple(
        CampaignBudgetDecision(
            campaign_id=str(row["campaign_id"]),
            budget_share=_number(row.get("budget_seed_share")) or 0.0,
            budget=_number(row.get("campaign_budget_seed")),
            execution_status=_text(row.get("execution_status")) or "EXECUTABLE",
            decision_basis=_text(
                (document.get("budget_derivation") or {}).get("formula_version")
            ),
            ad_groups=tuple(
                AdGroupBudgetSlot(
                    ad_group_slot_id=str(slot["ad_group_slot_id"]),
                    budget_share=_number(slot.get("budget_seed_share")) or 0.0,
                    allocation_basis=_text(slot.get("allocation_basis")),
                    budget=_number(slot.get("initial_daily_budget")),
                )
                for slot in (row.get("recommended_ad_groups") or [])
            ),
        )
        for row in campaigns
    )

    derivation = document.get("budget_derivation") or {}
    return StrategyOutput(
        strategy_id=STRATEGY_ID_DETERMINISTIC_SEED,
        strategy_version=_text(document.get("schema_version")) or UNVERSIONED,
        allocation_type=ALLOCATION_TYPE_INITIAL_SEED,
        scope=scope,
        campaigns=decisions,
        total_budget=_number(document.get("budget_seed_total")),
        # The seed is proportional to Multi-Touch Attribution evidence by
        # construction, which is legitimate for an Initial Strategy and
        # recorded here so a report can state which side of that line it
        # stood on.
        uses_attribution=True,
        lineage=DataLineage(
            source_system="MTA_AMC_CAMPAIGN_BRIDGE",
            source_reference=INITIAL_BUDGET_ARTIFACT,
            schema_version=_text(document.get("schema_version")) or UNVERSIONED,
            transformation_version=(
                _text(derivation.get("formula_version")) or PROJECTION_VERSION
            ),
            classification=RecordClassification.DECISION_TIME,
            is_synthetic=is_synthetic,
            report_period_start=start,
            report_period_end=end,
        ),
        warnings=tuple(str(item) for item in (document.get("warnings") or [])),
    )


def strategy_output_from_campaign_strategy(
    document: Mapping[str, Any],
    *,
    advertiser_id: str = UNRECORDED_ADVERTISER,
    is_synthetic: bool = True,
) -> StrategyOutput:
    """Project ``campaign_strategy.json``'s optimized plan into a StrategyOutput.

    Args:
        document: The parsed artifact.
        advertiser_id: The advertiser the plan was computed for. The artifact
            does not record one; the default is a visible sentinel.
        is_synthetic: Whether the underlying source was simulated.

    Returns:
        StrategyOutput: The optimized decision. Shares are derived as
        ``optimized_budget / allocated_budget``, so a plan that deliberately
        underspends still has shares summing to one; the underspend is
        recorded by the group-budget constraint, not by the share constraint.

    Raises:
        StrategyProjectionError: If the document is empty, if the plan is not
            optimized (naming its infeasibility reasons), if it allocates to
            no Campaign, or if it carries no response observation from which
            to recover the marketplace and window.
    """

    if not document:
        raise StrategyProjectionError(
            f"{CAMPAIGN_STRATEGY_ARTIFACT} is empty; the optimizer has not run"
        )
    plan = document.get("optimized_strategy") or {}
    if not plan:
        raise StrategyProjectionError(
            f"{CAMPAIGN_STRATEGY_ARTIFACT} carries no optimized_strategy"
        )
    if not plan.get("is_optimized"):
        reasons = [str(item) for item in (plan.get("infeasibility_reasons") or [])]
        raise StrategyProjectionError(
            "the optimizer refused to allocate"
            + (f": {'; '.join(reasons)}" if reasons else " and gave no reason")
            + "; a refusal is not an allocation of zero and is not scored"
        )

    allocations = plan.get("allocations") or []
    if not allocations:
        raise StrategyProjectionError(
            f"{CAMPAIGN_STRATEGY_ARTIFACT} allocates to no Campaign"
        )

    observations = document.get("response_observations") or []
    if not observations:
        raise StrategyProjectionError(
            f"{CAMPAIGN_STRATEGY_ARTIFACT} carries no response_observations, so "
            "the marketplace and reporting window of its plan are unknown"
        )

    dates = sorted(
        date for date in (_text(row.get("report_date")) for row in observations) if date
    )
    if not dates:
        raise StrategyProjectionError(
            f"{CAMPAIGN_STRATEGY_ARTIFACT} response_observations record no dates"
        )

    scope = ReportingScope(
        marketplace=_text(observations[0].get("marketplace")) or UNRECORDED_ADVERTISER,
        advertiser_id=advertiser_id,
        currency=_text(document.get("currency")) or UNRECORDED_ADVERTISER,
        report_start_date=dates[0],
        report_end_date=dates[-1],
    )

    # One Campaign's decision-time context, taken from its observations. The
    # allocation itself records neither, because the optimizer works on
    # response curves rather than on Campaign metadata.
    context: dict[str, dict[str, Any]] = {}
    for row in observations:
        identifier = _text(row.get("campaign_id"))
        if identifier is not None:
            context.setdefault(identifier, dict(row))

    allocated_total = _number(plan.get("allocated_budget")) or 0.0
    decisions = tuple(
        CampaignBudgetDecision(
            campaign_id=str(row["campaign_id"]),
            budget_share=(
                (_number(row.get("optimized_budget")) or 0.0) / allocated_total
                if allocated_total > 0
                else 0.0
            ),
            budget=_number(row.get("optimized_budget")),
            ad_product=_text(
                context.get(str(row.get("campaign_id")), {}).get("ad_product")
            ),
            provider=_provider(
                context.get(str(row.get("campaign_id")), {}).get("provider")
            ),
            # Empty rather than projected. The plan claims
            # NOT_AD_GROUP_OPTIMIZED, and inventing slots from an equal split
            # would present a projection as a decision.
            ad_groups=(),
            decision_basis=_text(plan.get("allocation_basis")),
        )
        for row in allocations
    )

    excluded = [str(item) for item in (plan.get("excluded_campaign_ids") or [])]
    warnings = tuple(f"EXCLUDED_CAMPAIGN:{item}" for item in excluded)

    return StrategyOutput(
        strategy_id=STRATEGY_ID_CAMPAIGN_RESPONSE_OPTIMIZER,
        strategy_version=_text(allocations[0].get("model_version")) or UNVERSIONED,
        allocation_type=ALLOCATION_TYPE_OPTIMIZED,
        scope=scope,
        campaigns=decisions,
        total_budget=_number(plan.get("authorized_budget")),
        # The optimizer fits response curves from observed budget and revenue.
        # Attribution is never one of its inputs.
        uses_attribution=False,
        lineage=DataLineage(
            source_system="CAMPAIGN_RESPONSE_OPTIMIZER",
            source_reference=CAMPAIGN_STRATEGY_ARTIFACT,
            schema_version=_text(allocations[0].get("model_version")) or UNVERSIONED,
            transformation_version=PROJECTION_VERSION,
            classification=RecordClassification.DECISION_TIME,
            is_synthetic=is_synthetic,
            provider=_provider(observations[0].get("provider")),
            report_period_start=dates[0],
            report_period_end=dates[-1],
        ),
        warnings=warnings,
    )


def load_strategy_outputs(
    directory: Path,
    *,
    currency: str | None = None,
    advertiser_id: str = UNRECORDED_ADVERTISER,
    is_synthetic: bool = True,
) -> tuple[ProjectionAttempt, ...]:
    """Project every strategy artifact in one directory.

    Args:
        directory: Where the two artifacts live, normally
            ``modules/mta_strategy_recommendation/outputs/``.
        currency: The currency ``initial_budget_recommendation.json``'s
            monetary fields are denominated in. When ``None``, that artifact
            is recorded as skipped with the reason rather than projected under
            a guessed currency.
        advertiser_id: The advertiser ``campaign_strategy.json`` was computed
            for.
        is_synthetic: Whether the underlying sources were simulated.

    Returns:
        tuple[ProjectionAttempt, ...]: One entry per artifact, in pipeline
        order — the seed first, then the optimized plan — whether or not each
        projected. An absent file is an attempt carrying its own reason, not a
        silent omission.
    """

    attempts: list[ProjectionAttempt] = []

    initial_path = directory / INITIAL_BUDGET_ARTIFACT
    if currency is None:
        attempts.append(
            ProjectionAttempt(
                artifact=INITIAL_BUDGET_ARTIFACT,
                strategy_id=STRATEGY_ID_DETERMINISTIC_SEED,
                error=(
                    f"{INITIAL_BUDGET_ARTIFACT} records no currency and none was "
                    "supplied; supply one from strategy_request.json rather than "
                    "scoring monetary fields under a guessed currency"
                ),
            )
        )
    else:
        attempts.append(
            _attempt(
                INITIAL_BUDGET_ARTIFACT,
                STRATEGY_ID_DETERMINISTIC_SEED,
                initial_path,
                lambda document: strategy_output_from_initial_budget(
                    document, currency=currency, is_synthetic=is_synthetic
                ),
            )
        )

    attempts.append(
        _attempt(
            CAMPAIGN_STRATEGY_ARTIFACT,
            STRATEGY_ID_CAMPAIGN_RESPONSE_OPTIMIZER,
            directory / CAMPAIGN_STRATEGY_ARTIFACT,
            lambda document: strategy_output_from_campaign_strategy(
                document, advertiser_id=advertiser_id, is_synthetic=is_synthetic
            ),
        )
    )
    return tuple(attempts)


def _attempt(
    artifact: str, strategy_id: str, path: Path, project
) -> ProjectionAttempt:
    """Read and project one artifact, recording a failure rather than raising."""

    if not path.is_file():
        return ProjectionAttempt(
            artifact=artifact,
            strategy_id=strategy_id,
            error=f"{path} does not exist; that strategy has not been run",
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return ProjectionAttempt(
            artifact=artifact,
            strategy_id=strategy_id,
            error=f"{path} could not be read: {type(error).__name__}: {error}",
        )
    try:
        return ProjectionAttempt(
            artifact=artifact, strategy_id=strategy_id, output=project(document)
        )
    except (StrategyProjectionError, ValueError, KeyError) as error:
        return ProjectionAttempt(
            artifact=artifact, strategy_id=strategy_id, error=str(error)
        )
