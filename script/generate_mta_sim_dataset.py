"""Generate and adapt data with the pinned ZheyuanWu MTA-SIM submodule.

This is the primary project data-generation command. It runs the validated
external generator, writes its synthetic CSV bundle to a caller-owned output
directory, and immediately loads the path and performance tables through the
local four-to-five-segment adapter. Ground truth is generated for later model
evaluation but is never exposed to the model-facing dataset.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_standard.src.mta_sim_generator_adapter import (  # noqa: E402
    SUPPORTED_VARIANTS,
    generate_and_load_mta_sim_dataset,
)


DEFAULT_SUBMODULE = PROJECT_ROOT / "external" / "mta_sim_dataset"
DEFAULT_CONFIG = DEFAULT_SUBMODULE / "ZheyuanWu" / "examples" / "baseline.toy.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "generated" / "mta_sim"


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for external generation and adaptation."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate synthetic MTA data with ZheyuanWu and validate it through "
            "the local standardized adapter."
        )
    )
    parser.add_argument(
        "--submodule",
        type=Path,
        default=DEFAULT_SUBMODULE,
        help="Checkout root of the MTA-SIM-dataset submodule.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="ZheyuanWu baseline or regional configuration file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Ignored caller-owned directory for generated data.",
    )
    parser.add_argument(
        "--variant",
        choices=SUPPORTED_VARIANTS,
        default="baseline",
        help="ZheyuanWu generator family.",
    )
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Run generation, adapt model inputs, and print a compact JSON summary."""

    args = build_argument_parser().parse_args(arguments)
    try:
        generated = generate_and_load_mta_sim_dataset(
            submodule_root=args.submodule,
            configuration_path=args.config,
            output_directory=args.output,
            variant=args.variant,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"MTA-SIM generation failed: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "generator": generated.manifest["generator"],
                "generator_version": generated.manifest["generator_version"],
                "output_directory": str(generated.output_directory),
                "path_rows": len(generated.dataset.path_rows),
                "performance_rows": len(generated.dataset.ads_rows),
                "touchpoints": len(generated.dataset.touchpoints),
                "report_start_date": generated.dataset.scope.report_start_date,
                "report_end_date": generated.dataset.scope.report_end_date,
                "marketplace": generated.dataset.scope.marketplace,
                "ground_truth_role": "evaluation_only",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
