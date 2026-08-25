"""Make a file read and a database read produce identical rows.

Four differences separate the two sources, and each is normalised here rather
than in a view:

* PostgreSQL folds unquoted identifiers to lowercase, so the advertising
  platform's camelCase field names survive only in file mode. Both modes are
  renamed to snake_case.
* The pipeline writes reliability flags as the strings `true` and `false`.
  They are parsed to real booleans, because a view filtering on the flag would
  otherwise keep unreliable rows in one mode and drop them in the other.
* A date read from a CSV is a string and from the database a `date`. Both are
  pinned to `YYYY-MM-DD`, which is also what survives the JSON the browser
  receives.
* Every numeric column arrives as text from a CSV and as a number from the
  database. All of them are coerced to floats or ints, with a blank becoming
  None rather than a not-a-number value JSON cannot represent.

Data flow:
    a CSV row or a database row -> here -> one snapshot key
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from backend.config import DESCRIPTION_ROW_MARKERS

#: Reliability flags the pipeline writes as the strings `true` and `false`.
BOOLEAN_COLUMNS: tuple[str, ...] = (
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
)

#: Date columns that appear across several artifacts.
DATE_COLUMNS: tuple[str, ...] = ("report_start_date", "report_end_date")

#: The five segments of a touchpoint key, in order. These names are the
#: canonical vocabulary: the database stores them as columns on `touchpoint`,
#: and file mode derives them by splitting the key, so both modes agree.
TOUCHPOINT_SEGMENTS: tuple[str, ...] = (
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    """Read a project CSV as dicts, dropping the Chinese field-description row.

    Only the Amazon Ads and path-report samples carry that row, directly under
    the header. It is documentation rather than data and must go before any
    numeric column is parsed, or every conversion in that column fails. The
    exact marker is matched rather than guessed, because a heuristic would
    silently discard a real first row from the files that have no such row.

    Every value comes back as a string: type inference is what makes a file
    read and a database read disagree, so the callers coerce the columns they
    know about instead.
    """
    path = Path(path)
    if not path.is_file():
        return []
    # `utf-8-sig` drops a byte-order mark that would otherwise become part of
    # the first header name, so every lookup of that column would miss.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    if rows:
        first = next(iter(rows[0].values()), "")
        if first in DESCRIPTION_ROW_MARKERS:
            rows = rows[1:]
    return rows


def read_json(path: str | Path) -> dict:
    """Read a JSON artifact, or return an empty object when it is absent.

    An absent artifact means the command that writes it has not run, which the
    views render as "not yet produced". That is a state, not a failure.
    """
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def to_number(value: Any) -> float | int | None:
    """Coerce one value to a number, with a blank becoming None.

    None rather than a not-a-number value: NaN is not representable in JSON
    and would reach the browser as null anyway, so producing it here would
    mean the two modes disagreed before serialisation and agreed after.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        number = float(text)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    # An integral value is returned as an int so a count reads as a count in
    # the JSON the browser receives, matching what the CSV states.
    if number.is_integer() and "." not in text and "e" not in text.lower():
        return int(number)
    return number


def numeric(rows: Iterable[MutableMapping[str, Any]], columns: Sequence[str]) -> list:
    """Coerce the named columns of every row to numbers."""
    rows = list(rows)
    for row in rows:
        for column in columns:
            if column in row:
                row[column] = to_number(row[column])
    return rows


def boolean(
    rows: Iterable[MutableMapping[str, Any]],
    columns: Sequence[str] = BOOLEAN_COLUMNS,
) -> list:
    """Coerce the reliability flag columns to real booleans.

    A CSV read yields the strings `true` and `false`, and both are non-empty.
    Without this, a truthiness test would accept either one.
    """
    rows = list(rows)
    for row in rows:
        for column in columns:
            if column not in row:
                continue
            value = row[column]
            row[column] = (
                value if isinstance(value, bool) else str(value).strip().lower() == "true"
            )
    return rows


def format_date(value: Any) -> str | None:
    """Pin one date value to `YYYY-MM-DD`, or None when it carries no date.

    A `date` is formatted from its own components rather than converted
    through any timezone, because a conversion to UTC reports the previous day
    for any host east of Greenwich. Every date the API returns goes through
    this one function for that reason.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"
    if isinstance(value, date):
        return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"
    return str(value)[:10]


def dates(
    rows: Iterable[MutableMapping[str, Any]],
    columns: Sequence[str] = DATE_COLUMNS,
) -> list:
    """Pin the named date columns of every row to `YYYY-MM-DD`."""
    rows = list(rows)
    for row in rows:
        for column in columns:
            if column in row:
                row[column] = format_date(row[column])
    return rows


def split_touchpoint(rows: Iterable[MutableMapping[str, Any]]) -> list:
    """Add the five key segments as their own fields.

    Files that already carry an `interaction_type` agree with the fifth
    segment, so overwriting is harmless and keeps the field present for the
    files that omit it.
    """
    rows = list(rows)
    for row in rows:
        if "touchpoint" not in row:
            continue
        segments = str(row["touchpoint"]).split(":")
        for index, name in enumerate(TOUCHPOINT_SEGMENTS):
            if index < len(segments):
                row[name] = segments[index]
    return rows


def project(
    rows: Iterable[Mapping[str, Any]], fields: Sequence[str]
) -> list[dict[str, Any]]:
    """Keep only the named fields, in the order given, so both modes agree.

    An absent text value is pinned to None in both modes. A CSV represents it
    as an empty string and PostgreSQL as NULL, and the two are not
    interchangeable to a view: a default-value expression yields the default in
    one mode and an empty string in the other, and JSON serialisation preserves
    the difference. Numeric fields are already pinned to None by `numeric`.
    """
    projected = []
    for row in rows:
        record: dict[str, Any] = {}
        for field in fields:
            value = row.get(field)
            record[field] = None if value is None or value == "" else value
        projected.append(record)
    return projected


def rename(
    rows: Iterable[Mapping[str, Any]], mapping: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Rename the platform's camelCase field names to the project's snake_case."""
    return [
        {mapping.get(key, key): value for key, value in row.items()} for row in rows
    ]
