"""The one place a PostgreSQL connection is opened.

Every read in `backend/repository/` runs through `rows()` or `orm_rows()`
here, so connection handling, pooling, and result shaping exist once. The
engine is created lazily: a `DATABASE=false` deployment never imports a
driver, which is what keeps a checkout with no database working.

Statements are expressed against `dashboard/models.py` wherever that module
defines the table, so the schema has one definition and a column rename is a
single edit. The MTA-SIM research tables are the deliberate exception — they
belong to the external simulator repository, not to this project's schema, so
they are read reflectively through `sql()` after `table_exists()` confirms
they are present.

Data flow:
    backend/config.py -> here -> backend/repository/&#42;
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Row

from backend.config import database_settings, use_database

_engine: Engine | None = None


def engine() -> Engine:
    """Return the shared engine, created on first use.

    Raises:
        RuntimeError: naming every missing `PG_*` variable, from
            `database_settings()`, rather than failing later at connection
            time with a misleading host-resolution error.
    """
    global _engine
    if _engine is None:
        settings = database_settings()
        _engine = create_engine(
            settings.url(),
            # Four is the dashboard's historical pool size and is sized for a
            # handful of concurrent readers, not for a public service.
            pool_size=4,
            max_overflow=0,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"connect_timeout": 20},
        )
    return _engine


def dispose_engine() -> None:
    """Close the pool so a settings change can rebuild it with new credentials."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def _mappings(result: Iterable[Row[Any]]) -> list[dict[str, Any]]:
    """Turn result rows into plain mutable dicts the coercions can rewrite."""
    return [dict(row) for row in result]


def sql(statement: str, parameters: Mapping[str, Any] | None = None) -> list[dict]:
    """Run one read-only textual statement and return its rows as dicts.

    Reserved for the MTA-SIM research tables, which this project's schema does
    not define. Parameters are always bound rather than interpolated.
    """
    with engine().connect() as connection:
        result = connection.execute(text(statement), dict(parameters or {}))
        return _mappings(result.mappings())


def orm_rows(statement: Any) -> list[dict]:
    """Run a SQLAlchemy Core or ORM select and return its rows as dicts.

    The statement is built from `dashboard/models.py` columns, so a column
    that no longer exists fails at import rather than at request time.
    """
    with engine().connect() as connection:
        return _mappings(connection.execute(statement).mappings())


def table_exists(name: str) -> bool:
    """Whether a table is present in the connected database.

    Used before reading the MTA-SIM research tables, which a deployment that
    imported only this project's own artifacts will not have. Their absence is
    an ordinary state, not a fault, so it is probed rather than caught.
    """
    rows = sql(
        "select to_regclass(:qualified)::text as table_name",
        {"qualified": f"public.{name}"},
    )
    return bool(rows and rows[0].get("table_name"))


def database_available() -> tuple[bool, str]:
    """Whether the configured database is reachable and carries results.

    Returns `(usable, message)` rather than raising, so the client can render
    a connection failure as a page-level state naming both remedies instead of
    as a failed fetch inside whichever chart read it first.
    """
    if not use_database():
        return False, "DATABASE=false"
    try:
        rows = sql("select count(*)::int as count from attribution_result")
        if not rows or not rows[0].get("count"):
            return False, "Connected, but attribution_result is empty."
        from backend.config import safe_summary

        return True, f"Connected to {safe_summary()}"
    except Exception as error:  # noqa: BLE001 - reported, never raised onward
        return False, f"{type(error).__name__}: {str(error)[:180]}"


def execute(statement: str, parameters: Mapping[str, Any] | None = None) -> list[dict]:
    """Run one writing statement inside a transaction and return any rows.

    Separate from `sql()` so that a read path cannot commit by accident: the
    two differ by which connection context they open, not by what the caller
    remembered to do.
    """
    with engine().begin() as connection:
        result = connection.execute(text(statement), dict(parameters or {}))
        if result.returns_rows:
            return _mappings(result.mappings())
        return []


def orm_execute(statement: Any) -> list[dict]:
    """Run a writing ORM statement inside a transaction and return any rows."""
    with engine().begin() as connection:
        result = connection.execute(statement)
        if result.returns_rows:
            return _mappings(result.mappings())
        return []


def scalar_columns(statements: Sequence[str]) -> list[list[dict]]:
    """Run several read statements on one connection, in order.

    Opening one connection for a group of reads that will be assembled into a
    single response costs one round trip rather than one per loader.
    """
    with engine().connect() as connection:
        return [
            _mappings(connection.execute(text(statement)).mappings())
            for statement in statements
        ]
