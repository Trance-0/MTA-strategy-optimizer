"""Run the contributed budget-to-revenue networks on canonical data.

The contributed trainer lives in ``contrib/mlp/code/train_models.py`` and is
never edited, never copied, and never forked. This module imports it at
runtime and calls its functions, so there is exactly one version of that model
and it is the contributor's own.

Two things separate their code from this project, and both are settled here:

- **Grain.** Their row is one marketplace-day carrying a four-way advertising
  budget vector for one product. This project's row is one Campaign's period.
  :func:`panel_from_response_dataset` pivots the second onto the first, using
  each Campaign's ``ad_product`` to choose which of the four budget slots its
  budget lands in.
- **Quality.** Their recorded held-out coefficient of determination
  (R-squared) is negative on both networks, so predicted revenue from this
  model is not decision-grade. Every result this module returns carries that
  finding rather than presenting a prediction on its own.

Nothing from ``contrib/`` is imported at module scope, so this module imports
cleanly when NumPy is absent and fails only when a caller actually asks for a
fit. Importing the contributed trainer has two side effects it performs at
import time and this module does not suppress: it creates a ``.mplconfig``
directory beside itself and sets ``MPLCONFIGDIR``. ``.mplconfig/`` is ignored
by the root ``.gitignore`` so that cannot dirty the contributor's tree.

Data flow: ``CampaignResponseDataset`` -> here -> the contributed trainer ->
``script/evaluate_strategies.py`` -> ``strategy_evaluation.json``.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from modules.mta_strategy_recommendation.src.response_dataset import (
    CampaignResponseDataset,
    assert_no_forbidden_response_features,
)

#: Where the contributed trainer and its recorded run live. Read, never written.
CONTRIB_ROOT = Path(__file__).resolve().parents[1] / "contrib" / "mlp"
CONTRIBUTED_TRAINER_PATH = CONTRIB_ROOT / "code" / "train_models.py"
CONTRIBUTED_PANEL_PATH = CONTRIB_ROOT / "data" / "prediction_panel.csv"
CONTRIBUTED_METRICS_PATH = CONTRIB_ROOT / "results" / "metrics.json"

#: Module name the contributed trainer is registered under. Prefixed so it
#: cannot collide with an installed distribution called ``train_models``.
CONTRIBUTED_MODULE_NAME = "mta_contrib_mlp_train_models"

#: The four advertising types the contributed model knows, in its own column
#: order. Mirrored here rather than imported because building a panel row must
#: work without NumPy; :func:`load_contributed_trainer` checks the two agree,
#: so a change on their side is a loud failure rather than a silent mismatch.
AD_TYPES = ("sp", "sb", "sd", "dsp")

#: This project's ad products mapped onto those four types. A Campaign carries
#: exactly one ad product, so this decides which budget slot it fills.
AD_TYPE_BY_AD_PRODUCT = {
    "SPONSORED_PRODUCTS": "sp",
    "SPONSORED_BRANDS": "sb",
    "SPONSORED_DISPLAY": "sd",
    "AMAZON_DSP": "dsp",
}

#: Fewer rows than this and no fit is reported as meaningful. A chronological
#: 60/20/20 split of 100 rows leaves 20 in the held-out split, and an
#: R-squared computed on fewer than 20 points is a number rather than a
#: measurement. The current committed artifact has 20 marketplace-days, so it
#: is refused, and that refusal is the correct outcome rather than a failure.
MINIMUM_PANEL_ROWS = 100

#: The contributed networks, and the default. Multitask is the default because
#: its recorded held-out R-squared, while negative, is the better of the two.
NETWORK_MULTITASK = "multitask"
NETWORK_MLP = "mlp"
NETWORKS = (NETWORK_MULTITASK, NETWORK_MLP)
DEFAULT_NETWORK = NETWORK_MULTITASK

#: Panel sources, recorded on a fit so a reader knows which numbers may be
#: compared against the contributor's own ``results/metrics.json``.
SOURCE_CONTRIBUTOR_PANEL = "contributor_panel"
SOURCE_CANONICAL = "canonical"

#: Fit outcomes. Only ``fitted`` ran a network; the other two are refusals
#: that return a result rather than raising.
STATUS_FITTED = "fitted"
STATUS_INSUFFICIENT_DATA = "insufficient_data"
STATUS_AUXILIARY_LABELS_UNAVAILABLE = "auxiliary_labels_unavailable"

#: Stated on every report. The model has learned the shape of the
#: budget-to-revenue relationship without learning its level.
QUALITY_CAVEAT = (
    "The contributed model's recorded held-out R-squared is negative on both "
    "networks, meaning its predictions are further from observed revenue than "
    "predicting the training mean would have been. No budget decision may be "
    "taken from its predicted revenue; only its directional behaviour, "
    "measured by the monotonicity check, is usable."
)


class ContributedModelError(RuntimeError):
    """The contributed model cannot be run, with the reason."""


@dataclass(frozen=True)
class AdaptedPanel:
    """Canonical observations pivoted onto the contributed model's row shape.

    Attributes:
        rows: One row per marketplace and date, in the contributed panel's own
            key names, sorted by marketplace then date so the same dataset
            always yields the same design matrix.
        feature_names: The design-matrix column names these rows will produce.
            Checked against ``FORBIDDEN_RESPONSE_FEATURES`` before any fit.
        marketplaces: Every marketplace present, in stable order.
        campaign_ids: Every Campaign that contributed budget, in stable order.
            Empty for the contributor's own panel, which has no Campaigns.
        absent_ad_types: Advertising types no row spends on. These are not
            observed zero spend; they are products this Campaign Group does
            not run, and a reader must not read their zeros as evidence.
        has_auxiliary_labels: Whether the rows carry the multitask network's
            auxiliary targets. False for canonical rows, because this project
            records no attributed unit count for the efficiency head.
        recorded_split: Whether the rows carry the contributor's own train,
            validation, and test assignment.
        source: ``canonical`` or ``contributor_panel``.
    """

    rows: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    feature_names: tuple[str, ...] = field(default_factory=tuple)
    marketplaces: tuple[str, ...] = field(default_factory=tuple)
    campaign_ids: tuple[str, ...] = field(default_factory=tuple)
    absent_ad_types: tuple[str, ...] = field(default_factory=tuple)
    has_auxiliary_labels: bool = False
    recorded_split: bool = False
    source: str = SOURCE_CANONICAL

    def __len__(self) -> int:
        return len(self.rows)

    def to_dict(self) -> dict:
        """Return the panel's shape, without its rows, as JSON-compatible values."""

        return {
            "source": self.source,
            "row_count": len(self.rows),
            "feature_count": len(self.feature_names),
            "feature_names": list(self.feature_names),
            "marketplaces": list(self.marketplaces),
            "campaign_ids": list(self.campaign_ids),
            "absent_ad_types": list(self.absent_ad_types),
            "has_auxiliary_labels": self.has_auxiliary_labels,
            "recorded_split": self.recorded_split,
        }


@dataclass(frozen=True)
class ContributedModelFit:
    """What running the contributed model on one panel produced, or why not.

    Attributes:
        network: Which contributed network was asked for.
        status: ``fitted``, or the refusal that stopped it.
        panel: The panel's shape, so a result carries its own provenance.
        validation_metrics: The contributed ``metrics`` output on the
            validation split, or ``None`` when no fit ran.
        holdout_metrics: The same on the held-out split, which is the only
            split ``is_usable`` reads.
        monotonicity: The contributed monotonicity check on the held-out
            split: raise every budget by ten percent and count the rows whose
            prediction rises.
        epochs: Epochs actually run before early stopping.
        notes: Why a refusal happened, and what remains true regardless.
    """

    network: str
    status: str
    panel: AdaptedPanel
    validation_metrics: Mapping[str, Any] | None = None
    holdout_metrics: Mapping[str, Any] | None = None
    monotonicity: Mapping[str, Any] | None = None
    epochs: int | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def holdout_r_squared(self) -> float | None:
        """Return the held-out R-squared, or ``None`` when none was computed."""

        if not self.holdout_metrics:
            return None
        value = self.holdout_metrics.get("R2")
        return None if value is None else float(value)

    @property
    def is_usable(self) -> bool:
        """Return whether this fit's predicted revenue may inform a decision.

        False whenever no fit ran and whenever the held-out R-squared is not
        positive. A model that loses to predicting the mean is not a model a
        budget may be moved on, so this is a property over the measurement
        rather than a flag a caller could set independently of it.
        """

        r_squared = self.holdout_r_squared
        return self.status == STATUS_FITTED and r_squared is not None and r_squared > 0

    def to_dict(self) -> dict:
        """Return this fit as JSON-compatible values."""

        return {
            "network": self.network,
            "status": self.status,
            "is_usable": self.is_usable,
            "holdout_r_squared": self.holdout_r_squared,
            "panel": self.panel.to_dict(),
            "validation_metrics": (
                None if self.validation_metrics is None else dict(self.validation_metrics)
            ),
            "holdout_metrics": (
                None if self.holdout_metrics is None else dict(self.holdout_metrics)
            ),
            "monotonicity": (
                None if self.monotonicity is None else dict(self.monotonicity)
            ),
            "epochs": self.epochs,
            "notes": list(self.notes),
        }


@functools.lru_cache(maxsize=1)
def load_contributed_trainer():
    """Import the contributed trainer as a module and return it.

    Importing trains nothing: their ``main()`` is guarded by
    ``if __name__ == "__main__"``, and their paths are self-locating, so the
    module works from its committed location with no path patching.

    Returns:
        The imported module, cached so repeated calls do not re-execute it.

    Raises:
        ContributedModelError: If NumPy is not installed, if the contributed
            trainer is not where this adapter expects it, or if its advertising
            types no longer match :data:`AD_TYPES`.
    """

    if importlib.util.find_spec("numpy") is None:
        raise ContributedModelError(
            "the contributed model needs NumPy, which is an opt-in dependency; "
            "install it with `uv sync --extra strategy-evaluation`"
        )
    if not CONTRIBUTED_TRAINER_PATH.exists():
        raise ContributedModelError(
            f"the contributed trainer is not at {CONTRIBUTED_TRAINER_PATH}; "
            "this adapter loads it in place and never copies it"
        )

    spec = importlib.util.spec_from_file_location(
        CONTRIBUTED_MODULE_NAME, CONTRIBUTED_TRAINER_PATH
    )
    if spec is None or spec.loader is None:
        raise ContributedModelError(
            f"{CONTRIBUTED_TRAINER_PATH} could not be loaded as a Python module"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    if tuple(getattr(module, "AD_TYPES", ())) != AD_TYPES:
        raise ContributedModelError(
            "the contributed model's advertising types "
            f"{tuple(getattr(module, 'AD_TYPES', ()))} no longer match this "
            f"adapter's {AD_TYPES}; the pivot would fill the wrong budget slots"
        )
    return module


def panel_from_response_dataset(dataset: CampaignResponseDataset) -> AdaptedPanel:
    """Pivot Campaign-period observations onto the contributed model's grain.

    Every observation sharing a marketplace and a period start becomes one
    row, and each Campaign's ``ad_product`` selects the budget slot its
    ``configured_budget`` lands in. A slot no Campaign fills gets zero and is
    named in ``absent_ad_types``, because a structural absence and an observed
    zero are different facts.

    Args:
        dataset: Canonical response observations. Only ``campaign_id``,
            ``marketplace``, ``report_start_date``, ``ad_product``,
            ``configured_budget``, and ``total_revenue`` are read.

    Returns:
        AdaptedPanel: Rows in the contributed panel's key names.

    Raises:
        ContributedModelError: If an observation carries an advertising
            product outside the four the contributed model knows, or a period
            start that is not an ISO date.
    """

    grouped: dict[tuple[str, str], dict[str, float]] = {}
    revenue: dict[tuple[str, str], float] = {}
    campaigns: dict[str, None] = {}
    for item in dataset:
        ad_type = AD_TYPE_BY_AD_PRODUCT.get(item.ad_product)
        if ad_type is None:
            raise ContributedModelError(
                f"campaign {item.campaign_id!r} runs ad product "
                f"{item.ad_product!r}, which is outside the four advertising "
                f"types the contributed model knows {AD_TYPES}"
            )
        key = (item.marketplace, item.report_start_date)
        budgets = grouped.setdefault(key, {name: 0.0 for name in AD_TYPES})
        budgets[ad_type] += float(item.configured_budget)
        revenue[key] = revenue.get(key, 0.0) + float(item.total_revenue)
        campaigns.setdefault(item.campaign_id, None)

    rows = tuple(
        _panel_row(marketplace, day, grouped[(marketplace, day)], revenue[(marketplace, day)])
        for marketplace, day in sorted(grouped)
    )
    marketplaces = sorted({marketplace for marketplace, _ in grouped})
    spent = {
        name
        for name in AD_TYPES
        if any(row[f"budget_{name}"] > 0.0 for row in rows)
    }
    feature_names = _feature_names(marketplaces)
    assert_no_forbidden_response_features(feature_names)
    return AdaptedPanel(
        rows=rows,
        feature_names=feature_names,
        marketplaces=tuple(marketplaces),
        campaign_ids=tuple(campaigns),
        absent_ad_types=tuple(name for name in AD_TYPES if name not in spent),
        has_auxiliary_labels=False,
        recorded_split=False,
        source=SOURCE_CANONICAL,
    )


def panel_from_contributor_file() -> AdaptedPanel:
    """Load the contributor's own panel through their own reader.

    Reproduces their experiment rather than this project's, so this is the
    only panel whose numbers may be compared against their recorded
    ``results/metrics.json``.

    Returns:
        AdaptedPanel: Their rows, with their recorded split and their
        auxiliary labels intact.

    Raises:
        ContributedModelError: If the contributed trainer cannot be loaded or
            their panel file is missing.
    """

    trainer = load_contributed_trainer()
    if not CONTRIBUTED_PANEL_PATH.exists():
        raise ContributedModelError(
            f"the contributor's panel is not at {CONTRIBUTED_PANEL_PATH}"
        )
    rows = tuple(trainer.load_panel())
    marketplaces = sorted({str(row["country"]) for row in rows})
    spent = {
        name
        for name in AD_TYPES
        if any(float(row[f"budget_{name}"]) > 0.0 for row in rows)
    }
    feature_names = _feature_names(marketplaces)
    assert_no_forbidden_response_features(feature_names)
    return AdaptedPanel(
        rows=rows,
        feature_names=feature_names,
        marketplaces=tuple(marketplaces),
        absent_ad_types=tuple(name for name in AD_TYPES if name not in spent),
        has_auxiliary_labels=True,
        recorded_split=_has_recorded_split(rows),
        source=SOURCE_CONTRIBUTOR_PANEL,
    )


def fit_contributed_model(
    panel: AdaptedPanel,
    *,
    network: str = DEFAULT_NETWORK,
    minimum_rows: int = MINIMUM_PANEL_ROWS,
) -> ContributedModelFit:
    """Fit the contributed network on one panel and measure what it learned.

    Never raises for a poor fit. A panel too small to measure, or one without
    the targets the requested network needs, returns a result whose
    ``is_usable`` is false and whose notes say why, because a refusal reported
    as a failure invites a retry that cannot succeed.

    Args:
        panel: Rows from :func:`panel_from_response_dataset` or
            :func:`panel_from_contributor_file`.
        network: ``multitask`` or ``mlp``.
        minimum_rows: Rows below which no fit is reported as meaningful.

    Returns:
        ContributedModelFit: A fitted result, or a refusal with its reason.

    Raises:
        ContributedModelError: If ``network`` is not one the contributed model
            provides, or the trainer cannot be loaded.
    """

    if network not in NETWORKS:
        raise ContributedModelError(
            f"the contributed model provides {NETWORKS}, not {network!r}"
        )
    if len(panel) < minimum_rows:
        return ContributedModelFit(
            network=network,
            status=STATUS_INSUFFICIENT_DATA,
            panel=panel,
            notes=(
                f"{len(panel)} rows is below the {minimum_rows} needed for a "
                f"held-out split large enough to measure, against a "
                f"{len(panel.feature_names)}-column design matrix.",
                QUALITY_CAVEAT,
            ),
        )
    if network == NETWORK_MULTITASK and not panel.has_auxiliary_labels:
        return ContributedModelFit(
            network=network,
            status=STATUS_AUXILIARY_LABELS_UNAVAILABLE,
            panel=panel,
            notes=(
                "The multitask network's traffic and efficiency heads need "
                "per-advertising-type impressions and an attributed unit "
                "count, and this project's response dataset records neither, "
                "so there is nothing for those heads to learn. Request "
                f"network={NETWORK_MLP!r} to fit the revenue head alone.",
                QUALITY_CAVEAT,
            ),
        )

    trainer = load_contributed_trainer()
    import numpy as np

    train_rows, validation_rows, holdout_rows = _split(panel)
    x_train_raw, y_train, catalogs, names = trainer.design_matrix(list(train_rows))
    x_validation_raw, y_validation, _, _ = trainer.design_matrix(
        list(validation_rows), catalogs
    )
    x_holdout_raw, y_holdout, _, _ = trainer.design_matrix(list(holdout_rows), catalogs)
    assert_no_forbidden_response_features(names)

    scaler = trainer.Standardizer().fit(x_train_raw)
    x_train = scaler.transform(x_train_raw)
    x_validation = scaler.transform(x_validation_raw)
    x_holdout = scaler.transform(x_holdout_raw)

    # The contributed trainer caps decoded revenue at twice the ninety-fifth
    # percentile of training revenue, which stops a large logarithm becoming an
    # absurd figure. Their `main()` is a script entry point rather than a
    # reusable function, so the three lines it uses to do that are restated
    # here; everything with a model in it is theirs.
    revenue_cap = float(np.percentile(y_train["revenue"], 95) * 2.0)

    def decode(log_prediction):
        return np.clip(np.expm1(np.clip(log_prediction, 0, None)), 0, revenue_cap)

    rng = np.random.default_rng(trainer.SEED)
    if network == NETWORK_MULTITASK:
        model, history = trainer.train_multitask(
            x_train, y_train, x_validation, y_validation, rng
        )

        def predict(matrix):
            return decode(model.forward(matrix)[0]["rev"])

    else:
        model, history = trainer.train_mlp(
            x_train, y_train["log_revenue"], x_validation, y_validation["log_revenue"], rng
        )

        def predict(matrix):
            return decode(model.forward(matrix)[0])

    return ContributedModelFit(
        network=network,
        status=STATUS_FITTED,
        panel=panel,
        validation_metrics=trainer.metrics(y_validation["revenue"], predict(x_validation)),
        holdout_metrics=trainer.metrics(y_holdout["revenue"], predict(x_holdout)),
        monotonicity=trainer.monotonicity_check(predict, x_holdout, scaler),
        epochs=int(history[-1]["epoch"]) if history else None,
        notes=(QUALITY_CAVEAT,),
    )


def contributed_model_report(
    dataset: CampaignResponseDataset,
    *,
    network: str = DEFAULT_NETWORK,
    minimum_rows: int = MINIMUM_PANEL_ROWS,
) -> dict:
    """Pivot, fit, and return one JSON-ready report on the contributed model.

    The single entry point ``script/evaluate_strategies.py`` calls. The
    contributor's own recorded metrics are read from their results file rather
    than restated here, so this report cannot drift from what they published.

    Args:
        dataset: Canonical response observations to fit against.
        network: ``multitask`` or ``mlp``.
        minimum_rows: Rows below which no fit is reported as meaningful.

    Returns:
        dict: The fit, the contributor's recorded quality, and the caveat.

    Raises:
        ContributedModelError: If the contributed model cannot be run at all.
    """

    fit = fit_contributed_model(
        panel_from_response_dataset(dataset),
        network=network,
        minimum_rows=minimum_rows,
    )
    return {
        "model_id": "asin_free_gmv_network",
        "contrib_folder": "mlp",
        "caveat": QUALITY_CAVEAT,
        "recorded_by_contributor": recorded_contributor_quality(),
        "fit": fit.to_dict(),
    }


def recorded_contributor_quality() -> dict | None:
    """Return the contributor's own recorded held-out quality, or ``None``.

    Read from their committed ``results/metrics.json`` rather than restated,
    so this project cannot report their model as better than they measured it.
    """

    if not CONTRIBUTED_METRICS_PATH.exists():
        return None
    recorded = json.loads(CONTRIBUTED_METRICS_PATH.read_text(encoding="utf-8"))
    monotonicity = recorded.get("monotonicity_all_types_plus10pct", {})
    return {
        "source": CONTRIBUTED_METRICS_PATH.relative_to(
            CONTRIB_ROOT.parents[1]
        ).as_posix(),
        "test": recorded.get("test"),
        "validation": recorded.get("val"),
        "monotonicity": monotonicity,
    }


def _panel_row(
    marketplace: str, day: str, budgets: Mapping[str, float], revenue: float
) -> dict[str, Any]:
    """Build one contributed-panel row from one marketplace-day's totals.

    The auxiliary targets are written as zero and flagged absent on the panel,
    never read: a canonical panel refuses the multitask fit that would use
    them, so no head is ever trained against a fabricated label.
    """

    try:
        weekday = date.fromisoformat(day).weekday()
    except ValueError as error:
        raise ContributedModelError(
            f"period start {day!r} is not an ISO date, so its day-of-week "
            "features cannot be derived"
        ) from error

    cost = sum(budgets[name] for name in AD_TYPES)
    row: dict[str, Any] = {
        "date": day,
        "country": marketplace,
        "split": "",
        "is_synthetic": 0,
        "cost": cost,
        "revenue": revenue,
        "log1p_revenue": math.log1p(max(revenue, 0.0)),
        "log1p_sales_ad": 0.0,
        "has_ad": 1.0 if cost > 0 else 0.0,
        "dow": float(weekday),
        "is_weekend": 1.0 if weekday >= 5 else 0.0,
    }
    for name in AD_TYPES:
        budget = max(budgets[name], 0.0)
        row[f"budget_{name}"] = budget
        row[f"share_{name}"] = budget / cost if cost > 0 else 0.0
        row[f"log1p_budget_{name}"] = math.log1p(budget)
        row[f"log1p_impressions_{name}"] = 0.0
    return row


def _feature_names(marketplaces: Sequence[str]) -> tuple[str, ...]:
    """Return the design-matrix column names the contributed model will build.

    Derived here rather than by importing the contributed module, so feature
    admissibility can be checked before NumPy is required.
    """

    return (
        tuple(f"log1p_budget_{name}" for name in AD_TYPES)
        + tuple(f"share_{name}" for name in AD_TYPES)
        + ("has_ad", "is_weekend")
        + tuple(f"dow_{index}" for index in range(7))
        + tuple(f"country_{marketplace}" for marketplace in marketplaces)
    )


def _has_recorded_split(rows: Iterable[Mapping[str, Any]]) -> bool:
    """Return whether every one of the contributor's three splits is populated."""

    present = {str(row.get("split", "")) for row in rows}
    return {"train", "val", "test"} <= present


def _split(
    panel: AdaptedPanel,
) -> tuple[
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
]:
    """Return the train, validation, and held-out rows for one panel.

    Uses the contributor's own assignment when their panel carries one, so
    their experiment is reproduced rather than re-split. Otherwise splits
    chronologically at sixty and eighty percent: a random split of a time
    series would put later days in training and score the model on days it had
    effectively already seen.
    """

    if panel.recorded_split:
        return (
            tuple(row for row in panel.rows if row["split"] == "train"),
            tuple(row for row in panel.rows if row["split"] == "val"),
            tuple(row for row in panel.rows if row["split"] == "test"),
        )
    count = len(panel.rows)
    train_end = int(count * 0.6)
    validation_end = int(count * 0.8)
    return (
        panel.rows[:train_end],
        panel.rows[train_end:validation_end],
        panel.rows[validation_end:],
    )
