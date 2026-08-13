"""The settings module pinned to the foot of the sidebar.

Holds the two things a reader may need to change without editing files: the
database credentials this dashboard connects with, and whether data access is
logged while it streams.

Credentials are written to `.env` at the repository root, which is git-ignored.
Nothing here writes a credential to a tracked file, to the page, or to the log:
`DatabaseSettings.safe_summary()` is the only rendering of a connection, and it
omits the password by construction.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from dashboard import config, data_source, theme

#: Written to `.env`. Order is preserved when the file is rewritten so a
#: hand-edited file keeps its shape.
ENV_KEYS = (
    "DATABASE",
    "PG_HOST",
    "PG_PORT",
    "PG_DATABASE",
    "PG_USER",
    "PG_PASSWORD",
    "PG_SSLMODE",
)

ENV_PATH = config.REPO_ROOT / ".env"

#: How many log records the in-memory stream keeps. Bounded so a long session
#: cannot grow without limit.
LOG_CAPACITY = 400

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

#: The loggers the stream attaches to. `dashboard` covers this package's own
#: records; the SQLAlchemy loggers carry the emitted SQL and connection events,
#: which is what makes "log the streaming data" meaningful rather than
#: decorative.
STREAM_LOGGERS = ("dashboard", "sqlalchemy.engine", "sqlalchemy.pool")


@dataclass
class LogRecordView:
    """One captured record, already formatted for display."""

    when: str
    level: str
    logger: str
    message: str


class RingBufferHandler(logging.Handler):
    """Collect recent records in memory for display in the settings modal.

    A file handler would be the wrong choice here: the reader wants to watch
    what the dashboard is doing right now, and a bounded deque cannot fill a
    disk on a demonstration machine.
    """

    def __init__(self, capacity: int = LOG_CAPACITY) -> None:
        super().__init__()
        self.records: deque[LogRecordView] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a broken record must not break a page
            message = "<unformattable log record>"
        self.records.append(
            LogRecordView(
                when=time.strftime("%H:%M:%S", time.localtime(record.created)),
                level=record.levelname,
                logger=record.name,
                message=message[:400],
            )
        )


@st.cache_resource
def _handler() -> RingBufferHandler:
    """Return the process-wide handler.

    Cached as a resource rather than stored in session state: the handler is
    attached to module-level loggers, so it must outlive a single rerun and be
    shared by every session rather than duplicated per session.
    """
    return RingBufferHandler()


def logging_enabled() -> bool:
    """Return whether the stream is currently attached."""
    return bool(st.session_state.get("logging_enabled", False))


def apply_logging(enabled: bool, level: str = "INFO") -> None:
    """Attach or detach the ring-buffer handler on the streamed loggers."""
    handler = _handler()
    handler.setLevel(getattr(logging, level, logging.INFO))
    for name in STREAM_LOGGERS:
        logger = logging.getLogger(name)
        if enabled:
            if handler not in logger.handlers:
                logger.addHandler(handler)
            logger.setLevel(getattr(logging, level, logging.INFO))
            # Without this, records also reach the root handler and are echoed
            # into the server console for every query.
            logger.propagate = False
        else:
            if handler in logger.handlers:
                logger.removeHandler(handler)
            logger.propagate = True
    st.session_state["logging_enabled"] = enabled
    st.session_state["logging_level"] = level


def read_env() -> dict[str, str]:
    """Read the current `.env` values, falling back to the live environment."""
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    for key in ENV_KEYS:
        values.setdefault(key, os.getenv(key, ""))
    return values


def write_env(updates: dict[str, str]) -> None:
    """Merge `updates` into `.env`, preserving comments and unrelated keys.

    The file is rewritten rather than appended to, so a key set twice cannot
    end up with the stale value winning depending on read order.
    """
    lines: list[str] = []
    seen: set[str] = set()

    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                lines.append(raw)
                continue
            key = stripped.partition("=")[0].strip()
            if key in updates:
                lines.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                lines.append(raw)

    missing = [key for key in ENV_KEYS if key in updates and key not in seen]
    if missing:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Written by the dashboard settings module.")
        lines.extend(f"{key}={updates[key]}" for key in missing)

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # `config` caches the mode and the settings for the life of the process, so
    # a rewritten file would otherwise not take effect until a restart.
    config.use_database.cache_clear()
    config.database_settings.cache_clear()
    for key, value in updates.items():
        os.environ[key] = value
    data_source.clear_caches()


def status() -> tuple[str, str, str]:
    """Return (label, colour, detail) describing the active source."""
    if config.use_database():
        usable, message = data_source.database_available()
        if usable:
            return "Database", "#7ee0b0", message
        return "Database", "#ffb4ad", f"Unavailable — {message}"
    return "Local files", "#9db7e8", "Reading committed CSV and JSON artifacts."


@st.dialog("Settings", width="large")
def settings_dialog() -> None:
    """The modal behind the sidebar's settings button."""
    connection, logs = st.tabs(["Data source", "Logging"])

    with connection:
        _connection_tab()
    with logs:
        _logging_tab()


def _connection_tab() -> None:
    """Edit the data-source mode and the PostgreSQL credentials."""
    values = read_env()
    label, colour, detail = status()

    st.markdown(
        f"""
        <div style="border:1px solid {theme.LINE};border-radius:9px;
                    padding:10px 13px;margin-bottom:14px;background:{theme.PLANE}">
          <span style="font-weight:640;color:{theme.TEXT};font-size:.9rem">
            {label}</span>
          <span style="color:{theme.MUTED};font-size:.8rem;margin-left:8px">
            {detail}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("settings_connection"):
        use_db = st.toggle(
            "Read from the database",
            value=config.use_database(),
            help=(
                "Off reads the committed CSV and JSON artifacts, which needs no "
                "database at all. On reads the imported PostgreSQL mirror."
            ),
        )

        st.markdown("**PostgreSQL connection**")
        left, right = st.columns([2, 1])
        host = left.text_input("Host", value=values.get("PG_HOST", ""))
        port = right.text_input("Port", value=values.get("PG_PORT", "5432"))

        left, right = st.columns(2)
        database = left.text_input("Database", value=values.get("PG_DATABASE", ""))
        user = right.text_input("User", value=values.get("PG_USER", ""))

        left, right = st.columns([2, 1])
        password = left.text_input(
            "Password",
            value=values.get("PG_PASSWORD", ""),
            type="password",
            help="Stored in .env, which is git-ignored, and never rendered back.",
        )
        modes = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        current = values.get("PG_SSLMODE", "prefer")
        sslmode = right.selectbox(
            "SSL mode", modes, index=modes.index(current) if current in modes else 2
        )

        test = st.form_submit_button("Test connection")
        save = st.form_submit_button("Save to .env", type="primary")

    if test or save:
        updates = {
            "DATABASE": "true" if use_db else "false",
            "PG_HOST": host.strip(),
            "PG_PORT": port.strip() or "5432",
            "PG_DATABASE": database.strip(),
            "PG_USER": user.strip(),
            "PG_PASSWORD": password,
            "PG_SSLMODE": sslmode,
        }

    if test:
        ok, message = _test_connection(updates)
        (st.success if ok else st.error)(message)

    if save:
        write_env(updates)
        st.success(
            "Saved to `.env` and caches cleared. "
            "Close this dialog to reload the dashboard."
        )

    st.caption(
        "Credentials are written to `.env` at the repository root, which is "
        "git-ignored. `sample.env` is the tracked template and must never hold "
        "a real credential."
    )


def _test_connection(updates: dict[str, str]) -> tuple[bool, str]:
    """Open a throwaway connection with the entered values.

    Tests what was typed rather than what is saved, so a reader can validate a
    correction before committing it to `.env`.
    """
    missing = [
        key
        for key in ("PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD")
        if not updates.get(key)
    ]
    if missing:
        return False, f"Missing {', '.join(missing)}."

    try:
        from sqlalchemy import create_engine, text

        settings = config.DatabaseSettings(
            host=updates["PG_HOST"],
            port=int(updates["PG_PORT"]),
            database=updates["PG_DATABASE"],
            user=updates["PG_USER"],
            password=updates["PG_PASSWORD"],
            sslmode=updates["PG_SSLMODE"],
        )
        engine = create_engine(
            settings.url(), connect_args={"connect_timeout": 10}
        )
        with engine.connect() as connection:
            version = connection.execute(text("select version()")).scalar()
            tables = connection.execute(
                text(
                    "select count(*) from information_schema.tables "
                    "where table_schema = 'public'"
                )
            ).scalar()
        engine.dispose()
        return True, (
            f"Connected to {settings.safe_summary()} — "
            f"{tables} table(s). {str(version).split(',')[0]}"
        )
    except Exception as error:  # noqa: BLE001 - shown verbatim to the reader
        return False, f"{type(error).__name__}: {str(error)[:300]}"


def _logging_tab() -> None:
    """Enable the stream and show what it has captured."""
    st.markdown(
        "Records what the dashboard reads while it reads it: the SQL issued to "
        "PostgreSQL, connection checkouts, and this package's own messages. "
        "Off by default, because logging every query costs time on each rerun."
    )

    left, middle, right = st.columns([1, 1, 1])
    enabled = left.toggle("Enable logging", value=logging_enabled())
    level = middle.selectbox(
        "Level",
        LOG_LEVELS,
        index=LOG_LEVELS.index(st.session_state.get("logging_level", "INFO")),
        help="DEBUG includes the full SQL statements SQLAlchemy emits.",
    )
    if right.button("Clear captured records", width="stretch"):
        _handler().records.clear()

    if enabled != logging_enabled() or level != st.session_state.get("logging_level"):
        apply_logging(enabled, level)

    records = list(_handler().records)
    if not records:
        st.info(
            "No records captured yet. Enable logging, then switch views or press "
            "Reload to generate activity."
        )
        return

    st.caption(f"{len(records)} record(s), newest last. Capacity {LOG_CAPACITY}.")
    rows = "".join(
        f"<div style='padding:2px 0;border-bottom:1px solid #f1f3f7'>"
        f"<span style='color:{theme.SUBTLE}'>{record.when}</span> "
        f"<span style='color:{_level_colour(record.level)};font-weight:600'>"
        f"{record.level}</span> "
        f"<span style='color:{theme.MUTED}'>{record.logger}</span><br>"
        f"<span style='color:{theme.TEXT}'>{_escape(record.message)}</span></div>"
        for record in records[-120:]
    )
    st.markdown(
        f"<div style='max-height:340px;overflow:auto;font-family:ui-monospace,"
        f"SFMono-Regular,Menlo,monospace;font-size:.72rem;border:1px solid "
        f"{theme.LINE};border-radius:8px;padding:10px'>{rows}</div>",
        unsafe_allow_html=True,
    )


def _escape(text: str) -> str:
    """Escape a log message so it cannot inject markup into the page."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _level_colour(level: str) -> str:
    return {
        "DEBUG": theme.SUBTLE,
        "INFO": theme.BLUE,
        "WARNING": theme.AMBER,
        "ERROR": theme.RED,
        "CRITICAL": theme.RED,
    }.get(level, theme.MUTED)
