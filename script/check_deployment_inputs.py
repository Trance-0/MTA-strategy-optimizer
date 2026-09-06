"""Validate the pinned simulator checkout before deployment tests and source synchronization."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = "external/mta_sim_dataset"
REQUIRED = (
    "ZheyuanWu/simulations/__init__.py",
    "ZheyuanWu/simulations/baseline/mta_dataset/__init__.py",
    "ZheyuanWu/simulations/baseline/mta_dataset/configuration.py",
    "ZheyuanWu/examples/baseline.toy.json",
)
REMEDY = "Initialize the pinned generator with git submodule sync and git submodule update --init -- external/mta_sim_dataset, or use the completed Gitea materialized snapshot with its parent history."


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def snapshot_errors(root: Path) -> list[str]:
    """Verify the mirror's recorded provenance and tracked, materialized inputs."""
    parent = git(root, "ls-tree", "HEAD^", "--", SUBMODULE).split()
    message = git(root, "show", "-s", "--format=%B", "HEAD")
    if (len(parent) < 3 or parent[0] != "160000"
            or not re.search(rf"^\s*{re.escape(SUBMODULE)}\s+{re.escape(parent[2])}\s*$", message, re.M)):
        return ["Materialized generator lacks the immediate parent's recorded Git pin"]
    git(root, "ls-files", "--error-unmatch", "--", *(f"{SUBMODULE}/{name}" for name in REQUIRED))
    if git(root, "status", "--porcelain", "--untracked-files=no", "--", SUBMODULE):
        return ["Materialized generator has modified tracked files"]
    return []


def validate(root: Path = ROOT) -> list[str]:
    errors = []
    checkout = root / SUBMODULE
    for name in REQUIRED:
        if not (checkout / name).is_file():
            errors.append(f"Missing generator input: {SUBMODULE}/{name}")
    config = checkout / REQUIRED[-1]
    if config.is_file():
        try:
            if not isinstance(json.loads(config.read_text(encoding="utf-8")), dict):
                errors.append("Toy configuration must be a JSON object")
        except (ValueError, OSError) as cause:
            errors.append(f"Invalid toy configuration: {cause}")
    try:
        expected = git(root, "ls-tree", "HEAD", "--", SUBMODULE).split()
        if len(expected) >= 3 and expected[:2] == ["040000", "tree"]:
            errors.extend(snapshot_errors(root))
        else:
            actual = git(checkout, "rev-parse", "HEAD")
            if len(expected) < 3 or expected[0] != "160000" or expected[2] != actual:
                errors.append("Generator checkout does not match the parent revision's pinned Git link")
            if git(checkout, "status", "--porcelain", "--untracked-files=no"):
                errors.append("Generator checkout has modified tracked files")
    except (OSError, subprocess.CalledProcessError):
        errors.append("Cannot verify the generator's pinned Git revision")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(errors))
        print(REMEDY)
        return 1
    print("Deployment generator files and Git provenance verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
