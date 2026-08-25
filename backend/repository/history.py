"""History: what was observed — spend, paths, and entity links.

Three snapshot keys come from here. In file mode they read the committed
platform samples, or the CSV files of a configured MTA-SIM run when one is
present; in database mode they read the tables those samples were imported
into.

Data flow:
    modules/mta_attribution/data/simulated/&#42;.csv        -.
                                                          +-> here -> /api/dashboard
    ads_daily_performance, path_report, entity bridge   -'
"""

from __future__ import annotations

from sqlalchemy import select

from backend.config import SIMULATED_DIR, simulator_data_directory, use_database
from backend.database import orm_rows
from backend.repository.coercion import (
    dates,
    numeric,
    project,
    read_csv,
    rename,
    split_touchpoint,
)
from dashboard.models import (
    AdsDailyPerformance,
    PathReport,
    Touchpoint,
    TouchpointEntityBridge,
)

#: The Amazon Ads sample uses the platform's camelCase field names. The
#: dashboard speaks snake_case everywhere, and PostgreSQL folds unquoted
#: identifiers to lowercase anyway, so file mode is renamed to match rather
#: than the database being forced to quote every alias.
ADS_COLUMN_RENAMES = {
    "reportDate": "report_date",
    "accountId": "account_id",
    "adProduct": "ad_product",
    "adType": "ad_type",
    "creativeType": "creative_type",
    "inventoryType": "inventory_type",
    "currencyCode": "currency",
    "normalizedTouchpoint": "touchpoint",
}

ADS_FIELDS: tuple[str, ...] = (
    "report_date",
    "marketplace",
    "account_id",
    "touchpoint",
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
    "cost_type",
    "currency",
    "impressions",
    "clicks",
    "cost",
    "purchases",
    "sales",
)

ADS_NUMERIC = ("impressions", "clicks", "cost", "purchases", "sales")


def ads_daily() -> list[dict]:
    """Daily platform performance per touchpoint, with a pinned report date.

    The `format` and `creative` fields are the touchpoint key's second and
    fourth segments. In the source file those arrive split across `adType`,
    `inventoryType`, and `creativeType`; the segments carry the same values,
    so both modes expose the segment names.
    """
    if use_database():
        statement = (
            select(
                AdsDailyPerformance.report_date,
                AdsDailyPerformance.marketplace,
                AdsDailyPerformance.account_id,
                Touchpoint.touchpoint_key.label("touchpoint"),
                Touchpoint.ad_product,
                Touchpoint.format,
                Touchpoint.placement,
                Touchpoint.creative,
                Touchpoint.interaction_type,
                Touchpoint.cost_type,
                AdsDailyPerformance.currency,
                AdsDailyPerformance.impressions,
                AdsDailyPerformance.clicks,
                AdsDailyPerformance.cost,
                AdsDailyPerformance.purchases,
                AdsDailyPerformance.sales,
            )
            .join(Touchpoint, Touchpoint.id == AdsDailyPerformance.touchpoint_pk)
            .order_by(AdsDailyPerformance.report_date)
        )
        rows = orm_rows(statement)
    else:
        directory = simulator_data_directory()
        source = (
            directory / "amazon_ads_daily_touchpoint_performance.csv"
            if directory
            else SIMULATED_DIR / "amazon_ads_report_sample.csv"
        )
        rows = rename(read_csv(source), ADS_COLUMN_RENAMES)
        split_touchpoint(rows)
    numeric(rows, ADS_NUMERIC)
    dates(rows, ["report_date"])
    return project([row for row in rows if row.get("report_date")], ADS_FIELDS)


PATH_FIELDS: tuple[str, ...] = (
    "report_start_date",
    "report_end_date",
    "marketplace",
    "advertiser_id",
    "path",
    "path_length",
    "users",
    "converted_users",
    "purchase_count",
    "revenue",
)

PATH_NUMERIC = ("users", "converted_users", "purchase_count", "revenue", "path_length")


def path_report() -> list[dict]:
    """Anonymous aggregated conversion paths with their outcome totals."""
    if use_database():
        statement = select(
            PathReport.report_start_date,
            PathReport.report_end_date,
            PathReport.marketplace,
            PathReport.advertiser_id,
            PathReport.path,
            PathReport.path_length,
            PathReport.users,
            PathReport.converted_users,
            PathReport.purchase_count,
            PathReport.revenue,
        ).order_by(PathReport.id)
        rows = orm_rows(statement)
    else:
        directory = simulator_data_directory()
        source = (
            directory / "amc_path_report.csv"
            if directory
            else SIMULATED_DIR / "amc_mta_path_report_raw_sample.csv"
        )
        rows = read_csv(source)
        for row in rows:
            # The file carries the path but not its length; the database stores
            # the length the pipeline computed the same way.
            row["path_length"] = len(str(row.get("path", "")).split(">"))
    numeric(rows, PATH_NUMERIC)
    return project(dates(rows), PATH_FIELDS)


BRIDGE_FIELDS: tuple[str, ...] = (
    "report_start_date",
    "report_end_date",
    "marketplace",
    "advertiser_id",
    "touchpoint",
    "campaign_group_id",
    "campaign_id",
    "ad_group_id",
    "keyword_id",
    "keyword_text",
    "match_type",
    "target_id",
    "audience_id",
    "advertised_asin",
    "sku_id",
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
)

BRIDGE_NUMERIC = (
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
)


def entity_bridge() -> list[dict]:
    """Touchpoint-to-Campaign and Ad Group links with their assisted outcomes."""
    if use_database():
        statement = (
            select(
                TouchpointEntityBridge.report_start_date,
                TouchpointEntityBridge.report_end_date,
                TouchpointEntityBridge.marketplace,
                TouchpointEntityBridge.advertiser_id,
                Touchpoint.touchpoint_key.label("touchpoint"),
                TouchpointEntityBridge.campaign_group_id,
                TouchpointEntityBridge.campaign_id,
                TouchpointEntityBridge.ad_group_id,
                TouchpointEntityBridge.keyword_id,
                TouchpointEntityBridge.keyword_text,
                TouchpointEntityBridge.match_type,
                TouchpointEntityBridge.target_id,
                TouchpointEntityBridge.audience_id,
                TouchpointEntityBridge.advertised_asin,
                TouchpointEntityBridge.sku_id,
                TouchpointEntityBridge.unique_users,
                TouchpointEntityBridge.journey_count,
                TouchpointEntityBridge.impressions,
                TouchpointEntityBridge.clicks,
                TouchpointEntityBridge.cost,
                TouchpointEntityBridge.assisted_converted_users,
                TouchpointEntityBridge.assisted_purchase_count,
                TouchpointEntityBridge.assisted_revenue,
                TouchpointEntityBridge.reported_purchases,
                TouchpointEntityBridge.reported_sales,
            )
            .join(Touchpoint, Touchpoint.id == TouchpointEntityBridge.touchpoint_pk)
            .order_by(TouchpointEntityBridge.id)
        )
        rows = orm_rows(statement)
    else:
        rows = read_csv(SIMULATED_DIR / "amc_touchpoint_entity_aggregate_sample.csv")
    numeric(rows, BRIDGE_NUMERIC)
    return project(dates(rows), BRIDGE_FIELDS)
