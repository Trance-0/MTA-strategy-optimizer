"""Campaigns: historical performance, filterable and queryable.

The one place a reader can interrogate the raw record -- daily platform
performance, the Campaign and Ad Group bridge, and the conversion paths. All
filters sit in a single row above the charts, so every panel on the page shows
the same slice.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data_source, theme
from dashboard.views import common


def render() -> None:
    st.markdown("# Campaigns")
    st.markdown(
        '<p class="caption">Observed performance and the entity bridge that '
        "links touchpoints to Campaigns and Ad Groups.</p>",
        unsafe_allow_html=True,
    )

    ads = data_source.load_ads_daily()
    bridge = data_source.load_entity_bridge()
    paths = data_source.load_path_report()

    performance, history, journeys = st.tabs(
        ["Daily performance", "Campaign bridge", "Conversion paths"]
    )
    with performance:
        _performance(ads)
    with history:
        _bridge(bridge)
    with journeys:
        _paths(paths)


def _performance(ads: pd.DataFrame) -> None:
    """Daily platform performance, filtered by window, product, and placement."""
    if ads.empty:
        common.empty_notice("daily performance")
        return

    filters = st.columns([1.6, 1, 1, 1])
    with filters[0]:
        scoped = common.date_range_filter(ads)
    with filters[1]:
        scoped = common.multiselect_filter(scoped, "ad_product", "Ad product")
    with filters[2]:
        scoped = common.multiselect_filter(scoped, "placement", "Placement")
    with filters[3]:
        scoped = common.multiselect_filter(
            scoped, "interaction_type", "Interaction type"
        )

    if scoped.empty:
        st.warning("No rows match the current filters.")
        return

    totals = st.columns(5)
    spend = float(scoped["cost"].sum())
    sales = float(scoped["sales"].sum())
    totals[0].metric("Spend", theme.money(spend))
    totals[1].metric("Sales", theme.money(sales))
    totals[2].metric("Impressions", theme.number(scoped["impressions"].sum()))
    totals[3].metric("Clicks", theme.number(scoped["clicks"].sum()))
    totals[4].metric("ROAS", f"{(sales / spend if spend else 0):,.2f}x")

    _spend_by_product(scoped)
    _efficiency(scoped)

    common.table_view(
        scoped.sort_values("report_date"),
        f"View all {len(scoped):,} filtered rows as a table",
    )


def _spend_by_product(scoped: pd.DataFrame) -> None:
    """Daily spend split by ad product."""
    st.markdown("## Daily spend by ad product")

    daily = (
        scoped.groupby([scoped["report_date"].dt.date, "ad_product"])["cost"]
        .sum()
        .reset_index()
    )
    daily.columns = ["date", "ad_product", "cost"]

    products = sorted(daily["ad_product"].unique())
    colors = theme.series_colors(products)

    figure = go.Figure()
    for product in products:
        subset = daily[daily["ad_product"] == product]
        figure.add_trace(
            go.Scatter(
                x=subset["date"],
                y=subset["cost"],
                name=common.pretty(product),
                mode="lines",
                line=dict(color=colors[product], width=2),
                hovertemplate=(
                    f"<b>{common.pretty(product)}</b><br>%{{x|%b %d}}<br>"
                    "Spend %{y:$,.2f}<extra></extra>"
                ),
            )
        )
    figure.update_yaxes(title_text="Daily spend")
    theme.style_figure(figure, height=300)
    st.plotly_chart(figure, width="stretch")


def _efficiency(scoped: pd.DataFrame) -> None:
    """Spend against reported sales per touchpoint."""
    st.markdown("## Spend and return by touchpoint")

    grouped = (
        scoped.groupby("touchpoint")[["cost", "sales", "impressions", "clicks"]]
        .sum()
        .reset_index()
        .sort_values("cost", ascending=False)
    )
    top = grouped.head(12).sort_values("cost")
    labels = [common.short_touchpoint(key) for key in top["touchpoint"]]

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            y=labels,
            x=top["cost"],
            name="Spend",
            orientation="h",
            marker=dict(color=theme.SERIES[0], line=dict(color=theme.SURFACE, width=2)),
            hovertemplate="<b>%{y}</b><br>Spend %{x:$,.2f}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text="Spend")
    theme.style_figure(figure, height=380, legend=False)
    st.plotly_chart(figure, width="stretch")

    theme.caption(
        f"Top 12 of {len(grouped)} touchpoints by spend. "
        "The table below carries every row."
    )
    common.table_view(grouped, "View all touchpoints as a table")


def _bridge(bridge: pd.DataFrame) -> None:
    """The touchpoint-to-Campaign links and their assisted outcomes."""
    if bridge.empty:
        common.empty_notice("entity bridge rows")
        return

    st.markdown("## Assisted outcomes by Campaign")

    filters = st.columns([1, 1, 2])
    with filters[0]:
        scoped = common.multiselect_filter(bridge, "campaign_id", "Campaign")
    with filters[1]:
        scoped = common.multiselect_filter(scoped, "ad_group_id", "Ad Group")

    if scoped.empty:
        st.warning("No rows match the current filters.")
        return

    grouped = (
        scoped.groupby("campaign_id")[
            [
                "assisted_converted_users",
                "assisted_purchase_count",
                "assisted_revenue",
                "cost",
                "unique_users",
            ]
        ]
        .sum()
        .reset_index()
    )

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=grouped["campaign_id"],
            y=grouped["assisted_revenue"],
            name="Assisted revenue",
            marker=dict(color=theme.SERIES[0], line=dict(color=theme.SURFACE, width=2)),
            hovertemplate="<b>%{x}</b><br>Assisted revenue %{y:$,.2f}<extra></extra>",
        )
    )
    figure.update_yaxes(title_text="Assisted revenue")
    theme.style_figure(figure, height=300, legend=False)
    st.plotly_chart(figure, width="stretch")

    theme.caption(
        "Assisted outcomes credit every touchpoint on a converting journey, so "
        "they sum to more than the reported total. They apportion, not add."
    )

    st.dataframe(
        scoped[
            [
                "campaign_id",
                "ad_group_id",
                "touchpoint",
                "keyword_text",
                "match_type",
                "unique_users",
                "journey_count",
                "cost",
                "assisted_converted_users",
                "assisted_purchase_count",
                "assisted_revenue",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "campaign_id": st.column_config.TextColumn("Campaign"),
            "ad_group_id": st.column_config.TextColumn("Ad Group"),
            "touchpoint": st.column_config.TextColumn("Touchpoint", width="medium"),
            "keyword_text": st.column_config.TextColumn("Keyword"),
            "match_type": st.column_config.TextColumn("Match"),
            "unique_users": st.column_config.NumberColumn("Users"),
            "journey_count": st.column_config.NumberColumn("Journeys"),
            "cost": st.column_config.NumberColumn("Cost", format="%.2f"),
            "assisted_converted_users": st.column_config.NumberColumn(
                "Assisted users", format="%.0f"
            ),
            "assisted_purchase_count": st.column_config.NumberColumn(
                "Assisted purchases", format="%.0f"
            ),
            "assisted_revenue": st.column_config.NumberColumn(
                "Assisted revenue", format="%.2f"
            ),
        },
    )


def _paths(paths: pd.DataFrame) -> None:
    """Aggregated conversion paths and how path length relates to conversion."""
    if paths.empty:
        common.empty_notice("conversion paths")
        return

    st.markdown("## Conversion paths")

    totals = st.columns(4)
    totals[0].metric("Distinct paths", theme.number(len(paths)))
    totals[1].metric("Users", theme.number(paths["users"].sum()))
    totals[2].metric("Converted users", theme.number(paths["converted_users"].sum()))
    totals[3].metric("Revenue", theme.money(paths["revenue"].sum()))

    by_length = (
        paths.groupby("path_length")[["users", "converted_users", "revenue"]]
        .sum()
        .reset_index()
    )
    by_length["conversion_rate"] = (
        by_length["converted_users"] / by_length["users"]
    ).fillna(0)

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=by_length["path_length"],
            y=by_length["conversion_rate"],
            marker=dict(color=theme.SERIES[0], line=dict(color=theme.SURFACE, width=2)),
            text=[f"{value:.1%}" for value in by_length["conversion_rate"]],
            textposition="outside",
            textfont=dict(size=11, color=theme.MUTED),
            hovertemplate=(
                "<b>%{x} touchpoints</b><br>Conversion rate %{y:.2%}<extra></extra>"
            ),
        )
    )
    figure.update_xaxes(title_text="Touchpoints on the path", dtick=1)
    figure.update_yaxes(title_text="Conversion rate", tickformat=".0%")
    theme.style_figure(figure, height=300, legend=False)
    st.plotly_chart(figure, width="stretch")

    theme.caption(
        "Longer paths convert more often here, which is why last-touch "
        "attribution understates the touchpoints that open a journey."
    )

    search = st.text_input(
        "Search paths", placeholder="e.g. SPONSORED_PRODUCTS, or CLICK"
    )
    listed = paths
    if search:
        listed = paths[paths["path"].str.contains(search, case=False, na=False)]

    st.dataframe(
        listed.sort_values("revenue", ascending=False)[
            ["path", "path_length", "users", "converted_users", "purchase_count", "revenue"]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "path": st.column_config.TextColumn("Path", width="large"),
            "path_length": st.column_config.NumberColumn("Length"),
            "users": st.column_config.NumberColumn("Users"),
            "converted_users": st.column_config.NumberColumn("Converted"),
            "purchase_count": st.column_config.NumberColumn("Purchases"),
            "revenue": st.column_config.NumberColumn("Revenue", format="%.2f"),
        },
    )
    theme.caption(f"{len(listed):,} of {len(paths):,} paths shown.")
