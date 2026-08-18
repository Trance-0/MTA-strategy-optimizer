"""The reporting window and account context shared by observation records.

Today these fields are scattered: ``mta_source`` and ``campaign_group`` in
``strategy_request.json`` each carry their own copy of ``marketplace`` and
``advertiser_id``, cross-validated for equality by
``hierarchy_validator.load_aligned_strategy_inputs``, and ``currency`` is
schema-required but never used in any calculation. ``ReportingScope``
composes these into one reusable value object instead of repeating them on
every record that needs to know its account, market, currency, and window.

Data flow: any record that observes something (delivery, budget, outcome,
attribution evidence) carries a ``ReportingScope`` describing where and when
it was observed, rather than inlining `marketplace`/`advertiser_id`/
`currency` fields of its own.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportingScope:
    """The account, market, currency, and date window an observation covers.

    Attributes:
        marketplace: Advertising marketplace code.
        advertiser_id: Advertiser or account identifier.
        currency: ISO-style currency code all monetary fields in the scoped
            record are denominated in.
        report_start_date: Inclusive ISO start date of the report window.
        report_end_date: Inclusive ISO end date of the report window.
        campaign_group_id: Optional campaign-group identifier, when the scope
            is further narrowed to one campaign group.
    """

    marketplace: str
    advertiser_id: str
    currency: str
    report_start_date: str
    report_end_date: str
    campaign_group_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("marketplace", "advertiser_id", "currency"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if not self.report_start_date or not self.report_end_date:
            raise ValueError("report_start_date and report_end_date are required")
        if self.report_end_date < self.report_start_date:
            raise ValueError("report_end_date must not precede report_start_date")
