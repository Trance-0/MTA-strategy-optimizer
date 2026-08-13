"""Campaign Optimizer: what each model predicts, and what the shift implies.

The two models disagree by construction -- Markov measures removal effect,
Shapley measures average marginal contribution -- so this view puts them side
by side per touchpoint and shows the governed recommendation between them. The
budget-shift panel then reads the recommendation forward: if spend followed
attributed credit rather than its current split, which touchpoints would gain
and which would give up budget.

The shift is a restatement of the recommendation, not a new model. It never
overrides the pipeline's own allocation, and it is disabled outright when the
outcome's reliability verdict is UNRELIABLE.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import data_source, theme
from dashboard.views import common


def render() -> None:
    st.markdown("# Campaign Optimizer")
    st.markdown(
        '<p class="caption">Model predictions per touchpoint, and the budget '
        "shift implied by moving spend toward attributed credit.</p>",
        unsafe_allow_html=True,
    )

    comparison = data_source.load_comparison_touchpoints()
    recommended = data_source.load_recommended_attribution()
    summary = data_source.load_comparison_summary()
    attribution = data_source.load_attribution_results()

    if comparison.empty or recommended.empty:
        common.empty_notice("model comparison output")
        return

    outcome = common.outcome_selector("optimizer_outcome")
    verdict = summary[summary["outcome"] == outcome]
    status = verdict.iloc[0]["reliability_status"] if not verdict.empty else "UNKNOWN"
    reason = verdict.iloc[0]["reliability_reason"] if not verdict.empty else ""
    common.reliability_banner(status, reason)

    _model_comparison(comparison, outcome)
    _recommended_table(recommended, outcome)
    _budget_shift(attribution, recommended, outcome, status)


def _model_comparison(comparison: pd.DataFrame, outcome: str) -> None:
    """Markov against Shapley for every touchpoint, largest gap first."""
    st.markdown("## Markov against Shapley")

    scoped = comparison[comparison["outcome"] == outcome].copy()
    if scoped.empty:
        common.empty_notice(f"comparison rows for {outcome}")
        return

    scoped = scoped.sort_values("markov_share")
    labels = [common.short_touchpoint(key) for key in scoped["touchpoint"]]

    figure = go.Figure()
    for column, model in (("markov_share", "markov"), ("shapley_share", "shapley")):
        figure.add_trace(
            go.Bar(
                y=labels,
                x=scoped[column],
                name=model.title(),
                orientation="h",
                marker=dict(
                    color=theme.MODEL_COLORS[model],
                    line=dict(color=theme.SURFACE, width=2),
                ),
                hovertemplate=(
                    f"<b>{model.title()}</b><br>%{{y}}<br>"
                    "Share %{x:.2%}<extra></extra>"
                ),
            )
        )
    figure.update_xaxes(title_text="Attributed share", tickformat=".0%")
    theme.style_figure(figure, height=460)
    figure.update_layout(barmode="group", bargroupgap=0.08)
    st.plotly_chart(figure, width="stretch")

    largest = scoped.reindex(scoped["gap_pp"].abs().sort_values(ascending=False).index)
    theme.caption(
        "Where the two bars differ, the models disagree about how much credit "
        f"a touchpoint deserves. Largest gap: "
        f"<b>{common.short_touchpoint(largest.iloc[0]['touchpoint'])}</b> at "
        f"{largest.iloc[0]['gap_pp']:.2f} percentage points."
    )
    common.table_view(
        largest[
            [
                "touchpoint",
                "markov_share",
                "shapley_share",
                "gap_pp",
                "relative_gap",
                "raw_converted_users",
                "reliability_status",
            ]
        ],
        "View comparison as a table",
    )


def _recommended_table(recommended: pd.DataFrame, outcome: str) -> None:
    """The governed value: a point when reliable, an interval when not."""
    st.markdown("## Recommended attribution")

    scoped = recommended[recommended["outcome"] == outcome].copy()
    if scoped.empty:
        common.empty_notice(f"recommended rows for {outcome}")
        return

    scoped = scoped.sort_values("official_share", ascending=False)
    scoped["touchpoint_label"] = scoped["touchpoint"].map(common.short_touchpoint)

    st.dataframe(
        scoped[
            [
                "touchpoint_label",
                "official_model",
                "official_share",
                "recommended_value",
                "benchmark_model",
                "benchmark_share",
                "gap_pp",
                "reliability_status",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "touchpoint_label": st.column_config.TextColumn(
                "Touchpoint", width="medium"
            ),
            "official_model": st.column_config.TextColumn("Official"),
            "official_share": st.column_config.NumberColumn(
                "Official share", format="%.4f"
            ),
            "recommended_value": st.column_config.TextColumn("Recommended"),
            "benchmark_model": st.column_config.TextColumn("Benchmark"),
            "benchmark_share": st.column_config.NumberColumn(
                "Benchmark share", format="%.4f"
            ),
            "gap_pp": st.column_config.NumberColumn("Gap (pp)", format="%.2f"),
            "reliability_status": st.column_config.TextColumn("Reliability"),
        },
    )
    theme.caption(
        "A RELIABLE row carries the official model's point value. An UNRELIABLE "
        "row carries the closed interval between the two models instead, and "
        "grants no budgeting authority."
    )


def _budget_shift(
    attribution: pd.DataFrame,
    recommended: pd.DataFrame,
    outcome: str,
    status: str,
) -> None:
    """Current spend split against the split implied by attributed credit."""
    st.markdown("## Implied budget shift")

    if str(status).upper() == "UNRELIABLE":
        st.warning(
            "This outcome is **UNRELIABLE**, so no budget shift is shown. "
            "The recommended value is an interval, and an interval cannot "
            "carry a spend split."
        )
        return

    scoped = recommended[recommended["outcome"] == outcome][
        ["touchpoint", "official_share"]
    ].copy()
    spend = (
        attribution[attribution["attribution_model"] == "markov"]
        .groupby("touchpoint")["cost"]
        .sum()
        .reset_index()
    )
    merged = scoped.merge(spend, on="touchpoint", how="inner")
    total_spend = float(merged["cost"].sum())
    if merged.empty or not total_spend:
        common.empty_notice("spend to compare against")
        return

    share_total = float(merged["official_share"].sum())
    merged["current_share"] = merged["cost"] / total_spend
    merged["target_share"] = merged["official_share"] / share_total
    merged["delta_pp"] = (merged["target_share"] - merged["current_share"]) * 100
    merged["implied_budget"] = merged["target_share"] * total_spend
    merged["delta_budget"] = merged["implied_budget"] - merged["cost"]

    control = st.columns([1, 3])
    with control[0]:
        top_n = st.slider("Touchpoints shown", 5, len(merged), min(10, len(merged)))

    ordered = merged.reindex(merged["delta_pp"].abs().sort_values().index).tail(top_n)
    labels = [common.short_touchpoint(key) for key in ordered["touchpoint"]]
    colors = [
        theme.SERIES[2] if value >= 0 else theme.SERIES[7]
        for value in ordered["delta_pp"]
    ]

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            y=labels,
            x=ordered["delta_pp"],
            orientation="h",
            marker=dict(color=colors, line=dict(color=theme.SURFACE, width=2)),
            customdata=ordered[["cost", "implied_budget", "delta_budget"]],
            hovertemplate=(
                "<b>%{y}</b><br>Shift %{x:+.2f} pp<br>"
                "Current spend %{customdata[0]:$,.2f}<br>"
                "Implied spend %{customdata[1]:$,.2f}<br>"
                "Change %{customdata[2]:+$,.2f}<extra></extra>"
            ),
        )
    )
    figure.add_vline(x=0, line=dict(color=theme.AXIS, width=1))
    figure.update_xaxes(title_text="Change in spend share (percentage points)")
    theme.style_figure(figure, height=max(320, 26 * top_n + 90), legend=False)
    st.plotly_chart(figure, width="stretch")

    gainers = merged[merged["delta_pp"] > 0]
    totals = st.columns(4)
    totals[0].metric("Spend re-allocated", theme.money(
        merged.loc[merged["delta_budget"] > 0, "delta_budget"].sum()
    ))
    totals[1].metric("Touchpoints gaining", theme.number(len(gainers)))
    totals[2].metric("Touchpoints reduced", theme.number(len(merged) - len(gainers)))
    totals[3].metric(
        "Largest single shift", f"{merged['delta_pp'].abs().max():.2f} pp"
    )

    theme.caption(
        "Green gains share, red gives it up. This restates the recommended "
        "attribution as a spend split at constant total budget; it does not "
        "predict the outcome of making the change, and it does not replace the "
        "allocation in the Budget Manager view."
    )
    common.table_view(
        merged.sort_values("delta_pp", ascending=False)[
            [
                "touchpoint",
                "cost",
                "current_share",
                "target_share",
                "implied_budget",
                "delta_budget",
                "delta_pp",
            ]
        ],
        "View the implied shift as a table",
    )
