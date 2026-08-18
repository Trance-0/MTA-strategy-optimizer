"""Data lineage: where a record came from, without coupling to a file path.

Today's only lineage-like fields are the `source_*_sha256` provenance hashes
on `BudgetRecommendationRun` in the dashboard schema — a content hash, not a
structured description of source system, schema version, or synthetic-versus-
observed status. ``DataLineage`` generalizes this into a reusable value
object, referencing a logical source (a table name, a report name, a
provider) rather than a local filesystem path, since the same logical source
may be read from a CSV in one environment and a database table in another.

Data flow: any canonical record's producer may attach a ``DataLineage``
describing how that record was derived; this module defines the type but
does not require any class above to carry one, so adoption can be gradual.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import Provider, RecordClassification


@dataclass(frozen=True)
class DataLineage:
    """Provenance for one canonical record.

    Attributes:
        source_system: The system of record, for example
            ``AMAZON_ADS_AMC`` or ``MTA_SIM_GENERATOR``.
        provider: The provider this lineage is scoped to, when applicable.
        source_reference: A logical reference to the source — a table or
            report name, not a local file path — so lineage survives moving
            between a CSV extract and a database import of the same source.
        schema_version: Version of the source schema this record was read
            under.
        transformation_version: Version of the adapter or compatibility
            layer that produced this record from the source.
        classification: Whether this record's fields were available at
            decision time, observed only after treatment, or are
            evaluation-only ground truth. See ``RecordClassification``.
        is_synthetic: Whether the source is simulated data rather than a
            real observed platform report.
        report_period_start: Optional inclusive ISO start date of the
            source's own reporting period, which may differ from the
            ``ReportingScope`` window of the record it describes.
        report_period_end: Optional inclusive ISO end date of the source's
            own reporting period.
    """

    source_system: str
    source_reference: str
    schema_version: str
    transformation_version: str
    classification: RecordClassification
    is_synthetic: bool
    provider: Provider | None = None
    report_period_start: str | None = None
    report_period_end: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "source_system",
            "source_reference",
            "schema_version",
            "transformation_version",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
