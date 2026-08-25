#!/usr/bin/env python3
"""SK-II 单品面板：真实 July + 模拟扩样。

真实源: amazonTestData/amazon_ads_report_sk2.csv
扩样: 用真实日的预算/曝光/成交经验分布 + 对数弹性生成式，模拟 2025-01～06
粒度: marketplace × date（无 ASIN）
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "amazonTestData" / "amazon_ads_report_sk2.csv"
OUT = Path(__file__).resolve().parents[1] / "data"

# 扩样后按日历切分
TRAIN_END = date(2025, 6, 20)
VAL_END = date(2025, 7, 10)
SIM_START = date(2025, 1, 1)
SIM_END = date(2025, 6, 30)
SEED = 42

AD_TYPES = ("sp", "sb", "sd", "dsp")
PRODUCT_MAP = {
    "SPONSORED_PRODUCTS": "sp",
    "SPONSORED_BRANDS": "sb",
    "SPONSORED_DISPLAY": "sd",
    "AMAZON_DSP": "dsp",
}

# P0 结构特征（Extended 27 维 = 19 基础 + 8）
STRUCT_COLS = [
    "share_cost_top_of_search",
    "share_cost_product_page",
    "share_cost_sb_headline",
    "share_cost_sp_product_ad",
    "share_cost_dsp_video",
    "share_cost_dsp_image",
    "share_cost_dsp_unspecified_creative",
    "n_placement_types",
]


def parse_day(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(raw)


def parse_num(raw: str | None) -> float:
    if raw is None:
        return 0.0
    text = str(raw).replace("$", "").replace(",", "").strip()
    if text == "":
        return 0.0
    return float(text)


def split_of(day: date) -> str:
    if day <= TRAIN_END:
        return "train"
    if day <= VAL_END:
        return "val"
    return "test"


def _log1p(value: float) -> float:
    return math.log1p(max(float(value), 0.0))


def _count(rows: list[dict], field: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for row in rows:
        out[str(row[field])] += 1
    return dict(out)


def finalize_row(day: date, country: str, budgets: dict, imps: dict, clicks: float, revenue: float, sales_ad: float, synthetic: int) -> dict:
    cost = sum(budgets[g] for g in AD_TYPES)
    impressions = sum(imps[g] for g in AD_TYPES)
    out = {
        "date": day.isoformat(),
        "country": country,
        "product": "SK-II",
        "split": split_of(day),
        "is_synthetic": synthetic,
        "cost": cost,
        "revenue": revenue,
        "gmv_ad": revenue,
        "sales_ad": sales_ad,
        "impressions": impressions,
        "clicks": clicks,
        "has_ad": 1.0 if cost > 0 else 0.0,
        "dow": day.weekday(),
        "is_weekend": 1.0 if day.weekday() >= 5 else 0.0,
    }
    for g in AD_TYPES:
        b = budgets[g]
        out[f"budget_{g}"] = b
        out[f"share_{g}"] = (b / cost) if cost > 0 else 0.0
        out[f"impressions_{g}"] = imps[g]
        out[f"log1p_budget_{g}"] = _log1p(b)
        out[f"log1p_impressions_{g}"] = _log1p(imps[g])
    out["log1p_revenue"] = _log1p(revenue)
    out["log1p_sales_ad"] = _log1p(sales_ad)
    out["log1p_impressions"] = _log1p(impressions)
    out["log1p_clicks"] = _log1p(clicks)
    return out


def build_real_panel() -> list[dict]:
    rows = list(csv.DictReader(SRC.open(newline="", encoding="utf-8")))
    buckets: dict[tuple[date, str], dict] = {}
    for row in rows:
        day = parse_day(row["reportDate"])
        market = row["marketplace"].strip().upper()
        product = PRODUCT_MAP.get(row["adProduct"].strip())
        if product is None:
            continue
        key = (day, market)
        if key not in buckets:
            buckets[key] = {
                "date": day,
                "country": market,
                **{f"budget_{g}": 0.0 for g in AD_TYPES},
                **{f"impressions_{g}": 0.0 for g in AD_TYPES},
                "clicks": 0.0,
                "sales": 0.0,
                "purchases": 0.0,
            }
        b = buckets[key]
        b[f"budget_{product}"] += parse_num(row["cost"])
        b[f"impressions_{product}"] += parse_num(row["impressions"])
        b["clicks"] += parse_num(row["clicks"])
        b["sales"] += parse_num(row["sales"])
        b["purchases"] += parse_num(row["purchases"])

    panel = []
    for (_day, _m), rec in sorted(buckets.items()):
        budgets = {g: rec[f"budget_{g}"] for g in AD_TYPES}
        imps = {g: rec[f"impressions_{g}"] for g in AD_TYPES}
        panel.append(
            finalize_row(
                rec["date"],
                rec["country"],
                budgets,
                imps,
                rec["clicks"],
                rec["sales"],
                rec["purchases"],
                synthetic=0,
            )
        )
    return panel


def fit_generator(real: list[dict]) -> dict:
    """对数弹性: log1p(R) ≈ a + Σ β_g log1p(B_g) + γ_weekend + δ_CA"""
    x_rows = []
    y = []
    y_impr = []
    y_sales = []
    budget_by_mkt_dow: dict[tuple[str, int], list[np.ndarray]] = defaultdict(list)
    impr_ratio: list[np.ndarray] = []

    for r in real:
        feats = [1.0] + [r[f"log1p_budget_{g}"] for g in AD_TYPES]
        feats.append(r["is_weekend"])
        feats.append(1.0 if r["country"] == "CA" else 0.0)
        x_rows.append(feats)
        y.append(r["log1p_revenue"])
        y_impr.append([r[f"log1p_impressions_{g}"] for g in AD_TYPES])
        y_sales.append(r["log1p_sales_ad"])
        budget_by_mkt_dow[(r["country"], int(r["dow"]))].append(
            np.array([r[f"budget_{g}"] for g in AD_TYPES], dtype=np.float64)
        )
        cost = r["cost"]
        if cost > 0:
            impr_ratio.append(np.array([r[f"impressions_{g}"] / max(r[f"budget_{g}"], 1.0) for g in AD_TYPES]))

    x = np.array(x_rows)
    yv = np.array(y)
    # ridge
    lam = 1.0
    xtx = x.T @ x + lam * np.eye(x.shape[1])
    coef = np.linalg.solve(xtx, x.T @ yv)
    resid = yv - x @ coef
    sigma = float(np.std(resid))

    # impressions ~ log1p from budgets (per type diagonal)
    xi = x[:, :5]  # intercept + 4 budgets
    yi = np.array(y_impr)
    coef_impr = []
    for j in range(4):
        xtxj = xi.T @ xi + lam * np.eye(xi.shape[1])
        coef_impr.append(np.linalg.solve(xtxj, xi.T @ yi[:, j]))
    ys = np.array(y_sales)
    coef_sales = np.linalg.solve(xi.T @ xi + lam * np.eye(xi.shape[1]), xi.T @ ys)

    # budget means by market×dow
    budget_stats = {}
    for key, arrs in budget_by_mkt_dow.items():
        a = np.vstack(arrs)
        budget_stats[f"{key[0]}|{key[1]}"] = {
            "mean": a.mean(axis=0).tolist(),
            "std": np.maximum(a.std(axis=0), 1.0).tolist(),
        }
    # fallback overall
    all_b = np.vstack([np.array([r[f"budget_{g}"] for g in AD_TYPES]) for r in real])
    budget_stats["ALL"] = {"mean": all_b.mean(axis=0).tolist(), "std": np.maximum(all_b.std(axis=0), 1.0).tolist()}

    return {
        "rev_coef": coef.tolist(),
        "rev_sigma": sigma,
        "impr_coef": [c.tolist() for c in coef_impr],
        "sales_coef": coef_sales.tolist(),
        "budget_stats": budget_stats,
        "impr_per_dollar": np.mean(impr_ratio, axis=0).tolist() if impr_ratio else [50, 40, 80, 30],
        "clicks_per_impr": float(np.mean([r["clicks"] / max(r["impressions"], 1) for r in real])),
    }


def simulate_expand(real: list[dict], gen: dict, rng: np.random.Generator) -> list[dict]:
    """模拟 Jan–Jun 每日×US/CA。"""
    out = []
    day = SIM_START
    coef = np.array(gen["rev_coef"])
    while day <= SIM_END:
        for country in ("US", "CA"):
            key = f"{country}|{day.weekday()}"
            stats = gen["budget_stats"].get(key, gen["budget_stats"]["ALL"])
            mean = np.array(stats["mean"])
            std = np.array(stats["std"])
            # 对数正态扰动
            noise = rng.normal(0, 0.25, size=4)
            budgets_arr = np.clip(mean * np.exp(noise) + rng.normal(0, std * 0.15), 1.0, None)
            # 偶尔做预算结构冲击
            if rng.random() < 0.15:
                scale = rng.uniform(0.7, 1.4, size=4)
                budgets_arr *= scale
            budgets = {g: float(budgets_arr[i]) for i, g in enumerate(AD_TYPES)}
            logb = np.array([_log1p(budgets[g]) for g in AD_TYPES])
            feats = np.array([1.0, *logb, 1.0 if day.weekday() >= 5 else 0.0, 1.0 if country == "CA" else 0.0])
            log_r = float(feats @ coef + rng.normal(0, gen["rev_sigma"]))
            revenue = float(np.expm1(max(log_r, 0.0)))
            # impressions from coef or $/impression
            imps = {}
            for i, g in enumerate(AD_TYPES):
                xi = np.array([1.0, *logb])
                log_i = float(np.array(gen["impr_coef"][i]) @ xi + rng.normal(0, 0.2))
                imps[g] = float(max(np.expm1(max(log_i, 0.0)), budgets[g] * gen["impr_per_dollar"][i] * 0.5))
            sales_ad = float(np.expm1(max(float(np.array(gen["sales_coef"]) @ np.array([1.0, *logb]) + rng.normal(0, 0.25)), 0.0)))
            clicks = float(sum(imps.values()) * gen["clicks_per_impr"] * rng.uniform(0.8, 1.2))
            out.append(finalize_row(day, country, budgets, imps, clicks, revenue, sales_ad, synthetic=1))
        day += timedelta(days=1)
    return out


def aggregate_structural_from_csv() -> tuple[dict[tuple[str, str], dict[str, float]], dict]:
    """从 SK2 明细聚合 marketplace×date 的结构花费占比。"""
    rows = list(csv.DictReader(SRC.open(newline="", encoding="utf-8")))
    buckets: dict[tuple[str, str], dict] = defaultdict(lambda: {"total_cost": 0.0, "parts": defaultdict(float)})

    for row in rows:
        day = parse_day(row["reportDate"]).isoformat()
        market = row["marketplace"].strip().upper()
        cost = parse_num(row["cost"])
        if cost <= 0:
            continue
        key = (day, market)
        b = buckets[key]
        b["total_cost"] += cost
        placement = (row.get("placement") or "UNSPECIFIED").strip().upper()
        creative = (row.get("creativeType") or "UNSPECIFIED").strip().upper()
        ad_type = (row.get("adType") or "UNSPECIFIED").strip().upper()
        ad_product = (row.get("adProduct") or "").strip()

        if placement == "TOP_OF_SEARCH":
            b["parts"]["top_of_search"] += cost
        elif placement == "PRODUCT_PAGE":
            b["parts"]["product_page"] += cost
        if ad_product == "SPONSORED_BRANDS" and ad_type == "HEADLINE":
            b["parts"]["sb_headline"] += cost
        if ad_product == "SPONSORED_PRODUCTS" and ad_type == "PRODUCT_AD":
            b["parts"]["sp_product_ad"] += cost
        if ad_product == "AMAZON_DSP":
            if creative == "VIDEO":
                b["parts"]["dsp_video"] += cost
            elif creative == "IMAGE":
                b["parts"]["dsp_image"] += cost
            else:
                b["parts"]["dsp_unspec_creative"] += cost
        b["parts"][f"pl_{placement}"] += cost

    out: dict[tuple[str, str], dict[str, float]] = {}
    placement_counts = []
    for key, rec in buckets.items():
        total = rec["total_cost"]
        parts = rec["parts"]
        n_pl = sum(1 for k, v in parts.items() if k.startswith("pl_") and v > 0)
        placement_counts.append(n_pl)
        out[key] = {
            "share_cost_top_of_search": parts.get("top_of_search", 0.0) / total,
            "share_cost_product_page": parts.get("product_page", 0.0) / total,
            "share_cost_sb_headline": parts.get("sb_headline", 0.0) / total,
            "share_cost_sp_product_ad": parts.get("sp_product_ad", 0.0) / total,
            "share_cost_dsp_video": parts.get("dsp_video", 0.0) / total,
            "share_cost_dsp_image": parts.get("dsp_image", 0.0) / total,
            "share_cost_dsp_unspecified_creative": parts.get("dsp_unspec_creative", 0.0) / total,
            "n_placement_types": float(n_pl),
        }

    stats = {
        "n_day_market": len(out),
        "mean_n_placement_types": float(np.mean(placement_counts)) if placement_counts else 0.0,
        "mean_shares": {
            c: float(np.mean([v[c] for v in out.values()])) for c in STRUCT_COLS if c != "n_placement_types"
        },
    }
    return out, stats


def fit_struct_generator(real_struct: list[dict]) -> dict:
    by_key: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for s in real_struct:
        by_key[(s["country"], s["dow"])].append(s)
    table = {}
    for key, items in by_key.items():
        table[f"{key[0]}|{key[1]}"] = {c: float(np.mean([it[c] for it in items])) for c in STRUCT_COLS}
    overall = {c: float(np.mean([s[c] for s in real_struct])) for c in STRUCT_COLS}
    table["ALL"] = overall
    return table


def sample_struct(country: str, dow: int, gen: dict, rng: np.random.Generator) -> dict:
    base = gen.get(f"{country}|{dow}", gen["ALL"]).copy()
    out = {}
    for c in STRUCT_COLS:
        if c == "n_placement_types":
            out[c] = float(max(1.0, base[c] + rng.normal(0, 0.3)))
            continue
        out[c] = float(np.clip(base[c] + rng.normal(0, 0.05), 0.0, 1.0))
    return out


def attach_structural_features(panel: list[dict], struct_map: dict[tuple[str, str], dict[str, float]]) -> list[dict]:
    real_struct_rows = []
    for row in panel:
        if int(row.get("is_synthetic", 0)) == 0:
            key = (row["date"], row["country"])
            if key in struct_map:
                for c in STRUCT_COLS:
                    row[c] = struct_map[key][c]
                real_struct_rows.append(
                    {"country": row["country"], "dow": int(row["dow"]), **{c: row[c] for c in STRUCT_COLS}}
                )

    gen = fit_struct_generator(real_struct_rows) if real_struct_rows else {"ALL": {c: 0.0 for c in STRUCT_COLS}}
    struct_rng = np.random.default_rng(SEED + 1000)
    for row in panel:
        if int(row.get("is_synthetic", 0)) == 1:
            sampled = sample_struct(row["country"], int(row["dow"]), gen, struct_rng)
            for c in STRUCT_COLS:
                row[c] = sampled[c]
        for c in STRUCT_COLS:
            row.setdefault(c, 0.0)
    return panel


def build_panel() -> tuple[list[dict], dict]:
    rng = np.random.default_rng(SEED)
    real = build_real_panel()
    gen = fit_generator(real)
    synth = simulate_expand(real, gen, rng)
    panel = sorted(synth + real, key=lambda r: (r["date"], r["country"]))
    for r in panel:
        r["split"] = split_of(parse_day(r["date"]))

    struct_map, struct_stats = aggregate_structural_from_csv()
    panel = attach_structural_features(panel, struct_map)

    stats = {
        "product": "SK-II",
        "source_file": str(SRC),
        "n_features": 27,
        "feature_set": "extended_27",
        "n_panel_rows": len(panel),
        "n_real": sum(1 for r in panel if int(r["is_synthetic"]) == 0),
        "n_synthetic": sum(1 for r in panel if int(r["is_synthetic"]) == 1),
        "date_min": min(r["date"] for r in panel),
        "date_max": max(r["date"] for r in panel),
        "split_counts": _count(panel, "split"),
        "country_counts": _count(panel, "country"),
        "mean_revenue": sum(r["revenue"] for r in panel) / len(panel),
        "mean_cost": sum(r["cost"] for r in panel) / len(panel),
        "struct_stats": struct_stats,
        "generator": {
            "rev_coef": gen["rev_coef"],
            "rev_sigma": gen["rev_sigma"],
            "note": "log1p(R)~a+Σβlog1p(B)+weekend+CA；合成日仅用于扩训；结构份额按市场×星期采样",
        },
        "time_split": {
            "train": f"<= {TRAIN_END}",
            "val": f"{TRAIN_END + timedelta(days=1)} .. {VAL_END}",
            "test": f">= {VAL_END + timedelta(days=1)}",
        },
        "note": "真实 July 62 行 + 模拟 Jan–Jun；Extended 27 维（含 P0 结构）；无 ASIN。",
    }
    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / "generator_params.json").write_text(json.dumps(gen, indent=2), encoding="utf-8")
    return panel, stats


FEATURE_COLS = [
    "log1p_budget_sp",
    "log1p_budget_sb",
    "log1p_budget_sd",
    "log1p_budget_dsp",
    "share_sp",
    "share_sb",
    "share_sd",
    "share_dsp",
    "has_ad",
    "is_weekend",
    "dow",
    "country",
    *STRUCT_COLS,
]


def write_outputs(panel: list[dict], stats: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "date",
        "country",
        "product",
        "split",
        "is_synthetic",
        "cost",
        "budget_sp",
        "budget_sb",
        "budget_sd",
        "budget_dsp",
        "share_sp",
        "share_sb",
        "share_sd",
        "share_dsp",
        "clicks",
        "impressions",
        "impressions_sp",
        "impressions_sb",
        "impressions_sd",
        "impressions_dsp",
        "gmv_ad",
        "sales_ad",
        "revenue",
        "has_ad",
        "dow",
        "is_weekend",
        "log1p_budget_sp",
        "log1p_budget_sb",
        "log1p_budget_sd",
        "log1p_budget_dsp",
        "log1p_impressions_sp",
        "log1p_impressions_sb",
        "log1p_impressions_sd",
        "log1p_impressions_dsp",
        "log1p_revenue",
        "log1p_impressions",
        "log1p_clicks",
        "log1p_sales_ad",
        *STRUCT_COLS,
    ]
    path = OUT / "prediction_panel.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(panel)

    schema = {
        "grain": "marketplace + date（SK-II，无 asin）",
        "product": "SK-II",
        "augmentation": "Jan–Jun 模拟；July 真实",
        "version": "v1.5-extended-27",
        "n_features": 27,
        "feature_cols": FEATURE_COLS,
        "struct_cols": list(STRUCT_COLS),
        "time_split": stats["time_split"],
        "aux_labels": {
            "traffic": "log1p_impressions_*",
            "efficiency": "log1p_sales_ad",
            "revenue": "log1p_revenue",
        },
        "note": "主口径 Extended 27 维；勿将当期 clicks/impressions 作输入",
    }
    (OUT / "dataset_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "feature_schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    priors = {
        "ad_types": list(AD_TYPES),
        "elasticities_for_whatif": {"sp": 0.40, "sb": 0.22, "sd": 0.16, "dsp": 0.12},
    }
    (OUT / "type_budget_priors.json").write_text(json.dumps(priors, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path} rows={len(panel)}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def main() -> None:
    panel, stats = build_panel()
    write_outputs(panel, stats)


if __name__ == "__main__":
    main()
