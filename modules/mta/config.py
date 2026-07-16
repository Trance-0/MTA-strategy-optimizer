from __future__ import annotations

from pathlib import Path


MTA_ROOT = Path(__file__).resolve().parent

# Change this one path when you want to run the pipeline on another dataset.
DATA_DIR = MTA_ROOT / "data" / "simulated"
# Output folders. You usually do not need to change these.
ATTRIBUTION_OUTPUT_DIR = MTA_ROOT / "outputs" / "attribution"
FIGURE_OUTPUT_DIR = MTA_ROOT / "outputs" / "figures"

# Expected input file names inside DATA_DIR.
MARKOV_PATHS_FILE = "markov_user_paths.csv"
SHAPLEY_CHANNEL_SETS_FILE = "shapley_user_channel_sets.csv"
CHANNEL_SPEND_FILE = "channel_spend.csv"

# Plot settings.
BOOTSTRAP_ITERATIONS = 80
BOOTSTRAP_SEED = 7

