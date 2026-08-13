"""Knowledge Base: the vocabulary and rules the numbers obey.

The reference design's Knowledge Base holds an ontology. This project has a
real one -- the five-segment touchpoint key, the three outcomes, the capacity
rules, and the reliability contract -- so the view is populated from the data
and configuration actually in use rather than from prose. Every entry here is
read from the current source, so it cannot drift from what the charts show.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import config, data_source, theme
from dashboard.views import common

#: What each segment of the touchpoint key means. The values are read from the
#: data; these are the definitions that give them meaning.
SEGMENT_NOTES = {
    "ad_product": "Which Amazon ad product served the impression or click.",
    "format": "The ad or inventory type. UNSPECIFIED when the product has none.",
    "placement": "Where it appeared. UNSPECIFIED for products without placement.",
    "creative": "The creative type. UNSPECIFIED when not reported.",
    "interaction_type": "IMPRESSION or CLICK. Decides which cost type applies.",
}


def render() -> None:
    st.markdown("# Knowledge Base")
    st.markdown(
        '<p class="caption">The vocabulary and rules behind every number in '
        "this dashboard, read from the data in use.</p>",
        unsafe_allow_html=True,
    )

    attribution = data_source.load_attribution_results()
    request = data_source.load_strategy_request()
    pool = data_source.load_candidate_pool()

    vocabulary, rules, entities, sources = st.tabs(
        ["Touchpoint vocabulary", "Rules", "Entities", "Data sources"]
    )
    with vocabulary:
        _vocabulary(attribution)
    with rules:
        _rules(request)
    with entities:
        _entities(request, pool)
    with sources:
        _sources()


def _vocabulary(attribution: pd.DataFrame) -> None:
    """The five key segments and every value each one takes."""
    st.markdown("## The five-segment touchpoint key")
    st.markdown(
        f"""
        <div class="panel">
          <code style="font-size:.86rem;color:{theme.BLUE}">
            AD_PRODUCT : FORMAT : PLACEMENT : CREATIVE : INTERACTION_TYPE
          </code>
          <p class="caption" style="margin-top:8px">
            One key identifies one kind of interaction. Every attributed value,
            every spend row, and every path step is expressed in these keys, so
            attribution and spend can be compared without a join key of their
            own.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if attribution.empty:
        common.empty_notice("touchpoint values")
        return

    rows = []
    for segment, note in SEGMENT_NOTES.items():
        if segment not in attribution.columns:
            continue
        values = sorted(attribution[segment].dropna().unique())
        rows.append(
            {
                "segment": common.pretty(segment),
                "meaning": note,
                "distinct": len(values),
                "values": ", ".join(values),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "segment": st.column_config.TextColumn("Segment"),
            "meaning": st.column_config.TextColumn("Meaning", width="large"),
            "distinct": st.column_config.NumberColumn("Values"),
            "values": st.column_config.TextColumn("Observed", width="large"),
        },
    )

    st.markdown("## Touchpoints in the current window")
    keys = sorted(attribution["touchpoint"].unique())
    st.dataframe(
        pd.DataFrame(
            {"touchpoint": keys, "reads as": [common.short_touchpoint(k) for k in keys]}
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "touchpoint": st.column_config.TextColumn("Key", width="large"),
            "reads as": st.column_config.TextColumn("Reads as", width="medium"),
        },
    )


def _rules(request: dict) -> None:
    """The reliability contract and the per-product capacity rules."""
    st.markdown("## Reliability contract")

    st.markdown(
        f"""
        <div class="panel">
          <div class="kv"><span>calculation_valid</span>
            <span>The arithmetic held: shares are finite and sum to one.</span></div>
          <div class="kv"><span>data_support_sufficient</span>
            <span>Enough observed journeys to support the estimate.</span></div>
          <div class="kv"><span>models_consistent</span>
            <span>Markov and Shapley agree within tolerance.</span></div>
          <div class="kv"><span>Verdict</span>
            <span><b>AND of all three.</b> One false flag means UNRELIABLE.</span></div>
        </div>
        <p class="caption">
          Diagnostics -- total variation distance, Spearman correlation, Top-K
          overlap -- inform the reader but never change the verdict. An
          UNRELIABLE row carries an interval instead of a point value and
          grants no budgeting authority.
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## Outcomes")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "outcome": label,
                    "key": key,
                    "share column": common.OUTCOME_SHARE_COLUMNS[key],
                    "attributed column": common.OUTCOME_VALUE_COLUMNS[key],
                }
                for key, label in common.OUTCOME_LABELS.items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    theme.caption(
        "Every outcome is attributed independently. A touchpoint can lead on "
        "revenue and trail on converted users; neither is derived from the other."
    )

    st.markdown("## Capacity rules")
    rules = request.get("capacity_rules", {})
    if not rules:
        st.info(
            "Capacity rules are pipeline configuration rather than observed "
            "data, so they are not stored in the database. Switch `DATABASE` "
            "to `false` in `.env` to read them from `strategy_request.json`."
        )
        return

    frame = pd.DataFrame(rules).T.reset_index().rename(columns={"index": "ad_product"})
    st.dataframe(frame, hide_index=True, width="stretch")
    theme.caption(
        "These caps decide how many Ad Groups a Campaign can support, which in "
        "turn sets its minimum required daily budget."
    )


def _entities(request: dict, pool: dict) -> None:
    """The advertising hierarchy and the eligible targeting objects."""
    st.markdown("## Advertising hierarchy")

    group = request.get("campaign_group", {})
    theme.panel(
        "Campaign Group",
        [
            ("Identifier", group.get("campaign_group_id", "--")),
            ("Name", group.get("group_name", "--")),
            ("Platform", group.get("platform", "--")),
            ("Marketplace", group.get("marketplace", "--")),
            ("Advertiser", group.get("advertiser_id", "--")),
            (
                "Total daily budget",
                theme.money(
                    group.get("total_daily_budget", 0.0),
                    common.currency_symbol(group.get("currency", "USD")),
                ),
            ),
        ],
    )

    campaigns = request.get("campaigns", [])
    if campaigns:
        st.dataframe(
            pd.DataFrame(campaigns),
            hide_index=True,
            width="stretch",
            column_config={
                "campaign_id": st.column_config.TextColumn("Campaign"),
                "campaign_name": st.column_config.TextColumn("Name", width="medium"),
                "ad_product": st.column_config.TextColumn("Ad product"),
                "status": st.column_config.TextColumn("Status"),
            },
        )
        theme.caption(
            "A Campaign carries exactly one ad product, which is why the ad "
            "product is the level at which attribution evidence is bridged "
            "into budget shares."
        )

    st.markdown("## Eligible targeting candidates")
    counts = pool.get("campaign_candidate_counts", [])
    if not counts:
        common.empty_notice("candidate counts")
        return

    st.dataframe(
        pd.DataFrame(counts), hide_index=True, width="stretch"
    )
    policy = pool.get("candidate_usage_policy", "--")
    theme.caption(
        f"Usage policy: <b>{policy}</b>. These counts drive the capacity "
        "calculation that decides how many new Ad Groups each Campaign "
        "can support."
    )


def _sources() -> None:
    """Where the current numbers are being read from."""
    st.markdown("## Active source")

    theme.panel(
        "Mode",
        [
            ("DATABASE", "true" if config.use_database() else "false"),
            ("Reading from", data_source.source_label()),
        ],
    )

    st.markdown("## Artifacts")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "artifact": "amazon_ads_report_sample.csv",
                    "layer": "History",
                    "provides": "Daily spend, impressions, clicks, and reported sales",
                },
                {
                    "artifact": "amc_mta_path_report_raw_sample.csv",
                    "layer": "History",
                    "provides": "Aggregated conversion paths",
                },
                {
                    "artifact": "amc_touchpoint_entity_aggregate_sample.csv",
                    "layer": "History",
                    "provides": "Touchpoint to Campaign and Ad Group bridge",
                },
                {
                    "artifact": "amc_markov_attribution_results.csv",
                    "layer": "Model output",
                    "provides": "Markov shares, attributed totals, efficiency",
                },
                {
                    "artifact": "amc_shapley_attribution_results.csv",
                    "layer": "Model output",
                    "provides": "Shapley shares, attributed totals, efficiency",
                },
                {
                    "artifact": "amc_mta_model_comparison_touchpoints.csv",
                    "layer": "Model output",
                    "provides": "Per-touchpoint gaps and reliability flags",
                },
                {
                    "artifact": "amc_mta_model_comparison_summary.csv",
                    "layer": "Model output",
                    "provides": "Per-outcome diagnostics and verdict",
                },
                {
                    "artifact": "amc_mta_recommended_attribution.csv",
                    "layer": "Model output",
                    "provides": "The governed value per touchpoint",
                },
                {
                    "artifact": "strategy_request.json",
                    "layer": "Entity",
                    "provides": "Campaign Group, Campaigns, weights, capacity rules",
                },
                {
                    "artifact": "candidate_pool.json",
                    "layer": "Entity",
                    "provides": "Eligible targeting object counts",
                },
                {
                    "artifact": "initial_budget_recommendation.json",
                    "layer": "Strategy",
                    "provides": "Campaign budgets and Ad Group slots",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "artifact": st.column_config.TextColumn("Artifact", width="medium"),
            "layer": st.column_config.TextColumn("Layer"),
            "provides": st.column_config.TextColumn("Provides", width="large"),
        },
    )
    theme.caption(
        "The dashboard reads these artifacts and never recomputes their "
        "values, so it cannot become a second, divergent implementation of "
        "the pipeline."
    )
