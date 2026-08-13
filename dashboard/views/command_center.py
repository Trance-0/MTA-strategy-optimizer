"""Command Center: the headline state of the account.

Answers three questions in order -- what was spent and returned, which
touchpoints the models credit, and whether that credit is trustworthy. The
reliability verdict sits beside the attribution figures rather than in a
footnote, because an unreliable share must not be read as a fact.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data_source, theme
from dashboard.views import common


def render() -> None:
    st.markdown("# Command Center")
    st.markdown(
        '<p class="caption">Attribution evidence and budget readiness for the '
        "current report window.</p>",
        unsafe_allow_html=True,
    )

    ads = data_source.load_ads_daily()
    attribution = data_source.load_attribution_results()
    summary = data_source.load_comparison_summary()
    budget = data_source.load_budget_recommendation()
    request = data_source.load_strategy_request()

    _kpi_row(ads, attribution, budget, request)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.55, 1])
    with left:
        _spend_and_return(ads)
    with right:
        _reliability(summary)

    _top_touchpoints(attribution)


def _kpi_row(ads, attribution, budget, request) -> None:
    """Five headline numbers. Each is a single value, so each is a tile."""
    group = request.get("campaign_group", {})
    currency = common.currency_symbol(group.get("currency", "USD"))

    spend = float(ads["cost"].sum())
    sales = float(ads["sales"].sum())
    roas = sales / spend if spend else 0.0
    days = ads["report_date"].dt.date.nunique()

    columns = st.columns(5)
    columns[0].metric("Total spend", theme.money(spend, currency))
    columns[1].metric("Reported sales", theme.money(sales, currency))
    columns[2].metric("Blended ROAS", f"{roas:,.2f}x")
    columns[3].metric(
        "Touchpoints",
        theme.number(attribution["touchpoint"].nunique()),
        help="Distinct five-segment interaction keys the models scored.",
    )
    columns[4].metric(
        "Recommended budget",
        theme.money(budget.get("budget_seed_total", 0.0), currency),
        help=f"Daily total across {len(budget.get('campaigns', []))} Campaigns.",
    )

    theme.caption(
        f"Window covers {days} days of platform-reported performance. "
        "Spend and sales are what the platform reported; attributed values "
        "below are what the models assigned."
    )


def _spend_and_return(ads: pd.DataFrame) -> None:
    """Daily spend against daily sales.

    Indexed to each series' own window mean rather than plotted on two axes:
    spend and sales differ by two orders of magnitude here, and a second
    y-axis would invent a correlation the data does not contain.
    """
    st.markdown("## Spend and return over time")

    daily = (
        ads.groupby(ads["report_date"].dt.date)[["cost", "sales"]].sum().reset_index()
    )
    daily.columns = ["date", "cost", "sales"]
    if daily.empty:
        st.info("No daily performance rows in this window.")
        return

    indexed = daily.copy()
    for column in ("cost", "sales"):
        mean = indexed[column].mean()
        indexed[column] = indexed[column] / mean * 100 if mean else 0

    figure = go.Figure()
    for column, label, color in (
        ("cost", "Spend", theme.SERIES[0]),
        ("sales", "Reported sales", theme.SERIES[1]),
    ):
        figure.add_trace(
            go.Scatter(
                x=indexed["date"],
                y=indexed[column],
                name=label,
                mode="lines",
                line=dict(color=color, width=2),
                customdata=daily[column],
                hovertemplate=(
                    f"<b>{label}</b><br>%{{x|%b %d}}<br>"
                    "Index %{y:.0f}<br>Actual %{customdata:,.2f}<extra></extra>"
                ),
            )
        )
    figure.add_hline(
        y=100, line=dict(color=theme.AXIS, width=1), annotation_text="window average"
    )
    figure.update_yaxes(title_text="Indexed to window average = 100")
    theme.style_figure(figure, height=300)
    st.plotly_chart(figure, width="stretch")

    theme.caption(
        "Both series are indexed to their own window average so they share one "
        "axis. Hover shows the actual amount. Exact daily values are in the "
        "Campaigns view table."
    )


def _reliability(summary: pd.DataFrame) -> None:
    """Per-outcome verdict on whether the two models agree."""
    st.markdown("## Model agreement")

    if summary.empty:
        st.info("No comparison summary available.")
        return

    rows = []
    for _, row in summary.iterrows():
        rows.append(
            f'<div class="kv"><span>{common.OUTCOME_LABELS.get(row["outcome"], row["outcome"])}'
            f"</span><span>{theme.status_pill(row['reliability_status'])}</span></div>"
        )
    st.markdown(
        '<div class="panel"><div class="panel-title">Reliability by outcome</div>'
        + "".join(rows)
        + "</div>",
        unsafe_allow_html=True,
    )

    display = summary[
        ["outcome", "tvd", "spearman_rho", "top_k_overlap_rate", "touchpoint_count"]
    ].copy()
    display["outcome"] = display["outcome"].map(
        lambda value: common.OUTCOME_LABELS.get(value, value)
    )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "outcome": st.column_config.TextColumn("Outcome"),
            "tvd": st.column_config.NumberColumn(
                "TVD", format="%.4f", help="Total variation distance. Lower is closer."
            ),
            "spearman_rho": st.column_config.NumberColumn("Spearman", format="%.3f"),
            "top_k_overlap_rate": st.column_config.NumberColumn(
                "Top-K overlap", format="%.2f"
            ),
            "touchpoint_count": st.column_config.NumberColumn("Touchpoints"),
        },
    )
    theme.caption(
        "Diagnostics inform the reader. They never change the verdict, which "
        "AND-aggregates the per-touchpoint reliability flags."
    )


def _top_touchpoints(attribution: pd.DataFrame) -> None:
    """Where the credit lands, by ad product, for each model."""
    st.markdown("## Attributed revenue by ad product")

    if attribution.empty:
        st.info("No attribution results available.")
        return

    grouped = (
        attribution.groupby(["ad_product", "attribution_model"])["attributed_revenue"]
        .sum()
        .reset_index()
    )
    order = (
        grouped.groupby("ad_product")["attributed_revenue"]
        .sum()
        .sort_values()
        .index.tolist()
    )

    figure = go.Figure()
    for model in sorted(grouped["attribution_model"].unique()):
        subset = grouped[grouped["attribution_model"] == model].set_index("ad_product")
        subset = subset.reindex(order)
        figure.add_trace(
            go.Bar(
                y=[common.pretty(name) for name in order],
                x=subset["attributed_revenue"],
                name=model.title(),
                orientation="h",
                marker=dict(
                    color=theme.MODEL_COLORS.get(model, theme.SERIES[0]),
                    line=dict(color=theme.SURFACE, width=2),
                ),
                hovertemplate=(
                    f"<b>{model.title()}</b><br>%{{y}}<br>"
                    "Attributed revenue %{x:$,.2f}<extra></extra>"
                ),
            )
        )
    figure.update_xaxes(title_text="Attributed revenue")
    theme.style_figure(figure, height=300)
    figure.update_layout(barmode="group", bargroupgap=0.08)
    st.plotly_chart(figure, width="stretch")

    theme.caption(
        "Both models are shown because neither is authoritative on its own. "
        "The governed recommendation is in the Budget Manager view."
    )
