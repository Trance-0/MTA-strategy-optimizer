"""Backend configuration, layered over the dashboard's existing settings.

`dashboard/config.py` already reads `.env` and already knows the repository's
paths and the PostgreSQL connection. This module re-exports it rather than
restating it, so there is exactly one definition of what `DATABASE=true` means
and one place a credential is read from. What is added here is the handful of
settings only an HTTP service needs: the interface it binds, whether the
deployment is read-only, and where an optional research snapshot lives.

Data flow:
    .env -> dashboard/config.py -> here -> backend/app.py
"""

from __future__ import annotations

import os
from pathlib import Path

from dashboard.config import (  # noqa: F401  (re-exported by design)
    ATTRIBUTION_MODULE,
    ATTRIBUTION_OUTPUT_DIR,
    DEFAULT_SCHEMA,
    DESCRIPTION_ROW_MARKERS,
    REPO_ROOT,
    SIMULATED_DIR,
    STRATEGY_INPUT_DIR,
    STRATEGY_MODULE,
    STRATEGY_OUTPUT_DIR,
    DatabaseSettings,
    _load_env,
    database_settings,
    is_hosted,
    use_database,
    valid_schema_name,
)

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _flag(name: str, default: str = "false") -> bool:
    """Read one boolean environment variable."""
    _load_env()
    return os.getenv(name, default).strip().lower() in _TRUE_VALUES


def config_read_only() -> bool:
    """Return True when deployment configuration may be read but not rewritten.

    A server deployment is given its configuration by the platform that
    deployed it. Letting a browser rewrite `.env` there would mean the running
    service and the deployment record disagree about their own configuration
    from the next restart onward.
    """
    return _flag("DASHBOARD_CONFIG_READ_ONLY")


def server_host() -> str:
    """The interface the API binds. Loopback is the safe default.

    The service exposes data-mutation and settings routes and implements no
    user authentication, so binding a public interface must be a deliberate
    act of configuration rather than what happens when nothing is set.
    """
    _load_env()
    return os.getenv("BACKEND_HOST", os.getenv("DASHBOARD_HOST", "127.0.0.1")).strip()


def server_port() -> int:
    """The port the API listens on."""
    _load_env()
    return int(os.getenv("BACKEND_PORT", os.getenv("DASHBOARD_PORT", "8501")))


def open_browser() -> bool:
    """Whether the local launcher asks to open the dashboard after startup."""
    return _flag("DASHBOARD_OPEN")


def simulator_data_directory() -> Path | None:
    """The optional MTA-SIM research run the research views read.

    Configuration rather than a cross-repository import: MTA-SIM and this
    project stay independently runnable. Returns None when unset, and the
    loaders fall back to the committed module fixtures.
    """
    _load_env()
    configured = os.getenv("MTA_SIM_DATA_DIR", "").strip()
    return Path(configured).resolve() if configured else None


def research_snapshot_path() -> Path | None:
    """The `simulation_research.json` the optimizer fits against, if present."""
    directory = simulator_data_directory()
    if directory is None:
        return None
    path = directory / "simulation_research.json"
    return path if path.is_file() else None


def client_dist_directory() -> Path | None:
    """The built Vue client, when one has been built beside this service.

    One process serving the API and the client keeps a deployment to one port.
    A development run serves the client from Vite instead and proxies here, so
    this is simply absent then.
    """
    path = REPO_ROOT / "dashboard" / "dist"
    return path if path.is_dir() else None


def safe_summary() -> str:
    """A connection description that never contains the password."""
    return database_settings().safe_summary()


def active_mode() -> str:
    """`database` or `local files`, for display in the client's rail."""
    return "database" if use_database() else "local files"


def source_label() -> str:
    """Where data is being read from, in one human-readable line."""
    if not use_database():
        directory = simulator_data_directory()
        return str(directory) if directory else "modules/*/data and outputs"
    try:
        return safe_summary()
    except RuntimeError as error:
        return f"Not configured — {error}"
