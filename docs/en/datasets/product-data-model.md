---
title: Product Data Model
description: Product, stock-item, keyword, search-volume, and market-share schema reference
order: 40
---

# Product Data Model (`msproduct`)

This page translates and restructures the preserved Chinese schema analysis in `docs/zh/product-data-model.md`. It groups the Product service schema into master data, relationships, long-tail metrics, time-series partitions, and business constraints so downstream consumers can reason about ownership and write order.

## Architecture Overview

<DrawioDiagram base="./product-data-model" alt="Product data model architecture" />

The model has five logical layers:

| Layer | Responsibility | Representative tables |
| --- | --- | --- |
| Dimension master data | Globally referenced dictionaries with the strongest foreign-key enforcement | `retailer`, `market`, `category`, `brand`, `segment` |
| Product master data | Product-to-Stock Keeping Unit (SKU) identity | `product`, `sku` |
| Product detail | Extensible SKU attributes, price observations, and health | `sku_attributes`, `sku_price_daily`, `sku_item_health` |
| Keyword relationships | Keyword links to Brand, Category, Segment, and SKU | `keyword`, `brand_keyword`, `category_keyword`, `keyword_segment`, `keyword_sku_mapping`, `keyword_categorization` |
| Search and market facts | Search volume, impressions, ranks, incremental return, and market share | `keyword_traffic`, `keyword_search_volume`, `keyword_impressions`, `keyword_sku_rank`, `keyword_sku_eiroas`, `market_share` |

## Core Master Data

### Dimensions

`retailer`, `market`, `category`, `brand`, and `segment` follow a common pattern:

```text
id      integer primary key
code    varchar, required and unique
name    varchar
source  varchar(255), only on category, market, and retailer
```

`code` is the stable cross-service business key. `source` identifies the upstream master-data system. These tables must exist before dependent Product and SKU rows are written.

### `product`

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | Integer primary key | Internal identifier |
| `gtin` | Required unique text | Global Trade Item Number and stable business key |
| `category_id` | Foreign key | References `category.id` |
| `brand_id` | Foreign key | References `brand.id` |
| `segment_id` | Foreign key | References `segment.id` |
| `source_system_code` | Text | Upstream source |
| `tier` | Text | Product tier such as priority or tail |

`product` is uniquely identified by `gtin`. Its Category, Brand, and Segment relationships are real database foreign keys, making it one of the most strictly constrained entities in the wider system.

### `sku`

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | Integer primary key | Internal identifier |
| `retailer_id` | Required foreign key | Retailer dimension |
| `market_id` | Nullable foreign key | Market dimension |
| `value` | Required text | Retailer-side SKU or Amazon Standard Identification Number (ASIN) |
| `product_id` | Required foreign key | Parent Product |
| `description` | Text | Display title |
| `scope_for_search_optimization` | Boolean | Whether search optimization may use the SKU |
| `specification_profit` | Numeric | Configured profit basis |
| `specification_for_paid_search_to_bid` | Boolean | Whether paid-search bidding may use the SKU |
| `specification_updated_at` | Timestamp | Last specification update |

`UNIQUE(retailer_id, market_id, value)` prevents duplicate SKU values within one retailer and market.

## Product Detail Tables

- `sku_attributes` stores extensible `(sku_id, name, value, source)` key-value attributes and indexes them by SKU, attribute name, and source.
- `sku_price_daily` stores `(sku_id, date, price, price_currency, store_country)`. It has no primary key, so writers must prevent duplicates. Currency values use high precision.
- `sku_item_health` records daily `(date, sku_id, item_health)` observations and is not partitioned.

## Keyword Model

`keyword` has an internal primary key, a unique `value`, and a `specification_for_paid_search_to_bid` switch. Updating that switch invokes `keyword_cleanup_keyword_sku_mapping_on_updated`, which removes mappings that are no longer eligible. The equivalent SKU trigger applies the same rule from the SKU side.

The relation tables `brand_keyword`, `category_keyword`, and `keyword_segment` have logical relationships but no database primary or foreign-key constraints. `keyword_sku_mapping` adds an internal primary key and a `priority` field for manually governed Keyword-to-SKU ordering.

### `keyword_categorization`

This table classifies a Keyword within Retailer, Market, Category, Brand, and Campaign Group context. Its important fields are:

- `category_id`, `retailer_id`, `market_id`, and `keyword_id`;
- nullable `brand_id` and `representative_keyword_id`;
- `search_volume_tag`, `search_branding_tag`, and optional `search_conquest_tag`;
- `group_id`, which scopes classification to a Campaign Group.

It has no primary key. The Product-service version is a master-data view of categorization and differs slightly from similarly named tables in Campaign and Budget services.

## Search, Rank, and Market Facts

| Table | Grain and role |
| --- | --- |
| `keyword_traffic` | Seed Keyword to discovered Keyword, with a 30-day exact-search-volume observation |
| `keyword_traffic_stats` | Monthly aggregation by seed Keyword |
| `search_volume_monthly` | Keyword-by-month search volume with Retailer and Market dimensions |
| `keyword_search_volume` | Campaign Group-scoped search volume with a composite primary key and real foreign keys |
| `keyword_impressions` | Monthly partitioned organic impression facts |
| `keyword_sku_daily_webscraping` | Monthly partitioned scraped item-position facts |
| `keyword_sku_rank` | Monthly partitioned SKU rank by Keyword |
| `keyword_sku_eiroas` | SKU × Keyword × date incremental Return on Ad Spend (ROAS) and incrementality factor |
| `market_share` | Monthly Category, Brand, Retailer, and Market share value |

`keyword_sku_eiroas.date` is text rather than a database date and therefore requires explicit conversion for date operations. The three monthly fact tables require partitions to be created before writes reach a new month.

## Integrity and Operational Rules

1. Write dimensions before Product, then Product before SKU. Real foreign keys enforce this order.
2. Use stable business keys across services: dimension `code`, Product `gtin`, `(retailer, market, value)` for SKU, and Keyword `value`.
3. Treat numeric IDs as service-local. Other services may copy them without sharing a database-level foreign key.
4. Assess trigger impact before bulk-changing paid-search eligibility: disabling a Keyword or SKU can delete Keyword-to-SKU mappings.
5. Validate relationship-table uniqueness in application code where the database supplies no primary key.
6. Pre-create monthly partitions for impression, scraping, and rank tables.
7. Assemble consumer views in Campaign, Budget, or application repositories; this schema defines no business views of its own.

## Core Entity Relationships

<DrawioDiagram base="./product-data-model-er" alt="Core Product data model entity relationships" />

The editable diagrams are maintained beside this page so schema ownership and visual documentation remain together.
