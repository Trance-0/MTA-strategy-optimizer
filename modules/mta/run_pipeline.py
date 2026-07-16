from __future__ import annotations

from pathlib import Path

from config import (
    ATTRIBUTION_OUTPUT_DIR,
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    DATA_DIR,
    FIGURE_OUTPUT_DIR,
)
from scripts.plot_mta_comparison import generate_figures
from scripts.run_mta_attribution import run_attribution


def main() -> None:
    attribution_files = run_attribution(
        data_dir=Path(DATA_DIR),
        output_dir=Path(ATTRIBUTION_OUTPUT_DIR),
    )
    figure_files = generate_figures(
        data_dir=Path(DATA_DIR),
        output_dir=Path(FIGURE_OUTPUT_DIR),
        iterations=BOOTSTRAP_ITERATIONS,
        seed=BOOTSTRAP_SEED,
    )

    print("Pipeline complete.")
    print("Attribution outputs:")
    for path in attribution_files:
        print(f"- {path}")
    print("Figure outputs:")
    for path in figure_files:
        print(f"- {path}")


if __name__ == "__main__":
    main()

