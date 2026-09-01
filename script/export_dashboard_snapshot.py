"""Export the Flask snapshot contract for the static dashboard build.

The live Flask backend and the GitHub Pages build read the same Python
repositories. This command writes the live payload to the generated client
data directory before Vite builds static assets; the browser never reads a
database or imports a server-side loader.

Data flow:
    backend.repository.snapshot -> dashboard/public/data/snapshot.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Pin public export mode before importing configuration modules, which cache
# these switches on first use. A developer's private `.env` cannot override a
# real environment variable because dotenv loads with override=False.
os.environ["DATABASE"] = "false"
os.environ["DASHBOARD_HOSTED"] = "true"

from backend.repository.snapshot import (
    clear_caches,
    load_research_history,
    load_snapshot,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "dashboard" / "public" / "data" / "snapshot.json"
RESEARCH_OUTPUT = REPO_ROOT / "dashboard" / "public" / "data" / "research-history.json"


def _write_json(path: Path, payload: dict) -> None:
    """Atomically write one minified static dashboard payload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    """Write a deterministic UTF-8 snapshot for Vite static mode."""
    clear_caches()
    payload = load_snapshot()
    if payload.get("mode") != "local files":
        raise RuntimeError(
            "Refusing to export a snapshot not read from committed local files."
        )
    research = load_research_history()
    _write_json(OUTPUT, payload)
    _write_json(RESEARCH_OUTPUT, research)
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)} ({OUTPUT.stat().st_size} bytes)")
    print(
        f"Wrote {RESEARCH_OUTPUT.relative_to(REPO_ROOT)} "
        f"({RESEARCH_OUTPUT.stat().st_size} bytes)"
    )


if __name__ == "__main__":
    main()
