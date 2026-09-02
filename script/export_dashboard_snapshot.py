"""Export dashboard resources for the static dashboard build.

The live Flask backend and the GitHub Pages build read the same Python
repositories. This command writes the live payload to the generated client
data directory before Vite builds static assets; the browser never reads a
database or imports a server-side loader.

Data flow:
    backend.repository.snapshot -> dashboard/public/data/resources/*.json
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
    RESOURCE_LOADERS,
    clear_caches,
    load_resource,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = REPO_ROOT / "dashboard" / "public" / "data" / "resources"
LEGACY_OUTPUTS = (
    REPO_ROOT / "dashboard" / "public" / "data" / "snapshot.json",
    REPO_ROOT / "dashboard" / "public" / "data" / "research-history.json",
)


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
    for legacy in LEGACY_OUTPUTS:
        legacy.unlink(missing_ok=True)
    expected = set(RESOURCE_LOADERS)
    if OUTPUT_DIRECTORY.exists():
        for existing in OUTPUT_DIRECTORY.glob("*.json"):
            if existing.stem not in expected:
                existing.unlink()
    for resource in RESOURCE_LOADERS:
        payload = load_resource(resource)
        if resource == "shell" and payload.get("mode") != "local files":
            raise RuntimeError(
                "Refusing to export resources not read from committed local files."
            )
        output = OUTPUT_DIRECTORY / f"{resource}.json"
        _write_json(output, payload)
        print(f"Wrote {output.relative_to(REPO_ROOT)} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
