"""SimilarityReference: a presentation-only "similar items" pointer.

Defines the field contract used by the dashboard's transparent historical
selector heuristic, without allowing that output to be
mistaken for canonical model input. Nothing in ``modules/mta_common/src/``
(outside this ``presentation`` subpackage) imports this module, and no
canonical, model-facing dataclass has a field typed to accept it — a
response model, attribution model, or optimizer reading a ``Campaign``,
``Product``, or ``CampaignEpisode`` has no attribute path to a
``SimilarityReference`` by construction. ``tests`` proves both directions:
that this module is unreachable from core imports, and that no core
dataclass field type-hints this class.

Referenced entities are plain string ids (``subject_id``/``comparable_id``),
not ``Campaign``/``Product`` object references, so this module does not need
to import the core package at all and cannot participate in a cycle with it.

Data flow: canonical product/campaign info feeds the separate dashboard
selector heuristic; that process's output is a
``SimilarityReference``, consumed only by the dashboard. It does not feed
back into attribution, response modeling, or optimization.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimilarityReference:
    """A dashboard-facing pointer from one subject to a similar comparable.

    Attributes:
        subject_type: What kind of entity ``subject_id`` identifies, for
            example ``PRODUCT`` or ``CAMPAIGN``.
        subject_id: Id of the entity the similarity was computed for.
        comparable_id: Id of the similar entity being referenced, of the
            same ``subject_type``.
        similarity_score: A presentation-only similarity value in
            ``[0, 1]``; not a model input.
        rationale: Free-text, human-readable explanation for display.
        generated_by: Identifier of the process or model version that
            produced this reference.
    """

    subject_type: str
    subject_id: str
    comparable_id: str
    similarity_score: float
    rationale: str | None = None
    generated_by: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("subject_type", "subject_id", "comparable_id"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if self.subject_id == self.comparable_id:
            raise ValueError("comparable_id must differ from subject_id")
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError("similarity_score must be between 0 and 1")
