from __future__ import annotations

import argparse
import html
import random
import sys
from pathlib import Path
from statistics import mean


MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MTA_ROOT / "src"))
sys.path.insert(0, str(MTA_ROOT))

from config import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    CHANNEL_SPEND_FILE,
    DATA_DIR,
    FIGURE_OUTPUT_DIR,
    MARKOV_PATHS_FILE,
    SHAPLEY_CHANNEL_SETS_FILE,
)
from mta_attribution import (
    MarkovChainAttribution,
    ShapleyValueAttribution,
    add_roi_metrics,
    load_spend_by_channel,
    read_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate bootstrap boxplot SVGs comparing Markov and Shapley attribution."
    )
    parser.add_argument(
        "--data-dir",
        default=DATA_DIR,
        type=Path,
        help="Directory containing simulated MTA input files.",
    )
    parser.add_argument(
        "--output-dir",
        default=FIGURE_OUTPUT_DIR,
        type=Path,
        help="Directory where SVG charts will be written.",
    )
    parser.add_argument(
        "--iterations",
        default=BOOTSTRAP_ITERATIONS,
        type=int,
        help="Bootstrap iterations per model.",
    )
    parser.add_argument(
        "--seed",
        default=BOOTSTRAP_SEED,
        type=int,
        help="Random seed for reproducible bootstrap samples.",
    )
    return parser.parse_args()


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def box_stats(values: list[float]) -> dict:
    ordered = sorted(values)
    q1 = percentile(ordered, 0.25)
    med = percentile(ordered, 0.5)
    q3 = percentile(ordered, 0.75)
    iqr = q3 - q1
    low_bound = q1 - 1.5 * iqr
    high_bound = q3 + 1.5 * iqr
    whisker_low = min(v for v in ordered if v >= low_bound)
    whisker_high = max(v for v in ordered if v <= high_bound)
    outliers = [v for v in ordered if v < whisker_low or v > whisker_high]
    return {
        "q1": q1,
        "median": med,
        "q3": q3,
        "mean": mean(ordered),
        "whisker_low": whisker_low,
        "whisker_high": whisker_high,
        "outliers": outliers,
    }


def bootstrap_attribution(
    data_dir: Path,
    iterations: int,
    seed: int,
    metric: str = "attributed_revenue",
) -> tuple[dict, dict]:
    rng = random.Random(seed)
    path_rows = read_csv(data_dir / MARKOV_PATHS_FILE)
    set_rows = read_csv(data_dir / SHAPLEY_CHANNEL_SETS_FILE)
    spend = load_spend_by_channel(data_dir / CHANNEL_SPEND_FILE)

    if len(path_rows) != len(set_rows):
        raise ValueError("markov_user_paths.csv and shapley_user_channel_sets.csv must have the same user count.")

    n = len(path_rows)
    channels = sorted(spend.keys())
    markov_values = {channel: [] for channel in channels}
    shapley_values = {channel: [] for channel in channels}

    for _ in range(iterations):
        sample_indices = [rng.randrange(n) for _ in range(n)]
        path_sample = [path_rows[i] for i in sample_indices]
        set_sample = [set_rows[i] for i in sample_indices]

        markov_results = add_roi_metrics(
            MarkovChainAttribution(path_sample).attribute(),
            spend,
        )
        shapley_results = add_roi_metrics(
            ShapleyValueAttribution(set_sample).attribute(),
            spend,
        )

        for result in markov_results:
            value = getattr(result, metric)
            if value is not None:
                markov_values[result.channel].append(value)
        for result in shapley_results:
            value = getattr(result, metric)
            if value is not None:
                shapley_values[result.channel].append(value)

    return markov_values, shapley_values


def y_bounds(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        padding = abs(max_value) * 0.1 or 1.0
        return min_value - padding, max_value + padding
    span = max_value - min_value
    return min(0.0, min_value - span * 0.08), max(0.0, max_value + span * 0.08)


def render_panel(
    title: str,
    values_by_channel: dict[str, list[float]],
    width: int,
    height: int,
    top: int,
    y_min: float,
    y_max: float,
    y_axis_label: str,
    tick_decimals: int = 0,
) -> str:
    left = 78
    right = width - 35
    panel_top = top + 48
    panel_bottom = top + height - 54
    plot_width = right - left
    plot_height = panel_bottom - panel_top
    channels = list(values_by_channel.keys())
    step = plot_width / len(channels)
    box_width = min(44, step * 0.46)

    def sx(i: int) -> float:
        return left + step * (i + 0.5)

    def sy(value: float) -> float:
        if y_max == y_min:
            return panel_bottom
        return panel_bottom - ((value - y_min) / (y_max - y_min)) * plot_height

    parts = [
        f'<text x="{width / 2}" y="{top + 24}" text-anchor="middle" '
        f'font-family="Helvetica, Arial, sans-serif" font-size="18" font-weight="700">{html.escape(title)}</text>',
        f'<rect x="{left}" y="{panel_top}" width="{plot_width}" height="{plot_height}" fill="white" stroke="black" stroke-width="1"/>',
    ]

    tick_count = 4
    for t in range(tick_count + 1):
        value = y_min + (y_max - y_min) * t / tick_count
        y = sy(value)
        parts.append(f'<line x1="{left - 5}" y1="{y:.2f}" x2="{left}" y2="{y:.2f}" stroke="black" stroke-width="1"/>')
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="11">{value:,.{tick_decimals}f}</text>'
        )

    for i, channel in enumerate(channels):
        x = sx(i)
        stats = box_stats(values_by_channel[channel])
        q1 = sy(stats["q1"])
        q3 = sy(stats["q3"])
        median = sy(stats["median"])
        whisker_low = sy(stats["whisker_low"])
        whisker_high = sy(stats["whisker_high"])
        mean_y = sy(stats["mean"])

        parts.extend(
            [
                f'<line x1="{x:.2f}" y1="{whisker_low:.2f}" x2="{x:.2f}" y2="{q1:.2f}" stroke="black" stroke-width="1"/>',
                f'<line x1="{x:.2f}" y1="{q3:.2f}" x2="{x:.2f}" y2="{whisker_high:.2f}" stroke="black" stroke-width="1"/>',
                f'<line x1="{x - box_width / 4:.2f}" y1="{whisker_low:.2f}" x2="{x + box_width / 4:.2f}" y2="{whisker_low:.2f}" stroke="black" stroke-width="1"/>',
                f'<line x1="{x - box_width / 4:.2f}" y1="{whisker_high:.2f}" x2="{x + box_width / 4:.2f}" y2="{whisker_high:.2f}" stroke="black" stroke-width="1"/>',
                f'<rect x="{x - box_width / 2:.2f}" y="{q3:.2f}" width="{box_width:.2f}" height="{max(q1 - q3, 1):.2f}" fill="white" stroke="black" stroke-width="1"/>',
                f'<line x1="{x - box_width / 2:.2f}" y1="{median:.2f}" x2="{x + box_width / 2:.2f}" y2="{median:.2f}" stroke="black" stroke-width="2"/>',
                f'<line x1="{x - 5:.2f}" y1="{mean_y:.2f}" x2="{x + 5:.2f}" y2="{mean_y:.2f}" stroke="black" stroke-width="1.5"/>',
                f'<line x1="{x:.2f}" y1="{mean_y - 5:.2f}" x2="{x:.2f}" y2="{mean_y + 5:.2f}" stroke="black" stroke-width="1.5"/>',
            ]
        )

        for outlier in stats["outliers"]:
            y = sy(outlier)
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5" fill="white" stroke="black" stroke-width="1"/>')

        parts.append(f'<line x1="{x:.2f}" y1="{panel_bottom}" x2="{x:.2f}" y2="{panel_bottom + 9}" stroke="black" stroke-width="1"/>')
        parts.append(
            f'<text x="{x:.2f}" y="{panel_bottom + 28}" text-anchor="middle" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="12">{html.escape(channel)}</text>'
        )

    parts.append(
        f'<text x="{left - 54}" y="{(panel_top + panel_bottom) / 2}" text-anchor="middle" '
        f'transform="rotate(-90 {left - 54} {(panel_top + panel_bottom) / 2})" '
        f'font-family="Helvetica, Arial, sans-serif" font-size="12">{html.escape(y_axis_label)}</text>'
    )

    return "\n".join(parts)


def render_svg(
    markov_values: dict[str, list[float]],
    shapley_values: dict[str, list[float]],
    output_path: Path,
    title1: str = "Markov Chain Attribution",
    title2: str = "Shapley Value Attribution",
    y_axis_label: str = "Attributed revenue",
    tick_decimals: int = 0,
) -> None:
    width = 780
    panel_height = 360
    gap = 54
    height = panel_height * 2 + gap + 20
    all_values = [
        value
        for values_by_channel in (markov_values, shapley_values)
        for values in values_by_channel.values()
        for value in values
    ]
    y_min, y_max = y_bounds(all_values)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        render_panel(title1, markov_values, width, panel_height, 20, y_min, y_max, y_axis_label, tick_decimals),
        render_panel(
            title2,
            shapley_values,
            width,
            panel_height,
            20 + panel_height + gap,
            y_min,
            y_max,
            y_axis_label,
            tick_decimals,
        ),
        "</svg>",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg))


def render_single_svg(
    values: dict[str, list[float]],
    output_path: Path,
    title: str,
    y_axis_label: str = "Attributed revenue",
    tick_decimals: int = 0,
) -> None:
    width = 780
    panel_height = 360
    height = panel_height + 40
    all_values = [value for series in values.values() for value in series]
    y_min, y_max = y_bounds(all_values)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        render_panel(title, values, width, panel_height, 20, y_min, y_max, y_axis_label, tick_decimals),
        "</svg>",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg))


def generate_figures(
    data_dir: Path,
    output_dir: Path,
    iterations: int,
    seed: int,
) -> list[Path]:
    markov_values, shapley_values = bootstrap_attribution(
        data_dir=data_dir,
        iterations=iterations,
        seed=seed,
    )
    markov_roi_values, shapley_roi_values = bootstrap_attribution(
        data_dir=data_dir,
        iterations=iterations,
        seed=seed,
        metric="roi",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_output = output_dir / "mta_model_comparison.svg"
    roi_comparison_output = output_dir / "mta_roi_comparison.svg"
    markov_output = output_dir / "markov_bootstrap_boxplot.svg"
    shapley_output = output_dir / "shapley_bootstrap_boxplot.svg"
    render_svg(
        markov_values,
        shapley_values,
        comparison_output,
    )
    render_svg(
        markov_roi_values,
        shapley_roi_values,
        roi_comparison_output,
        y_axis_label="ROI",
        tick_decimals=2,
    )
    render_single_svg(
        markov_values,
        markov_output,
        "Markov Chain Attribution",
    )
    render_single_svg(
        shapley_values,
        shapley_output,
        "Shapley Value Attribution",
    )
    return [comparison_output, roi_comparison_output, markov_output, shapley_output]


def main() -> None:
    args = parse_args()
    output_files = generate_figures(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        iterations=args.iterations,
        seed=args.seed,
    )
    for path in output_files:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
