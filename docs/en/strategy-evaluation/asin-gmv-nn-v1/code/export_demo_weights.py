#!/usr/bin/env python3
"""Train Extended-27 MLP and export weights for BrandLens demo (browser JS)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parent
OUT_DIR = CODE_DIR.parent
RESULT_DIR = OUT_DIR / "results"
DEMO_JSON = RESULT_DIR / "demo_mlp_extended27.json"

sys.path.insert(0, str(CODE_DIR))
from build_dataset import STRUCT_COLS  # noqa: E402
from train_models import SEED, Standardizer, design_matrix, load_panel, metrics, train_mlp  # noqa: E402


def main() -> None:
    rng = np.random.default_rng(SEED)
    panel = load_panel()
    train_rows = [r for r in panel if r["split"] == "train"]
    val_rows = [r for r in panel if r["split"] == "val"]
    test_rows = [r for r in panel if r["split"] == "test"]

    x_tr_raw, y_tr, catalogs, names = design_matrix(train_rows)
    x_va_raw, y_va, _, _ = design_matrix(val_rows, catalogs)
    x_te_raw, y_te, _, _ = design_matrix(test_rows, catalogs)
    assert x_tr_raw.shape[1] == 27, x_tr_raw.shape

    scaler = Standardizer().fit(x_tr_raw)
    x_tr = scaler.transform(x_tr_raw)
    x_va = scaler.transform(x_va_raw)
    x_te = scaler.transform(x_te_raw)
    rev_cap = float(np.percentile(y_tr["revenue"], 95) * 2.0)

    mlp, hist = train_mlp(x_tr, y_tr["log_revenue"], x_va, y_va["log_revenue"], rng)

    def decode(log_pred: np.ndarray) -> np.ndarray:
        return np.clip(np.expm1(np.clip(log_pred, 0, None)), 0, rev_cap)

    te_m = metrics(y_te["revenue"], decode(mlp.forward(x_te)[0]))

    real_us = [r for r in panel if int(r.get("is_synthetic", 0)) == 0 and r["country"] == "US"] or [
        r for r in panel if int(r.get("is_synthetic", 0)) == 0
    ]

    def mean_key(k: str) -> float:
        return float(np.mean([r[k] for r in real_us]))

    payload = {
        "version": "v1.5-extended-27-mlp",
        "product": "SK-II",
        "n_features": 27,
        "hidden": [32, 16],
        "feature_names": names,
        "country_classes": catalogs["country"],
        "scaler_mean": scaler.mean.tolist(),
        "scaler_std": scaler.std.tolist(),
        "rev_cap": rev_cap,
        "weights": {k: v.tolist() for k, v in mlp.params.items()},
        "defaults": {
            "budget_sp": mean_key("budget_sp"),
            "budget_sb": mean_key("budget_sb"),
            "budget_sd": mean_key("budget_sd"),
            "budget_dsp": mean_key("budget_dsp"),
            "is_weekend": 0,
            "dow": 2,
            "country": "US",
            "struct": {c: mean_key(c) for c in STRUCT_COLS},
        },
        "test_metrics": te_m,
        "epochs": hist[-1]["epoch"],
        "note": "Browser demo: MLP Extended-27 → log1p(attributed revenue).",
    }
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    DEMO_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"wrote": str(DEMO_JSON), "test": te_m, "n_features": 27}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
