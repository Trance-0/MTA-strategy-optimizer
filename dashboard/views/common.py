"""Helpers shared by more than one view.

Only presentation lives here -- label vocabulary, formatting, and the filter
row. Nothing in this module computes an attribution or budget number.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import theme

#: Outcome keys as the pipeline writes them, and how they are shown.
OUTCOME_LABELS = {
    "converted_users": "Converted users",
    "purchase_count": "Purchases",
    "revenue": "Revenue",
}

#: The share column that belongs to each outcome.
OUTCOME_SHARE_COLUMNS = {
    "converted_users": "converted_user_share",
    "purchase_count": "purchase_count_share",
    "revenue": "revenue_share",
}

#: The attributed-total column that belongs to each outcome.
OUTCOME_VALUE_COLUMNS = {
    "converted_users": "attributed_converted_users",
    "purchase_count": "attributed_purchase_count",
    "revenue": "attributed_revenue",
}

_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}


def currency_symbol(code: str) -> str:
    """Return the symbol for a currency code, falling back to the code."""
    return _CURRENCY_SYMBOLS.get(str(code).upper(), f"{code} ")


def pretty(value: str) -> str:
    """Turn an UPPER_SNAKE enum into readable title case."""
    return str(value).replace("_", " ").title()


def short_touchpoint(key: str) -> str:
    """Shorten a five-segment key for an axis tick.

    Drops the segments that are `UNSPECIFIED`, which carry no information and
    would otherwise make every label the same length and unreadable.
    """
    parts = [part for part in str(key).split(":") if part != "UNSPECIFIED"]
    return " / ".join(pretty(part) for part in parts)


def date_range_filter(frame: pd.DataFrame, column: str = "report_date"):
    """Render a date-range control and return the filtered frame.

    Placed by the caller in one filter row above everything it scopes, so
    every chart on the page re-renders against the same slice.
    """
    if frame.empty or column not in frame.columns:
        return frame

    earliest = frame[column].min().date()
    latest = frame[column].max().date()
    chosen = st.date_input(
        "Report window",
        value=(earliest, latest),
        min_value=earliest,
        max_value=latest,
        help="Filters every chart and table on this page.",
    )
    if not isinstance(chosen, tuple) or len(chosen) != 2:
        return frame
    start, end = chosen
    mask = (frame[column].dt.date >= start) & (frame[column].dt.date <= end)
    return frame[mask]


def multiselect_filter(frame: pd.DataFrame, column: str, label: str):
    """Render a dimension filter and return the filtered frame."""
    if frame.empty or column not in frame.columns:
        return frame
    options = sorted(value for value in frame[column].dropna().unique() if value != "")
    chosen = st.multiselect(
        label, options, default=[], format_func=pretty, placeholder="All"
    )
    if not chosen:
        return frame
    return frame[frame[column].isin(chosen)]


def outcome_selector(key: str, label: str = "Outcome") -> str:
    """Render the outcome picker and return the selected key."""
    return st.selectbox(
        label,
        list(OUTCOME_LABELS),
        format_func=lambda value: OUTCOME_LABELS[value],
        key=key,
    )


def table_view(frame: pd.DataFrame, label: str = "View as table") -> None:
    """Offer the values behind a chart, so no value is reachable only by hover."""
    with st.expander(label):
        st.dataframe(frame, hide_index=True, width="stretch")


def empty_notice(what: str) -> None:
    """Explain an empty panel rather than rendering a blank card."""
    st.info(
        f"No {what} available from the current data source. "
        "Run the pipeline, or switch `DATABASE` in `.env`."
    )


def reliability_banner(status: str, reason: str) -> None:
    """State the governing reliability verdict at the top of a view."""
    tint = {
        "RELIABLE": ("#eaf7f0", theme.GREEN),
        "UNRELIABLE": ("#fdf0ef", theme.RED),
        "PARTIAL": ("#fff5d8", theme.AMBER),
    }.get(str(status).upper(), (theme.PLANE, theme.MUTED))

    st.markdown(
        f"""
        <div style="background:{tint[0]};border:1px solid {tint[1]}33;
                    border-radius:10px;padding:11px 14px;margin-bottom:14px">
          <span class="pill" style="background:{theme.SURFACE};color:{tint[1]}">
            {str(status).upper()}
          </span>
          <span style="color:{theme.TEXT};font-size:.86rem;margin-left:10px">
            {reason}
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
