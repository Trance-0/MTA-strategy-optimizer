"""Controlled vocabularies shared by every canonical data-model class.

``Provider`` identifies which advertising platform a record came from,
independent of the ``ad_product`` marketed on that platform.
``FieldAvailability`` replaces silent none-means-missing collapsing with five
explicit, distinguishable states. ``StrategyObjective`` and
``BudgetUsagePolicy`` are the two independent axes a future strategy
optimizer chooses between; nothing in this module implements the optimizer
itself. ``AssignmentType`` and ``RecordClassification`` support the
evaluation-only isolation implemented in ``episode.py`` and
``evaluation_only.py``.

Data flow: every canonical dataclass in ``modules/mta_common/src/``
references one or more of these enums instead of restating string literals
or collapsing them into a single boolean or sentinel value.
"""

from __future__ import annotations

from enum import StrEnum


class Provider(StrEnum):
    """The advertising platform or data source a record originates from.

    ``GENERIC`` is not a real platform. It exists so ``ProviderCapabilities``
    and the tests that use it can demonstrate a second, differently shaped
    provider profile without this module claiming to adapt a second real
    advertising platform.
    """

    AMAZON_ADS = "AMAZON_ADS"
    GENERIC = "GENERIC"


class FieldAvailability(StrEnum):
    """Why a field on a canonical record does or does not carry a value.

    Attributes:
        AVAILABLE: The field carries a real observed or provided value.
        NOT_APPLICABLE: The concept the field represents does not exist for
            this record, for example ``interaction_type`` on a provider whose
            ad products are not billed per impression or click.
        NOT_PROVIDED: The source system could in principle supply the field,
            but this specific extract, report, or provider integration does
            not include it.
        UNKNOWN: It is not known whether the field applies or what its value
            would be.
        REDACTED: The field was deliberately withheld, for example for
            privacy or contractual reasons.
    """

    AVAILABLE = "AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_PROVIDED = "NOT_PROVIDED"
    UNKNOWN = "UNKNOWN"
    REDACTED = "REDACTED"


class StrategyObjective(StrEnum):
    """What a future budget optimizer would maximize.

    Orthogonal to ``BudgetUsagePolicy``: every combination of the two is
    representable. Neither this enum nor ``BudgetUsagePolicy`` implements an
    optimizer; both are declarations a future optimizer would read.
    """

    MAXIMIZE_REVENUE = "MAXIMIZE_REVENUE"
    MAXIMIZE_PROFIT = "MAXIMIZE_PROFIT"


class BudgetUsagePolicy(StrEnum):
    """Whether a future budget optimizer must exhaust an authorized budget.

    ``SPEND_UP_TO_BUDGET`` allows an optimizer to leave budget unused when no
    further spend is justified. ``SPEND_FULL_BUDGET`` requires the full
    authorized amount to be allocated. Orthogonal to ``StrategyObjective``.
    """

    SPEND_UP_TO_BUDGET = "SPEND_UP_TO_BUDGET"
    SPEND_FULL_BUDGET = "SPEND_FULL_BUDGET"


class AssignmentType(StrEnum):
    """How a budget was assigned. Reserved for a future intervention study.

    No current pipeline populates this; it exists on ``BudgetObservation`` so
    that field's shape does not need to change when experimentation support
    is added.
    """

    RANDOMIZED = "RANDOMIZED"
    RULE_BASED = "RULE_BASED"
    MANUAL = "MANUAL"
    UNKNOWN = "UNKNOWN"


class RecordClassification(StrEnum):
    """When in the decision cycle a record's fields became available.

    Attributes:
        DECISION_TIME: Known before treatment (budget, targeting) is chosen.
        OBSERVED_AFTER_TREATMENT: Known only after treatment ran, from normal
            reporting.
        EVALUATION_ONLY_GROUND_TRUTH: Known only to a simulator or a
            controlled experiment; must never reach a model-facing record.
            See ``evaluation_only.py``.
    """

    DECISION_TIME = "DECISION_TIME"
    OBSERVED_AFTER_TREATMENT = "OBSERVED_AFTER_TREATMENT"
    EVALUATION_ONLY_GROUND_TRUTH = "EVALUATION_ONLY_GROUND_TRUTH"


class MarginSource(StrEnum):
    """Whether a ProductEconomics margin was given directly or derived."""

    EXPLICIT = "EXPLICIT"
    DERIVED = "DERIVED"
