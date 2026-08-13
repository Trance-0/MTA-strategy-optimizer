"""Budget Manager: the recommended allocation and how it was derived.

Shows the initial daily budget the strategy module proposes for each Campaign,
the MTA score that produced each share, and the Ad Group slots the budget is
divided into. The derivation is on the page rather than behind a link, because
a budget number without its basis invites the reader to trust it blindly.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data_source, theme
from dashboard.views import common


def render() -> None:
    st.markdown("# Budget Manager")
    st.markdown(
        '<p class="caption">Deterministic initial allocation derived from '
        "historical attribution. This is a seed, not an optimiser result.</p>",
        unsafe_allow_html=True,
    )

    budget = data_source.load_budget_recommendation()
    request = data_source.load_strategy_request()

    if not budget or not budget.get("campaigns"):
        common.empty_notice("budget recommendation")
        return

    group = request.get("campaign_group", {})
    currency = common.currency_symbol(group.get("currency", "USD"))
    campaigns = pd.DataFrame(_flatten(budget))

    _header(budget, group, campaigns, currency)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.5, 1])
    with left:
        _allocation_chart(campaigns, currency)
    with right:
        _derivation_panel(budget, request)

    _score_to_budget(campaigns, currency)
    _slots(budget, currency)


def _flatten(budget: dict) -> list[dict]:
    """Flatten the nested recommendation into one row per Campaign."""
    rows = []
    for entry in budget.get("campaigns", []):
        contributions = entry.get("outcome_contributions", {})
        bridge = entry.get("bridge_summary", {})
        rows.append(
            {
                "campaign_id": entry["campaign_id"],
                "mta_score": float(entry.get("campaign_mta_score", 0.0)),
                "budget_share": float(entry.get("budget_seed_share", 0.0)),
                "daily_budget": float(entry.get("campaign_budget_seed", 0.0)),
                "minimum_required": float(
                    entry.get("minimum_required_daily_budget", 0.0)
                ),
                "ad_groups": int(entry.get("recommended_ad_group_count", 0)),
                "converted_users": float(contributions.get("converted_users", 0.0)),
                "purchase_count": float(contributions.get("purchase_count", 0.0)),
                "revenue": float(contributions.get("revenue", 0.0)),
                "historical_ad_groups": int(
                    bridge.get("historical_ad_group_count", 0)
                ),
                "touchpoints": int(bridge.get("touchpoint_count", 0)),
                "fallback_used": bool(bridge.get("fallback_used", False)),
                "execution_status": entry.get("execution_status", ""),
            }
        )
    return rows


def _header(budget: dict, group: dict, campaigns: pd.DataFrame, currency: str) -> None:
    """Handoff state and the four headline totals."""
    status = budget.get("handoff_status", "UNKNOWN")
    executable = (campaigns["execution_status"] == "EXECUTABLE").sum()
    common.reliability_banner(
        "RELIABLE" if status == "READY_FOR_OPTIMIZATION" else "PARTIAL",
        f"Handoff status <b>{status}</b> &nbsp;·&nbsp; {executable} of "
        f"{len(campaigns)} Campaigns executable &nbsp;·&nbsp; "
        f"recommendation type <b>{budget.get('recommendation_type', '--')}</b>.",
    )

    columns = st.columns(4)
    columns[0].metric(
        "Total daily budget", theme.money(budget.get("budget_seed_total", 0.0), currency)
    )
    columns[1].metric("Campaigns", theme.number(len(campaigns)))
    columns[2].metric("New Ad Group slots", theme.number(campaigns["ad_groups"].sum()))
    columns[3].metric(
        "Group budget",
        theme.money(group.get("total_daily_budget", 0.0), currency),
        help="The Campaign Group's own total, from the strategy request.",
    )


def _allocation_chart(campaigns: pd.DataFrame, currency: str) -> None:
    """Recommended daily budget per Campaign, against the required minimum."""
    st.markdown("## Recommended daily budget")

    ordered = campaigns.sort_values("daily_budget")
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            y=ordered["campaign_id"],
            x=ordered["daily_budget"],
            name="Recommended",
            orientation="h",
            marker=dict(
                color=theme.SERIES[0], line=dict(color=theme.SURFACE, width=2)
            ),
            text=[theme.money(value, currency) for value in ordered["daily_budget"]],
            textposition="outside",
            textfont=dict(size=11, color=theme.MUTED),
            hovertemplate=(
                "<b>%{y}</b><br>Recommended %{x:,.2f}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            y=ordered["campaign_id"],
            x=ordered["minimum_required"],
            name="Required minimum",
            mode="markers",
            marker=dict(
                color=theme.SERIES[7],
                size=11,
                symbol="line-ns",
                line=dict(color=theme.SERIES[7], width=3),
            ),
            hovertemplate="Minimum required %{x:,.2f}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text=f"Daily budget ({currency.strip()})")
    theme.style_figure(figure, height=300)
    st.plotly_chart(figure, width="stretch")

    theme.caption(
        "Every recommended budget clears its Campaign's required minimum, "
        "which is the per-Ad-Group floor times the recommended slot count."
    )


def _derivation_panel(budget: dict, request: dict) -> None:
    """The formula, weights, and universe the allocation came from."""
    st.markdown("## Derivation")

    derivation = budget.get("budget_derivation", {})
    weights = derivation.get("outcome_weights", {}) or request.get(
        "outcome_weights", {}
    )

    theme.panel(
        "Formula",
        [
            ("Version", derivation.get("formula_version", "--")),
            ("Normalisation", derivation.get("normalization_universe", "--")),
            ("Optimised", "No" if not budget.get("is_optimized") else "Yes"),
            ("Schema", budget.get("schema_version", "--")),
        ],
    )
    theme.panel(
        "Outcome weights",
        [
            (common.OUTCOME_LABELS.get(key, key), f"{float(value):.2f}")
            for key, value in weights.items()
        ]
        or [("Not recorded", "--")],
    )
    theme.caption(
        "The MTA score is the weighted sum of a Campaign's three normalised "
        "outcome contributions. Budget share is that score, renormalised."
    )


def _score_to_budget(campaigns: pd.DataFrame, currency: str) -> None:
    """How each outcome contributed to each Campaign's score."""
    st.markdown("## Score composition")

    ordered = campaigns.sort_values("mta_score", ascending=False)
    figure = go.Figure()
    for outcome, label in common.OUTCOME_LABELS.items():
        figure.add_trace(
            go.Bar(
                x=ordered["campaign_id"],
                y=ordered[outcome],
                name=label,
                marker=dict(
                    color=theme.OUTCOME_COLORS[outcome],
                    line=dict(color=theme.SURFACE, width=2),
                ),
                hovertemplate=(
                    f"<b>{label}</b><br>%{{x}}<br>"
                    "Contribution %{y:.4f}<extra></extra>"
                ),
            )
        )
    figure.update_yaxes(title_text="Normalised outcome contribution")
    theme.style_figure(figure, height=300)
    figure.update_layout(barmode="stack")
    st.plotly_chart(figure, width="stretch")

    theme.caption(
        "Stacked contributions before weighting. A Campaign leading on revenue "
        "but trailing on converted users is visible here, not in the total."
    )

    display = ordered[
        [
            "campaign_id",
            "mta_score",
            "budget_share",
            "daily_budget",
            "minimum_required",
            "ad_groups",
            "historical_ad_groups",
            "touchpoints",
            "execution_status",
        ]
    ]
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "campaign_id": st.column_config.TextColumn("Campaign"),
            "mta_score": st.column_config.NumberColumn("MTA score", format="%.6f"),
            "budget_share": st.column_config.NumberColumn("Share", format="%.4f"),
            "daily_budget": st.column_config.NumberColumn(
                "Daily budget", format="%.2f"
            ),
            "minimum_required": st.column_config.NumberColumn(
                "Minimum", format="%.2f"
            ),
            "ad_groups": st.column_config.NumberColumn("New slots"),
            "historical_ad_groups": st.column_config.NumberColumn("Historical"),
            "touchpoints": st.column_config.NumberColumn("Touchpoints"),
            "execution_status": st.column_config.TextColumn("Status"),
        },
    )


def _slots(budget: dict, currency: str) -> None:
    """The anonymous Ad Group slots the Campaign budget is divided into."""
    st.markdown("## Ad Group slots")

    rows = []
    for entry in budget.get("campaigns", []):
        for slot in entry.get("recommended_ad_groups", []):
            rows.append(
                {
                    "campaign_id": entry["campaign_id"],
                    "slot": slot.get("ad_group_slot_id", ""),
                    "basis": slot.get("allocation_basis", ""),
                    "share": float(slot.get("budget_seed_share", 0.0)),
                    "daily_budget": float(slot.get("initial_daily_budget", 0.0)),
                }
            )

    if not rows:
        common.empty_notice("Ad Group slots")
        return

    frame = pd.DataFrame(rows)
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        column_config={
            "campaign_id": st.column_config.TextColumn("Campaign"),
            "slot": st.column_config.TextColumn("Slot"),
            "basis": st.column_config.TextColumn("Allocation basis"),
            "share": st.column_config.NumberColumn("Share", format="%.4f"),
            "daily_budget": st.column_config.NumberColumn(
                "Daily budget", format="%.2f"
            ),
        },
    )
    theme.caption(
        "Slots are anonymous: a proposed Ad Group has no history yet, so it "
        "carries no historical identifier."
    )
