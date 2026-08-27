"""Environment configuration and repository paths for the dashboard.

Reads `.env` at the repository root. The single switch that matters is
`DATABASE`: when false the dashboard reads the committed CSV and JSON files
directly, and when true it reads the PostgreSQL database described by the
`PG_*` variables.

`PG_SCHEMA` selects which schema within that database is read. One instance
commonly holds several -- one per simulation scenario -- and they are not
interchangeable: a schema may carry the simulator's research tables without
this project's own. `public` is the fallback, because it is what every
deployment that predates the setting was reading.

`.env` is git-ignored. `sample.env` is the tracked template; copy it and fill
in real values. Never put real credentials in a tracked file.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

#: Repository root, two levels above this file.
REPO_ROOT = Path(__file__).resolve().parent.parent

ATTRIBUTION_MODULE = REPO_ROOT / "modules" / "mta_attribution"
STRATEGY_MODULE = REPO_ROOT / "modules" / "mta_strategy_recommendation"

SIMULATED_DIR = ATTRIBUTION_MODULE / "data" / "simulated"
ATTRIBUTION_OUTPUT_DIR = ATTRIBUTION_MODULE / "outputs" / "attribution"
STRATEGY_INPUT_DIR = STRATEGY_MODULE / "data" / "simulated"
STRATEGY_OUTPUT_DIR = STRATEGY_MODULE / "outputs"

#: Amazon Ads and path-report samples carry a Chinese field-description row
#: directly under the header. It is documentation, not data, and every reader
#: must drop it before parsing numbers.
DESCRIPTION_ROW_MARKERS = ("报告日期", "报告开始日期")

_TRUE_VALUES = {"1", "true", "yes", "on"}

#: The schema read when `PG_SCHEMA` is unset. Every deployment that predates
#: the setting was reading this one, so it is the fallback rather than an
#: arbitrary default.
DEFAULT_SCHEMA = "public"

#: A PostgreSQL unquoted identifier. A schema name cannot be a bound parameter
#: -- it names an object rather than carrying a value -- so it is placed into
#: `search_path` as text, and this is the shape that may be. The real defence
#: is `backend/services/schemas.py`, which accepts only a name the connected
#: server reports; this refuses the characters that would end the option and
#: begin another before any connection is opened.
SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$")


def valid_schema_name(value: str) -> bool:
    """Whether `value` is safe to place into a `search_path` connect option."""
    return bool(SCHEMA_NAME.match(value or ""))


def _load_env() -> None:
    """Load `.env` from the repository root, without overriding real env vars."""
    load_dotenv(REPO_ROOT / ".env", override=False)


@dataclass(frozen=True)
class DatabaseSettings:
    """PostgreSQL connection settings read from the environment."""

    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str
    schema: str = DEFAULT_SCHEMA

    def url(self) -> str:
        """Return a SQLAlchemy URL with credentials percent-encoded.

        Encoding matters: a password containing `@` or `/` corrupts the URL
        and produces a misleading host-resolution error.
        """
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"
        )

    def connect_args(self, timeout: int = 20) -> dict[str, object]:
        """Connection arguments that pin the session to the selected schema.

        The schema is applied through libpq's `-c` option rather than by
        qualifying every statement, because the statements are built from
        `dashboard/models.py`, which names no schema, and from the reflective
        reads of the external `mta_sim_*` tables, which name none either.
        Setting it on the connection means both follow the selection without a
        second definition of where a table lives.

        The selected schema is the whole search path, with no fallback behind
        it. A fallback would be the more forgiving choice and is the wrong one
        here: a schema holding the simulator's research tables but not this
        project's own would resolve the rest from `public` and put one
        scenario's attribution beside another's history, with nothing on the
        page saying so. Missing means missing. `pg_catalog` is searched
        implicitly and holds every function these statements call, so pinning
        costs nothing a read needs.

        Raises:
            ValueError: if the schema name is not a plain identifier, rather
                than passing text that could close the option and open another.
        """
        arguments: dict[str, object] = {"connect_timeout": timeout}
        if self.schema and self.schema != DEFAULT_SCHEMA:
            if not valid_schema_name(self.schema):
                raise ValueError(
                    f"PG_SCHEMA is not a valid PostgreSQL identifier: {self.schema!r}"
                )
            arguments["options"] = f"-csearch_path={self.schema}"
        return arguments

    def safe_summary(self) -> str:
        """Return a display string that never contains the password."""
        summary = f"{self.user}@{self.host}:{self.port}/{self.database}"
        return f"{summary} ({self.schema})" if self.schema != DEFAULT_SCHEMA else summary


@lru_cache(maxsize=1)
def is_hosted() -> bool:
    """Return True when running as the published browser build.

    `web/index.html` sets `DASHBOARD_HOSTED` when it mounts the app through
    stlite. WebAssembly has no raw TCP socket, so that build cannot reach
    PostgreSQL at all, and `.env` is not writable in a browser tab. The flag
    lets the settings module say so plainly instead of offering controls that
    could never take effect.
    """
    _load_env()
    return os.getenv("DASHBOARD_HOSTED", "false").strip().lower() in _TRUE_VALUES


@lru_cache(maxsize=1)
def use_database() -> bool:
    """Return True when the dashboard should read from PostgreSQL."""
    if is_hosted():
        return False
    _load_env()
    return os.getenv("DATABASE", "false").strip().lower() in _TRUE_VALUES


@lru_cache(maxsize=1)
def database_settings() -> DatabaseSettings:
    """Return the configured PostgreSQL settings.

    Raises:
        RuntimeError: if a required variable is missing, naming the variable
            and pointing at `sample.env`.
    """
    _load_env()
    missing = [
        name
        for name in ("PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD")
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy sample.env to .env and fill in the connection details, "
            "or set DATABASE=false to read the local CSV files instead."
        )
    return DatabaseSettings(
        host=os.environ["PG_HOST"],
        port=int(os.getenv("PG_PORT", "5432")),
        database=os.environ["PG_DATABASE"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        sslmode=os.getenv("PG_SSLMODE", "prefer"),
        schema=os.getenv("PG_SCHEMA", "").strip() or DEFAULT_SCHEMA,
    )
