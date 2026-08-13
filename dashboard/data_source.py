"""Dual-mode data access for the dashboard.

Every view calls the loader functions here and never touches a file path or a
SQL statement itself. Each function returns the same DataFrame columns, dtypes,
and values in both modes, so a view cannot tell whether `DATABASE` was true or
false. Three differences make that non-trivial, and each is normalised here
rather than in the views:

* PostgreSQL folds unquoted identifiers to lowercase, so the platform's
  camelCase field names survive only in file mode. Both modes are renamed to
  snake_case.
* The pipeline writes reliability flags as the strings `true` and `false`, and
  the non-empty string `"false"` is truthy. They are parsed to real booleans.
* A date read from a file is a string and from the database a `date`; pandas
  also infers a different datetime unit for each. Both are pinned.

`script/verify_source_parity.py` asserts these invariants against a live
database.

Data flow:
    DATABASE=false -> modules/*/data/simulated/*.csv, modules/*/outputs/**
    DATABASE=true  -> PostgreSQL tables defined in dashboard/models.py

Results are cached with Streamlit's data cache, so switching views does not
re-read the source. Use the Reload button in the sidebar to clear it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard import config

_CACHE_TTL = 600


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a project CSV, dropping the Chinese field-description row.

    Only the Amazon Ads and path-report samples carry that row, directly under
    the header. It must go before any numeric column is parsed, or every
    numeric conversion in that column fails. The check matches the exact
    marker rather than guessing, because a heuristic would silently discard a
    real data row from the files that have no description row.
    """
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if frame.empty:
        return frame
    if str(frame.iloc[0, 0]) in config.DESCRIPTION_ROW_MARKERS:
        frame = frame.iloc[1:].reset_index(drop=True)
    return frame


def _to_numeric(
    frame: pd.DataFrame, columns: list[str], float_columns: tuple[str, ...] = ()
) -> pd.DataFrame:
    """Coerce the named columns to numbers, leaving blanks as NaN.

    `float_columns` are forced to float even when every sampled value is a
    whole number. Pandas would otherwise infer int64 from a file whose values
    happen to be integral, disagreeing with the same column read back from a
    Float database column.
    """
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            if column in float_columns:
                frame[column] = frame[column].astype("float64")
    return frame


#: Date columns that appear across several artifacts. A CSV read yields
#: strings and the database yields `date` objects, so both are parsed to
#: datetimes here and a view can always compare or format them the same way.
_DATE_COLUMNS = ("report_start_date", "report_end_date")


def _to_datetime(frame: pd.DataFrame, columns=_DATE_COLUMNS) -> pd.DataFrame:
    """Parse the named date columns, leaving unparsable values as NaT.

    The unit is pinned because pandas infers microseconds from a parsed
    string and seconds from a database `date`, which are unequal dtypes even
    when they hold the same instant.
    """
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").astype(
                "datetime64[us]"
            )
    return frame


#: Reliability flags, written by the pipeline as the strings `true`/`false`.
_BOOLEAN_COLUMNS = (
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
)


def _to_boolean(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce the reliability flag columns to real booleans.

    A CSV read yields the strings `true` and `false`, and the non-empty string
    `"false"` is truthy in Python. Without this, a view filtering on the flag
    would keep unreliable rows in file mode and drop them in database mode.
    """
    for column in _BOOLEAN_COLUMNS:
        if column in frame.columns:
            frame[column] = (
                frame[column].astype(str).str.strip().str.lower().eq("true")
            )
    return frame


def _engine():
    """Create a SQLAlchemy engine from the configured settings."""
    from sqlalchemy import create_engine

    return create_engine(
        config.database_settings().url(), connect_args={"connect_timeout": 20}
    )


def _query(sql: str) -> pd.DataFrame:
    """Run a read-only query and return the result as a DataFrame."""
    return pd.read_sql(sql, _engine())


# ---------------------------------------------------------------------------
# Mode reporting
# ---------------------------------------------------------------------------


def active_mode() -> str:
    """Return `database` or `local files`, for display in the sidebar."""
    return "database" if config.use_database() else "local files"


def source_label() -> str:
    """Return a human-readable description of where data is being read from."""
    if config.use_database():
        return config.database_settings().safe_summary()
    return "modules/*/data and outputs"


def database_available() -> tuple[bool, str]:
    """Check that the configured database is reachable and populated.

    Returns:
        A pair of (usable, message). `usable` is False when the dashboard
        should fall back to files.
    """
    if not config.use_database():
        return False, "DATABASE=false"
    try:
        from sqlalchemy import text

        with _engine().connect() as connection:
            count = connection.execute(
                text("select count(*) from attribution_result")
            ).scalar()
        if not count:
            return False, "Connected, but attribution_result is empty."
        return True, f"Connected to {config.database_settings().safe_summary()}"
    except Exception as error:  # noqa: BLE001 - surfaced verbatim in the UI
        return False, f"{type(error).__name__}: {str(error)[:180]}"


# ---------------------------------------------------------------------------
# Model output
# ---------------------------------------------------------------------------


@st.cache_data(ttl=_CACHE_TTL)
def load_attribution_results() -> pd.DataFrame:
    """Per-model attributed outcomes, cost, and efficiency for each touchpoint.

    Columns: attribution_model, touchpoint, interaction_type, the three share
    and three attributed columns, impressions, clicks, cost, reported figures,
    and roas/roi/cpa/cost_per_converted_user.
    """
    if config.use_database():
        frame = _query(
            """
            select r.attribution_model, t.touchpoint_key as touchpoint,
                   t.interaction_type, t.ad_product, t.format, t.placement,
                   t.creative,
                   r.converted_user_share, r.purchase_count_share,
                   r.revenue_share, r.attributed_converted_users,
                   r.attributed_purchase_count, r.attributed_revenue,
                   r.impressions, r.clicks, r.cost, r.reported_purchases,
                   r.reported_sales, r.roas, r.roi, r.cpa,
                   r.cost_per_converted_user
            from attribution_result r
            join touchpoint t on t.id = r.touchpoint_pk
            order by r.attribution_model, t.touchpoint_key
            """
        )
    else:
        frames = []
        for model in ("markov", "shapley"):
            path = (
                config.ATTRIBUTION_OUTPUT_DIR / f"amc_{model}_attribution_results.csv"
            )
            frames.append(_read_csv(path))
        frame = pd.concat(frames, ignore_index=True)
        frame = _split_touchpoint(frame)

    return _to_numeric(
        frame,
        [
            "converted_user_share",
            "purchase_count_share",
            "revenue_share",
            "attributed_converted_users",
            "attributed_purchase_count",
            "attributed_revenue",
            "impressions",
            "clicks",
            "cost",
            "reported_purchases",
            "reported_sales",
            "roas",
            "roi",
            "cpa",
            "cost_per_converted_user",
        ],
    )


#: The five segments of a touchpoint key, in order. These names are the
#: canonical vocabulary: the database stores them as columns on `touchpoint`,
#: and file mode derives them by splitting the key, so both modes agree.
TOUCHPOINT_SEGMENTS = (
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
)


def _split_touchpoint(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the five key segments as their own columns.

    The fifth segment is the interaction type. Files that already carry an
    `interaction_type` column agree with it, so overwriting is harmless and
    keeps the column present for the files that omit it.
    """
    if "touchpoint" not in frame.columns:
        return frame
    segments = frame["touchpoint"].str.split(":", expand=True)
    for index, name in enumerate(TOUCHPOINT_SEGMENTS):
        if index < segments.shape[1]:
            frame[name] = segments[index]
    return frame


@st.cache_data(ttl=_CACHE_TTL)
def load_comparison_touchpoints() -> pd.DataFrame:
    """Markov against Shapley per touchpoint and outcome, with reliability."""
    if config.use_database():
        frame = _query(
            """
            select t.touchpoint_key as touchpoint, c.outcome, c.markov_share,
                   c.shapley_share, c.gap_pp, c.relative_gap,
                   c.raw_unique_paths, c.raw_converted_users,
                   c.raw_purchase_count, c.calculation_valid,
                   c.data_support_sufficient, c.models_consistent,
                   c.reliability_status, c.reliability_reason,
                   t.ad_product, t.format, t.placement, t.creative,
                   t.interaction_type
            from model_comparison_touchpoint c
            join touchpoint t on t.id = c.touchpoint_pk
            order by c.outcome, t.touchpoint_key
            """
        )
    else:
        frame = _read_csv(
            config.ATTRIBUTION_OUTPUT_DIR / "amc_mta_model_comparison_touchpoints.csv"
        )
        frame = _split_touchpoint(frame)

    frame = _to_numeric(
        frame,
        [
            "markov_share",
            "shapley_share",
            "gap_pp",
            "relative_gap",
            "raw_unique_paths",
            "raw_converted_users",
            "raw_purchase_count",
        ],
    )
    return _to_boolean(frame)


@st.cache_data(ttl=_CACHE_TTL)
def load_comparison_summary() -> pd.DataFrame:
    """One diagnostic row per outcome: TVD, Spearman, and Top-K overlap."""
    if config.use_database():
        frame = _query(
            """
            select s.outcome, r.report_start_date, r.report_end_date,
                   r.max_touchpoint_gap_days, s.touchpoint_count, s.tvd,
                   s.spearman_rho, s.top_k_overlap_rate, s.calculation_valid,
                   s.data_support_sufficient, s.models_consistent,
                   s.reliability_status, s.reliability_reason
            from model_comparison_summary s
            join attribution_run r on r.id = s.run_pk
            order by s.outcome
            """
        )
    else:
        frame = _read_csv(
            config.ATTRIBUTION_OUTPUT_DIR / "amc_mta_model_comparison_summary.csv"
        )

    frame = _to_numeric(
        frame,
        ["touchpoint_count", "tvd", "spearman_rho", "top_k_overlap_rate",
         "max_touchpoint_gap_days"],
    )
    return _to_boolean(_to_datetime(frame))


@st.cache_data(ttl=_CACHE_TTL)
def load_recommended_attribution() -> pd.DataFrame:
    """The governed view: official share, benchmark, and recommended value."""
    if config.use_database():
        frame = _query(
            """
            select t.touchpoint_key as touchpoint, r.outcome, t.interaction_type,
                   r.official_model, r.official_share, r.recommended_value,
                   r.benchmark_model, r.benchmark_share, r.gap_pp,
                   r.relative_gap, r.calculation_valid,
                   r.data_support_sufficient, r.models_consistent,
                   r.reliability_status, r.reliability_reason,
                   t.ad_product, t.format, t.placement, t.creative
            from recommended_attribution r
            join touchpoint t on t.id = r.touchpoint_pk
            order by r.outcome, t.touchpoint_key
            """
        )
    else:
        frame = _read_csv(
            config.ATTRIBUTION_OUTPUT_DIR / "amc_mta_recommended_attribution.csv"
        )
        frame = _split_touchpoint(frame)

    frame = _to_numeric(
        frame, ["official_share", "benchmark_share", "gap_pp", "relative_gap"]
    )
    return _to_boolean(frame)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


#: The Amazon Ads sample uses the platform's camelCase field names. The
#: dashboard speaks snake_case everywhere, and PostgreSQL folds unquoted
#: identifiers to lowercase anyway, so file mode is renamed to match rather
#: than the database being forced to quote every alias.
_ADS_COLUMN_RENAMES = {
    "reportDate": "report_date",
    "accountId": "account_id",
    "adProduct": "ad_product",
    "adType": "ad_type",
    "creativeType": "creative_type",
    "inventoryType": "inventory_type",
    "currencyCode": "currency",
    "normalizedTouchpoint": "touchpoint",
}


@st.cache_data(ttl=_CACHE_TTL)
def load_ads_daily() -> pd.DataFrame:
    """Daily platform performance per touchpoint, with a parsed report_date.

    The `format` and `creative` columns are the touchpoint key's second and
    fourth segments. In the source file those arrive split across
    `adType`/`inventoryType` and `creativeType`; the segments carry the same
    values, so both modes expose the segment names.
    """
    if config.use_database():
        frame = _query(
            """
            select a.report_date, a.marketplace, a.account_id,
                   t.touchpoint_key as touchpoint, t.ad_product,
                   t.format, t.placement, t.creative, t.interaction_type,
                   t.cost_type, a.currency, a.impressions,
                   a.clicks, a.cost, a.purchases, a.sales
            from ads_daily_performance a
            join touchpoint t on t.id = a.touchpoint_pk
            order by a.report_date
            """
        )
    else:
        frame = _read_csv(config.SIMULATED_DIR / "amazon_ads_report_sample.csv")
        frame = frame.rename(columns=_ADS_COLUMN_RENAMES)
        frame = _split_touchpoint(frame)
        frame = frame.drop(
            columns=["ad_type", "creative_type", "inventory_type"], errors="ignore"
        )

    frame = _to_numeric(frame, ["impressions", "clicks", "cost", "purchases", "sales"])
    frame = _to_datetime(frame, ("report_date",))
    return frame.dropna(subset=["report_date"])


@st.cache_data(ttl=_CACHE_TTL)
def load_path_report() -> pd.DataFrame:
    """Anonymous aggregated conversion paths with their outcome totals."""
    if config.use_database():
        frame = _query(
            """
            select report_start_date, report_end_date, marketplace,
                   advertiser_id, path, path_length, users, converted_users,
                   purchase_count, revenue
            from path_report
            order by revenue desc
            """
        )
    else:
        frame = _read_csv(config.SIMULATED_DIR / "amc_mta_path_report_raw_sample.csv")
        frame["path_length"] = frame["path"].str.count(">") + 1

    frame = _to_numeric(
        frame,
        ["users", "converted_users", "purchase_count", "revenue", "path_length"],
    )
    return _to_datetime(frame)


@st.cache_data(ttl=_CACHE_TTL)
def load_entity_bridge() -> pd.DataFrame:
    """Touchpoint-to-Campaign/Ad Group links and their assisted outcomes."""
    if config.use_database():
        frame = _query(
            """
            select b.report_start_date, b.report_end_date, b.marketplace,
                   b.advertiser_id, t.touchpoint_key as touchpoint,
                   b.campaign_group_id, b.campaign_id, b.ad_group_id,
                   b.keyword_id, b.keyword_text, b.match_type, b.target_id,
                   b.audience_id, b.advertised_asin, b.sku_id, b.unique_users,
                   b.journey_count, b.impressions, b.clicks, b.cost,
                   b.assisted_converted_users, b.assisted_purchase_count,
                   b.assisted_revenue, b.reported_purchases, b.reported_sales
            from touchpoint_entity_bridge b
            join touchpoint t on t.id = b.touchpoint_pk
            order by b.campaign_id, b.ad_group_id
            """
        )
    else:
        frame = _read_csv(
            config.SIMULATED_DIR / "amc_touchpoint_entity_aggregate_sample.csv"
        )

    frame = _to_numeric(
        frame,
        [
            "unique_users",
            "journey_count",
            "impressions",
            "clicks",
            "cost",
            "assisted_converted_users",
            "assisted_purchase_count",
            "assisted_revenue",
            "reported_purchases",
            "reported_sales",
        ],
        float_columns=(
            "assisted_converted_users",
            "assisted_purchase_count",
            "assisted_revenue",
        ),
    )
    return _to_datetime(frame)


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


@st.cache_data(ttl=_CACHE_TTL)
def load_budget_recommendation() -> dict:
    """The canonical initial-budget recommendation, as a nested mapping.

    Returned in the JSON artifact's own shape in both modes, so views can read
    `campaigns[i]["recommended_ad_groups"]` without branching.
    """
    if config.use_database():
        run = _query(
            """
            select * from budget_recommendation_run order by id desc limit 1
            """
        )
        if run.empty:
            return {}
        run_row = run.iloc[0]
        campaigns = _query(
            f"""
            select * from campaign_budget_recommendation
            where run_pk = {int(run_row['id'])} order by campaign_id
            """
        )
        slots = _query(
            """
            select s.*, c.campaign_id
            from ad_group_budget_slot s
            join campaign_budget_recommendation c
              on c.id = s.campaign_recommendation_pk
            order by s.ad_group_slot_id
            """
        )
        return _rebuild_budget_document(run_row, campaigns, slots)

    path = config.STRATEGY_OUTPUT_DIR / "initial_budget_recommendation.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _rebuild_budget_document(run_row, campaigns: pd.DataFrame, slots: pd.DataFrame) -> dict:
    """Reassemble the JSON artifact shape from three relational tables."""
    campaign_records = []
    for _, row in campaigns.iterrows():
        own_slots = slots[slots["campaign_id"] == row["campaign_id"]]
        campaign_records.append(
            {
                "campaign_id": row["campaign_id"],
                "recommended_ad_group_count": int(row["recommended_ad_group_count"]),
                "count_rationale": {
                    "count_formula_version": row["count_formula_version"],
                    "capacity_required_count": int(row["capacity_required_count"]),
                    "final_recommended_count": int(row["recommended_ad_group_count"]),
                },
                "outcome_contributions": {
                    "converted_users": float(row["score_converted_users"]),
                    "purchase_count": float(row["score_purchase_count"]),
                    "revenue": float(row["score_revenue"]),
                },
                "campaign_mta_score": float(row["campaign_mta_score"]),
                "bridge_summary": {
                    "historical_ad_group_count": int(
                        row["bridge_historical_ad_group_count"]
                    ),
                    "touchpoint_count": int(row["bridge_touchpoint_count"]),
                    "fallback_used": bool(row["bridge_fallback_used"]),
                },
                "budget_seed_share": float(row["budget_seed_share"]),
                "minimum_required_daily_budget": float(
                    row["minimum_required_daily_budget"]
                ),
                "campaign_budget_seed": float(row["campaign_budget_seed"]),
                "execution_status": row["execution_status"],
                "recommended_ad_groups": [
                    {
                        "ad_group_slot_id": slot["ad_group_slot_id"],
                        "allocation_basis": slot["allocation_basis"],
                        "budget_seed_share": float(slot["budget_seed_share"]),
                        "initial_daily_budget": float(slot["initial_daily_budget"]),
                    }
                    for _, slot in own_slots.iterrows()
                ],
            }
        )

    return {
        "schema_version": run_row["schema_version"],
        "campaign_group_id": run_row["campaign_group_id"],
        "candidate_pool_id": run_row["candidate_pool_id"],
        "mta_batch_id": run_row["mta_batch_id"],
        "mta_source_snapshot": {
            "report_start_date": str(run_row["source_report_start_date"]),
            "report_end_date": str(run_row["source_report_end_date"]),
            "marketplace": run_row["source_marketplace"],
            "advertiser_id": run_row["source_advertiser_id"],
            "attribution_sha256": run_row["source_attribution_sha256"],
            "entity_sha256": run_row["source_entity_sha256"],
        },
        "recommendation_type": run_row["recommendation_type"],
        "handoff_status": run_row["handoff_status"],
        "is_optimized": bool(run_row["is_optimized"]),
        "budget_derivation": {
            "formula_version": run_row["formula_version"],
            "normalization_universe": run_row["normalization_universe"],
            "outcome_weights": {
                "converted_users": float(run_row["weight_converted_users"]),
                "purchase_count": float(run_row["weight_purchase_count"]),
                "revenue": float(run_row["weight_revenue"]),
            },
        },
        "campaigns": campaign_records,
        "budget_seed_total": float(run_row["budget_seed_total"]),
        "warnings": [],
    }


@st.cache_data(ttl=_CACHE_TTL)
def load_strategy_request() -> dict:
    """The Campaign Group, its Campaigns, weights, and capacity rules.

    Capacity rules are pipeline configuration rather than observed data, so no
    table holds them; in database mode the key is present but empty. Views must
    treat it as optional. The outcome weights are recoverable, because the
    budget run records the weights it was executed with.
    """
    if config.use_database():
        groups = _query(
            """
            select g.campaign_group_id, g.group_name, g.platform, g.currency,
                   g.total_daily_budget, g.sample_version, g.candidate_pool_id,
                   g.mta_batch_id, a.marketplace, a.advertiser_id
            from campaign_group g
            join advertiser a on a.id = g.advertiser_pk
            limit 1
            """
        )
        if groups.empty:
            return {}
        campaigns = _query(
            """
            select campaign_id, campaign_name, ad_product, status
            from campaign order by campaign_id
            """
        )
        run = _query(
            """
            select weight_converted_users, weight_purchase_count,
                   weight_revenue, source_report_start_date,
                   source_report_end_date, source_marketplace,
                   source_advertiser_id, source_attribution_sha256,
                   source_entity_sha256
            from budget_recommendation_run order by id desc limit 1
            """
        )
        weights = {}
        source = {}
        if not run.empty:
            row = run.iloc[0]
            weights = {
                "converted_users": float(row["weight_converted_users"]),
                "purchase_count": float(row["weight_purchase_count"]),
                "revenue": float(row["weight_revenue"]),
            }
            source = {
                "report_start_date": str(row["source_report_start_date"]),
                "report_end_date": str(row["source_report_end_date"]),
                "marketplace": row["source_marketplace"],
                "advertiser_id": row["source_advertiser_id"],
                "attribution_sha256": row["source_attribution_sha256"],
                "entity_sha256": row["source_entity_sha256"],
            }
        group = groups.iloc[0]
        return {
            "sample_version": group["sample_version"] or "",
            "candidate_pool_id": group["candidate_pool_id"] or "",
            "mta_batch_id": group["mta_batch_id"] or "",
            "mta_source": source,
            "campaign_group": {
                "campaign_group_id": group["campaign_group_id"],
                "group_name": group["group_name"],
                "platform": group["platform"],
                "marketplace": group["marketplace"],
                "advertiser_id": group["advertiser_id"],
                "currency": group["currency"],
                "total_daily_budget": float(group["total_daily_budget"]),
            },
            "campaigns": campaigns.to_dict("records"),
            "outcome_weights": weights,
            "capacity_rules": {},
        }

    path = config.STRATEGY_INPUT_DIR / "strategy_request.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(ttl=_CACHE_TTL)
def load_candidate_pool() -> dict:
    """Eligible keyword, SKU, target, and audience counts per Campaign."""
    if config.use_database():
        frame = _query(
            """
            select c.campaign_id, tc.candidate_kind, tc.eligible_count,
                   tc.candidate_pool_id, tc.candidate_usage_policy,
                   tc.sample_version
            from targeting_candidate tc
            join campaign c on c.id = tc.campaign_pk
            order by c.campaign_id
            """
        )
        counts: dict[str, dict] = {}
        pool_id = ""
        policy = ""
        version = ""
        for _, row in frame.iterrows():
            pool_id = pool_id or row["candidate_pool_id"]
            policy = policy or (row["candidate_usage_policy"] or "")
            version = version or (row["sample_version"] or "")
            entry = counts.setdefault(
                row["campaign_id"], {"campaign_id": row["campaign_id"]}
            )
            entry[row["candidate_kind"]] = int(row["eligible_count"])
        group = _query("select campaign_group_id from campaign_group limit 1")
        return {
            "sample_version": version,
            "candidate_pool_id": pool_id,
            "campaign_group_id": (
                group.iloc[0]["campaign_group_id"] if not group.empty else ""
            ),
            "candidate_usage_policy": policy,
            "campaign_candidate_counts": list(counts.values()),
        }

    path = config.STRATEGY_INPUT_DIR / "candidate_pool.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def clear_caches() -> None:
    """Drop every cached DataFrame so the next read hits the source again."""
    st.cache_data.clear()
