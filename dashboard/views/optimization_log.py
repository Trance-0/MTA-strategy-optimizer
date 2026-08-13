"""Optimization Log: the run record and its provenance.

The reference design shows an audit trail of optimisation actions. No module in
this project writes such a trail, so rather than invent placeholder entries
this view shows the real record that does exist: which attribution run produced
the evidence, which files it hashed, and which budget run consumed it. That is
the same question -- what happened, and can it be reproduced -- answered from
data instead of from a mock.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import data_source, theme
from dashboard.views import common


def render() -> None:
    st.markdown("# Optimization Log")
    st.markdown(
        '<p class="caption">Provenance of the current numbers: which run '
        "produced them, over which window, from which inputs.</p>",
        unsafe_allow_html=True,
    )

    budget = data_source.load_budget_recommendation()
    request = data_source.load_strategy_request()
    summary = data_source.load_comparison_summary()
    comparison = data_source.load_comparison_touchpoints()

    _run_record(budget, request, summary)
    _stage_trail(budget, request, summary, comparison)
    _flag_detail(comparison)


def _run_record(budget: dict, request: dict, summary: pd.DataFrame) -> None:
    """Identifiers and the report window the run covered."""
    st.markdown("## Run record")

    snapshot = budget.get("mta_source_snapshot", {}) or request.get("mta_source", {})
    window_start = snapshot.get("report_start_date", "--")
    window_end = snapshot.get("report_end_date", "--")

    if not summary.empty:
        row = summary.iloc[0]
        if pd.notna(row.get("report_start_date")):
            window_start = str(row["report_start_date"])[:10]
            window_end = str(row["report_end_date"])[:10]

    left, right = st.columns(2)
    with left:
        theme.panel(
            "Attribution run",
            [
                ("Batch", budget.get("mta_batch_id", "--")),
                ("Window", f"{window_start} to {window_end}"),
                ("Marketplace", snapshot.get("marketplace", "--")),
                ("Advertiser", snapshot.get("advertiser_id", "--")),
                (
                    "Touchpoint gap",
                    f"{int(summary.iloc[0]['max_touchpoint_gap_days'])} days"
                    if not summary.empty
                    and pd.notna(summary.iloc[0].get("max_touchpoint_gap_days"))
                    else "--",
                ),
            ],
        )
    with right:
        theme.panel(
            "Budget run",
            [
                ("Schema", budget.get("schema_version", "--")),
                ("Campaign Group", budget.get("campaign_group_id", "--")),
                ("Candidate pool", budget.get("candidate_pool_id", "--")),
                ("Type", budget.get("recommendation_type", "--")),
                ("Handoff", budget.get("handoff_status", "--")),
            ],
        )

    hashes = [
        ("Attribution input", snapshot.get("attribution_sha256")),
        ("Entity input", snapshot.get("entity_sha256")),
    ]
    theme.panel(
        "Input digests",
        [
            (label, f"<code style='font-size:.72rem'>{value}</code>")
            for label, value in hashes
            if value
        ]
        or [("Not recorded", "--")],
    )
    theme.caption(
        "The digests identify the exact input files. A recommendation can be "
        "traced back to the attribution output that justified it."
    )


def _stage_trail(
    budget: dict, request: dict, summary: pd.DataFrame, comparison: pd.DataFrame
) -> None:
    """The pipeline stages that ran, in order, with what each produced."""
    st.markdown("## Pipeline stages")

    campaigns = budget.get("campaigns", [])
    slots = sum(len(entry.get("recommended_ad_groups", [])) for entry in campaigns)
    reliable = (
        int((summary["reliability_status"] == "RELIABLE").sum())
        if not summary.empty
        else 0
    )

    stages = pd.DataFrame(
        [
            {
                "stage": "1. Standardisation",
                "produced": "Five-segment touchpoint keys",
                "count": comparison["touchpoint"].nunique() if not comparison.empty else 0,
                "status": "COMPLETE",
            },
            {
                "stage": "2. Attribution",
                "produced": "Markov and Shapley shares per touchpoint",
                "count": len(comparison),
                "status": "COMPLETE",
            },
            {
                "stage": "3. Comparison",
                "produced": "Reliability verdict per outcome",
                "count": len(summary),
                "status": f"{reliable}/{len(summary)} RELIABLE" if len(summary) else "--",
            },
            {
                "stage": "4. Budget seed",
                "produced": "Campaign budgets and Ad Group slots",
                "count": len(campaigns),
                "status": budget.get("handoff_status", "--"),
            },
            {
                "stage": "5. Optimisation",
                "produced": "Optimised allocation",
                "count": 0,
                "status": "NOT RUN",
            },
        ]
    )

    st.dataframe(
        stages,
        hide_index=True,
        width="stretch",
        column_config={
            "stage": st.column_config.TextColumn("Stage", width="medium"),
            "produced": st.column_config.TextColumn("Produced", width="large"),
            "count": st.column_config.NumberColumn("Rows"),
            "status": st.column_config.TextColumn("Status"),
        },
    )
    theme.caption(
        f"Stage 5 has not run: <code>is_optimized</code> is "
        f"<b>{str(budget.get('is_optimized', False)).lower()}</b>. The current "
        f"allocation across {len(campaigns)} Campaigns and {slots} Ad Group "
        "slots is a deterministic seed derived from historical attribution."
    )

    warnings = budget.get("warnings", [])
    if warnings:
        st.markdown("### Warnings raised")
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("The budget run completed with no warnings.")


def _flag_detail(comparison: pd.DataFrame) -> None:
    """Which reliability flags each touchpoint passed."""
    st.markdown("## Reliability flags by touchpoint")

    if comparison.empty:
        common.empty_notice("comparison rows")
        return

    outcome = common.outcome_selector("log_outcome")
    scoped = comparison[comparison["outcome"] == outcome].copy()
    if scoped.empty:
        common.empty_notice(f"rows for {outcome}")
        return

    scoped["touchpoint_label"] = scoped["touchpoint"].map(common.short_touchpoint)
    st.dataframe(
        scoped[
            [
                "touchpoint_label",
                "calculation_valid",
                "data_support_sufficient",
                "models_consistent",
                "reliability_status",
                "reliability_reason",
            ]
        ].sort_values("reliability_status"),
        hide_index=True,
        width="stretch",
        column_config={
            "touchpoint_label": st.column_config.TextColumn(
                "Touchpoint", width="medium"
            ),
            "calculation_valid": st.column_config.CheckboxColumn("Calculation"),
            "data_support_sufficient": st.column_config.CheckboxColumn("Data support"),
            "models_consistent": st.column_config.CheckboxColumn("Consistent"),
            "reliability_status": st.column_config.TextColumn("Verdict"),
            "reliability_reason": st.column_config.TextColumn("Reason", width="large"),
        },
    )
    theme.caption(
        "The verdict is the AND of the three flags. One false flag makes the "
        "row UNRELIABLE regardless of how close the two models happen to be."
    )
