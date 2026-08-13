"""Environment configuration and repository paths for the dashboard.

Reads `.env` at the repository root. The single switch that matters is
`DATABASE`: when false the dashboard reads the committed CSV and JSON files
directly, and when true it reads the PostgreSQL database described by the
`PG_*` variables.

`.env` is git-ignored. `sample.env` is the tracked template; copy it and fill
in real values. Never put real credentials in a tracked file.
"""

from __future__ import annotations

import os
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

    def safe_summary(self) -> str:
        """Return a display string that never contains the password."""
        return f"{self.user}@{self.host}:{self.port}/{self.database}"


@lru_cache(maxsize=1)
def use_database() -> bool:
    """Return True when the dashboard should read from PostgreSQL."""
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
    )
