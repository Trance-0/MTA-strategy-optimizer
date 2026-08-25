#!/usr/bin/env python3
"""SK-II 单品：MLP + 机制型多任务网（无 ASIN 维）。

默认输入：**Extended 27 维**（预算/份额/日历/市场 + P0 结构花费占比）。
仅 numpy / matplotlib。
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parent
OUT_DIR = CODE_DIR.parent
DATA_PATH = OUT_DIR / "data" / "prediction_panel.csv"
RESULT_DIR = OUT_DIR / "results"
MPL_DIR = OUT_DIR / ".mplconfig"
MPL_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_DIR)

from build_dataset import STRUCT_COLS  # noqa: E402

SEED = 42
HIDDEN = (32, 16)
DROPOUT = 0.15
LR = 1e-3
WEIGHT_DECAY = 1e-4
EPOCHS = 400
PATIENCE = 40
BATCH = 32
LAMBDA_REV = 1.0
LAMBDA_TRAFFIC = 0.3
LAMBDA_EFF = 0.2
AD_TYPES = ("sp", "sb", "sd", "dsp")
BUDGET_COLS = [f"log1p_budget_{g}" for g in AD_TYPES]
SHARE_COLS = [f"share_{g}" for g in AD_TYPES]
TYPE_ELASTICITY = {"sp": 0.40, "sb": 0.22, "sd": 0.16, "dsp": 0.12}


def log1p_np(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.clip(x, 0, None))


def load_panel() -> list[dict]:
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in row:
            if key in {"date", "country", "product", "asin", "brand", "split"}:
                continue
            if key == "is_synthetic":
                row[key] = int(float(row[key])) if row[key] != "" else 0
                continue
            row[key] = float(row[key]) if row[key] != "" else 0.0
    return rows


def one_hot(values: list[str], classes: list[str]) -> np.ndarray:
    index = {c: i for i, c in enumerate(classes)}
    out = np.zeros((len(values), len(classes)), dtype=np.float64)
    for i, value in enumerate(values):
        if value in index:
            out[i, index[value]] = 1.0
    return out


def design_matrix(rows: list[dict], catalogs: dict[str, list[str]] | None = None):
    """SK-II Extended-27：预算+份额+时间+市场+P0 结构；无 asin。"""
    for row in rows:
        for c in STRUCT_COLS:
            row.setdefault(c, 0.0)
    numeric = np.column_stack(
        [
            *[np.array([r[c] for r in rows]) for c in BUDGET_COLS],
            *[np.array([r[c] for r in rows]) for c in SHARE_COLS],
            np.array([r["has_ad"] for r in rows]),
            np.array([r["is_weekend"] for r in rows]),
        ]
    )
    dow = one_hot([str(int(r["dow"])) for r in rows], [str(i) for i in range(7)])
    if catalogs is None:
        catalogs = {"country": sorted({r["country"] for r in rows})}
    country = one_hot([r["country"] for r in rows], catalogs["country"])
    struct = np.column_stack([[r[c] for r in rows] for c in STRUCT_COLS])
    x = np.hstack([numeric, dow, country, struct])
    y = {
        "revenue": np.array([r["revenue"] for r in rows], dtype=np.float64),
        "log_revenue": np.array([r["log1p_revenue"] for r in rows], dtype=np.float64),
        "log_impr": np.column_stack([np.array([r[f"log1p_impressions_{g}"] for r in rows]) for g in AD_TYPES]),
        "log_sales_ad": np.array([r["log1p_sales_ad"] for r in rows], dtype=np.float64),
        "budgets": np.column_stack([np.array([r[f"budget_{g}"] for r in rows]) for g in AD_TYPES]),
        "shares": np.column_stack([np.array([r[f"share_{g}"] for r in rows]) for g in AD_TYPES]),
    }
    names = (
        list(BUDGET_COLS)
        + list(SHARE_COLS)
        + ["has_ad", "is_weekend"]
        + [f"dow_{i}" for i in range(7)]
        + [f"country_{c}" for c in catalogs["country"]]
        + list(STRUCT_COLS)
    )
    return x, y, catalogs, names


class Standardizer:
    def fit(self, x: np.ndarray) -> "Standardizer":
        self.mean = x.mean(axis=0)
        self.std = x.std(axis=0)
        self.std[self.std < 1e-6] = 1.0
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std


def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def huber_grad(pred: np.ndarray, target: np.ndarray, delta: float = 1.0) -> tuple[float, np.ndarray]:
    pred = np.asarray(pred, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    squeeze = pred.ndim == 1
    if squeeze:
        pred = pred.reshape(-1, 1)
        target = target.reshape(-1, 1)
    err = pred - target
    abs_e = np.abs(err)
    quad = np.minimum(abs_e, delta)
    lin = abs_e - quad
    loss = float(np.mean(0.5 * quad**2 + delta * lin))
    grad = np.where(abs_e <= delta, err, delta * np.sign(err)) / err.size
    if squeeze:
        return loss, grad.ravel()
    return loss, grad


class Adam:
    def __init__(self, params: dict[str, np.ndarray], lr: float = LR):
        self.lr = lr
        self.t = 0
        self.m = {k: np.zeros_like(v) for k, v in params.items()}
        self.v = {k: np.zeros_like(v) for k, v in params.items()}

    def step(self, params: dict[str, np.ndarray], grads: dict[str, np.ndarray]) -> None:
        self.t += 1
        b1, b2, eps = 0.9, 0.999, 1e-8
        for key, grad in grads.items():
            self.m[key] = b1 * self.m[key] + (1 - b1) * grad
            self.v[key] = b2 * self.v[key] + (1 - b2) * (grad**2)
            mhat = self.m[key] / (1 - b1**self.t)
            vhat = self.v[key] / (1 - b2**self.t)
            params[key] -= self.lr * mhat / (np.sqrt(vhat) + eps)


def init_dense(rng: np.random.Generator, n_in: int, n_out: int) -> tuple[np.ndarray, np.ndarray]:
    w = rng.normal(0, np.sqrt(2.0 / n_in), size=(n_in, n_out))
    b = np.zeros(n_out)
    return w, b


class MLP:
    def __init__(self, n_in: int, rng: np.random.Generator):
        w1, b1 = init_dense(rng, n_in, HIDDEN[0])
        w2, b2 = init_dense(rng, HIDDEN[0], HIDDEN[1])
        w3, b3 = init_dense(rng, HIDDEN[1], 1)
        self.params = {"W1": w1, "b1": b1, "W2": w2, "b2": b2, "W3": w3, "b3": b3}
        self.rng = rng

    def forward(self, x: np.ndarray, train: bool = False) -> tuple[np.ndarray, dict]:
        h1_pre = x @ self.params["W1"] + self.params["b1"]
        h1 = relu(h1_pre)
        mask = np.ones_like(h1)
        if train and DROPOUT > 0:
            mask = (self.rng.random(h1.shape) >= DROPOUT).astype(np.float64) / (1.0 - DROPOUT)
            h1 = h1 * mask
        h2_pre = h1 @ self.params["W2"] + self.params["b2"]
        h2 = relu(h2_pre)
        y = (h2 @ self.params["W3"] + self.params["b3"]).ravel()
        cache = {"x": x, "h1_pre": h1_pre, "h1": h1, "mask": mask, "h2_pre": h2_pre, "h2": h2, "y": y}
        return y, cache

    def backward(self, cache: dict, d_y: np.ndarray) -> dict[str, np.ndarray]:
        d_y = d_y.reshape(-1, 1)
        grads = {}
        grads["W3"] = cache["h2"].T @ d_y + WEIGHT_DECAY * self.params["W3"]
        grads["b3"] = d_y.sum(axis=0)
        d_h2 = d_y @ self.params["W3"].T
        d_h2_pre = d_h2 * (cache["h2_pre"] > 0)
        grads["W2"] = cache["h1"].T @ d_h2_pre + WEIGHT_DECAY * self.params["W2"]
        grads["b2"] = d_h2_pre.sum(axis=0)
        d_h1 = d_h2_pre @ self.params["W2"].T
        d_h1 = d_h1 * cache["mask"]
        d_h1_pre = d_h1 * (cache["h1_pre"] > 0)
        grads["W1"] = cache["x"].T @ d_h1_pre + WEIGHT_DECAY * self.params["W1"]
        grads["b1"] = d_h1_pre.sum(axis=0)
        return grads


class MultiTaskNet:
    def __init__(self, n_in: int, rng: np.random.Generator):
        w1, b1 = init_dense(rng, n_in, HIDDEN[0])
        w2, b2 = init_dense(rng, HIDDEN[0], HIDDEN[1])
        wr, br = init_dense(rng, HIDDEN[1], 1)
        wt, bt = init_dense(rng, HIDDEN[1], 4)
        we, be = init_dense(rng, HIDDEN[1], 1)
        self.params = {
            "W1": w1,
            "b1": b1,
            "W2": w2,
            "b2": b2,
            "Wr": wr,
            "br": br,
            "Wt": wt,
            "bt": bt,
            "We": we,
            "be": be,
        }
        self.rng = rng

    def forward(self, x: np.ndarray, train: bool = False) -> tuple[dict[str, np.ndarray], dict]:
        h1_pre = x @ self.params["W1"] + self.params["b1"]
        h1 = relu(h1_pre)
        mask = np.ones_like(h1)
        if train and DROPOUT > 0:
            mask = (self.rng.random(h1.shape) >= DROPOUT).astype(np.float64) / (1.0 - DROPOUT)
            h1 = h1 * mask
        h2_pre = h1 @ self.params["W2"] + self.params["b2"]
        h2 = relu(h2_pre)
        out = {
            "rev": (h2 @ self.params["Wr"] + self.params["br"]).ravel(),
            "traf": h2 @ self.params["Wt"] + self.params["bt"],
            "eff": (h2 @ self.params["We"] + self.params["be"]).ravel(),
        }
        cache = {"x": x, "h1_pre": h1_pre, "h1": h1, "mask": mask, "h2_pre": h2_pre, "h2": h2}
        return out, cache

    def backward(self, cache: dict, d_heads: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        h2 = cache["h2"]
        grads: dict[str, np.ndarray] = {}
        d_rev = d_heads["rev"].reshape(-1, 1)
        d_traf = np.asarray(d_heads["traf"], dtype=np.float64)
        if d_traf.ndim == 1:
            d_traf = d_traf.reshape(-1, 1)
        d_eff = d_heads["eff"].reshape(-1, 1)
        grads["Wr"] = h2.T @ d_rev + WEIGHT_DECAY * self.params["Wr"]
        grads["br"] = d_rev.sum(axis=0)
        grads["Wt"] = h2.T @ d_traf + WEIGHT_DECAY * self.params["Wt"]
        grads["bt"] = d_traf.sum(axis=0)
        grads["We"] = h2.T @ d_eff + WEIGHT_DECAY * self.params["We"]
        grads["be"] = d_eff.sum(axis=0)
        d_h2 = (
            d_rev @ self.params["Wr"].T
            + d_traf @ self.params["Wt"].T
            + d_eff @ self.params["We"].T
        )
        d_h2_pre = d_h2 * (cache["h2_pre"] > 0)
        grads["W2"] = cache["h1"].T @ d_h2_pre + WEIGHT_DECAY * self.params["W2"]
        grads["b2"] = d_h2_pre.sum(axis=0)
        d_h1 = (d_h2_pre @ self.params["W2"].T) * cache["mask"]
        d_h1_pre = d_h1 * (cache["h1_pre"] > 0)
        grads["W1"] = cache["x"].T @ d_h1_pre + WEIGHT_DECAY * self.params["W1"]
        grads["b1"] = d_h1_pre.sum(axis=0)
        return grads


def iterate_minibatches(n: int, batch: int, rng: np.random.Generator):
    idx = rng.permutation(n)
    for start in range(0, n, batch):
        yield idx[start : start + batch]


def train_mlp(x_tr, y_tr, x_va, y_va, rng: np.random.Generator):
    model = MLP(x_tr.shape[1], rng)
    opt = Adam(model.params)
    best = None
    best_val = np.inf
    wait = 0
    history = []
    for epoch in range(1, EPOCHS + 1):
        losses = []
        for batch_idx in iterate_minibatches(len(x_tr), BATCH, rng):
            pred, cache = model.forward(x_tr[batch_idx], train=True)
            loss, grad = huber_grad(pred, y_tr[batch_idx])
            grads = model.backward(cache, grad)
            opt.step(model.params, grads)
            losses.append(loss)
        val_pred, _ = model.forward(x_va, train=False)
        val_loss, _ = huber_grad(val_pred, y_va)
        history.append({"epoch": epoch, "train": float(np.mean(losses)), "val": val_loss})
        if val_loss < best_val - 1e-5:
            best_val = val_loss
            best = {k: v.copy() for k, v in model.params.items()}
            wait = 0
        else:
            wait += 1
            if wait >= PATIENCE:
                break
    if best:
        model.params = best
    return model, history


def train_multitask(x_tr, y_tr, x_va, y_va, rng: np.random.Generator):
    model = MultiTaskNet(x_tr.shape[1], rng)
    opt = Adam(model.params)
    best = None
    best_val = np.inf
    wait = 0
    history = []
    for epoch in range(1, EPOCHS + 1):
        losses = []
        for batch_idx in iterate_minibatches(len(x_tr), BATCH, rng):
            out, cache = model.forward(x_tr[batch_idx], train=True)
            l_r, g_r = huber_grad(out["rev"], y_tr["log_revenue"][batch_idx])
            l_t, g_t = huber_grad(out["traf"], y_tr["log_impr"][batch_idx])
            l_e, g_e = huber_grad(out["eff"], y_tr["log_sales_ad"][batch_idx])
            loss = LAMBDA_REV * l_r + LAMBDA_TRAFFIC * l_t + LAMBDA_EFF * l_e
            grads = model.backward(
                cache,
                {
                    "rev": LAMBDA_REV * g_r,
                    "traf": LAMBDA_TRAFFIC * g_t,
                    "eff": LAMBDA_EFF * g_e,
                },
            )
            opt.step(model.params, grads)
            losses.append(loss)
        val_out, _ = model.forward(x_va, train=False)
        l_r, _ = huber_grad(val_out["rev"], y_va["log_revenue"])
        l_t, _ = huber_grad(val_out["traf"], y_va["log_impr"])
        l_e, _ = huber_grad(val_out["eff"], y_va["log_sales_ad"])
        val_loss = LAMBDA_REV * l_r + LAMBDA_TRAFFIC * l_t + LAMBDA_EFF * l_e
        history.append({"epoch": epoch, "train": float(np.mean(losses)), "val": val_loss, "val_rev": l_r})
        if val_loss < best_val - 1e-5:
            best_val = val_loss
            best = {k: v.copy() for k, v in model.params.items()}
            wait = 0
        else:
            wait += 1
            if wait >= PATIENCE:
                break
    if best:
        model.params = best
    return model, history


def metrics(y: np.ndarray, yhat: np.ndarray) -> dict[str, float]:
    yhat = np.clip(yhat, 0, None)
    err = yhat - y
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    medae = float(np.median(np.abs(err)))
    denom = np.abs(y) + np.abs(yhat) + 1e-6
    smape = float(np.mean(2.0 * np.abs(err) / denom))
    mask = y >= 10
    mape = float(np.mean(np.abs(err[mask]) / y[mask])) if mask.any() else float("nan")
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    log_y = log1p_np(y)
    log_hat = log1p_np(yhat)
    ss_res_l = float(np.sum((log_hat - log_y) ** 2))
    ss_tot_l = float(np.sum((log_y - log_y.mean()) ** 2))
    r2_log = 1.0 - ss_res_l / ss_tot_l if ss_tot_l > 0 else float("nan")
    return {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "MedAE": round(medae, 4),
        "sMAPE": round(smape, 4),
        "MAPE_gmv>=10": None if np.isnan(mape) else round(mape, 4),
        "R2": None if np.isnan(r2) else round(r2, 4),
        "R2_log1p": None if np.isnan(r2_log) else round(r2_log, 4),
        "n": int(len(y)),
        "n_gmv_ge_10": int(mask.sum()),
    }


def apply_new_budgets(x_raw: np.ndarray, new_budgets: np.ndarray) -> np.ndarray:
    """写入 log1p 四类预算（列 0-3）和份额（列 4-7）。"""
    out = x_raw.copy()
    budgets = np.clip(new_budgets, 0, None)
    out[:, 0:4] = np.log1p(budgets)
    total = budgets.sum(axis=1, keepdims=True)
    shares = np.divide(budgets, total, out=np.zeros_like(budgets), where=total > 0)
    zero = total.ravel() <= 0
    shares[zero] = x_raw[zero, 4:8]
    out[:, 4:8] = shares
    return out


def shares_of(budgets: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    total = budgets.sum(axis=1, keepdims=True)
    shares = np.divide(budgets, total, out=np.zeros_like(budgets), where=total > 0)
    zero = total.ravel() <= 0
    shares[zero] = fallback[zero]
    return shares


def mix_multiplier(share_old: np.ndarray, share_new: np.ndarray) -> np.ndarray:
    elasticity = np.array([TYPE_ELASTICITY[g] for g in AD_TYPES], dtype=np.float64)
    quality_old = share_old @ elasticity
    quality_new = share_new @ elasticity
    return quality_new / np.clip(quality_old, 1e-6, None)


def predict_with_mix(predict_fn, scaler: Standardizer, x_raw: np.ndarray, budgets_new: np.ndarray, shares_old: np.ndarray) -> np.ndarray:
    x_new = apply_new_budgets(x_raw, budgets_new)
    nn = predict_fn(scaler.transform(x_new))
    return nn * mix_multiplier(shares_old, shares_of(budgets_new, shares_old))


def scenario_summary(name: str, base_pred: np.ndarray, new_pred: np.ndarray) -> dict:
    delta = new_pred - base_pred
    return {
        "scenario": name,
        "mean_pred_base": round(float(base_pred.mean()), 4),
        "mean_pred_new": round(float(new_pred.mean()), 4),
        "mean_delta": round(float(delta.mean()), 4),
        "median_delta": round(float(np.median(delta)), 4),
        "share_up": round(float(np.mean(delta > 1e-6)), 4),
    }


def monotonicity_check(predict_fn, x: np.ndarray, scaler: Standardizer) -> dict:
    x_raw = x * scaler.std + scaler.mean
    budgets = np.expm1(np.clip(x_raw[:, 0:4], 0, None))
    bumped = apply_new_budgets(x_raw, budgets * 1.1)
    base = predict_fn(scaler.transform(x_raw))
    up = predict_fn(scaler.transform(bumped))
    delta = up - base
    return {
        "n": int(len(base)),
        "share_pred_up": round(float(np.mean(delta > 0)), 4),
        "share_pred_flat": round(float(np.mean(np.abs(delta) < 1e-6)), 4),
        "median_delta_gmv": round(float(np.median(delta)), 4),
        "mean_delta_gmv": round(float(np.mean(delta)), 4),
    }


def save_plots(hist_mlp, hist_mt, y_true, preds: dict[str, np.ndarray]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([h["epoch"] for h in hist_mlp], [h["val"] for h in hist_mlp], label="MLP val Huber")
    ax.plot([h["epoch"] for h in hist_mt], [h["val"] for h in hist_mt], label="Multitask val loss")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title("Validation loss")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULT_DIR / "learning_curves.png", dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharex=True, sharey=True)
    vmax = max(float(y_true.max()), max(float(v.max()) for v in preds.values()))
    for ax, (name, yhat) in zip(axes, preds.items()):
        ax.scatter(y_true, yhat, s=8, alpha=0.5)
        ax.plot([0, vmax], [0, vmax], color="black", linewidth=0.8)
        ax.set_title(name)
        ax.set_xlabel("Actual attributed sales")
        if ax is axes[0]:
            ax.set_ylabel("Predicted")
    fig.suptitle("Test set: budget -> attributed revenue")
    fig.tight_layout()
    fig.savefig(RESULT_DIR / "pred_vs_actual.png", dpi=120)
    plt.close(fig)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    rows = load_panel()
    train_rows = [r for r in rows if r["split"] == "train"]
    val_rows = [r for r in rows if r["split"] == "val"]
    test_rows = [r for r in rows if r["split"] == "test"]

    x_tr_raw, y_tr, catalogs, names = design_matrix(train_rows)
    x_va_raw, y_va, _, _ = design_matrix(val_rows, catalogs)
    x_te_raw, y_te, _, _ = design_matrix(test_rows, catalogs)

    scaler = Standardizer().fit(x_tr_raw)
    x_tr, x_va, x_te = map(scaler.transform, (x_tr_raw, x_va_raw, x_te_raw))

    # 单品小样本：限制预测上限，避免 expm1 爆炸
    rev_cap = float(np.percentile(y_tr["revenue"], 95) * 2.0)

    def decode(log_pred: np.ndarray) -> np.ndarray:
        return np.clip(np.expm1(np.clip(log_pred, 0, None)), 0, rev_cap)

    mlp, hist_mlp = train_mlp(x_tr, y_tr["log_revenue"], x_va, y_va["log_revenue"], rng)
    mlp_va = decode(mlp.forward(x_va)[0])
    mlp_te = decode(mlp.forward(x_te)[0])

    mt, hist_mt = train_multitask(x_tr, y_tr, x_va, y_va, rng)
    mt_va = decode(mt.forward(x_va)[0]["rev"])
    mt_te_out = mt.forward(x_te)[0]
    mt_te = decode(mt_te_out["rev"])

    def mlp_fn(z):
        return decode(mlp.forward(z)[0])

    def mt_fn(z):
        return decode(mt.forward(z)[0]["rev"])

    budgets = y_te["budgets"]
    shares = y_te["shares"]
    base_mix = predict_with_mix(mt_fn, scaler, x_te_raw, budgets, shares)
    scen_all = predict_with_mix(mt_fn, scaler, x_te_raw, budgets * 1.1, shares)
    sp_up = budgets.copy()
    sp_up[:, 0] *= 1.1
    scen_sp = predict_with_mix(mt_fn, scaler, x_te_raw, sp_up, shares)
    shift = budgets.copy()
    move = 0.2 * shift[:, 0]
    shift[:, 0] -= move
    shift[:, 1] += move
    scen_shift = predict_with_mix(mt_fn, scaler, x_te_raw, shift, shares)
    nn_only_shift = mt_fn(scaler.transform(apply_new_budgets(x_te_raw, shift)))

    report = {
        "n_features": int(x_tr.shape[1]),
        "feature_set": "extended_27",
        "hidden": list(HIDDEN),
        "inputs": list(BUDGET_COLS)
        + list(SHARE_COLS)
        + ["has_ad", "is_weekend", "dow", "marketplace"]
        + list(STRUCT_COLS),
        "label": "SK-II attributed sales (no ASIN)",
        "product": "SK-II",
        "baselines_removed": ["persistence_lag1", "ridge_log_elastic", "asin", "baseline_19"],
        "type_elasticities_prior": TYPE_ELASTICITY,
        "split_rows": {"train": len(train_rows), "val": len(val_rows), "test": len(test_rows)},
        "split_synthetic": {
            "train_synth": sum(1 for r in train_rows if int(r.get("is_synthetic", 0)) == 1),
            "val_real": sum(1 for r in val_rows if int(r.get("is_synthetic", 0)) == 0),
            "test_real": sum(1 for r in test_rows if int(r.get("is_synthetic", 0)) == 0),
        },
        "epochs_mlp": hist_mlp[-1]["epoch"],
        "epochs_multitask": hist_mt[-1]["epoch"],
        "val": {
            "mlp": metrics(y_va["revenue"], mlp_va),
            "multitask": metrics(y_va["revenue"], mt_va),
        },
        "test": {
            "mlp": metrics(y_te["revenue"], mlp_te),
            "multitask": metrics(y_te["revenue"], mt_te),
        },
        "test_aux_multitask": {
            "type_impressions_sum": metrics(
                np.expm1(y_te["log_impr"]).sum(axis=1),
                np.expm1(np.clip(mt_te_out["traf"], 0, None)).sum(axis=1),
            ),
            "sales_ad": metrics(np.expm1(y_te["log_sales_ad"]), np.expm1(np.clip(mt_te_out["eff"], 0, None))),
        },
        "monotonicity_all_types_plus10pct": {
            "mlp": monotonicity_check(mlp_fn, x_te, scaler),
            "multitask": monotonicity_check(mt_fn, x_te, scaler),
        },
        "whatif_test_multitask_plus_prior": {
            "all_types_plus10pct": scenario_summary("四类预算同时+10%", base_mix, scen_all),
            "sp_only_plus10pct": scenario_summary("仅 SP +10%", base_mix, scen_sp),
            "shift_20pct_sp_to_sb": scenario_summary("SP 的 20% 改投 SB（总额不变）", base_mix, scen_shift),
            "shift_20pct_sp_to_sb_nn_only": scenario_summary("同上但不用先验弹性（纯网络）", mt_te, nn_only_shift),
        },
        "caveat": "Extended-27 主口径。训练含 Jan–Jun 模拟日；测试段含真实 July 后半。无 ASIN。",
    }

    # 结构快照（供详细模型文档引用）
    n_in = int(x_tr.shape[1])
    structure = {
        "input_dim": n_in,
        "feature_names": names,
        "mlp": {
            "layers": [
                {"name": "Dense1", "in": n_in, "out": HIDDEN[0], "act": "ReLU", "dropout": DROPOUT},
                {"name": "Dense2", "in": HIDDEN[0], "out": HIDDEN[1], "act": "ReLU"},
                {"name": "Out", "in": HIDDEN[1], "out": 1, "act": "linear", "target": "log1p(revenue)"},
            ],
            "n_params": int(
                n_in * HIDDEN[0]
                + HIDDEN[0]
                + HIDDEN[0] * HIDDEN[1]
                + HIDDEN[1]
                + HIDDEN[1] * 1
                + 1
            ),
        },
        "multitask": {
            "shared": [
                {"name": "Dense1", "in": n_in, "out": HIDDEN[0], "act": "ReLU", "dropout": DROPOUT},
                {"name": "Dense2", "in": HIDDEN[0], "out": HIDDEN[1], "act": "ReLU"},
            ],
            "heads": {
                "traffic": {"out": 4, "target": "log1p(impressions_sp/sb/sd/dsp)", "lambda": LAMBDA_TRAFFIC},
                "efficiency": {"out": 1, "target": "log1p(sales_ad)", "lambda": LAMBDA_EFF},
                "revenue": {"out": 1, "target": "log1p(revenue)", "lambda": LAMBDA_REV},
            },
            "n_params": int(
                n_in * HIDDEN[0]
                + HIDDEN[0]
                + HIDDEN[0] * HIDDEN[1]
                + HIDDEN[1]
                + HIDDEN[1] * 1
                + 1
                + HIDDEN[1] * 4
                + 4
                + HIDDEN[1] * 1
                + 1
            ),
        },
        "train": {
            "optimizer": "Adam",
            "lr": LR,
            "weight_decay": WEIGHT_DECAY,
            "loss": "Huber(delta=1) on log1p space",
            "batch": BATCH,
            "early_stopping_patience": PATIENCE,
        },
    }
    (RESULT_DIR / "model_structure.json").write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")

    pred_path = RESULT_DIR / "test_predictions.csv"
    with pred_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date",
                "country",
                "product",
                "revenue",
                "pred_mlp",
                "pred_multitask",
                "budget_sp",
                "budget_sb",
                "budget_sd",
                "budget_dsp",
            ]
        )
        for i, row in enumerate(test_rows):
            writer.writerow(
                [
                    row["date"],
                    row["country"],
                    row.get("product", "SK-II"),
                    row["revenue"],
                    mlp_te[i],
                    mt_te[i],
                    row["budget_sp"],
                    row["budget_sb"],
                    row["budget_sd"],
                    row["budget_dsp"],
                ]
            )

    (RESULT_DIR / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULT_DIR / "history_mlp.json").write_text(json.dumps(hist_mlp), encoding="utf-8")
    (RESULT_DIR / "history_multitask.json").write_text(json.dumps(hist_mt), encoding="utf-8")
    save_plots(hist_mlp, hist_mt, y_te["revenue"], {"MLP": mlp_te, "multitask": mt_te})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("features", len(names), "wrote", RESULT_DIR)


if __name__ == "__main__":
    main()
